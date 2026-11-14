#!/usr/bin/env python3
"""Record fresh output identity, not a claim of historical binary equivalence."""
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from patchkit.environment import libc_version
from patchkit import variants, json_generation
output = Path(sys.argv[1])
profile = sys.argv[2]
variant = sys.argv[3] if len(sys.argv) > 3 else 'build007'
prepared = Path(sys.argv[4]) if len(sys.argv) > 4 else None
identity = json.loads((output / 'source-identity.json').read_text())
if identity['variant'] != variant:
    raise SystemExit('build/source variant mismatch')
if prepared is None or variants.verify_source(prepared, variant) != identity:
    raise SystemExit('original prepared source changed during build')
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
record = {'schema': 1, 'profile': profile, 'system': platform.system(), 'machine': platform.machine(),
          'libc': libc_version(), 'os_release': Path('/etc/os-release').read_text(),
          'variant': variant, 'source_identity': identity,
          'patch_sha256': identity['patch_sha256'],
          'normalized_source_sha256': identity['normalized_source_sha256'],
          'binaries': {name: digest(output / name) for name in ['php', 'php-fpm']},
          'configure': (output / 'configure-arguments.txt').read_text().splitlines(),
          'toolchain': (output / 'toolchain.txt').read_text(),
          'CFLAGS': __import__('os').environ.get('CFLAGS'), 'CPPFLAGS': __import__('os').environ.get('CPPFLAGS'),
          'LDFLAGS': __import__('os').environ.get('LDFLAGS'),
          'DEB_HOST_MULTIARCH': __import__('os').environ.get('DEB_HOST_MULTIARCH'),
          'result': 'BUILT_NOT_RUNTIME_VERIFIED', 'external_module_compatibility': 'NOT_TESTED',
          'historical_build007_binary_equivalence': 'NOT_CLAIMED'}
if any((output / name).exists() or (output / name).is_symlink() for name in ['build.json', 'SHA256SUMS', 'json-generation.json']):
    raise SystemExit('build records must be new')
generation = json_generation.finish(output / 'source', output / 'json-generation-plan.json', identity['normalized_source_sha256'])
json_generation.write_new(output / 'json-generation.json', generation)
record['json_generation'] = generation
record['json_generation_receipt_sha256'] = digest(output / 'json-generation.json')
with (output / 'build.json').open('x') as stream:
    stream.write(json.dumps(record, indent=2, sort_keys=True) + '\n')
with (output / 'SHA256SUMS').open('x') as stream:
    stream.write(''.join(digest(output/name) + '  ' + name + '\n' for name in ['php', 'php-fpm', 'build.json', 'json-generation-plan.json', 'json-generation.json']))
print(json.dumps({'result': record['result'], 'profile': profile, 'binaries': record['binaries']}))
