"""Guard plus real small make; no PHP/FPM runtime claim."""
from contextlib import redirect_stdout, redirect_stderr
import hashlib, importlib, io, json, os
from pathlib import Path
import shutil, subprocess, tarfile, tempfile, unittest
from unittest.mock import patch
DATA = {'ext/json/json_scanner.re': b'lexer input\n', 'ext/json/json_scanner.c': b'lexer C\n', 'ext/json/php_json_scanner_defs.h': b'lexer header\n', 'ext/json/json_parser.y': b'grammar input\n', 'ext/json/json_parser.tab.c': b'parser C\n', 'ext/json/json_parser.tab.h': b'parser header\n'}
TARGETS = ['ext/json/json_scanner.c', 'ext/json/json_parser.tab.c']
MAKE = 'all: consumed\nconsumed: $(srcdir)/json_scanner.c $(srcdir)/json_parser.tab.c $(srcdir)/php_json_scanner_defs.h $(srcdir)/json_parser.tab.h\n\tcat $^ > $@\n$(srcdir)/json_scanner.c: $(srcdir)/json_scanner.re\n\t@echo UNEXPECTED_REGEN >> marker; exit 1\n$(srcdir)/json_parser.tab.c: $(srcdir)/json_parser.y\n\t@echo UNEXPECTED_REGEN >> marker; exit 1\n'

class JsonGenerationFixture(unittest.TestCase):

    def setUp(self):
        try:
            self.m = importlib.import_module('patchkit.json_generation')
        except ImportError:
            self.fail('content-verified JSON generation guard is absent')
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / 'source with spaces'
        self.source.mkdir()
        for name, data in DATA.items():
            p = self.source / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        self.pins = {n: hashlib.sha256(v).hexdigest() for n, v in DATA.items()}
        pins = patch.object(self.m, 'BUNDLE', self.pins)
        pins.start()
        self.addCleanup(pins.stop)

    def guard(self, source, out):
        text = io.StringIO()
        with redirect_stdout(text):
            self.assertEqual(self.m.main([str(source), str(out)]), 0)
        return (text.getvalue().splitlines(), json.loads(out.read_text()))

class JsonGenerationTests(JsonGenerationFixture):

    def test_fixed_bytes_reuse_at_equal_reverse_and_second_boundary_times(self):
        for label, stamp in [('equal', 1543944180), ('reverse', 1543944182), ('boundary', 1543944181)]:
            with self.subTest(label=label):
                source = self.root / label
                shutil.copytree(self.source, source)
                for name in DATA:
                    value = stamp if name.endswith(('.re', '.y')) else 1543944180
                    os.utime(source / name, (value, value))
                flags, plan = self.guard(source, self.root / (label + '.json'))
                self.assertEqual(plan['targets'], TARGETS)
                self.assertEqual(plan['mode'], 'pregenerated')
                work = self.root / (label + '-make')
                work.mkdir()
                (work / 'Makefile').write_text(MAKE)
                run = subprocess.run(['make', 'srcdir=' + str(source / 'ext/json')] + flags, cwd=work, capture_output=True, text=True, timeout=10)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                self.assertFalse((work / 'marker').exists())
                self.assertEqual((work / 'consumed').read_bytes(), b'lexer C\nparser C\nlexer header\nparser header\n')
                receipt = self.m.finish(source, self.root / (label + '.json'), 'a' * 64)
                self.assertEqual(receipt['before'], self.pins)
                self.assertEqual(receipt['after'], self.pins)
                self.assertEqual(receipt['prepared_source_sha256'], 'a' * 64)

    def test_extract_copy_chain_keeps_selected_bundle(self):
        from patchkit import sources
        archive = self.root / 'inputs.tar'
        with tarfile.open(archive, 'w') as tf:
            for name, data in reversed(list(DATA.items())):
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mtime = 1543944180
                tf.addfile(info, io.BytesIO(data))
        sources.extract(archive, self.root / 'extract')
        shutil.copytree(self.root / 'extract', self.root / 'variant')
        subprocess.run(['cp', '-R', str(self.root / 'variant'), str(self.root / 'copy')], check=True)
        flags, plan = self.guard(self.root / 'copy', self.root / 'plan.json')
        self.assertEqual(len(flags), 2)
        self.assertEqual(plan['before'], self.pins)
        self.assertEqual(self.m.finish(self.root / 'copy', self.root / 'plan.json', 'b' * 64)['after'], self.pins)

    def test_each_input_c_header_tamper_rejected_regardless_of_time(self):
        for name in DATA:
            for stamp in (1, 2000000000):
                with self.subTest(name=name, time=stamp):
                    p = self.source / name
                    p.write_bytes(DATA[name] + b'changed')
                    os.utime(p, (stamp, stamp))
                    out = self.root / 'bad.json'
                    with self.assertRaises(ValueError):
                        self.m.prepare(self.source, out)
                    self.assertFalse(out.exists())
                    p.write_bytes(DATA[name])

    def test_missing_and_symlinked_output_rejected(self):
        p = self.source / 'ext/json/json_parser.tab.h'
        p.unlink()
        with self.assertRaises(ValueError):
            self.m.prepare(self.source, self.root / 'missing.json')
        outside = self.root / 'outside'
        outside.write_bytes(DATA['ext/json/json_parser.tab.h'])
        p.symlink_to(outside)
        with self.assertRaises(ValueError):
            self.m.prepare(self.source, self.root / 'link.json')

    def test_source_and_plan_change_after_guard_block_receipt(self):
        plan = self.root / 'plan.json'
        self.m.prepare(self.source, plan)
        p = self.source / 'ext/json/json_scanner.c'
        p.write_bytes(b'regenerated')
        with self.assertRaises(ValueError):
            self.m.finish(self.source, plan, 'a' * 64)
        p.write_bytes(DATA['ext/json/json_scanner.c'])
        record = json.loads(plan.read_text())
        record['targets'] = []
        plan.write_text(json.dumps(record))
        with self.assertRaises(ValueError):
            self.m.finish(self.source, plan, 'a' * 64)

    def test_new_reviewed_input_output_tuple_can_replace_old_tuple(self):
        pins = dict(self.pins)
        for name in ['ext/json/json_scanner.re', 'ext/json/json_scanner.c', 'ext/json/php_json_scanner_defs.h']:
            data = b'reviewed next ' + DATA[name]
            (self.source / name).write_bytes(data)
            pins[name] = hashlib.sha256(data).hexdigest()
        with self.assertRaises(ValueError):
            self.m.prepare(self.source, self.root / 'old.json')
        with patch.object(self.m, 'BUNDLE', pins):
            self.m.prepare(self.source, self.root / 'next.json')
            self.assertEqual(self.m.finish(self.source, self.root / 'next.json', 'c' * 64)['after'], pins)

    def test_existing_plan_preserved_and_no_cli_hash_override(self):
        out = self.root / 'existing.json'
        out.write_text('keep')
        with self.assertRaises(FileExistsError):
            self.m.prepare(self.source, out)
        self.assertEqual(out.read_text(), 'keep')
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.m.main([str(self.source), str(out), '--hash', 'anything'])

class BuildRecordGenerationTests(JsonGenerationFixture):

    def run_record(self, output, identity, drift=False):
        import runpy, sys
        from patchkit import variants, environment
        script = Path(__file__).resolve().parents[1] / 'scripts/build-record.py'
        original = Path.read_text

        def text(path, *args, **kwargs):
            return 'ID=fixture\n' if str(path) == '/etc/os-release' else original(path, *args, **kwargs)
        with patch.object(sys, 'argv', [str(script), str(output), 'portable', 'build007', str(self.source)]), patch.object(variants, 'verify_source', side_effect=ValueError('prepared source drift') if drift else None, return_value=identity), patch.object(environment, 'libc_version', return_value='fixture-only'), patch.object(Path, 'read_text', text), redirect_stdout(io.StringIO()):
            runpy.run_path(str(script), run_name='__main__')

    def output_fixture(self):
        out = self.root / 'build'
        out.mkdir()
        shutil.copytree(self.source, out / 'source')
        identity = {'variant': 'build007', 'normalized_source_sha256': 'd' * 64, 'patch_sha256': 'e' * 64}
        (out / 'source-identity.json').write_text(json.dumps(identity))
        (out / 'configure-arguments.txt').write_text('--fixture-only\n')
        (out / 'toolchain.txt').write_text('fixture-only\n')
        for name in ['php', 'php-fpm']:
            (out / name).write_bytes(b'fixture bytes, never executed')
        self.m.prepare(out / 'source', out / 'json-generation-plan.json')
        return (out, identity)

    def test_build_record_binds_receipt_and_prepared_source(self):
        out, identity = self.output_fixture()
        self.run_record(out, identity)
        record = json.loads((out / 'build.json').read_text())
        self.assertIn('json_generation', record)
        self.assertEqual(record['json_generation']['prepared_source_sha256'], 'd' * 64)
        self.assertEqual(record['json_generation']['before'], self.pins)
        self.assertEqual(record['json_generation']['after'], self.pins)
        self.assertEqual(record['json_generation_receipt_sha256'], hashlib.sha256((out / 'json-generation.json').read_bytes()).hexdigest())
        self.assertIn('json-generation.json', (out / 'SHA256SUMS').read_text())

    def test_build_record_cannot_publish_success_after_generated_header_drift(self):
        out, identity = self.output_fixture()
        (out / 'source/ext/json/json_parser.tab.h').write_bytes(b'drift')
        with self.assertRaises(ValueError):
            self.run_record(out, identity)
        self.assertFalse((out / 'build.json').exists())
        self.assertFalse((out / 'SHA256SUMS').exists())

    def test_original_prepared_source_check_still_blocks_record(self):
        out, identity = self.output_fixture()
        with self.assertRaises(ValueError):
            self.run_record(out, identity, True)
        self.assertFalse((out / 'build.json').exists())
