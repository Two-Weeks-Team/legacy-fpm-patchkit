"""Decisions about local evidence, not a PHP runtime acceptance claim."""
from pathlib import Path
import tempfile
import unittest


class CookieRuntimeTests(unittest.TestCase):
    def setUp(self):
        try:
            from patchkit import cookie_runtime
        except ImportError:
            self.fail('paired cookie runtime verifier is absent')
        self.runtime=cookie_runtime

    def test_exact_expected_map_and_complete_worker_record_are_required(self):
        want={'C':{'__Host-demo':'trusted'},'G':{},'P':{}}
        output='PID=12\nC|S5f5f486f73742d64656d6f=V74727573746564\nCOMPLETE=yes\n'
        self.assertEqual(self.runtime.check_response(output,want),'12')
        for bad in [output.replace('COMPLETE=yes\n',''),output.replace('V74727573746564','V756e74727573746564'),output+'C|S78=V78\n',output+output]:
            with self.subTest(output=bad),self.assertRaises(ValueError):self.runtime.check_response(bad,want)

    def test_log_slices_do_not_allow_two_plus_zero_request_diagnostics(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);offsets={}
            (root/'php.log').write_text('')
            self.runtime.require_quiet(self.runtime.log_delta(root,offsets))
            (root/'php.log').write_text('PHP Warning: synthetic\nPHP Warning: synthetic\n')
            first=self.runtime.log_delta(root,offsets)
            with self.assertRaises(ValueError):self.runtime.require_quiet(first)
            self.runtime.require_quiet(self.runtime.log_delta(root,offsets))
            (root/'php.log').write_text('PHP Warning: shutdown-only\n')
            with self.assertRaises(ValueError):self.runtime.log_delta(root,offsets)

    def test_shutdown_only_diagnostic_cannot_be_ignored(self):
        with self.assertRaises(ValueError):self.runtime.require_quiet({'process.log':'NOTICE: exiting\nPHP Warning: late error\n'})
        self.runtime.require_quiet({'fpm.log':'NOTICE: exiting, bye-bye!\n'})

    def test_fcgi_stderr_is_a_failure_even_without_known_warning_words(self):
        with self.assertRaises(ValueError):self.runtime.require_quiet({'fcgi':'unexpected output'})

    def test_expected_parent_phpt_failure_cannot_hide_setup_errors(self):
        result={'returncode':1,'stdout':'FAIL cookie regression\n','stderr':'','timed_out':False,'forced_cleanup':False,'output_budget_exceeded':False}
        self.runtime.require_parent_phpt(result)
        for change in [{'stderr':'error'},{'stdout':'SKIP cookie\n'},{'returncode':2},{'output_budget_exceeded':True}]:
            with self.assertRaises(ValueError):self.runtime.require_parent_phpt(dict(result,**change))

    def test_cli_case_boundaries_and_exact_maps_are_checked(self):
        from patchkit.cookie_cases import cases,flatten
        lines=[]
        for case in cases():
            lines.append('BEGIN='+case['name'])
            lines.extend('G|'+k+'='+v for k,v in flatten(case['candidate']['G']).items())
            lines.append('END='+case['name'])
        valid='\n'.join(lines)+'\n'
        self.assertEqual(len(self.runtime.check_cli(valid,'candidate')),19)
        for broken in [valid.rsplit('END=',1)[0],valid+valid,valid.replace('BEGIN=dot-host','BEGIN=unknown',1)]:
            with self.assertRaises(ValueError):self.runtime.check_cli(broken,'candidate')
