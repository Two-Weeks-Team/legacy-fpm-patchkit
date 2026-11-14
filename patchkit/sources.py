"""Pinned public source acquisition and bounded, link-free extraction."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import tempfile
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MAX_ARCHIVE = 32 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def verify_file(path, expected):
    if Path(path).is_symlink() or sha256(path) != expected:
        raise ValueError('SHA-256 mismatch: ' + Path(path).name)


def relative(name):
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name or not p.parts:
        raise ValueError('unsafe relative path: ' + name)
    return p


def extract(archive, destination):
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError('extraction destination must be new')
    with tarfile.open(archive, 'r:*') as tf:
        members = tf.getmembers()
        if len(members) > 50000 or sum(x.size for x in members) > MAX_EXPANDED:
            raise ValueError('archive size budget exceeded')
        names = set()
        for item in members:
            relative(item.name)
            if not (item.isdir() or item.isfile()) or item.name in names:
                raise ValueError('archive contains link, special or duplicate entry')
            names.add(item.name)
        # Validate the whole archive before creating any output.
        destination.mkdir(parents=True)
        for item in members:
            target = destination / item.name
            if item.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with tf.extractfile(item) as src, target.open('xb') as dst:
                    shutil.copyfileobj(src, dst)
                target.chmod(item.mode & 0o777)


def inventory(root, normalized=False):
    rows = {}
    for path in sorted(Path(root).rglob('*')):
        name = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise ValueError('source symlink: ' + name)
        if normalized and (name.startswith('.pc/') or name.endswith('.orig')):
            continue
        if path.is_file():
            rows[name] = sha256(path)
    return rows


def tree_digest(root, normalized=False):
    data = json.dumps(inventory(root, normalized), sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(data).hexdigest()


def verify_changed(root, manifest, state):
    for name, row in manifest['changed'].items():
        relative(name)
        verify_file(Path(root) / name, row[state])


class HTTPSOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme != 'https':
            raise ValueError('non-HTTPS redirect rejected')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(cache):
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    lock = json.loads((ROOT / 'provenance/inputs.json').read_text())
    opener = urllib.request.build_opener(HTTPSOnly)
    result = []
    for row in lock['archives']:
        relative(row['name'])
        target = cache / row['name']
        if target.exists() or target.is_symlink():
            verify_file(target, row['sha256'])
        else:
            if urllib.parse.urlsplit(row['url']).scheme != 'https':
                raise ValueError('source URL must use HTTPS')
            with tempfile.NamedTemporaryFile(dir=cache, delete=False) as dst:
                temporary = Path(dst.name)
                try:
                    request = urllib.request.Request(row['url'], headers={'User-Agent': 'Legacy-FPM-Patchkit/0.1.0'})
                    with opener.open(request, timeout=60) as src:
                        total = 0
                        while True:
                            chunk = src.read(1024 * 1024)
                            if not chunk:
                                break
                            total += len(chunk)
                            if total > MAX_ARCHIVE:
                                raise ValueError('download size budget exceeded')
                            dst.write(chunk)
                    dst.flush()
                    verify_file(temporary, row['sha256'])
                    os.link(temporary, target)  # exclusive publication; never overwrite cache
                finally:
                    temporary.unlink(missing_ok=True)
        result.append({'name': row['name'], 'sha256': sha256(target)})
    return result


def run_patch(root, patch, log, strict=True):
    args = ['patch', '-p1', '-f', '-i', str(Path(patch).resolve())]
    if strict:
        args += ['-F', '0']
    with Path(log).open('ab') as stream:
        process = subprocess.run(args, cwd=root, stdout=stream, stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL, timeout=120)
    if process.returncode:
        raise ValueError('patch failed; inspect preparation.log')


def merge_packaging(packaging, source):
    # Quilt source archives can include binary fixtures OUTSIDE debian/.
    for path in Path(packaging).iterdir():
        target = Path(source) / path.name
        if path.is_dir():
            shutil.copytree(path, target, dirs_exist_ok=True)
        else:
            shutil.copyfile(path, target)


def prepare(cache, destination):
    """Prepare a NEW source tree. No existing tree is changed, including on failure."""
    cache, destination = Path(cache), Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError('source destination must be new')
    inputs = json.loads((ROOT / 'provenance/inputs.json').read_text())
    manifest = json.loads((ROOT / 'provenance/build007-source.json').read_text())
    verify_file(ROOT / 'patches/build007.patch', manifest['patch_sha256'])
    for row in inputs['archives']:
        verify_file(cache / row['name'], row['sha256'])
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.patchkit-', dir=destination.parent) as temporary:
        stage = Path(temporary)
        extract(cache / inputs['archives'][0]['name'], stage / 'upstream')
        extract(cache / inputs['archives'][1]['name'], stage / 'packaging')
        source = stage / 'upstream/php-7.0.33'
        merge_packaging(stage / 'packaging', source)
        log = stage / 'preparation.log'
        series = (source / 'debian/patches/series').read_text().splitlines()
        count = 0
        for line in series:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            name, *options = line.split()
            relative(name)
            if options:
                raise ValueError('unsupported vendor patch option')
            run_patch(source, source / 'debian/patches' / name, log, strict=False)
            count += 1
        verify_changed(source, manifest, 'before')
        baseline = tree_digest(source, normalized=True)
        if baseline != inputs['normalized_baseline_sha256']:
            raise ValueError('normalized baseline tree mismatch: ' + baseline)
        run_patch(source, ROOT / 'patches/build007.patch', log)
        verify_changed(source, manifest, 'after')
        candidate = tree_digest(source, normalized=True)
        if candidate != inputs['normalized_candidate_sha256']:
            raise ValueError('normalized candidate tree mismatch: ' + candidate)
        # Strip only documented patch bookkeeping/backups, never compiled inputs.
        for backup in source.rglob('*.orig'):
            backup.unlink()
        receipt = {'schema': 1, 'vendor_patches': count, 'changed_files': len(manifest['changed']),
                   'patch_sha256': manifest['patch_sha256'], 'baseline_sha256': baseline,
                   'candidate_sha256': candidate, 'result': 'SOURCE_VERIFIED',
                   'binary_compatibility': 'NOT_TESTED'}
        source.rename(destination)
        (destination.parent / (destination.name + '.preparation.json')).write_text(json.dumps(receipt, indent=2) + '\n')
        shutil.copyfile(log, destination.parent / (destination.name + '.preparation.log'))
    return receipt
