#!/usr/bin/env python3
"""Check complete advisory accounting; optionally recheck the prepared source proof."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from patchkit.coverage import validate, validate_necessity
from patchkit.sources import tree_digest

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, help='exact prepared source, for additional evidence-hash checks')
args = parser.parse_args()
catalog = json.loads((root / 'provenance/security-advisories-20261114.json').read_text())
ledger = json.loads((root / 'evidence/security-coverage-20261114.json').read_text())
counts = validate(catalog, ledger)
necessity_path = root / 'evidence/implementation-necessity-20261114.json'
necessity = json.loads(necessity_path.read_text()) if necessity_path.exists() else None
necessity_counts = validate_necessity(ledger, necessity) if necessity else None
if len(catalog['entries']) != catalog['published_advisory_count']:
    raise ValueError('catalog count differs')
if ledger['catalog_sha256'] != hashlib.sha256((root / 'provenance/security-advisories-20261114.json').read_bytes()).hexdigest():
    raise ValueError('catalog snapshot identity differs')
if ledger['candidate_source_sha256'] != json.loads((root / 'provenance/inputs.json').read_text())['normalized_candidate_sha256']:
    raise ValueError('candidate source identity differs')
if len(ledger['vendor_fixes']) != ledger['vendor_cve_count']:
    raise ValueError('vendor CVE count differs')
for lang, name in [('en', 'docs/SECURITY_COVERAGE.md'), ('ko', 'docs/SECURITY_COVERAGE.ko.md')]:
    text = (root / name).read_text()
    expected = set(x['ghsa_id'] for x in catalog['entries'])
    found = set(re.findall(r'GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}', text))
    if found != expected:
        raise ValueError(name + ': rendered catalog coverage differs')
    for row in ledger['vendor_fixes']:
        if row['cve_id'] not in text:
            raise ValueError(name + ': missing vendor CVE ' + row['cve_id'])
    if 'COVERAGE_COUNTS: ' + json.dumps(counts, sort_keys=True) not in text:
        raise ValueError(name + ': stale rendered counts')
if args.source:
    source = args.source.resolve()
    if tree_digest(source, normalized=True) != ledger['candidate_source_sha256']:
        raise ValueError('prepared source digest differs')
    for name, proof in ledger['source_files'].items():
        target = (source if proof['root'] == 'prepared-source' else root) / name
        data = target.read_bytes()
        if hashlib.sha256(data).hexdigest() != proof['sha256']:
            raise ValueError('source evidence hash differs: ' + name)
    enabled = {s.strip() for s in (source / 'debian/patches/series').read_text().splitlines()
               if s.strip() and not s.lstrip().startswith('#')}
    if enabled != set(catalog['vendor_patch_names']):
        raise ValueError('active vendor patch census differs from frozen snapshot')
    series_hash = hashlib.sha256((source / 'debian/patches/series').read_bytes()).hexdigest()
    if series_hash != catalog['vendor_series_sha256'] or series_hash != ledger['vendor_series_sha256']:
        raise ValueError('active vendor series identity differs')
    for row in ledger['vendor_fixes']:
        for patch in row['patches']:
            if patch['name'] not in enabled:
                raise ValueError('vendor patch disabled: ' + patch['name'])
            data = (source / 'debian/patches' / patch['name']).read_bytes()
            if hashlib.sha256(data).hexdigest() != patch['sha256']:
                raise ValueError('vendor patch hash differs: ' + patch['name'])
print(json.dumps({'result': 'COVERAGE_ACCOUNTING_VERIFIED', 'catalog_advisories': len(catalog['entries']),
                  'counts': counts, 'source_hashes_rechecked': bool(args.source),
                  'necessity_counts': necessity_counts,
                  'security_runtime_pass_inferred': False}, indent=2))
