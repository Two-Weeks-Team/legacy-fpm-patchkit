"""Run with python3 -m patchkit; no installation or privileged daemon required."""
import argparse
import json
from pathlib import Path
import sys

from . import __version__, sources, inspection, rehearsal, variants


def main(argv=None):
    parser = argparse.ArgumentParser(description='Legacy FPM Patchkit — source and local verification, no remote deployment.')
    parser.add_argument('--version', action='version', version=__version__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('verify', help='Verify bundled patch and provenance inputs')
    fetch = commands.add_parser('fetch', help='Download pinned official source archives over HTTPS')
    fetch.add_argument('--cache', type=Path, default=Path('.work/downloads'))
    prepare = commands.add_parser('prepare', help='Reconstruct and patch a NEW source tree, offline')
    prepare.add_argument('--cache', type=Path, default=Path('.work/downloads'))
    prepare.add_argument('--output', type=Path, default=Path('.work/source'))
    prepare.add_argument('--variant', choices=['build007', 'acl-filter-20261114', 'multipart-20261114', 'cookie-20261114', 'fpm-log-20261114'], default='build007')
    inspect = commands.add_parser('inspect', help='Read ELF/hash metadata without executing the binary')
    inspect.add_argument('--binary', required=True, type=Path)
    inspect.add_argument('--build-record', type=Path)
    drill = commands.add_parser('rehearse', help='Backup/replace/restore synthetic files in a NEW directory')
    drill.add_argument('--candidate', required=True, type=Path)
    drill.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'verify':
            manifest = json.loads((sources.ROOT / 'provenance/build007-source.json').read_text())
            sources.verify_file(sources.ROOT / 'patches/build007.patch', manifest['patch_sha256'])
            result = {'result': 'INPUTS_VERIFIED', 'changed_files': len(manifest['changed']),
                      'patch_sha256': manifest['patch_sha256'], 'runtime_tested': False}
        elif args.command == 'fetch':
            result = {'result': 'ARCHIVES_VERIFIED', 'archives': sources.fetch(args.cache)}
        elif args.command == 'prepare':
            result = sources.prepare(args.cache, args.output) if args.variant == variants.DEFAULT else variants.prepare(args.cache, args.output, args.variant)
        elif args.command == 'inspect':
            result = inspection.inspect(args.binary, args.build_record)
        else:
            result = rehearsal.run(args.candidate, args.output)
    except (ValueError, OSError, TimeoutError) as error:
        print(json.dumps({'result': 'FAIL', 'error': str(error)}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
