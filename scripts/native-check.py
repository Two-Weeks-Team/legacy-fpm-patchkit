#!/usr/bin/env python3
"""Benign, private Unix-socket FPM/session/upload regressions. Python 3.5+."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import pwd
import re
import subprocess
import sys
import tempfile
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from patchkit import fcgi, reporting, environment

FIXTURE = r'''<?php
ob_start();
header('Content-Type: text/plain');
$action = isset($_GET['action']) ? $_GET['action'] : 'session';
echo 'pid=' . getmypid() . "\n";
if ($action === 'session') {
    $before = ini_get('session.serialize_handler');
    $target = isset($_GET['target']) ? $_GET['target'] : $before;
    $ret = @ini_set('session.serialize_handler', $target);
    echo 'switch=' . ($ret === false ? 'blocked' : 'allowed') . "\n";
    echo 'handler=' . ini_get('session.serialize_handler') . "\n";
    echo 'started=' . (session_start() ? 'yes' : 'no') . "\n";
    $value = isset($_SESSION['plain']) ? $_SESSION['plain'] : 'empty';
    echo 'previous=' . $value . "\n";
    $_SESSION['plain'] = 'patchkit-value';
    session_write_close();
} elseif ($action === 'upload') {
    $item = isset($_FILES['attachment']) ? $_FILES['attachment'] : null;
    $ok = $item && $item['error'] === UPLOAD_ERR_OK && is_uploaded_file($item['tmp_name']);
    echo 'upload=' . ($ok ? 'yes' : 'no') . "\n";
    if ($ok) {
        $data = file_get_contents($item['tmp_name']);
        echo 'bytes=' . strlen($data) . "\n";
        echo 'digest=' . hash('sha256', $data) . "\n";
    }
}
echo "complete=yes\n";
'''


def fields(body):
    return dict(line.split('=', 1) for line in body.decode().splitlines() if '=' in line)


def checked_response(result):
    if result['stderr']:
        raise ValueError('unexpected FastCGI stderr: ' + result['stderr'].decode('utf-8', 'replace')[-4000:])
    values = fields(result['body'])
    if values.get('complete') != 'yes':
        raise ValueError('incomplete PHP fixture response')
    return values


def collect_logs(root):
    diagnostics = {}
    for name in ['fpm.log', 'process.log']:
        path = root / name
        if not path.exists():
            continue
        text = path.read_text()[-32768:].replace(str(root), '<test-root>')
        diagnostics[name] = text
    return diagnostics


def check_logs(root):
    diagnostics = collect_logs(root)
    for text in diagnostics.values():
        if re.search(r'PHP (?:Warning|Fatal|Parse|Notice|Deprecated)|\b(?:WARNING|ERROR|ALERT|EMERGENCY):', text):
            raise ValueError('unexpected FPM diagnostic: ' + text)
    return diagnostics


def stop_process(process, grace=10):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            raise ValueError('test FPM required forced cleanup; inspect worker cleanup before retrying')


def campaign(binary, codec, progress):
    with tempfile.TemporaryDirectory(prefix='pk-', dir='/tmp') as temporary:
        root = Path(temporary)
        for name in ['sessions', 'uploads']:
            (root / name).mkdir()
        script = root / 'check.php'
        script.write_text(FIXTURE)
        socket_path = root / 'fpm.sock'
        config = root / 'fpm.conf'
        user = pwd.getpwuid(os.getuid()).pw_name
        config.write_text('''[global]
error_log = {root}/fpm.log
daemonize = no
[proof]
listen = {root}/fpm.sock
pm = static
pm.max_children = 1
user = {user}
clear_env = yes
catch_workers_output = yes
php_admin_flag[display_errors] = off
php_admin_flag[log_errors] = on
php_admin_value[session.save_path] = {root}/sessions
php_admin_value[upload_tmp_dir] = {root}/uploads
php_value[session.serialize_handler] = {codec}
php_value[session.upload_progress.enabled] = {progress}
'''.format(root=root, user=user, codec=codec, progress='On' if progress else 'Off'))
        env = os.environ.copy()
        env['PHP_INI_SCAN_DIR'] = ''
        command = [str(binary), '-n', '-y', str(config), '-F']
        if os.getuid() == 0:
            command += ['-R']  # owned isolated test only
        with (root / 'process.log').open('wb') as log:
            process = subprocess.Popen(command, env=env, stdout=log, stderr=log)
            try:
                deadline = time.monotonic() + 15
                while not socket_path.exists():
                    if process.poll() is not None or time.monotonic() >= deadline:
                        raise ValueError('FPM did not start: ' + (root / 'process.log').read_text()[-1800:])
                    time.sleep(0.05)
                sid = uuid.uuid4().hex
                def ask(query, body=b'', content_type=''):
                    values = {'REQUEST_METHOD': 'POST' if body else 'GET',
                              'SCRIPT_FILENAME': str(script), 'SCRIPT_NAME': '/check.php',
                              'QUERY_STRING': query, 'REQUEST_URI': '/check.php?' + query,
                              'SERVER_PROTOCOL': 'HTTP/1.1', 'SERVER_NAME': 'localhost',
                              'SERVER_PORT': '80', 'REMOTE_ADDR': '127.0.0.1',
                              'CONTENT_LENGTH': str(len(body)), 'CONTENT_TYPE': content_type,
                              'HTTP_COOKIE': 'PHPSESSID=' + sid, 'GATEWAY_INTERFACE': 'CGI/1.1'}
                    result = fcgi.request(socket_path, values, body)
                    return checked_response(result)
                checks = []
                first = ask('action=session&target=' + codec)
                assert first['handler'] == codec and first['switch'] == 'allowed' and first['started'] == 'yes', 'same-handler session assignment failed'
                checks.append('same-handler assignment/session start')
                again = ask('action=session&target=' + codec)
                assert again['previous'] == 'patchkit-value', 'plain session value did not persist'
                assert first['pid'] == again['pid'], 'worker changed during session round trip'
                checks.append('same-worker plain session persistence')
                for target in ['php', 'php_binary', 'php_serialize']:
                    if target != codec:
                        response = ask('action=session&target=' + target)
                        assert response['switch'] == 'blocked' and response['handler'] == codec, 'different-handler switch was not rejected: ' + codec + ' -> ' + target
                        assert response['started'] == 'yes' and response['previous'] == 'patchkit-value', 'session data changed after rejected codec switch'
                        checks.append('different-handler rejection: ' + target)
                boundary = 'patchkit' + uuid.uuid4().hex
                data = b'ordinary-upload\n' * 32
                body = ('--' + boundary + '\r\nContent-Disposition: form-data; name="PHP_SESSION_UPLOAD_PROGRESS"\r\n\r\nproof\r\n--' + boundary + '\r\nContent-Disposition: form-data; name="attachment"; filename="sample.txt"\r\nContent-Type: text/plain\r\n\r\n').encode() + data + ('\r\n--' + boundary + '--\r\n').encode()
                uploaded = ask('action=upload', body, 'multipart/form-data; boundary=' + boundary)
                assert uploaded['upload'] == 'yes' and int(uploaded['bytes']) == len(data), 'ordinary multipart upload failed'
                assert uploaded['digest'] == hashlib.sha256(data).hexdigest(), 'upload content digest mismatch'
                assert not list((root / 'uploads').iterdir()), 'uploaded temporary file remained after request'
                checks.append('ordinary multipart upload/digest/temp cleanup')
                final = ask('action=session&target=' + codec)
                assert final['pid'] == first['pid'] and final['previous'] == 'patchkit-value', 'same-worker/session continuity failed after upload'
                checks.append('same-worker continuity after upload')
                return {'codec': codec, 'progress': progress, 'checks': checks,
                        'diagnostics': check_logs(root), 'result': 'PASS'}
            except Exception as error:
                raise ValueError(type(error).__name__ + ': ' + str(error) + '; diagnostics=' + json.dumps(collect_logs(root)))
            finally:
                stop_process(process)


def main():
    if sys.flags.optimize:
        raise SystemExit('Native checks require assertions: do not use Python -O.')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fpm', required=True, type=Path)
    parser.add_argument('--cli', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        reporting.require_new(args.output)
    except ValueError as error:
        parser.error(str(error))
    report = {'schema': 1, 'scope': 'benign isolated local regression; not exploit or application acceptance',
              'machine': platform.machine(), 'libc': environment.libc_version(), 'campaigns': [],
              'external_modules': 'NOT_TESTED', 'production': 'NOT_ACCESSED'}
    try:
        for name, binary in [('fpm', args.fpm), ('cli', args.cli)]:
            if binary.is_symlink() or not binary.is_file():
                raise ValueError('regular trusted test binary required')
            report[name + '_sha256'] = hashlib.sha256(binary.read_bytes()).hexdigest()
        env = os.environ.copy()
        env['PHP_INI_SCAN_DIR'] = ''
        output = subprocess.check_output([str(args.cli.resolve()), '-n', '-r', 'echo PHP_VERSION;'], env=env, timeout=10)
        report['php_version'] = output.decode()
        if not report['php_version'].startswith('7.0.33'):
            raise ValueError('unexpected PHP version')
        for codec in ['php', 'php_binary', 'php_serialize']:
            for progress in [True, False]:
                report['campaigns'].append(campaign(args.fpm.resolve(), codec, progress))
        report['result'] = 'BENIGN_RUNTIME_PASS'
    except Exception as error:
        report['result'] = 'FAIL'
        report['error'] = type(error).__name__ + ': ' + str(error)
    reporting.write_new(args.output, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report['result'] == 'BENIGN_RUNTIME_PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
