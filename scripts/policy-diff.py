#!/usr/bin/env python3
"""Benign two-binary serializer-policy control, not an exploit test. Python 3.5+."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from patchkit import fcgi, reporting
spec = importlib.util.spec_from_file_location('native_check', str(ROOT / 'scripts/native-check.py'))
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


def distinguishes(stock, candidate):
    return (stock.get('switch') == 'allowed' and stock.get('handler') == 'php_binary'
            and stock.get('started') == 'yes' and candidate.get('switch') == 'blocked'
            and candidate.get('handler') == 'php' and candidate.get('started') == 'yes')


def binary_digest(binary):
    if binary.is_symlink() or not binary.is_file():
        raise ValueError('a trusted regular test binary is required')
    digest = hashlib.sha256()
    with binary.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def observe(binary):
    if binary.is_symlink() or not binary.is_file():
        raise ValueError('a trusted regular test binary is required')
    with tempfile.TemporaryDirectory(prefix='pk-diff-', dir='/tmp') as temporary:
        root = Path(temporary)
        (root / 'sessions').mkdir()
        (root / 'probe.php').write_text(native.FIXTURE)
        user = pwd.getpwuid(os.getuid()).pw_name
        (root / 'fpm.conf').write_text('''[global]
error_log = {root}/fpm.log
daemonize = no
[proof]
listen = {root}/fpm.sock
pm = static
pm.max_children = 1
user = {user}
clear_env = yes
php_admin_flag[display_errors] = off
php_admin_flag[log_errors] = on
php_admin_value[session.save_path] = {root}/sessions
php_value[session.serialize_handler] = php
php_value[session.upload_progress.enabled] = On
'''.format(root=root, user=user))
        env = os.environ.copy()
        env['PHP_INI_SCAN_DIR'] = ''
        args = [str(binary.resolve()), '-n', '-y', str(root / 'fpm.conf'), '-F']
        if os.getuid() == 0:
            args += ['-R']
        with (root / 'process.log').open('wb') as log:
            process = subprocess.Popen(args, env=env, stdout=log, stderr=log)
            try:
                deadline = time.monotonic() + 15
                while not (root / 'fpm.sock').exists():
                    if process.poll() is not None or time.monotonic() >= deadline:
                        raise ValueError('control FPM did not start')
                    time.sleep(0.05)
                # Fresh empty SID avoids treating a codec/data-decode mismatch as
                # proof of the policy difference under test.
                values = {'REQUEST_METHOD': 'GET', 'SCRIPT_FILENAME': str(root / 'probe.php'),
                          'SCRIPT_NAME': '/probe.php', 'QUERY_STRING': 'action=session&target=php_binary',
                          'SERVER_PROTOCOL': 'HTTP/1.1', 'SERVER_NAME': 'localhost', 'SERVER_PORT': '80',
                          'REMOTE_ADDR': '127.0.0.1', 'GATEWAY_INTERFACE': 'CGI/1.1',
                          'HTTP_COOKIE': 'PHPSESSID=' + uuid.uuid4().hex}
                observed = native.checked_response(fcgi.request(root / 'fpm.sock', values))
                native.check_logs(root)
                return {key: observed[key] for key in ['switch', 'handler', 'started']}
            except Exception as error:
                raise ValueError(str(error) + '; diagnostics=' + json.dumps(native.collect_logs(root)))
            finally:
                native.stop_process(process)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-fpm', required=True, type=Path)
    parser.add_argument('--candidate-fpm', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        reporting.require_new(args.output)
    except ValueError as error:
        parser.error(str(error))
    report = {'schema': 1, 'scope': 'benign serializer-transition policy difference; not exploit resistance'}
    try:
        for name, binary in [('stock', args.stock_fpm), ('candidate', args.candidate_fpm)]:
            report[name + '_sha256'] = binary_digest(binary)
        for name, binary in [('stock', args.stock_fpm), ('candidate', args.candidate_fpm)]:
            report[name] = observe(binary)
        report['result'] = 'POLICY_DIFF_OBSERVED' if distinguishes(report['stock'], report['candidate']) else 'FAIL'
    except Exception as error:
        report['result'] = 'FAIL'
        report['error'] = type(error).__name__ + ': ' + str(error)
    reporting.write_new(args.output, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report['result'] == 'POLICY_DIFF_OBSERVED' else 1


if __name__ == '__main__':
    sys.exit(main())
