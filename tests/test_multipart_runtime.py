"""Fixture/evidence decision tests; never a real PHP multipart PASS."""
import unittest
from pathlib import Path
import tempfile


class MultipartRuntimeTests(unittest.TestCase):
    def setUp(self):
        try:
            from patchkit import multipart_runtime
        except ImportError:
            self.fail('multipart paired FPM fixture runner is absent')
        self.module=multipart_runtime

    def test_all_requests_are_small_and_budget_boundary_cases_are_distinct(self):
        cases=self.module.cases()
        self.assertIn('parts-three',{c['name'] for c in cases})
        self.assertIn('parts-four',{c['name'] for c in cases})
        self.assertIn('boundary-cap',{c['name'] for c in cases})
        self.assertIn('boundary-over-cap',{c['name'] for c in cases})
        self.assertTrue(all(len(self.module.body(c))<48000 for c in cases))

    def test_warning_occurrences_must_be_exact_without_double_counting_channels(self):
        text='PHP Warning: Multipart body parts limit exceeded 3. To increase the limit change max_multipart_body_parts in php.ini.\n'
        self.module.check_warnings({'php':text,'fcgi':text},{'parts':1})
        for logs in [{'php':text+text},{'php':''},{'php':text+'PHP Warning: unrelated\n'}]:
            with self.subTest(logs=logs), self.assertRaises(ValueError):
                self.module.check_warnings(logs,{'parts':1})

    def test_response_must_preserve_exact_field_file_bytes_and_complete(self):
        expected={'post':{'a':'41'},'files':{},'limit':'3'}
        self.module.check_response('PID=12\nLIMIT=3\nPOST:a=41\nPROGRESS=0\nCOMPLETE=yes\n',expected)
        for response in ['PID=12\nLIMIT=3\nPOST:a=42\nPROGRESS=0\nCOMPLETE=yes\n','PID=12\nLIMIT=3\nPOST:a=41\nPROGRESS=1\nCOMPLETE=yes\n','PID=12\nLIMIT=3\nPOST:a=41\nPROGRESS=0\n']:
            with self.assertRaises(ValueError):self.module.check_response(response,expected)

    def test_extra_fields_cannot_hide_a_missing_total_part_limit(self):
        expected={'post':{'a':'41'},'files':{},'limit':'3'}
        with self.assertRaises(ValueError):
            self.module.check_response('PID=12\nLIMIT=3\nPOST:a=41\nPOST:b=42\nPROGRESS=0\nCOMPLETE=yes\n',expected)

    def test_repeated_records_are_rejected(self):
        with self.assertRaises(ValueError):
            self.module.check_response('PID=12\nLIMIT=3\nPOST:a=41\nPOST:a=41\nPROGRESS=0\nCOMPLETE=yes\n',{'post':{'a':'41'},'files':{},'limit':'3'})

    def test_short_owned_workspace_preserves_failure_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)/'evidence'
            with self.assertRaisesRegex(ValueError,'synthetic failure'):
                with self.module.case_workspace(output) as work:
                    self.assertLess(len(str(work/'fpm.sock')),100)
                    work.mkdir();(work/'diagnostic').write_text('preserve')
                    raise ValueError('synthetic failure')
            self.assertEqual((output/'diagnostic').read_text(),'preserve')

    def test_expected_parent_phpt_failures_do_not_hide_stderr_or_truncation(self):
        result={'returncode':1,'stdout':'FAIL ini\nFAIL default\n','stderr':'','timed_out':False,'forced_cleanup':False,'output_budget_exceeded':False}
        self.module.require_parent_phpt(result)
        for change in [{'stderr':'unexpected diagnostic'},{'output_budget_exceeded':True},{'returncode':2},{'stdout':'SKIP ini\nFAIL default\n'}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.module.require_parent_phpt(dict(result,**change))


if __name__=='__main__':unittest.main()
