import copy
import unittest

from patchkit.coverage import validate_necessity


class NecessityTests(unittest.TestCase):
    def setUp(self):
        self.ledger = {'candidate_source_sha256': 'a' * 64, 'entries': [
            {'ghsa_id': 'GHSA-one', 'cve_id': None, 'status': 'PLANNED'},
            {'ghsa_id': 'GHSA-two', 'cve_id': 'CVE-2026-1', 'status': 'PLANNED'},
            {'ghsa_id': 'GHSA-fixed', 'cve_id': None, 'status': 'RESOLVED'}], 'source_files': {'main/example.c': {'line_count':20}}}
        row = {'id': 'GHSA-one', 'cve_id': None, 'decision': 'REQUIRED',
               'shipped_source_action': 'REQUIRED', 'component': 'main',
               'reason_ko': '소스 결함 경로 확인.', 'reason_en': 'Source mechanism present.',
               'prerequisites': [], 'candidate_evidence': ['main/example.c:4'],
               'official_sources': ['https://github.com/php/php-src/commit/' + 'b' * 40],
               'official_fix_comparison': 'Official guard is absent at the same call site.',
               'next_verification': 'Paired isolated regression.', 'priority': 'P1'}
        second = copy.deepcopy(row)
        second.update(id='GHSA-two', cve_id='CVE-2026-1', decision='OUTSIDE_LINUX_FPM',
                      component='Windows CGI', priority='P3')
        self.review = {'schema': 1, 'candidate_source_sha256': 'a' * 64,
                       'entries': [row, second]}

    def test_outside_runtime_does_not_erase_distributed_source_work(self):
        counts = validate_necessity(self.ledger, self.review)
        self.assertEqual(counts['REQUIRED'], 1)
        self.assertEqual(counts['OUTSIDE_LINUX_FPM'], 1)
        self.assertEqual(self.review['entries'][1]['shipped_source_action'], 'REQUIRED')

    def test_missing_duplicate_or_nonplanned_rows_cannot_change_review_denominator(self):
        for rows in [self.review['entries'][:1], [self.review['entries'][0]] * 2,
                     self.review['entries'] + [dict(self.review['entries'][0], id='GHSA-fixed')]]:
            with self.subTest(rows=len(rows)):
                value = dict(self.review, entries=rows)
                with self.assertRaisesRegex(ValueError, 'identity|coverage|duplicate'):
                    validate_necessity(self.ledger, value)

    def test_verdict_cannot_be_reused_with_a_different_candidate(self):
        self.review['candidate_source_sha256'] = 'c' * 64
        with self.assertRaisesRegex(ValueError, 'source identity'):
            validate_necessity(self.ledger, self.review)

    def test_conditional_needs_specific_prerequisites_and_next_verification(self):
        row = self.review['entries'][0]
        row.update(decision='CONDITIONAL', prerequisites=[])
        with self.assertRaisesRegex(ValueError, 'prerequisite'):
            validate_necessity(self.ledger, self.review)

    def test_mechanism_absence_cannot_be_used_to_claim_a_pending_source_fix(self):
        self.review['entries'][0]['decision'] = 'MECHANISM_ABSENT'
        with self.assertRaisesRegex(ValueError, 'source action'):
            validate_necessity(self.ledger, self.review)


    def test_source_proven_reclassification_keeps_original_review_denominator(self):
        self.ledger['entries'][0].update(status='NOT_APPLICABLE',
            prior_assessment={'status':'PLANNED'})
        self.review['entries'][0].update(decision='MECHANISM_ABSENT', shipped_source_action='NONE')
        self.assertEqual(validate_necessity(self.ledger,self.review)['MECHANISM_ABSENT'],1)


    def test_source_references_require_recorded_files_and_valid_lines(self):
        for reference in ['../../outside:1', 'main/missing.c:1', 'main/example.c:0', 'main/example.c:21']:
            with self.subTest(reference=reference):
                self.review['entries'][0]['candidate_evidence']=[reference]
                with self.assertRaisesRegex(ValueError,'source reference'):
                    validate_necessity(self.ledger,self.review)


    def test_conditional_source_work_requires_an_explicit_prior_review_gate(self):
        row=self.review['entries'][0]
        row.update(decision='CONDITIONAL',shipped_source_action='CONDITIONAL',prerequisites=['Exact linked library contract'])
        with self.assertRaisesRegex(ValueError,'prerequisite gate'):
            validate_necessity(self.ledger,self.review)

    def test_shipped_source_totals_cannot_drift_from_item_actions(self):
        self.review['shipped_source_counts']={'REQUIRED':99,'CONDITIONAL':0,'NONE':0}
        with self.assertRaisesRegex(ValueError,'shipped source counts'):
            validate_necessity(self.ledger,self.review)
