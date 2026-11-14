#!/usr/bin/env python3
"""Legacy-guest compatible source verification; Python 3.5+; no PHP execution."""
import hashlib
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
source = Path(sys.argv[1])
expected = json.loads((root / 'provenance/inputs.json').read_text())['normalized_candidate_sha256']
rows = {}
for path in sorted(source.rglob('*')):
    name = path.relative_to(source).as_posix()
    if path.is_symlink():
        raise SystemExit('Source symlink rejected: ' + name)
    if path.is_file() and not name.startswith('.pc/') and not name.endswith('.orig'):
        rows[name] = hashlib.sha256(path.read_bytes()).hexdigest()
actual = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
if actual != expected:
    raise SystemExit('Source tree mismatch: ' + actual)
print('Verified candidate source tree ' + actual)
