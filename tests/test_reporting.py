from pathlib import Path
import tempfile
import unittest
from patchkit import reporting


class ReportTests(unittest.TestCase):
    def test_existing_failed_report_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'result.json'
            path.write_text('existing FAIL')
            with self.assertRaises(ValueError):
                reporting.require_new(path)
            self.assertEqual(path.read_text(), 'existing FAIL')

    def test_late_symlink_does_not_overwrite_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / 'result.json'
            protected = root / 'protected'
            protected.write_text('preserve')
            reporting.require_new(path)
            path.symlink_to(protected)
            with self.assertRaises(FileExistsError):
                reporting.write_new(path, {'result': 'PASS'})
            self.assertEqual(protected.read_text(), 'preserve')

    def test_new_report_can_be_written(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'result.json'
            reporting.require_new(path)
            reporting.write_new(path, {'result': 'FAIL'})
            self.assertIn('FAIL', path.read_text())
