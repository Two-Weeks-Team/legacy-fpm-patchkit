#!/usr/bin/env python3
"""Verify an entire source tree against a named repository-pinned variant."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from patchkit import variants
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('source', type=Path)
parser.add_argument('--variant', choices=['build007', 'acl-filter-20261114', 'multipart-20261114'], default='build007')
parser.add_argument('--json', action='store_true')
args = parser.parse_args()
try:
    identity = variants.verify_source(args.source, args.variant)
except (ValueError, OSError) as error:
    raise SystemExit(str(error))
print(json.dumps(identity, sort_keys=True) if args.json else 'Verified candidate source tree ' + identity['normalized_source_sha256'])
