"""Bounded, owned-process Linux checks for the ACL/filter source variant.

No production targets, service managers, remote transports or arbitrary manifests.
All sockets are ephemeral local test sockets; only processes started here are stopped.
"""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import platform
import pwd
import re
import shutil
import signal
import socket
import struct
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from . import fcgi, sources, variants

VARIANT = 'acl-filter-20261114'


def new_run_directory(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=False)
    return path.resolve()


def write_new(path, data):
    with Path(path).open('x') as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write('\n')


def clean_env():
    env = {key: os.environ[key] for key in ('PATH', 'LANG', 'LC_ALL', 'TMPDIR') if key in os.environ}
    env['PHP_INI_SCAN_DIR'] = ''
    return env


def stop_owned(process, grace=3):
    """The process group was created by this runner with start_new_session=True."""
    forced = False
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        forced = True
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=3)
    # Allow the directly owned master/worker group to finish reaping naturally.
    end = time.monotonic() + grace
    while True:
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            break
        if time.monotonic() >= end:
            os.killpg(process.pid, signal.SIGKILL)
            forced = True
            break
        time.sleep(0.02)
    return {'pid': process.pid, 'reaped': process.poll() is not None, 'forced_cleanup': forced}


def command(argv, directory, label, timeout, env=None):
    directory = Path(directory)
    stdout_path, stderr_path = directory/(label+'.stdout'), directory/(label+'.stderr')
    with stdout_path.open('xb') as stdout, stderr_path.open('xb') as stderr:
        process = subprocess.Popen([str(a) for a in argv], cwd=directory, env=env or clean_env(),
                                   stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                   start_new_session=True)
        timed_out = False
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
        finally:
            cleanup = stop_owned(process)
    record = {'command': [str(a) for a in argv], 'returncode': process.returncode,
              'timed_out': timed_out, 'stdout': stdout_path.read_text(errors='replace')[-131072:],
              'stderr': stderr_path.read_text(errors='replace')[-131072:],
              'output_budget_exceeded': max(stdout_path.stat().st_size, stderr_path.stat().st_size) > 8*1024*1024}
    record.update(cleanup)
    write_new(directory/(label+'.command.json'), record)
    return record


def require_command(record):
    if record['timed_out'] or record['returncode'] or record['forced_cleanup'] or record['output_budget_exceeded']:
        raise ValueError('command failed: ' + repr(record['command']))


def evaluate_acl(want_allow, response, logs, peer):
    if 'Wrong IP address' in logs or 'There are no allowed addresses' in logs:
        raise ValueError('allowlist parse failed; refusal is not ACL evidence')
    marker = "Connection disallowed: IP address '" + peer + "' has been dropped."
    other_logs = '\n'.join(line for line in logs.splitlines() if marker not in line)
    if re.search(r'PHP (?:Warning|Fatal|Parse|Notice)|\b(?:WARNING|ERROR|ALERT|EMERGENCY):', other_logs):
        raise ValueError('unexpected FPM diagnostic')
    if want_allow:
        if response is None or response['body'] != b'acl-ok\n' or response['stderr'] or 'Connection disallowed:' in logs:
            raise ValueError('allowed peer did not complete the benign FastCGI request')
    elif response is not None or marker not in logs:
        raise ValueError('refusal requires the exact peer drop log and no application response')


def require_phpt_pass(record, count):
    statuses = phpt_statuses(record['stdout'])
    if record['returncode'] or record['stderr'] or statuses != ['PASS'] * count:
        raise ValueError('PHPT did not pass all requested tests without skips/warnings/leaks')


def phpt_statuses(output):
    return re.findall(r'^(PASS|FAIL|SKIP|BORK|WARN|LEAK|XFAIL)\b', output.replace('\r','\n'), re.M)


def memcheck_evidence(xml):
    errors = ET.fromstring(xml).findall('error')
    relevant = []
    for error in errors:
        if error.findtext('kind') not in ('UninitCondition', 'UninitValue'):
            continue
        stack = error.find('stack')
        frames = stack.findall('frame') if stack is not None else []
        # The fixed source has the tmp[*s] branch at line 108. A wrapper,
        # sibling helper or allocation-origin stack cannot prove this RED.
        if any((f.findtext('fn') or '') in ('php_filter_encode_url', 'php_filter_encoded') and
               Path(f.findtext('file') or '').name == 'sanitizing_filters.c' and
               f.findtext('line') == '108' for f in frames):
            relevant.append(ET.tostring(error, encoding='unicode'))
    return {'all_errors': len(errors), 'filter_uninitialized_errors': len(relevant), 'relevant_errors': relevant}


def filter_cases():
    safe = b'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._'
    rows = [('byte-%02x' % i, bytes([i]), 0, bytes([i]) if i in safe else ('%%%02X' % i).encode()) for i in range(256)]
    rows += [('repeated-ff', b'\xff'*32, 0, b'%FF'*32), ('empty', b'', 0, b''),
             ('safe', safe, 0, safe), ('ordinary', b'A z!+%~', 0, b'A%20z%21%2B%25%7E'),
             ('binary', b'A\x00\x1f\x7f\x80\xfe\xffZ', 0, b'A%00%1F%7F%80%FE%FFZ'),
             ('strip-low', b'A\x00\x1f \xffZ', 4, b'A%20%FFZ'),
             ('strip-high', b'A\x1f\x7f\x80\xffZ', 8, b'A%1FZ'),
             ('strip-backtick', b'A`B~', 512, b'AB%7E'),
             ('strip-all', b'\x00A` \xffZ', 524, b'A%20Z'),
             ('encode-low', b'A\x00\x1fZ', 16, b'A%00%1FZ'),
             ('encode-high', b'A\x7f\x80\xffZ', 32, b'A%7F%80%FFZ'),
             ('encode-amp', b'A&B', 64, b'A%26B'),
             ('encode-all', b'A\x00&\xffZ', 112, b'A%00%26%FFZ'),
             ('long', b'A z!'*4096, 0, b'A%20z%21'*4096)]
    return [{'id': name, 'input_hex': data.hex(), 'flags': flags, 'expected_hex': expected.hex()} for name, data, flags, expected in rows]


def check_filter(cases, actual, candidate):
    if not isinstance(actual, dict) or set(actual) != {row['id'] for row in cases}:
        raise ValueError('missing/extra filter outputs')
    mismatches = [row['id'] for row in cases if actual[row['id']] != row['expected_hex']]
    try:
        unrelated = [row['id'] for row in cases if row['id'] in mismatches and
                     bytes.fromhex(actual[row['id']]).replace(b'\xff', b'%FF').hex() != row['expected_hex']]
    except (ValueError, TypeError) as error:
        raise ValueError('invalid filter byte output') from error
    if (candidate and mismatches) or unrelated:
        raise ValueError('filter output mismatch: ' + repr(mismatches))
    return {'cases': len(cases), 'mismatches': mismatches, 'actual': actual,
            'result': 'PASS' if not mismatches else 'BASELINE_FF_OUTPUT_MISMATCH_OBSERVED'}


def filter_fixture(cases):
    # Values contain hex/ids/integers only; no request input is executed as code.
    literal = ',\n'.join("array('%s','%s',%d)" % (row['id'],row['input_hex'],row['flags']) for row in cases)
    return "<?php\n$cases=array(" + literal + ");\nforeach($cases as $c){echo $c[0],\"=\",bin2hex(filter_var(hex2bin($c[1]),FILTER_SANITIZE_ENCODED,$c[2])),\"\\n\";}\n"


def parse_filter_output(output):
    result = {}
    for line in output.splitlines():
        match = re.fullmatch(r'([a-z0-9-]+)=((?:[0-9a-f]{2})*)',line)
        if match is None or match[1] in result:
            raise ValueError('malformed/duplicate filter output record')
        result[match[1]] = match[2]
    return result


def tcp_request(family, host, port, script, timeout=5):
    if host not in ('::1', '127.0.0.1'):
        raise ValueError('only literal loopback peers are allowed')
    end = time.monotonic() + timeout
    with socket.socket(family, socket.SOCK_STREAM) as stream:
        stream.settimeout(timeout)
        stream.connect((host, port))
        values = {'REQUEST_METHOD': 'GET', 'SCRIPT_FILENAME': str(script), 'SCRIPT_NAME': '/check.php',
                  'QUERY_STRING': '', 'REQUEST_URI': '/check.php', 'SERVER_PROTOCOL': 'HTTP/1.1',
                  'SERVER_NAME': 'localhost', 'SERVER_PORT': str(port), 'REMOTE_ADDR': host,
                  'CONTENT_LENGTH': '0', 'GATEWAY_INTERFACE': 'CGI/1.1'}
        for data in [fcgi.record(1, struct.pack('!HB5x', 1, 0)), fcgi.record(4, fcgi.params(values)), fcgi.record(4), fcgi.record(5)]:
            stream.settimeout(max(0.001, end-time.monotonic()))
            stream.sendall(data)
        return fcgi.read_response(stream, deadline=end)


def unused_port(dual):
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0 if dual else 1)
        s.bind(('::' if dual else '::1', 0))
        return s.getsockname()[1]


def require_fpm_exit(before_stop, after_stop, forced):
    if before_stop is not None or after_stop not in (0, -signal.SIGTERM) or forced:
        raise ValueError('FPM exited unexpectedly or required forced cleanup')


@contextmanager
def fpm_instance(binary, directory, allowlist, dual, fixture, timeout):
    directory.mkdir()
    script = directory/'check.php'
    script.write_text(fixture)
    port = unused_port(dual)
    user = pwd.getpwuid(os.getuid()).pw_name
    config = directory/'fpm.conf'
    config.write_text('''[global]
error_log = {root}/fpm.log
daemonize = no
[proof]
listen = [{host}]:{port}
listen.allowed_clients = {allowed}
pm = static
pm.max_children = 1
pm.max_requests = 16
request_terminate_timeout = 5s
user = {user}
clear_env = yes
catch_workers_output = yes
php_admin_flag[display_errors] = off
php_admin_flag[log_errors] = on
'''.format(root=directory, host='::' if dual else '::1', port=port, allowed=allowlist, user=user))
    argv = [str(binary), '-n', '-y', str(config), '-F'] + (['-R'] if os.getuid() == 0 else [])
    with (directory/'process.log').open('xb') as log:
        p = subprocess.Popen(argv, env=clean_env(), stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        try:
            end = time.monotonic() + min(timeout, 12)
            while True:
                logs = read_fpm_logs(directory)
                if p.poll() is not None:
                    raise ValueError('FPM exited before readiness: ' + logs)
                if 'ready to handle connections' in logs:
                    break
                if time.monotonic() >= end:
                    raise ValueError('FPM readiness deadline exceeded: ' + logs)
                time.sleep(0.03)
            yield port, script
        finally:
            before_stop = p.poll()
            cleanup = stop_owned(p)
            logs = read_fpm_logs(directory)
            write_new(directory/'process.json', {'command': argv, 'returncode_before_stop': before_stop,
                       'returncode': p.returncode, 'logs_after_cleanup': logs, **cleanup})
            require_fpm_exit(before_stop, p.returncode, cleanup['forced_cleanup'])
            other_logs = '\n'.join(line for line in logs.splitlines() if 'Connection disallowed:' not in line)
            if re.search(r'PHP (?:Warning|Fatal|Parse|Notice)|\b(?:WARNING|ERROR|ALERT|EMERGENCY):', other_logs):
                raise ValueError('FPM shutdown diagnostic')


def read_fpm_logs(directory):
    return '\n'.join((directory/name).read_text(errors='replace')[-65536:] for name in ('fpm.log', 'process.log') if (directory/name).exists())


def acl_case(binary, directory, allowlist, dual, want_allow, budget):
    response, request_error = None, None
    peer = '127.0.0.1' if dual else '::1'
    with fpm_instance(binary, directory, allowlist, dual, '<?php echo "acl-ok\\n";\n', budget()) as (port, script):
        try:
            response = tcp_request(socket.AF_INET if dual else socket.AF_INET6, peer, port, script, min(5, budget()))
        except (OSError, ValueError, TimeoutError) as error:
            request_error = type(error).__name__ + ': ' + str(error)
        logs = read_fpm_logs(directory)
        # Log writes may lag the socket close; bound the wait independently.
        end = time.monotonic() + min(1, budget())
        while response is None and 'has been dropped.' not in logs and time.monotonic() < end:
            time.sleep(0.02)
            logs = read_fpm_logs(directory)
        record = {'allowed_clients': allowlist, 'peer': peer, 'dual_stack': dual,
                  'expected_allow': want_allow, 'request_error': request_error,
                  'response_body_hex': response['body'].hex() if response else None,
                  'response_stderr_hex': response['stderr'].hex() if response else None,
                  'logs': logs}
        write_new(directory/'observation.json', record)
        evaluate_acl(want_allow, response, logs, peer)
    return {**record, 'result': 'PASS'}


def run_phpt(cli, source, output, fixture, budget):
    output.mkdir()
    copied = output/'tests'
    copied.mkdir()
    names = ['024', '027', '032', 'bug7586', 'bug69203']
    paths = []
    for name in names:
        dest = copied/(name+'.phpt')
        shutil.copyfile(source/'ext/filter/tests'/(name+'.phpt'), dest)
        paths.append(dest)
    env = clean_env()
    env.update(TEST_PHP_EXECUTABLE=str(cli), NO_INTERACTION='1', REPORT_EXIT_STATUS='1', TERM='dumb')
    old = command([cli, '-n', source/'run-tests.php', '-n', '-q'] + paths, output, 'existing-phpt', min(120, budget()), env)
    require_command(old)
    require_phpt_pass(old, len(paths))
    new = copied/'acl-filter-full-byte.phpt'
    shutil.copyfile(fixture, new)
    result = command([cli, '-n', source/'run-tests.php', '-n', '-q', new], output, 'new-phpt', min(120, budget()), env)
    status = phpt_statuses(result['stdout'])
    completed = (status == ['PASS'] and result['returncode'] == 0) or (status == ['FAIL'] and result['returncode'] == 1)
    if result['timed_out'] or result['forced_cleanup'] or result['output_budget_exceeded'] or result['stderr'] or not completed:
        raise ValueError('new PHPT did not complete as PASS or a recorded baseline FAIL')
    return {'existing': old, 'new': result}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for side in ('baseline', 'candidate'):
        for name in ('cli', 'fpm', 'source'):
            parser.add_argument('--'+side+'-'+name, type=Path, required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--timeout', type=int, default=900, choices=range(60, 1801), metavar='60..1800')
    args = parser.parse_args(argv)
    root = new_run_directory(args.output)
    deadline = time.monotonic() + args.timeout
    def budget():
        remaining = deadline-time.monotonic()
        if remaining <= 0:
            raise TimeoutError('whole-run deadline exceeded')
        return remaining
    report = {'schema': 1, 'result': 'FAIL', 'system': platform.platform(), 'production': 'NOT_ACCESSED',
              'baseline': {}, 'candidate': {}, 'phases': {}, 'inputs_before': {}}
    try:
        if platform.system() != 'Linux':
            report['result'] = 'NOT_RUN'
            raise ValueError('Linux runtime required; no cross-platform emulation')
        bindv6 = Path('/proc/sys/net/ipv6/bindv6only').read_text().strip()
        report['bindv6only'] = bindv6
        if bindv6 != '0':
            raise ValueError('dual-stack prerequisite bindv6only=0 is unavailable')
        unused_port(False)
        unused_port(True)
        valgrind = shutil.which('valgrind')
        if not valgrind:
            raise ValueError('valgrind prerequisite unavailable')
        cases = filter_cases()
        write_new(root/'filter-cases.json', cases)
        script = root/'filter.php'
        script.write_text(filter_fixture(cases))
        for side in ('baseline', 'candidate'):
            variant = variants.DEFAULT if side == 'baseline' else VARIANT
            cli, fpm, source = (getattr(args, side+'_'+name).resolve() for name in ('cli','fpm','source'))
            for path in (getattr(args, side+'_cli'), getattr(args, side+'_fpm')):
                if path.is_symlink() or not path.is_file():
                    raise ValueError('regular trusted local test binaries required')
            identity = variants.verify_source(source, variant)
            build_dir = fpm.parent
            build = json.loads((build_dir/'build.json').read_text())
            if build['source_identity'] != identity or build['binaries'] != {'php': sources.sha256(cli), 'php-fpm': sources.sha256(fpm)}:
                raise ValueError('binary/build/source identity mismatch')
            header = build_dir/'objects/main/php_config.h'
            config = header.read_text()
            if not re.search(r'^#define HAVE_IPV6 1\s*$', config, re.M):
                raise ValueError('HAVE_IPV6 is not enabled in this build')
            report['inputs_before'][str(source)] = identity['normalized_source_sha256']
            directory = root/side
            directory.mkdir()
            (directory/'php_config.h').write_text(config)
            shutil.copyfile(build_dir/'build.json', directory/'build.json')
            observed = report[side]
            observed.update(source_identity=identity, cli_sha256=sources.sha256(cli), fpm_sha256=sources.sha256(fpm))
            version = command([cli, '-n', '-r', 'echo PHP_VERSION;'], directory, 'version', min(10,budget()))
            require_command(version)
            if not version['stdout'].startswith('7.0.33') or version['stderr']:
                raise ValueError('unexpected PHP version/diagnostic')
            specs = [('A1', '::1', False, True), ('A2', '::2', False, side == 'baseline'),
                     ('A3', '127.0.0.1', True, True), ('A4', '127.0.0.2', True, False),
                     ('A5', '2001:db8::1', False, False)]
            observed['acl'] = {}
            for label, allowed, dual, want in specs:
                observed['acl'][label] = acl_case(fpm, directory/label, allowed, dual, want, budget)
            output = command([cli, '-n', script], directory, 'filter-cli', min(20,budget()))
            require_command(output)
            if output['stderr']:
                raise ValueError('filter CLI diagnostic')
            observed['filter_cli'] = check_filter(cases, parse_filter_output(output['stdout']), side=='candidate')
            with fpm_instance(fpm, directory/'filter-fpm', '::1', False, script.read_text(), budget()) as (port, file):
                response = tcp_request(socket.AF_INET6, '::1', port, file, min(5,budget()))
                if response['stderr']:
                    raise ValueError('filter FPM stderr')
                observed['filter_fpm'] = check_filter(cases, parse_filter_output(response['body'].decode('ascii')), side=='candidate')
            logs = read_fpm_logs(directory/'filter-fpm')
            if re.search(r'PHP (?:Warning|Fatal|Parse|Notice)|\b(?:WARNING|ERROR|ALERT|EMERGENCY):', logs):
                raise ValueError('filter FPM diagnostic')
            fixture = sources.ROOT/'tests/fixtures/acl-filter-full-byte.phpt'
            observed['phpt'] = run_phpt(cli, source, directory/'phpt', fixture, budget)
            if side == 'candidate':
                require_command(observed['phpt']['new'])
                require_phpt_pass(observed['phpt']['new'], 1)
            xml = directory/'memcheck.xml'
            env = clean_env()
            env['USE_ZEND_ALLOC'] = '0'
            observed['memcheck_command'] = command([valgrind, '--tool=memcheck', '--leak-check=no', '--track-origins=yes',
                        '--num-callers=24', '--error-exitcode=86', '--xml=yes', '--xml-file='+str(xml), cli, '-n', script],
                        directory, 'memcheck', min(120,budget()), env)
            observation = observed['memcheck_command']
            if observation['timed_out'] or observation['forced_cleanup'] or observation['output_budget_exceeded'] or observation['returncode'] not in (0,86):
                raise ValueError('memcheck did not complete')
            observed['memcheck'] = memcheck_evidence(xml.read_text())
            observed['filter_valgrind'] = check_filter(cases, parse_filter_output(observation['stdout']), side=='candidate')
            if side == 'candidate' and (observed['memcheck']['all_errors'] or observation['returncode']):
                raise ValueError('candidate memcheck reported errors')
            if side == 'baseline' and observed['memcheck']['all_errors'] != observed['memcheck']['filter_uninitialized_errors']:
                raise ValueError('baseline memcheck has unrelated errors; do not conflate them')
            native = command([sys.executable, '-B', sources.ROOT/'scripts/native-check.py', '--fpm', fpm, '--cli', cli,
                              '--output', directory/'native-36.json'], directory, 'native-36', min(180,budget()))
            require_command(native)
            native_result = json.loads((directory/'native-36.json').read_text())
            if native_result['result'] != 'BENIGN_RUNTIME_PASS' or sum(len(c['checks']) for c in native_result['campaigns']) != 36:
                raise ValueError('existing 36 checks did not all pass')
            observed['native_checks'] = 36
            if sources.sha256(cli) != observed['cli_sha256'] or sources.sha256(fpm) != observed['fpm_sha256']:
                raise ValueError('binary changed during verification')
            if variants.verify_source(source,variant) != identity:
                raise ValueError('prepared source changed during verification')
        red = report['baseline']['memcheck']['filter_uninitialized_errors'] > 0
        report['filter_uninitialized_red'] = 'OBSERVED' if red else 'NOT_OBSERVED'
        report['result'] = 'LOCAL_RUNTIME_PASS' if red else 'PARTIAL_BASELINE_MEMCHECK_RED_NOT_OBSERVED'
    except Exception as error:
        report['error'] = type(error).__name__ + ': ' + str(error)
    finally:
        write_new(root/'result.json', report)
    print(json.dumps({'result': report['result'], 'error': report.get('error'), 'output': str(root)}))
    return 0 if report['result'] == 'LOCAL_RUNTIME_PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
