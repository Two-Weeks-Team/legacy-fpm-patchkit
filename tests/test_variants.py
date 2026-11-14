"""Real filesystem/patch transactions for an explicitly pinned source variant."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from patchkit import sources


class VariantTests(unittest.TestCase):
    def setUp(self):
        try:
            from patchkit import variants
        except ImportError:
            self.fail('Explicit pinned source variant preparation is absent')
        self.variants = variants
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.kit = self.root / 'kit'
        (self.kit / 'provenance/variants').mkdir(parents=True)
        (self.kit / 'patches').mkdir()
        self.base = self.root / 'base'
        self.base.mkdir()
        (self.base / 'input').write_text('before\n')
        (self.base / 'keep').write_text('preserved\n')
        self.after = self.root / 'expected'
        self.after.mkdir()
        (self.after / 'input').write_text('after\n')
        (self.after / 'keep').write_text('preserved\n')
        self.name = 'acl-filter-20261114'
        delta = self.kit / 'patches/acl-filter-20261114.patch'
        delta.write_text('--- a/input\n+++ b/input\n@@ -1 +1 @@\n-before\n+after\n')
        original_patch = self.kit / 'patches/build007.patch'
        original_patch.write_text('fixed historical input')
        base_hash = sources.tree_digest(self.base, normalized=True)
        (self.kit / 'provenance/inputs.json').write_text(json.dumps({'normalized_candidate_sha256': base_hash}))
        (self.kit / 'provenance/build007-source.json').write_text(json.dumps({'patch_sha256': sources.sha256(original_patch)}))
        self.manifest = dict(schema=1, variant=self.name, base_variant='build007',
                             baseline_source_sha256=base_hash,
                             baseline_patch_sha256=sources.sha256(original_patch),
                             patch_sha256=sources.sha256(delta),
                             candidate_source_sha256=sources.tree_digest(self.after, normalized=True),
                             changed={'input': {'before': sources.sha256(self.base/'input'), 'after': sources.sha256(self.after/'input')}})
        manifest_path = self.kit / ('provenance/variants/' + self.name + '.json')
        manifest_path.write_text(json.dumps(self.manifest))
        registry = {self.name: sources.sha256(manifest_path)}
        self.addCleanup(patch.stopall)
        patch.object(sources, 'ROOT', self.kit).start()
        patch.object(variants, 'PINNED_VARIANTS', registry).start()
        self.output = self.root / 'candidate'

    def test_patch_transaction_hashes_entire_tree_and_preserves_baseline(self):
        before = sources.tree_digest(self.base)
        record = self.variants.prepare_from_baseline(self.base, self.output, self.name)
        self.assertEqual((self.output/'input').read_text(), 'after\n')
        self.assertEqual((self.output/'keep').read_text(), 'preserved\n')
        self.assertEqual(sources.tree_digest(self.base), before)
        self.assertEqual(record['normalized_source_sha256'], sources.tree_digest(self.after, normalized=True))
        self.assertEqual(record['variant'], self.name)

    def test_default_build007_verifier_uses_historical_pin(self):
        identity = self.variants.verify_source(self.base)
        self.assertEqual(identity['variant'], 'build007')
        self.assertEqual(identity['normalized_source_sha256'], self.manifest['baseline_source_sha256'])
        with self.assertRaisesRegex(ValueError, 'source'):
            self.variants.verify_source(self.after)

    def test_wrong_variant_cannot_fall_back_to_default_or_use_manifest_path(self):
        for bad in ['unknown', '../../other', str(self.kit/'provenance/inputs.json')]:
            with self.subTest(variant=bad), self.assertRaisesRegex(ValueError, 'variant'):
                self.variants.verify_source(self.base, bad)

    def test_baseline_drift_cannot_be_patched(self):
        (self.base/'keep').write_text('drift')
        with self.assertRaisesRegex(ValueError, 'source'):
            self.variants.prepare_from_baseline(self.base, self.output, self.name)
        self.assertFalse(self.output.exists())

    def test_candidate_unrelated_file_drift_fails_even_when_two_target_hashes_match(self):
        self.variants.prepare_from_baseline(self.base, self.output, self.name)
        (self.output/'keep').write_text('drift')
        with self.assertRaisesRegex(ValueError, 'source'):
            self.variants.verify_source(self.output, self.name)

    def test_patch_tampering_is_rejected_before_output(self):
        (self.kit/'patches/acl-filter-20261114.patch').write_text('tampered')
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            self.variants.prepare_from_baseline(self.base, self.output, self.name)
        self.assertFalse(self.output.exists())

    def test_manifest_tampering_cannot_select_a_new_expected_hash(self):
        p = self.kit/'provenance/variants/acl-filter-20261114.json'
        content = json.loads(p.read_text())
        content['candidate_source_sha256'] = '0' * 64
        p.write_text(json.dumps(content))
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            self.variants.prepare_from_baseline(self.base, self.output, self.name)

    def test_existing_output_and_sidecars_preserved(self):
        self.output.mkdir()
        marker = self.output/'marker'
        marker.write_text('keep')
        with self.assertRaises(ValueError):
            self.variants.prepare_from_baseline(self.base, self.output, self.name)
        self.assertEqual(marker.read_text(), 'keep')

    def test_existing_receipt_is_never_overwritten_or_followed(self):
        receipt = Path(str(self.output)+'.preparation.json')
        receipt.write_text('other owner receipt')
        with self.assertRaises(ValueError):
            self.variants.prepare_from_baseline(self.base, self.output, self.name)
        self.assertEqual(receipt.read_text(), 'other owner receipt')
        self.assertFalse(self.output.exists())

    def test_late_output_race_never_replaces_other_directory(self):
        original = sources.run_patch
        def racing(*args, **kwargs):
            self.output.mkdir()
            (self.output/'marker').write_text('late owner')
            return original(*args, **kwargs)
        with patch.object(sources, 'run_patch', side_effect=racing):
            with self.assertRaises(FileExistsError):
                self.variants.prepare_from_baseline(self.base, self.output, self.name)
        self.assertEqual((self.output/'marker').read_text(), 'late owner')


if __name__ == '__main__':
    unittest.main()
