"""The cookie delta must verify the full multipart parent chain."""
import json
import unittest
from unittest.mock import patch
from patchkit import sources, variants
from tests import test_multipart_variant as parent_tests


class CookieVariantTests(unittest.TestCase):
    def setUp(self):
        parent=parent_tests.MultipartVariantTests(methodName='runTest');parent.setUp();self.addCleanup(parent.doCleanups)
        self.parent=parent;self.fixture=parent.fixture;self.name='cookie-20261114'
        self.expected=self.fixture.root/'cookie-expected';self.expected.mkdir()
        (self.expected/'input').write_text('cookie\n');(self.expected/'keep').write_text('child\n')
        delta=self.fixture.kit/'patches/cookie-20261114.patch';delta.write_text('--- a/input\n+++ b/input\n@@ -1 +1 @@\n-after\n+cookie\n')
        record={'schema':1,'variant':self.name,'base_variant':'multipart-20261114',
            'baseline_source_sha256':sources.tree_digest(parent.expected,normalized=True),
            'baseline_patch_sha256':sources.sha256(self.fixture.kit/'patches/multipart-20261114.patch'),
            'patch_sha256':sources.sha256(delta),'candidate_source_sha256':sources.tree_digest(self.expected,normalized=True),
            'changed':{'input':{'before':sources.sha256(parent.expected/'input'),'after':sources.sha256(self.expected/'input')}}}
        p=self.fixture.kit/'provenance/variants/cookie-20261114.json';p.write_text(json.dumps(record))
        self.registry=patch.object(variants,'PINNED_VARIANTS',{**variants.PINNED_VARIANTS,self.name:sources.sha256(p)})
        self.registry.start();self.addCleanup(self.registry.stop)

    def test_cookie_transaction_preserves_the_multipart_parent(self):
        result=variants.prepare_from_baseline(self.parent.expected,self.fixture.output,self.name)
        self.assertEqual(result['baseline_variant'],'multipart-20261114')
        self.assertEqual((self.fixture.output/'input').read_text(),'cookie\n')
        self.assertEqual((self.fixture.output/'keep').read_text(),'child\n')
        self.assertEqual((self.parent.expected/'input').read_text(),'after\n')

    def test_earlier_acl_source_is_rejected_as_cookie_parent(self):
        with self.assertRaises(ValueError):variants.prepare_from_baseline(self.fixture.after,self.fixture.output,self.name)
        self.assertFalse(self.fixture.output.exists())
