import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('native_check', Path(__file__).resolve().parents[1] / 'scripts/native-check.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


class NativeHarnessTests(unittest.TestCase):
    def test_runtime_stderr_cannot_pass_with_valid_stdout(self):
        with self.assertRaisesRegex(ValueError, 'stderr'):
            native.checked_response({'body': b'complete=yes\n', 'stderr': b'PHP Warning: synthetic'})

    def test_unexpected_fpm_log_warning_cannot_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'fpm.log').write_text('WARNING: synthetic runtime problem')
            with self.assertRaisesRegex(ValueError, 'diagnostic'):
                native.check_logs(root)

    def test_startup_notices_are_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'fpm.log').write_text('NOTICE: ready to handle connections')
            self.assertIn('NOTICE: ready', native.check_logs(root)['fpm.log'])


if __name__ == '__main__':
    unittest.main()
