"""Local paired legacy worker-log checks; separate from the upstream FLUSH fix."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import platform
import pwd
import re
import shutil
import subprocess
import sys
import time
from . import advisory_runtime as common, fcgi, sources, variants
from .multipart_runtime import case_workspace

LOGS=('fpm.log','process.log','php.log')
CASES=(
    ('normal',b'normal-one\nnormal-two\n',False),
    ('nul',b'Pre\x00SecretTail\nNEXT\n',False),
    ('tail',b'Pre\x00SecretTail',True),
    ('backslash',b'literal\\x00\n%s %n %% "quote"\n',False),
    ('controls',b'Tab\tCR\rESC\x1bDEL\x7f\n',False),
    ('expansion',b'\x00'*1023+b'TAIL\nNEXT\n',False),
)

def encode(data):
    # Expected wire representation, not used to produce worker output.
    result=bytearray()
    for c in data:
        if c==10:continue
        if c==92:result.extend(b'\\\\')
        elif c<32 or c==127:result.extend(('\\x%02x'%c).encode())
        else:result.append(c)
    return bytes(result)

def check_payload(actual,token,payload,side,tail,kind):
    begin=('BEGIN:'+token).encode();end=('END:'+token).encode();barrier=('BARRIER:'+token).encode()
    if side=='candidate' or kind not in ('nul','tail','expansion'):
        content=encode(payload) if side=='candidate' else payload.replace(b'\n',b'')
        if actual!=begin+content+(b'' if tail else end)+barrier:raise ValueError('exact worker log payload mismatch')
        return
    if not actual.startswith(begin) or not actual.endswith(barrier):raise ValueError('parent loss missing independent request boundaries')
    middle=actual[len(begin):-len(barrier)]
    if kind=='tail':allowed=[b'Pre']
    elif kind=='nul':allowed=[b'Pre'+next_line+last for next_line in (b'',b'NEXT') for last in (b'',end)]
    else:allowed=[suffix+last for suffix in (b'',b'TAIL',b'NEXT',b'TAILNEXT') for last in (b'',end)]
    if middle not in allowed:raise ValueError('parent did not show only the known legacy NUL loss')

def log_payload(channels,pid,stream):
    if channels.get('fcgi',b''):raise ValueError('unexpected FastCGI stderr')
    out=bytearray();pattern=rb'^.*\bWARNING: \[pool proof\] child '+pid.encode()+rb' said into '+stream.encode()+rb': "(.*)"(?:, pipe is closed)?$'
    for name in LOGS:
        data=channels.get(name,b'');remaining=[]
        if data and not data.endswith(b'\n'):raise ValueError('incomplete diagnostic record')
        for line in data.split(b'\n')[:-1]:
            if len(line)+1>1024:raise ValueError('legacy final logger cap exceeded')
            match=re.fullmatch(pattern,line) if name=='fpm.log' else None
            if match:
                out.extend(match.group(1));continue
            if b'said into ' in line:raise ValueError('wrong worker/stream/unframed child diagnostic')
            allowed=rb'^.*\bNOTICE: (?:fpm is running, pid [0-9]+|ready to handle connections|Terminating \.\.\.|exiting, bye-bye!|systemd monitor interval set to [0-9]+ms|\[pool proof\] \'user\' directive is ignored when FPM is not running as root)$'
            if re.fullmatch(allowed,line):continue
            remaining.append(line)
        text=b'\n'.join(remaining).decode(errors='replace')
        if text:raise ValueError('unexpected startup/request/shutdown diagnostic')
    return bytes(out)

def snapshot(root):
    return {n:(root/n).read_bytes() if (root/n).exists() else b'' for n in LOGS}

def delta(now,previous):
    if any(not now[n].startswith(previous.get(n,b'')) for n in LOGS):raise ValueError('owned log truncated or rewritten')
    return {n:now[n][len(previous.get(n,b'')):] for n in LOGS}

def drain(root,marker,budget,process):
    deadline=time.monotonic()+min(10,budget());last=None;stable_since=None
    while True:
        if process.poll() is not None:raise ValueError('owned FPM exited while awaiting worker logs')
        now=snapshot(root);stamp=tuple(len(now[n]) for n in LOGS);moment=time.monotonic()
        if stamp!=last:last=stamp;stable_since=moment
        # Wait for visible request ownership plus a conditionally quiet window;
        # response completion alone is not proof that the master consumed pipes.
        if marker in now['fpm.log'] and moment-stable_since>=0.15:return now
        if moment>=deadline:raise TimeoutError('owned worker-log drain deadline')
        time.sleep(0.02)

def fixture_php():
    values=','.join("'%s'=>'%s'"%(name,payload.hex()) for name,payload,tail in CASES)
    tails=','.join("'%s'=>%s"%(name,'true' if tail else 'false') for name,payload,tail in CASES)
    return '''<?php
ob_start(); header('Content-Type: text/plain');
$cases=array(%s); $tails=array(%s);
$name=isset($_GET['case'])?$_GET['case']:'';
$stream=isset($_GET['stream'])?$_GET['stream']:'';
$trial=isset($_GET['trial'])?$_GET['trial']:'';
if(!isset($cases[$name]) || !in_array($stream,array('stdout','stderr'),true) || !in_array($trial,array('0','1'),true)){http_response_code(400);exit;}
$token=$name.'-'.$stream.'-'.$trial;
$file=fopen('php://'.$stream,'wb');
$barrier=isset($_GET['barrier']);
$bytes=$barrier?"\\nBARRIER:".$token."\\n":"BEGIN:".$token."\\n".hex2bin($cases[$name]).($tails[$name]?'':"\\nEND:".$token."\\n");
$n=fwrite($file,$bytes);fflush($file);fclose($file);
if($n!==strlen($bytes)){throw new Exception('incomplete synthetic stream write');}
echo 'PID=',getmypid(),"\\nTOKEN=",$token,"\\nCOMPLETE=yes\\n";
'''%(values,tails)

@contextmanager
def instance(binary,root,budget):
    root.mkdir();(root/'check.php').write_text(fixture_php())
    config='''[global]
error_log = {root}/fpm.log
daemonize = no
[proof]
listen = {root}/fpm.sock
pm = static
pm.max_children = 1
request_terminate_timeout = 10s
user = {user}
clear_env = yes
catch_workers_output = yes
php_admin_flag[display_errors] = off
php_admin_flag[log_errors] = on
php_admin_value[error_log] = {root}/php.log
'''.format(root=root,user=pwd.getpwuid(os.getuid()).pw_name)
    (root/'fpm.conf').write_text(config)
    command=[str(binary),'-n','-y',str(root/'fpm.conf'),'-F']+(['-R'] if os.getuid()==0 else [])
    with (root/'process.log').open('xb') as log:
        process=subprocess.Popen(command,env=common.clean_env(),stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
        try:
            end=time.monotonic()+min(12,budget())
            while not ((root/'fpm.sock').exists() and b'ready to handle connections' in snapshot(root)['fpm.log']):
                if process.poll() is not None:raise ValueError('owned FPM startup exit')
                if time.monotonic()>=end:raise TimeoutError('owned FPM startup deadline')
                time.sleep(0.03)
            yield process
        finally:
            before=process.poll();cleanup=common.stop_owned(process)
            common.write_new(root/'process.json',{'command':command,'before_stop':before,'returncode':process.returncode,**cleanup})
            common.require_fpm_exit(before,process.returncode,cleanup['forced_cleanup'])

def request(root,name,stream,trial,barrier,budget):
    query='case='+name+'&stream='+stream+'&trial='+str(trial)+('&barrier=1' if barrier else '')
    params={'REQUEST_METHOD':'GET','SCRIPT_FILENAME':str(root/'check.php'),'SCRIPT_NAME':'/check.php',
            'QUERY_STRING':query,'REQUEST_URI':'/check.php?'+query,'SERVER_PROTOCOL':'HTTP/1.1',
            'SERVER_NAME':'localhost','SERVER_PORT':'80','REMOTE_ADDR':'127.0.0.1','GATEWAY_INTERFACE':'CGI/1.1'}
    return fcgi.request(root/'fpm.sock',params,timeout=min(10,budget()))

def acknowledge(response,token):
    text=response['body'].decode('ascii');match=re.fullmatch(r'PID=([1-9][0-9]*)\nTOKEN='+re.escape(token)+r'\nCOMPLETE=yes\n',text)
    if not match or response['stderr']:raise ValueError('bad application acknowledgment/FastCGI stderr')
    return match.group(1)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for side in ('parent','candidate'):
        for name in ('cli','fpm','source'):parser.add_argument('--'+side+'-'+name,type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args(argv)
    root=common.new_run_directory(args.output);end=time.monotonic()+600
    def budget():
        left=end-time.monotonic()
        if left<=0:raise TimeoutError('whole legacy log campaign deadline')
        return left
    report={'schema':1,'result':'FAIL','production':'NOT_ACCESSED','syslog_transport':'NOT_RUN','parent':{},'candidate':{}}
    try:
        if platform.system()!='Linux':report['result']='NOT_RUN';raise ValueError('Linux runtime required')
        manifest=variants.manifest('fpm-log-20261114')
        for side in ('parent','candidate'):
            directory=root/side;directory.mkdir();variant='cookie-20261114' if side=='parent' else 'fpm-log-20261114'
            cli,fpm,source=[getattr(args,side+'_'+n).resolve() for n in ('cli','fpm','source')]
            for raw in [getattr(args,side+'_cli'),getattr(args,side+'_fpm')]:
                if raw.is_symlink() or not raw.is_file():raise ValueError('regular trusted binary required')
            identity=variants.verify_source(source,variant);source_hash=identity['normalized_source_sha256']
            binaries={'php':sources.sha256(cli),'php-fpm':sources.sha256(fpm)};build=json.loads((fpm.parent/'build.json').read_text())
            if build['variant']!=variant or build['source_identity']!=identity or build['binaries']!=binaries:raise ValueError('build/source/binary identity mismatch')
            common.write_new(directory/'build.json',build);observed=report[side];observed.update(source_sha256=source_hash,binaries=binaries,cases={})
            version=common.command([cli,'-n','-r','echo PHP_VERSION,":",PHP_INT_SIZE;'],directory,'version',min(10,budget()));common.require_command(version)
            if version['stderr'] or not re.fullmatch(r'7\.0\.33[^:]*:(4|8)',version['stdout']):raise ValueError('unexpected PHP version/diagnostic')
            for name,payload,tail in CASES:
              for stream in ('stdout','stderr'):
                output=directory/(name+'-'+stream);pids=[]
                with case_workspace(output) as work:
                  with instance(fpm,work,budget) as process:
                    previous={n:b'' for n in LOGS}
                    for trial in range(2):
                        token=name+'-'+stream+'-'+str(trial)
                        response=request(work,name,stream,trial,False,budget);pid=acknowledge(response,token);pids.append(pid)
                        (work/('response-'+str(trial)+'.bin')).write_bytes(response['body']);(work/('fcgi-'+str(trial)+'.bin')).write_bytes(response['stderr'])
                        drain(work,('BEGIN:'+token).encode(),budget,process)
                        barrier=request(work,name,stream,trial,True,budget)
                        if acknowledge(barrier,token)!=pid:raise ValueError('worker changed at log barrier')
                        (work/('barrier-'+str(trial)+'.bin')).write_bytes(barrier['body'])
                        now=drain(work,('BARRIER:'+token).encode(),budget,process);channels=delta(now,previous);previous=now
                        for channel,data in channels.items():(work/(str(trial)+'-'+channel)).write_bytes(data)
                        actual=log_payload(channels,pid,stream);check_payload(actual,token,payload,side,tail,name)
                        common.write_new(work/('trial-'+str(trial)+'.json'),{'token':token,'worker':pid,'input_hex':payload.hex(),'logged_hex':actual.hex(),'result':'KNOWN_LEGACY_LOSS' if side=='parent' and name in ('nul','tail','expansion') else 'BYTES_VERIFIED'})
                    if len(set(pids))!=1:raise ValueError('worker changed across repetitions')
                  shutdown=delta(snapshot(work),previous)
                  for channel,data in shutdown.items():(work/('shutdown-'+channel)).write_bytes(data)
                  if log_payload(shutdown,pids[0],stream):raise ValueError('unexpected post-request child output')
                observed['cases'][name+'-'+stream]='KNOWN_LEGACY_LOSS' if side=='parent' and name in ('nul','tail','expansion') else 'BYTES_VERIFIED'
            phpt=directory/'phpt';phpt.mkdir();fixture=phpt/'fpm-log-producer.phpt';shutil.copyfile(sources.ROOT/'tests/fixtures/fpm-log-producer.phpt',fixture)
            env=common.clean_env();env.update(TEST_PHP_EXECUTABLE=str(cli),NO_INTERACTION='1',REPORT_EXIT_STATUS='1',TERM='dumb')
            check=common.command([cli,'-n',source/'run-tests.php','-n','-q',fixture],phpt,'phpt',min(120,budget()),env)
            common.require_command(check);common.require_phpt_pass(check,1)
            normal=common.command([sys.executable,'-B',sources.ROOT/'scripts/native-check.py','--fpm',fpm,'--cli',cli,'--output',directory/'native-36.json'],directory,'native-36',min(180,budget()));common.require_command(normal)
            benign=json.loads((directory/'native-36.json').read_text())
            if benign['result']!='BENIGN_RUNTIME_PASS' or sum(len(c['checks']) for c in benign['campaigns'])!=36:raise ValueError('existing 36 checks failed')
            if variants.verify_source(source,variant)!=identity or {k:sources.sha256(cli if k=='php' else fpm) for k in binaries}!=binaries:raise ValueError('input changed during campaign')
        report['result']='PAIRED_LEGACY_LOG_RUNTIME_PASS'
    except Exception as error:report['error']=type(error).__name__+': '+str(error)
    finally:common.write_new(root/'result.json',report)
    print(json.dumps({'result':report['result'],'error':report.get('error')}));return int(report['result']!='PAIRED_LEGACY_LOG_RUNTIME_PASS')
