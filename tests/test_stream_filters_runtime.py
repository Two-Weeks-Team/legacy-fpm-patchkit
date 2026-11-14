from pathlib import Path
import tempfile
import unittest

class StreamFiltersRuntimeTests(unittest.TestCase):
    def setUp(self):
        try:
            from patchkit import stream_filters_runtime
        except ImportError:
            self.fail('paired stream filters runner absent')
        self.runtime=stream_filters_runtime

    def test_exact_response_requires_all_codec_records_and_completion(self):
        want={'b64':'4142','qp':''};good='PID=12\nb64=4142\nqp=\nCOMPLETE=yes\n'
        self.assertEqual(self.runtime.check_frame(good,want),'12')
        for bad in [good.replace('COMPLETE=yes\n',''),good.replace('b64=4142','b64=4242'),good+good,good+'extra=1\n']:
            with self.assertRaises(ValueError):self.runtime.check_frame(bad,want)

    def test_parent_pending_phpt_requires_the_known_split_output(self):
        record=dict(returncode=1,stdout='FAIL pending boundary\n',stderr='',timed_out=False,forced_cleanup=False,output_budget_exceeded=False)
        self.runtime.require_pending_red(record,b'410a42\n')
        for changes,data in [({},b'4142'),({},b'parse error'),({'returncode':2},b'410a42'),({'stderr':'error'},b'410a42')]:
            with self.assertRaises(ValueError):self.runtime.require_pending_red(dict(record,**changes),data)

    def test_memory_red_requires_target_invalid_read_in_read_stack(self):
        error='<error><kind>InvalidRead</kind><stack><frame><fn>php_conv_base64_encode_convert</fn></frame></stack><auxwhat>Address 0x1 is 0 bytes after a block of size 1 alloc\'d</auxwhat></error>'
        record=dict(returncode=97,stdout='PROBE_COMPLETE\n',stderr='',timed_out=False,forced_cleanup=False,output_budget_exceeded=False)
        self.runtime.require_memory(record,'<valgrindoutput>'+error+'</valgrindoutput>','parent')
        for xml in ['<valgrindoutput/>','<valgrindoutput>'+error.replace('InvalidRead','InvalidWrite')+'</valgrindoutput>','<valgrindoutput>'+error.replace('php_conv_base64_encode_convert','unrelated')+'</valgrindoutput>','<valgrindoutput>'+error+error.replace('InvalidRead','UninitValue')+'</valgrindoutput>']:
            with self.assertRaises(ValueError):self.runtime.require_memory(record,xml,'parent')
        good=dict(record,returncode=0)
        self.runtime.require_memory(good,'<valgrindoutput/>','candidate')
        with self.assertRaises(ValueError):self.runtime.require_memory(good,'<valgrindoutput>'+error+'</valgrindoutput>','candidate')

    def test_fixture_sections_and_literal_expected_maps_are_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'case.phpt';path.write_text('--TEST--\nbenign\n--FILE--\n<?php echo "x=41\\nCOMPLETE=yes\\n";\n--EXPECT--\nx=41\nCOMPLETE=yes\n')
            script,want=self.runtime.fixture(path);self.assertIn('<?php',script);self.assertEqual(want,{'x':'41'})
            path.write_text(path.read_text().replace('x=41\nCOMPLETE','x=41\nx=42\nCOMPLETE'))
            with self.assertRaises(ValueError):self.runtime.fixture(path)
