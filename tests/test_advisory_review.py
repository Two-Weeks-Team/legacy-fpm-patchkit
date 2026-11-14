"""Benign Python-only expected-rejection tests for runtime classification and exclusive record publication.

Failures here demonstrate review findings, not actual PHP/FPM/Valgrind observations.
"""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))
from patchkit import advisory_runtime as runtime
from patchkit import variants


class ReviewReproductions(unittest.TestCase):
    def test_unrelated_strip_error_with_wrapper_frame_does_not_count_as_target_red(self):
        xml = '''<valgrindoutput><error><kind>UninitCondition</kind><stack>
        <frame><fn>php_filter_strip</fn><file>sanitizing_filters.c</file><line>137</line></frame>
        <frame><fn>php_filter_encoded</fn><file>sanitizing_filters.c</file><line>243</line></frame>
        </stack></error></valgrindoutput>'''
        observed = runtime.memcheck_evidence(xml)
        self.assertEqual(observed['all_errors'], 1)
        self.assertEqual(observed['filter_uninitialized_errors'], 0,
                         'A different helper on the same file/caller stack must not prove tmp[255] RED')

    def test_crashed_baseline_phpt_driver_is_not_a_completed_fail(self):
        with tempfile.TemporaryDirectory(prefix='phpt-review-') as tmp:
            root = Path(tmp)
            source = root / 'source'
            (source / 'ext/filter/tests').mkdir(parents=True)
            for name in ['024', '027', '032', 'bug7586', 'bug69203']:
                (source / 'ext/filter/tests' / (name + '.phpt')).write_text('synthetic copied test')
            fixture = root / 'new.phpt'
            fixture.write_text('synthetic copied test')
            common = {'timed_out': False, 'forced_cleanup': False, 'output_budget_exceeded': False,
                      'command': ['synthetic-unit-driver'], 'stderr': ''}
            old = {**common, 'returncode': 0, 'stdout': 'PASS fixture\n' * 5}
            crashed = {**common, 'returncode': -11, 'stdout': 'FAIL fixture\n'}
            with patch.object(runtime, 'command', side_effect=[old, crashed]):
                with self.assertRaises(ValueError, msg='SIGSEGV must not be accepted as a completed baseline PHPT FAIL'):
                    runtime.run_phpt(root / 'not-executed-php', source, root / 'output', fixture, lambda: 30)

    def test_build_record_must_not_follow_dangling_output_symlink(self):
        with tempfile.TemporaryDirectory(prefix='record-review-') as tmp:
            root = Path(tmp)
            output = root / 'output'
            output.mkdir()
            identity = {'variant': 'build007', 'patch_sha256': 'a' * 64, 'normalized_source_sha256': 'b' * 64}
            (output / 'source-identity.json').write_text(json.dumps(identity))
            (output / 'php').write_bytes(b'NONEXECUTED UNIT FIXTURE')
            (output / 'php-fpm').write_bytes(b'NONEXECUTED UNIT FIXTURE')
            (output / 'configure-arguments.txt').write_text('--unit-fixture\n')
            (output / 'toolchain.txt').write_text('unit fixture, not a native build\n')
            target = root / 'other-owner-new-path.json'
            (output / 'build.json').symlink_to(target)
            original_read = Path.read_text
            def fixture_read(path, *args, **kwargs):
                if str(path) == '/etc/os-release':
                    return 'ID=nonexecuting-unit-fixture\n'
                return original_read(path, *args, **kwargs)
            script = KIT / 'scripts/build-record.py'
            # Only the verified input and Linux metadata are stubs. Actual output
            # publication follows the original script's exists()/write_text() code.
            with patch.object(variants, 'verify_source', return_value=identity), \
                 patch('patchkit.environment.libc_version', return_value='UNIT_FIXTURE'), \
                 patch.object(Path, 'read_text', fixture_read), \
                 patch.object(sys, 'argv', [str(script), str(output), 'portable', 'build007', str(root / 'prepared')]), \
                 redirect_stdout(io.StringIO()):
                try:
                    runpy.run_path(str(script), run_name='__main__')
                except (ValueError, FileExistsError, SystemExit):
                    pass
            self.assertFalse(target.exists(), 'Build publication followed a dangling output symlink')


if __name__ == '__main__':
    unittest.main(verbosity=2)
