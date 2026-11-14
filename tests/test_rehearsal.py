from pathlib import Path
import tempfile
import unittest
from patchkit import rehearsal


class RehearsalTests(unittest.TestCase):
    def test_replace_and_restore_real_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = root / 'candidate'
            candidate.write_bytes(b'new verified bytes')
            candidate.chmod(0o755)
            result = rehearsal.run(candidate, root / 'drill')
            self.assertEqual(result['result'], 'REHEARSAL_PASS')
            self.assertEqual((root / 'drill/current').read_bytes(), b'synthetic-original')
            self.assertEqual(candidate.read_bytes(), b'new verified bytes')

    def test_existing_directory_never_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = root / 'candidate'
            candidate.write_bytes(b'new')
            with self.assertRaises(ValueError):
                rehearsal.run(candidate, root)
            self.assertEqual(candidate.read_bytes(), b'new')

    def test_symlink_candidate_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'real').write_bytes(b'new')
            (root / 'link').symlink_to(root / 'real')
            with self.assertRaises(ValueError):
                rehearsal.run(root / 'link', root / 'drill')


if __name__ == '__main__':
    unittest.main()
