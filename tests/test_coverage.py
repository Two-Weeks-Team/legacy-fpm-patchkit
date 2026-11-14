import copy
import unittest

from patchkit.coverage import validate


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.catalog = {'schema': 1, 'entries': [
            {'ghsa_id': 'GHSA-one', 'cve_id': 'CVE-2026-1'},
            {'ghsa_id': 'GHSA-two', 'cve_id': None},
        ]}
        self.ledger = {'schema': 1, 'entries': [
            self.row('GHSA-one', 'CVE-2026-1', 'RESOLVED', 'source-only'),
            self.row('GHSA-two', None, 'PLANNED', 'not-run'),
        ], 'vendor_fixes': [], 'source_files': {'main/example.c': {
            'root': 'prepared-source', 'sha256': 'a' * 64, 'line_count': 20}}}

    def row(self, ghsa, cve, status, validation):
        return {'ghsa_id': ghsa, 'cve_id': cve, 'status': status,
                'reason_en': 'Inspected source mechanism.', 'reason_ko': '소스 경로 확인.',
                'source_evidence': ['main/example.c:12: inspected source'],
                'upstream_url': 'https://github.com/php/php-src/security/advisories/' + ghsa,
                'planned_action_en': 'Port upstream guard and run isolated regression.' if status == 'PLANNED' else '',
                'planned_action_ko': '가드 이식과 격리 회귀 검증.' if status == 'PLANNED' else '',
                'validation': validation}

    def test_complete_catalog_preserves_advisory_without_cve(self):
        self.assertEqual(validate(self.catalog, self.ledger), {'RESOLVED': 1, 'NOT_APPLICABLE': 0, 'PLANNED': 1, 'VENDOR_RESOLVED': 0})

    def test_missing_advisory_cannot_silently_reduce_denominator(self):
        self.ledger['entries'].pop()
        with self.assertRaisesRegex(ValueError, 'catalog coverage'):
            validate(self.catalog, self.ledger)

    def test_duplicate_advisory_rejected(self):
        self.ledger['entries'].append(copy.deepcopy(self.ledger['entries'][0]))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            validate(self.catalog, self.ledger)

    def test_unknown_status_cannot_be_published(self):
        self.ledger['entries'][1]['status'] = 'UNKNOWN'
        with self.assertRaisesRegex(ValueError, 'status'):
            validate(self.catalog, self.ledger)

    def test_unimplemented_protection_cannot_be_counted_as_fixed(self):
        self.ledger['entries'][1]['status'] = 'RESOLVED'
        with self.assertRaisesRegex(ValueError, 'validation'):
            validate(self.catalog, self.ledger)

    def test_planned_requires_concrete_action_in_both_languages(self):
        self.ledger['entries'][1]['planned_action_ko'] = ''
        with self.assertRaisesRegex(ValueError, 'planned action'):
            validate(self.catalog, self.ledger)

    def test_fixed_requires_source_evidence(self):
        self.ledger['entries'][0]['source_evidence'] = []
        with self.assertRaisesRegex(ValueError, 'source evidence'):
            validate(self.catalog, self.ledger)

    def test_cve_identity_must_match_official_catalog(self):
        self.ledger['entries'][0]['cve_id'] = 'CVE-2026-999'
        with self.assertRaisesRegex(ValueError, 'CVE identity'):
            validate(self.catalog, self.ledger)

    def test_vendor_fix_requires_enabled_verified_patch(self):
        self.ledger['vendor_fixes'] = [{'cve_id': 'CVE-2019-1', 'status': 'RESOLVED',
            'validation': 'vendor-source', 'patches': []}]
        with self.assertRaisesRegex(ValueError, 'vendor patch'):
            validate(self.catalog, self.ledger)

    def test_source_reference_must_name_a_recorded_file_and_existing_line(self):
        for reference in ('main/missing.c:12', 'main/example.c:999', 'main/example.c:0'):
            with self.subTest(reference=reference):
                self.ledger['entries'][0]['source_evidence'] = [reference]
                with self.assertRaisesRegex(ValueError, 'unbacked source reference'):
                    validate(self.catalog, self.ledger)

    def test_evidence_path_cannot_escape_prepared_source(self):
        self.ledger['source_files']['../outside'] = {
            'root': 'prepared-source', 'sha256': 'a' * 64, 'line_count': 20}
        with self.assertRaisesRegex(ValueError, 'unsafe source evidence path'):
            validate(self.catalog, self.ledger)

    def test_missing_vendor_cve_cannot_shrink_the_frozen_census(self):
        self.catalog['vendor_patch_names'] = ['CVE-2019-1.patch']
        with self.assertRaisesRegex(ValueError, 'vendor CVE census'):
            validate(self.catalog, self.ledger)
