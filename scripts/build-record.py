#!/usr/bin/env python3
"""Record fresh output identity, not a claim of historical binary equivalence."""
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
output = Path(sys.argv[1])
profile = sys.argv[2]
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
record = {'schema': 1, 'profile': profile, 'system': platform.system(), 'machine': platform.machine(),
          'libc': list(platform.libc_ver()), 'os_release': Path('/etc/os-release').read_text(),
          'patch_sha256': digest(root / 'patches/build007.patch'),
          'normalized_source_sha256': json.loads((root / 'provenance/inputs.json').read_text())['normalized_candidate_sha256'],
          'binaries': {name: digest(output / name) for name in ['php', 'php-fpm']},
          'configure': (output / 'configure-arguments.txt').read_text().splitlines(),
          'toolchain': (output / 'toolchain.txt').read_text(),
          'CFLAGS': __import__('os').environ.get('CFLAGS'), 'CPPFLAGS': __import__('os').environ.get('CPPFLAGS'),
          'LDFLAGS': __import__('os').environ.get('LDFLAGS'),
          'DEB_HOST_MULTIARCH': __import__('os').environ.get('DEB_HOST_MULTIARCH'),
          'result': 'BUILT_NOT_RUNTIME_VERIFIED', 'external_module_compatibility': 'NOT_TESTED',
          'historical_build007_binary_equivalence': 'NOT_CLAIMED'}
(output / 'build.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
(output / 'SHA256SUMS').write_text(''.join(digest(output/name) + '  ' + name + '\n' for name in ['php', 'php-fpm', 'build.json']))
print(json.dumps({'result': record['result'], 'profile': profile, 'binaries': record['binaries']}))
