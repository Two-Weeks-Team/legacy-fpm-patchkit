"""Runner decisions and bounded owned-process cleanup; never PHP acceptance."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


class AdvisoryRuntimeTests(unittest.TestCase):
    def setUp(self):
        try:
            from patchkit import advisory_runtime
        except ImportError:
            self.fail('Bounded real-binary advisory runner is absent')
        self.runtime = advisory_runtime

    def test_socket_connect_and_no_response_are_not_a_refusal_pass(self):
        for response in [None, {'body': b'acl-ok\n', 'stderr': b''}]:
            with self.subTest(response=response), self.assertRaises(ValueError):
                self.runtime.evaluate_acl(False, response, 'NOTICE: ready to handle connections', '::1')

    def test_parse_error_cannot_become_a_security_refusal(self):
        log = "Wrong IP address '::2'\nConnection disallowed: IP address '::1' has been dropped."
        with self.assertRaisesRegex(ValueError, 'parse'):
            self.runtime.evaluate_acl(False, None, log, '::1')

    def test_refusal_requires_exact_peer_log_and_no_application_response(self):
        log = "ERROR: Connection disallowed: IP address '::1' has been dropped."
        self.runtime.evaluate_acl(False, None, log, '::1')
        with self.assertRaises(ValueError):
            self.runtime.evaluate_acl(False, None, log, '127.0.0.1')
        with self.assertRaises(ValueError):
            self.runtime.evaluate_acl(False, {'body': b'acl-ok\n', 'stderr': b''}, log, '::1')

    def test_allow_requires_complete_marker_no_stderr_and_no_refusal_log(self):
        self.runtime.evaluate_acl(True, {'body': b'acl-ok\n', 'stderr': b''}, '', '::1')
        for response in [None, {'body': b'', 'stderr': b''}, {'body': b'acl-ok\n', 'stderr': b'warning'}]:
            with self.assertRaises(ValueError):
                self.runtime.evaluate_acl(True, response, '', '::1')

    def test_phpt_exit_zero_cannot_hide_skips_warnings_or_missing_cases(self):
        for text in ['SKIP case\n', 'WARN case\n', 'LEAK case\n', 'PASS case\n']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.runtime.require_phpt_pass({'returncode': 0, 'stdout': text, 'stderr': ''}, 5)
        self.runtime.require_phpt_pass({'returncode': 0, 'stdout': 'PASS case\n' * 5, 'stderr': ''}, 5)

    def test_real_phpt_progress_carriage_returns_are_parsed(self):
        text = 'TEST 1/1 [fixture]\rPASS normal filter [fixture]\n'
        self.runtime.require_phpt_pass({'returncode': 0, 'stdout': text, 'stderr': ''}, 1)

    def test_ff_in_input_does_not_excuse_corruption_of_normal_characters(self):
        cases = [{'id': 'binary', 'input_hex': '41ff5a', 'flags': 0, 'expected_hex': '412546465a'}]
        with self.assertRaises(ValueError):
            self.runtime.check_filter(cases, {'binary': '42ff5a'}, candidate=False)

    def test_filter_output_protocol_rejects_duplicate_or_malformed_records(self):
        self.assertEqual(self.runtime.parse_filter_output('empty=\nff=254646\n'), {'empty': '', 'ff': '254646'})
        for text in ['ff=ff\nff=254646\n', 'ff=zz\n', 'ff=f\n', 'incomplete']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.runtime.parse_filter_output(text)

    def test_unrelated_valgrind_error_does_not_supply_filter_red(self):
        unrelated = '<valgrindoutput><error><kind>UninitCondition</kind><stack><frame><fn>elsewhere</fn></frame></stack></error></valgrindoutput>'
        relevant = unrelated.replace('<fn>elsewhere</fn>', '<fn>php_filter_encode_url</fn><file>sanitizing_filters.c</file><line>108</line>')
        self.assertEqual(self.runtime.memcheck_evidence(unrelated)['filter_uninitialized_errors'], 0)
        self.assertEqual(self.runtime.memcheck_evidence(relevant)['filter_uninitialized_errors'], 1)

    def test_candidate_filter_failure_cannot_be_ignored(self):
        cases = [{'id': 'ff', 'input_hex': 'ff', 'flags': 0, 'expected_hex': '254646'}]
        with self.assertRaises(ValueError):
            self.runtime.check_filter(cases, {'ff': 'ff'}, candidate=True)
        record = self.runtime.check_filter(cases, {'ff': 'ff'}, candidate=False)
        self.assertEqual(record['mismatches'], ['ff'])

    def test_normal_baseline_mismatch_is_a_failure_even_with_other_ff_cases(self):
        cases = [{'id': 'safe', 'input_hex': '41', 'flags': 0, 'expected_hex': '41'}]
        with self.assertRaises(ValueError):
            self.runtime.check_filter(cases, {'safe': '42'}, candidate=False)

    def test_command_timeout_reaps_its_own_process_and_preserves_output(self):
        with tempfile.TemporaryDirectory() as directory:
            record = self.runtime.command([sys.executable, '-u', '-c', 'import time; print("started"); time.sleep(30)'], Path(directory), 'timeout', 0.2)
            self.assertTrue(record['timed_out'])
            self.assertIn('started', record['stdout'])
            self.assertIsNotNone(record['returncode'])
            self.assertTrue(record['reaped'])

    def test_existing_result_directory_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'marker').write_text('preserve')
            with self.assertRaises(FileExistsError):
                self.runtime.new_run_directory(root)
            self.assertEqual((root/'marker').read_text(), 'preserve')

    def test_successful_request_cannot_hide_a_crashed_fpm_master(self):
        for before, after, forced in [(7, 7, False), (None, -11, False), (None, -9, True)]:
            with self.subTest(before=before, after=after), self.assertRaises(ValueError):
                self.runtime.require_fpm_exit(before, after, forced)
        self.runtime.require_fpm_exit(None, 0, False)
        self.runtime.require_fpm_exit(None, -15, False)

    def test_timeout_cleanup_leaves_an_independently_started_process_alive(self):
        other = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], start_new_session=True)
        try:
            with tempfile.TemporaryDirectory() as directory:
                record = self.runtime.command([sys.executable, '-c', 'import time; time.sleep(30)'], Path(directory), 'bounded', 0.1)
                self.assertTrue(record['timed_out'])
                self.assertIsNone(other.poll())
        finally:
            other.terminate()
            other.wait(timeout=3)


if __name__ == '__main__':
    unittest.main()
