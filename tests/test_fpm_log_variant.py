"""The legacy logging delta must verify the full cookie parent chain."""
import json
import unittest
from unittest.mock import patch
from patchkit import sources, variants
from tests import test_cookie_variant as parent_tests


class FpmLogVariantTests(unittest.TestCase):
    def setUp(self):
        parent=parent_tests.CookieVariantTests(methodName='runTest');parent.setUp();self.addCleanup(parent.doCleanups)
        self.parent=parent;self.fixture=parent.fixture;self.name='fpm-log-20261114'
        self.expected=self.fixture.root/'fpm-log-expected';self.expected.mkdir()
        (self.expected/'input').write_text('fpm-log\n');(self.expected/'keep').write_text('child\n')
        delta=self.fixture.kit/'patches/fpm-log-20261114.patch';delta.write_text('--- a/input\n+++ b/input\n@@ -1 +1 @@\n-cookie\n+fpm-log\n')
        record={'schema':1,'variant':self.name,'base_variant':'cookie-20261114',
            'baseline_source_sha256':sources.tree_digest(parent.expected,normalized=True),
            'baseline_patch_sha256':sources.sha256(self.fixture.kit/'patches/cookie-20261114.patch'),
            'patch_sha256':sources.sha256(delta),'candidate_source_sha256':sources.tree_digest(self.expected,normalized=True),
            'changed':{'input':{'before':sources.sha256(parent.expected/'input'),'after':sources.sha256(self.expected/'input')}}}
        p=self.fixture.kit/'provenance/variants/fpm-log-20261114.json';p.write_text(json.dumps(record))
        self.registry=patch.object(variants,'PINNED_VARIANTS',{**variants.PINNED_VARIANTS,self.name:sources.sha256(p)})
        self.registry.start();self.addCleanup(self.registry.stop)

    def test_fpm_log_transaction_preserves_the_cookie_parent(self):
        result=variants.prepare_from_baseline(self.parent.expected,self.fixture.output,self.name)
        self.assertEqual(result['baseline_variant'],'cookie-20261114')
        self.assertEqual((self.fixture.output/'input').read_text(),'fpm-log\n')
        self.assertEqual((self.fixture.output/'keep').read_text(),'child\n')
        self.assertEqual((self.parent.expected/'input').read_text(),'cookie\n')

    def test_earlier_acl_source_is_rejected_as_fpm_log_parent(self):
        with self.assertRaises(ValueError):variants.prepare_from_baseline(self.fixture.after,self.fixture.output,self.name)
        self.assertFalse(self.fixture.output.exists())
