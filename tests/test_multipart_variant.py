"""A second fixed delta must preserve and verify its actual parent variant."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from patchkit import sources, variants
from tests import test_variants as parent_tests


class MultipartVariantTests(unittest.TestCase):
    def setUp(self):
        fixture=parent_tests.VariantTests(methodName='runTest');fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.fixture=fixture
        self.name='multipart-20261114'
        self.expected=fixture.root/'second-expected';self.expected.mkdir()
        (self.expected/'input').write_text('after\n');(self.expected/'keep').write_text('child\n')
        delta=fixture.kit/'patches/multipart-20261114.patch';delta.write_text('--- a/keep\n+++ b/keep\n@@ -1 +1 @@\n-preserved\n+child\n')
        data={'schema':1,'variant':self.name,'base_variant':fixture.name,
              'baseline_source_sha256':sources.tree_digest(fixture.after,normalized=True),
              'baseline_patch_sha256':sources.sha256(fixture.kit/'patches/acl-filter-20261114.patch'),
              'patch_sha256':sources.sha256(delta),'candidate_source_sha256':sources.tree_digest(self.expected,normalized=True),
              'changed':{'keep':{'before':sources.sha256(fixture.after/'keep'),'after':sources.sha256(self.expected/'keep')}}}
        manifest=fixture.kit/'provenance/variants/multipart-20261114.json';manifest.write_text(json.dumps(data))
        registry={**variants.PINNED_VARIANTS,self.name:sources.sha256(manifest)}
        self.registry=patch.object(variants,'PINNED_VARIANTS',registry);self.registry.start();self.addCleanup(self.registry.stop)

    def test_real_child_patch_transaction_preserves_first_delta(self):
        result=variants.prepare_from_baseline(self.fixture.after,self.fixture.output,self.name)
        self.assertEqual(result['baseline_variant'],'acl-filter-20261114')
        self.assertEqual((self.fixture.output/'input').read_text(),'after\n')
        self.assertEqual((self.fixture.output/'keep').read_text(),'child\n')
        self.assertEqual((self.fixture.after/'keep').read_text(),'preserved\n')

    def test_base_build007_is_rejected_when_child_requires_first_delta(self):
        with self.assertRaises(ValueError):
            variants.prepare_from_baseline(self.fixture.base,self.fixture.output,self.name)
        self.assertFalse(self.fixture.output.exists())
