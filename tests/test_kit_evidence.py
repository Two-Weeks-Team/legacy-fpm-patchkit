"""Kit evidence drift must fail before any native source/build is required."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class KitEvidenceTests(unittest.TestCase):
    def test_kit_drift_is_rejected_without_prepared_source(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            kit = Path(temporary)
            for name in ('scripts', 'patchkit', 'provenance', 'evidence', 'docs'):
                shutil.copytree(root / name, kit / name)
            argv = [sys.executable, '-B', 'scripts/check-coverage.py']
            baseline = subprocess.run(argv, cwd=kit, capture_output=True, text=True)
            self.assertEqual(baseline.returncode, 0, baseline.stderr)
            driver = kit / 'scripts/build.sh'
            driver.write_bytes(driver.read_bytes() + b'\n# unreviewed driver change\n')
            drift = subprocess.run(argv, cwd=kit, capture_output=True, text=True)
            self.assertNotEqual(drift.returncode, 0, 'Kit drift passed without --source')
            self.assertIn('source evidence hash differs: scripts/build.sh', drift.stderr)
