"""Reuse only the reviewed JSON lexer/grammar and generated C/header tuple.

Changing a lexer/grammar requires a reviewed update of this fixed tuple together
with its generated C and companion header. No caller-supplied trust root exists.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

BUNDLE = {
    'ext/json/json_scanner.re': '9bbd7c18de5e56abf9359193f47112ce254ac106fe06671841c1257d6ef620e9',
    'ext/json/json_scanner.c': '997803e6bf02068f61db344bfd2ea0dd077c7701359ba48fd8979f3d40ecf5c1',
    'ext/json/php_json_scanner_defs.h': '10abc51aba2e43d9d75edf2506bd5af3f8b16953559c89a946c3d670ee9f922d',
    'ext/json/json_parser.y': '113704af638aeb80d9285a90b2c49a760724a8e148a76245c959f54463765ca1',
    'ext/json/json_parser.tab.c': '7d86ed19b08af1c0a3cf2b453bc1abce11175a1fdd99127476bd8f87d79edc12',
    'ext/json/json_parser.tab.h': 'aacdf9a63d795eff57a2107c0d80a4d2cdb2df80e89391eee00b7c3baaad28dc',
}
TARGETS = ['ext/json/json_scanner.c', 'ext/json/json_parser.tab.c']


def verify_bundle(source):
    source = Path(source)
    hashes = {}
    for name, expected in BUNDLE.items():
        path = source / name
        if any(p.is_symlink() for p in (path, path.parent, path.parent.parent, source)) or not path.is_file():
            raise ValueError('regular JSON bundle file required: ' + name)
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        if hashes[name] != expected:
            raise ValueError('JSON bundle mismatch; review inputs and generated C/headers together: ' + name)
    return hashes


def _plan(hashes):
    return {'schema': 1, 'mode': 'pregenerated', 'targets': list(TARGETS),
            'bundle_sha256': hashlib.sha256(json.dumps(BUNDLE, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
            'before': hashes}


def write_new(path, record):
    with Path(path).open('x') as stream:
        json.dump(record, stream, indent=2, sort_keys=True)
        stream.write('\n')


def prepare(source, output):
    plan = _plan(verify_bundle(source))
    write_new(output, plan)
    return plan


def finish(source, plan_path, prepared_source_sha256):
    if not re.fullmatch(r'[a-f0-9]{64}', prepared_source_sha256):
        raise ValueError('prepared source SHA-256 required')
    plan_path = Path(plan_path)
    if plan_path.is_symlink() or not plan_path.is_file():
        raise ValueError('regular JSON generation plan required')
    after = verify_bundle(source)
    plan = json.loads(plan_path.read_text())
    if plan != _plan(after):
        raise ValueError('JSON generation plan differs from the reviewed bundle')
    return dict(plan, after=after, prepared_source_sha256=prepared_source_sha256)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args(argv)
    source = args.source.absolute()
    if '\n' in str(source) or '\r' in str(source):
        raise ValueError('JSON make argument paths must be single lines')
    plan = prepare(source, args.output)
    for target in plan['targets']:
        print('--old-file=' + str(source / target))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
