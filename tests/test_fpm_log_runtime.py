import unittest

class FpmLogRuntimeTests(unittest.TestCase):
    def setUp(self):
        try:
            from patchkit import fpm_log_runtime
        except ImportError:
            self.fail('legacy log runner absent')
        self.runtime=fpm_log_runtime

    def test_candidate_requires_nul_tail_and_following_normal_line(self):
        payload=b'Pre\x00SecretTail\nNEXT\n';token='case-0'
        good=b'BEGIN:case-0Pre\\x00SecretTailNEXTEND:case-0BARRIER:case-0'
        self.runtime.check_payload(good,token,payload,'candidate',False,'nul')
        for bad in [good.replace(b'SecretTail',b''),good.replace(b'NEXT',b''),good+good,good.replace(b'END:case-0',b'')]:
            with self.assertRaises(ValueError):self.runtime.check_payload(bad,token,payload,'candidate',False,'nul')

    def test_parent_requires_known_loss_not_an_arbitrary_failure(self):
        payload=b'Pre\x00SecretTail\nNEXT\n';token='case-0'
        self.runtime.check_payload(b'BEGIN:case-0PreBARRIER:case-0',token,payload,'parent',False,'nul')
        for bad in [b'',b'BEGIN:case-0BARRIER:case-0',b'BEGIN:case-0garbageBARRIER:case-0',b'BEGIN:case-0PreSecretTailBARRIER:case-0']:
            with self.assertRaises(ValueError):self.runtime.check_payload(bad,token,payload,'parent',False,'nul')

    def test_intended_warning_must_have_exact_worker_stream_and_frame(self):
        good=b'[date] WARNING: [pool proof] child 12 said into stderr: "hello"\n'
        self.assertEqual(self.runtime.log_payload({'fpm.log':good},'12','stderr'),b'hello')
        for channels in [{'fpm.log':good.replace(b'child 12',b'child 13')},{'fpm.log':good+b'PHP Warning: extra\n'},{'fpm.log':good,'process.log':b'PHP Warning: late\n'},{'fpm.log':good,'fcgi':b'anything'},{'fpm.log':good.replace(b'stderr',b'stdout')},{'fpm.log':b'x'*1025+b'\n'}]:
            with self.assertRaises(ValueError):self.runtime.log_payload(channels,'12','stderr')

    def test_backslash_is_distinguishable_from_nul_and_controls(self):
        a=b'BEGIN:tPre\\x00END:tBARRIER:t'
        b=b'BEGIN:tPre\\\\x00END:tBARRIER:t'
        self.runtime.check_payload(a,'t',b'Pre\x00','candidate',False,'other')
        self.runtime.check_payload(b,'t',b'Pre\\x00','candidate',False,'other')
        with self.assertRaises(ValueError):self.runtime.check_payload(a,'t',b'Pre\\x00','candidate',False,'other')

    def test_unrecognized_records_and_shutdown_only_diagnostics_fail(self):
        for text in [b'unknown diagnostic\n',b'[date] NOTICE: unexpected condition\n',b'[date] WARNING: late shutdown warning\n']:
            with self.subTest(text=text),self.assertRaises(ValueError):self.runtime.log_payload({'process.log':text},'12','stderr')
        self.assertEqual(self.runtime.log_payload({'fpm.log':b'[date] NOTICE: Terminating ...\n[date] NOTICE: exiting, bye-bye!\n'},'12','stderr'),b'')
