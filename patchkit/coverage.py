"""Validate reviewed advisory accounting; never infer a security verdict from versions."""
from collections import Counter
from pathlib import PurePosixPath
import re

STATUSES = ('RESOLVED', 'NOT_APPLICABLE', 'PLANNED')
NECESSITY = ('REQUIRED', 'CONDITIONAL', 'OUTSIDE_LINUX_FPM', 'MECHANISM_ABSENT', 'ALREADY_COVERED')


def validate_necessity(ledger, review):
    """Check source-bound review completeness without granting fixed credit."""
    if review.get('schema') != 1:
        raise ValueError('unsupported necessity schema')
    if review.get('candidate_source_sha256') != ledger.get('candidate_source_sha256'):
        raise ValueError('necessity source identity differs')
    expected = {r['ghsa_id']: r.get('cve_id') for r in ledger['entries']
                if r['status'] == 'PLANNED' or r.get('prior_assessment', {}).get('status') == 'PLANNED'}
    seen = set()
    counts = Counter({decision: 0 for decision in NECESSITY})
    source_counts = Counter({action: 0 for action in ('REQUIRED', 'CONDITIONAL', 'NONE')})
    ledger_rows = {row['ghsa_id']: row for row in ledger['entries']}
    for row in review['entries']:
        key = row.get('id')
        if key in seen:
            raise ValueError('duplicate necessity identity: ' + str(key))
        if key not in expected or row.get('cve_id') != expected[key]:
            raise ValueError('necessity identity differs: ' + str(key))
        seen.add(key)
        decision = row.get('decision')
        if decision not in NECESSITY:
            raise ValueError('invalid necessity decision: ' + str(key))
        action = row.get('shipped_source_action')
        if action not in ('REQUIRED', 'CONDITIONAL', 'NONE'):
            raise ValueError('invalid shipped source action: ' + str(key))
        if action == 'CONDITIONAL' and ledger_rows[key].get('implementation_gate') != 'prerequisite-review':
            raise ValueError('conditional source action needs a prerequisite gate: ' + str(key))
        if decision in ('MECHANISM_ABSENT', 'ALREADY_COVERED') and action != 'NONE':
            raise ValueError('absence/coverage conflicts with source action: ' + str(key))
        for field in ('component', 'reason_en', 'reason_ko', 'official_fix_comparison', 'next_verification'):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError('missing necessity explanation: ' + str(key))
        prerequisites = row.get('prerequisites')
        if not isinstance(prerequisites, list) or not all(isinstance(p, str) and p.strip() for p in prerequisites):
            raise ValueError('invalid necessity prerequisites: ' + str(key))
        if decision == 'CONDITIONAL' and not prerequisites:
            raise ValueError('conditional verdict needs a prerequisite: ' + str(key))
        evidence = row.get('candidate_evidence')
        if not evidence or not all(isinstance(ref, str) and re.match(r'[^: ]+:\d+', ref) for ref in evidence):
            raise ValueError('missing necessity source evidence: ' + str(key))
        for reference in evidence:
            match = re.match(r'([^: ]+):(\d+)', reference)
            proof = ledger.get('source_files', {}).get(match[1])
            if not proof or not 1 <= int(match[2]) <= proof['line_count']:
                raise ValueError('unbacked necessity source reference: ' + str(key))
        urls = row.get('official_sources')
        if not urls or not all(isinstance(url, str) and url.startswith('https://') for url in urls):
            raise ValueError('missing necessity official source: ' + str(key))
        if row.get('priority') not in ('P1', 'P2', 'P3'):
            raise ValueError('invalid necessity priority: ' + str(key))
        counts[decision] += 1
        source_counts[action] += 1
    if seen != set(expected):
        raise ValueError('necessity coverage does not match planned catalog')
    if review.get('counts') and any(review['counts'].get(key, 0) != counts[key] for key in NECESSITY):
        raise ValueError('necessity counts differ from reviewed rows')
    if review.get('shipped_source_counts') and any(review['shipped_source_counts'].get(key, 0) != source_counts[key] for key in source_counts):
        raise ValueError('shipped source counts differ from reviewed rows')
    return dict(counts)


def validate(catalog, ledger):
    if catalog.get('schema') != 1 or ledger.get('schema') != 1:
        raise ValueError('unsupported coverage schema')
    proofs = ledger.get('source_files', {})
    for name, proof in proofs.items():
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or proof.get('root') not in ('kit', 'prepared-source'):
            raise ValueError('unsafe source evidence path: ' + name)
        if not re.fullmatch(r'[a-f0-9]{64}', proof.get('sha256', '')) or not isinstance(proof.get('line_count'), int) or proof['line_count'] < 1:
            raise ValueError('invalid source evidence identity: ' + name)
    official = {}
    for row in catalog['entries']:
        key = row['ghsa_id']
        if key in official:
            raise ValueError('duplicate official advisory: ' + key)
        official[key] = row
    seen = set()
    counts = Counter({s: 0 for s in STATUSES})
    for row in ledger['entries']:
        key = row['ghsa_id']
        if key in seen:
            raise ValueError('duplicate assessment: ' + key)
        seen.add(key)
        if key not in official or row.get('cve_id') != official[key].get('cve_id'):
            raise ValueError('CVE identity differs from official catalog: ' + key)
        status = row.get('status')
        if status not in STATUSES:
            raise ValueError('unsupported coverage status: ' + str(status))
        if not row.get('reason_en', '').strip() or not row.get('reason_ko', '').strip():
            raise ValueError('missing bilingual reason: ' + key)
        evidence = row.get('source_evidence', [])
        if not evidence or not all(isinstance(s, str) and re.search(r'[^ ]+:\d+', s) for s in evidence):
            raise ValueError('missing source evidence: ' + key)
        for reference in evidence:
            match = re.match(r'([^: ]+):(\d+)', reference)
            if not match or match[1] not in proofs or not 1 <= int(match[2]) <= proofs[match[1]]['line_count']:
                raise ValueError('unbacked source reference: ' + key)
        expected_url = 'https://github.com/php/php-src/security/advisories/' + key
        if row.get('upstream_url') != expected_url:
            raise ValueError('upstream reference mismatch: ' + key)
        validation = row.get('validation')
        valid = {'RESOLVED': {'source-only', 'paired-benign'},
                 'NOT_APPLICABLE': {'not-applicable'}, 'PLANNED': {'not-run'}}
        if validation not in valid[status]:
            raise ValueError('validation cannot support status: ' + key)
        if status == 'PLANNED' and not all(row.get(k, '').strip() for k in ('planned_action_en', 'planned_action_ko')):
            raise ValueError('missing concrete planned action: ' + key)
        counts[status] += 1
    if seen != set(official):
        raise ValueError('catalog coverage does not match official snapshot')
    vendor_seen = set()
    expected_vendor = {}
    for name in catalog.get('vendor_patch_names', []):
        for cve in re.findall(r'CVE-\d{4}-\d+', name):
            expected_vendor.setdefault(cve, set()).add(name)
    for row in ledger.get('vendor_fixes', []):
        key = row['cve_id']
        if key in vendor_seen:
            raise ValueError('duplicate vendor CVE: ' + key)
        vendor_seen.add(key)
        if row.get('status') != 'RESOLVED' or row.get('validation') != 'vendor-source':
            raise ValueError('vendor fix lacks source validation: ' + key)
        patches = row.get('patches', [])
        if not patches or not all(p.get('enabled') is True and re.fullmatch(r'[a-f0-9]{64}', p.get('sha256', '')) for p in patches):
            raise ValueError('vendor patch must be enabled and hash-verified: ' + key)
        if {p['name'] for p in patches} != expected_vendor.get(key):
            raise ValueError('vendor patch census differs: ' + key)
    if vendor_seen != set(expected_vendor):
        raise ValueError('vendor CVE census differs from frozen catalog')
    counts['VENDOR_RESOLVED'] = len(vendor_seen)
    return dict(counts)
