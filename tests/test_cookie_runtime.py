"""Decisions about local evidence, not a PHP runtime acceptance claim."""
from pathlib import Path
import ast
import copy
from contextlib import contextmanager
import inspect
import json
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

    def test_actual_case_loop_preserves_mixed_key_fixture_evidence(self):
        # The real loop records every literal case before each pair of mocked
        # responses. This is an evidence/decision test, not PHP/FPM execution.
        r=self.runtime
        tree=ast.parse(inspect.getsource(r.main))
        loop=next(n for n in ast.walk(tree) if isinstance(n,ast.For) and isinstance(n.target,ast.Name) and n.target.id=='case')
        code=compile(ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(loop)],type_ignores=[])),'actual-cookie-loop','exec')
        for side in ('parent','candidate'):
            with self.subTest(side=side),tempfile.TemporaryDirectory() as temporary:
                directory=Path(temporary);observed={'cases':{}};sent=[]
                @contextmanager
                def workspace(output):yield output
                @contextmanager
                def instance(binary,root,budget):
                    root.mkdir();yield
                def request(work,case,budget):
                    sent.append(case['name']);body='PID=123\n'
                    for kind in ('C','G','P'):
                        body+=''.join(kind+'|'+k+'='+v+'\n' for k,v in r.flatten(case[side][kind]).items())
                    return {'body':(body+'COMPLETE=yes\n').encode(),'stderr':b''}
                ns=dict(r.__dict__,directory=directory,observed=observed,side=side,fpm=Path('NOT_EXECUTED'),
                        budget=lambda:30,case_workspace=workspace,instance=instance,request=request)
                exec(code,ns)
                self.assertEqual(len(observed['cases']),19)
                self.assertEqual(len(sent),38)
                record=json.loads((directory/'normal-array'/'fixture.json').read_text())
                self.assertEqual(record['expected_map_encoding'],'typed-path-v1')
                for expected_side in ('parent','candidate'):
                    for kind in ('C','G','P'):
                        self.assertEqual(record[expected_side][kind]['S6e756d/S3031'],'V70')
                        self.assertEqual(record[expected_side][kind]['S6e756d/I0'],'V7a')
                source=next(c for c in r.cases() if c['name']=='normal-array')
                self.assertEqual(record['cookie'],source['cookie'])
                self.assertEqual(record['form'],source['form'])
