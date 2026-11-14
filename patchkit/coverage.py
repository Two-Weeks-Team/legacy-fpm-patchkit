"""Validate reviewed advisory accounting; never infer a security verdict from versions."""
from collections import Counter
from pathlib import PurePosixPath
import re

STATUSES = ('RESOLVED', 'NOT_APPLICABLE', 'PLANNED')


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
