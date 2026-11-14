import importlib.util
from pathlib import Path
import unittest
import os
import subprocess
import sys
import tempfile

spec = importlib.util.spec_from_file_location('policy_diff', Path(__file__).resolve().parents[1] / 'scripts/policy-diff.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class PolicyDifferenceTests(unittest.TestCase):
    def test_candidate_only_rejection_is_observed(self):
        self.assertTrue(policy.distinguishes({'switch': 'allowed', 'handler': 'php_binary', 'started': 'yes'},
                                            {'switch': 'blocked', 'handler': 'php', 'started': 'yes'}))

    def test_two_rejections_are_not_a_distinguishing_control(self):
        same = {'switch': 'blocked', 'handler': 'php', 'started': 'yes'}
        self.assertFalse(policy.distinguishes(same, same))

    def test_candidate_session_failure_is_not_a_pass(self):
        self.assertFalse(policy.distinguishes({'switch': 'allowed', 'handler': 'php_binary', 'started': 'yes'},
                                             {'switch': 'blocked', 'handler': 'php', 'started': 'no'}))

    def test_nonregular_binary_is_rejected_before_any_read(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fifo = root / 'fifo'
            os.mkfifo(fifo)
            script = Path(__file__).resolve().parents[1] / 'scripts/policy-diff.py'
            try:
                process = subprocess.run([sys.executable, str(script), '--stock-fpm', str(fifo), '--candidate-fpm', str(fifo), '--output', str(root / 'result.json')], capture_output=True, text=True, timeout=2)
            except subprocess.TimeoutExpired:
                self.fail('nonregular binary blocked during read before validation')
            self.assertNotEqual(process.returncode, 0)
            self.assertIn('regular', (root / 'result.json').read_text())
