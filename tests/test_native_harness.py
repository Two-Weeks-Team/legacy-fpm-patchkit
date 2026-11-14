import importlib.util
from pathlib import Path
import tempfile
import subprocess
import sys
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

    def test_forced_cleanup_is_a_failure_and_owned_process_is_reaped(self):
        process = subprocess.Popen([sys.executable, '-c', 'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print("ready",flush=True); time.sleep(30)'], stdout=subprocess.PIPE)
        try:
            self.assertEqual(process.stdout.readline().strip(), b'ready')
            with self.assertRaisesRegex(ValueError, 'forced cleanup'):
                native.stop_process(process, grace=0.05)
            self.assertIsNotNone(process.poll())
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()


if __name__ == '__main__':
    unittest.main()
