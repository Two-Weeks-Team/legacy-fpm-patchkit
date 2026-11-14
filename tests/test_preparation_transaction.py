"""Real tar/patch/filesystem transactions using tiny synthetic source inputs."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from patchkit import sources


def digest(data):
    return hashlib.sha256(data).hexdigest()


def tree_hash(rows):
    return digest(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode())


class PreparationTransactionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.kit = self.root / 'kit'
        self.cache = self.root / 'cache'
        self.output = self.root / 'source'
        for folder in ['patches', 'provenance']:
            (self.kit / folder).mkdir(parents=True)
        self.cache.mkdir()

    def archive(self, name, entries):
        path = self.cache / name
        with tarfile.open(path, 'w') as tf:
            for key, data in entries.items():
                item = tarfile.TarInfo(key)
                item.size = len(data)
                item.mode = 0o644
                tf.addfile(item, io.BytesIO(data))
        return {'name': name, 'sha256': digest(path.read_bytes())}

    def inputs(self, bad_patch=False):
        archives = [self.archive('upstream.tar', {'php-7.0.33/file': b'old\n'}),
                    self.archive('packaging.tar', {'debian/patches/series': b''})]
        (self.cache / 'source.dsc').write_bytes(b'synthetic source descriptor')
        archives.append({'name': 'source.dsc', 'sha256': digest((self.cache / 'source.dsc').read_bytes())})
        content = b'invalid patch\n' if bad_patch else b'--- a/file\n+++ b/file\n@@ -1 +1 @@\n-old\n+new\n'
        (self.kit / 'patches/build007.patch').write_bytes(content)
        manifest = {'patch_sha256': digest(content), 'changed': {'file': {'before': digest(b'old\n'), 'after': digest(b'new\n')}}}
        (self.kit / 'provenance/build007-source.json').write_text(json.dumps(manifest))
        inputs = {'archives': archives,
                  'normalized_baseline_sha256': tree_hash({'file': digest(b'old\n'), 'debian/patches/series': digest(b'')}),
                  'normalized_candidate_sha256': tree_hash({'file': digest(b'new\n'), 'debian/patches/series': digest(b'')})}
        (self.kit / 'provenance/inputs.json').write_text(json.dumps(inputs))

    def test_actual_patch_transaction_publishes_source_and_receipts(self):
        self.inputs()
        with patch.object(sources, 'ROOT', self.kit):
            result = sources.prepare(self.cache, self.output)
        self.assertEqual(result['result'], 'SOURCE_VERIFIED')
        self.assertEqual((self.output / 'file').read_bytes(), b'new\n')
        self.assertEqual(json.loads(Path(str(self.output) + '.preparation.json').read_text()), result)
        self.assertTrue(Path(str(self.output) + '.preparation.log').is_file())

    def test_real_patch_failure_preserves_log_and_no_final_source(self):
        self.inputs(bad_patch=True)
        with patch.object(sources, 'ROOT', self.kit):
            with self.assertRaisesRegex(ValueError, 'patch failed'):
                sources.prepare(self.cache, self.output)
        self.assertFalse(self.output.exists())
        self.assertTrue(Path(str(self.output) + '.failed-preparation.log').read_bytes())

    def test_late_sidecar_symlink_is_not_followed(self):
        self.inputs()
        protected = self.root / 'protected'
        protected.write_text('PRESERVE ME')
        original = sources.run_patch
        def racing_patch(*args, **kwargs):
            Path(str(self.output) + '.preparation.json').symlink_to(protected)
            return original(*args, **kwargs)
        with patch.object(sources, 'ROOT', self.kit), patch.object(sources, 'run_patch', side_effect=racing_patch):
            with self.assertRaises(FileExistsError):
                sources.prepare(self.cache, self.output)
        self.assertEqual(protected.read_text(), 'PRESERVE ME')
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
