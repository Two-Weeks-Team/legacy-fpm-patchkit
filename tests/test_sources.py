import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from patchkit import sources


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def archive(self, name, kind=None):
        path = self.root / 'input.tar'
        with tarfile.open(path, 'w') as tf:
            item = tarfile.TarInfo(name)
            if kind:
                item.type = kind
                item.linkname = '../outside'
                tf.addfile(item)
            else:
                item.size = 4
                tf.addfile(item, io.BytesIO(b'data'))
        return path

    def test_digest_mismatch_is_rejected(self):
        path = self.root / 'file'
        path.write_bytes(b'bad')
        with self.assertRaises(ValueError):
            sources.verify_file(path, '0' * 64)

    def test_archive_extracts_regular_file(self):
        path = self.archive('source/good')
        target = self.root / 'out'
        sources.extract(path, target)
        self.assertEqual((target / 'source/good').read_bytes(), b'data')

    def test_archive_rejects_traversal_before_writing(self):
        for name in ['../outside', '/absolute', 'a/../../outside']:
            with self.subTest(name=name):
                path = self.archive(name)
                target = self.root / 'out'
                with self.assertRaises(ValueError):
                    sources.extract(path, target)
                self.assertFalse(target.exists())

    def test_archive_rejects_links(self):
        for kind in [tarfile.SYMTYPE, tarfile.LNKTYPE]:
            with self.subTest(kind=kind):
                with self.assertRaises(ValueError):
                    sources.extract(self.archive('source/link', kind), self.root / 'out')

    def test_archive_refuses_existing_output(self):
        path = self.archive('source/good')
        target = self.root / 'out'
        target.mkdir()
        (target / 'keep').write_text('keep')
        with self.assertRaises(ValueError):
            sources.extract(path, target)
        self.assertEqual((target / 'keep').read_text(), 'keep')

    def test_source_hash_detects_content_changes(self):
        (self.root / 'file').write_text('one')
        first = sources.tree_digest(self.root)
        (self.root / 'file').write_text('two')
        self.assertNotEqual(first, sources.tree_digest(self.root))

    def test_source_hash_rejects_symlink(self):
        (self.root / 'link').symlink_to('/etc/passwd')
        with self.assertRaises(ValueError):
            sources.tree_digest(self.root)

    def test_changed_files_match_before_and_after(self):
        path = self.root / 'file'
        path.write_bytes(b'before')
        manifest = {'changed': {'file': {'before': hashlib.sha256(b'before').hexdigest(),
                                         'after': hashlib.sha256(b'after').hexdigest()}}}
        sources.verify_changed(self.root, manifest, 'before')
        with self.assertRaises(ValueError):
            sources.verify_changed(self.root, manifest, 'after')
        path.write_bytes(b'after')
        sources.verify_changed(self.root, manifest, 'after')

    def test_manifest_path_escape_rejected(self):
        manifest = {'changed': {'../outside': {'before': '0' * 64}}}
        with self.assertRaises(ValueError):
            sources.verify_changed(self.root, manifest, 'before')

    def test_checked_in_patch_has_frozen_digest(self):
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / 'provenance/build007-source.json').read_text())
        sources.verify_file(root / 'patches/build007.patch', manifest['patch_sha256'])

    def test_packaging_overlay_keeps_vendor_binary_fixtures(self):
        packaging = self.root / 'packaging'
        (packaging / 'ext/exif/tests').mkdir(parents=True)
        (packaging / 'ext/exif/tests/image.jpg').write_bytes(b'fixture')
        (packaging / 'debian').mkdir()
        (packaging / 'debian/control').write_text('package')
        target = self.root / 'source'
        target.mkdir()
        sources.merge_packaging(packaging, target)
        self.assertEqual((target / 'ext/exif/tests/image.jpg').read_bytes(), b'fixture')
        self.assertEqual((target / 'debian/control').read_text(), 'package')


if __name__ == '__main__':
    unittest.main()
