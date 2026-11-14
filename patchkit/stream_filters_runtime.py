"""Pinned paired Linux stream-filter checks with explicit memory and codec gates."""
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
import xml.etree.ElementTree as ET
from . import advisory_runtime as common, fcgi, sources, variants
from .cookie_runtime import log_delta, require_quiet
from .multipart_runtime import case_workspace

PROBE='''<?php
// Close the synthetic stream without inspecting or displaying converted bytes.
$stream=fopen('php://temp','w+b');
$filter=stream_filter_append($stream,'convert.base64-encode',STREAM_FILTER_WRITE,
    array('line-length'=>4,'line-break-chars'=>"\\0X"));
fwrite($stream,'AAAAAA');stream_filter_remove($filter);fclose($stream);
echo "PROBE_COMPLETE\\n";
'''

def fixture(path):
    text=Path(path).read_text();match=re.fullmatch(r'--TEST--\n.+?\n--FILE--\n(.*?)--EXPECT--\n(.*)',text,re.S)
    if not match or not match.group(1).startswith('<?php'):raise ValueError('invalid literal PHPT sections')
    result={}
    for line in match.group(2).splitlines():
        key,separator,value=line.partition('=')
        if not separator or key in result:raise ValueError('invalid/duplicate literal expectation')
        result[key]=value
    if result.pop('COMPLETE',None)!='yes' or not result or any(not re.fullmatch(r'[a-z0-9-]+',k) or not re.fullmatch(r'(?:[0-9a-f]{2})*',v) for k,v in result.items()):raise ValueError('invalid codec expectation/completion')
    return match.group(1),result

def check_frame(text,want):
    result={}
    for line in text.splitlines():
        key,sep,value=line.partition('=')
        if not sep or key in result:raise ValueError('malformed/duplicate response')
        result[key]=value
    pid=result.get('PID','')
    if not re.fullmatch(r'[1-9][0-9]*',pid) or result!={**want,'PID':pid,'COMPLETE':'yes'}:raise ValueError('exact codec response/worker completion mismatch')
    return pid

def require_pending_red(record,output):
    if record['returncode']!=1 or record['timed_out'] or record['forced_cleanup'] or record['output_budget_exceeded'] or record['stderr'] or common.phpt_statuses(record['stdout'])!=['FAIL'] or output.strip()!=b'410a42':raise ValueError('parent pending PHPT did not show the exact known CR/LF split error')

def require_memory(record,xml,side):
    if record['timed_out'] or record['forced_cleanup'] or record['output_budget_exceeded'] or record['stderr'] or record['stdout']!='PROBE_COMPLETE\n':raise ValueError('memory-checker command/producer did not complete cleanly')
    root=ET.fromstring(xml)
    if root.tag!='valgrindoutput':raise ValueError('not a Valgrind XML report')
    errors=root.findall('error')
    if side=='candidate':
        if record['returncode']!=0 or errors:raise ValueError('candidate memory diagnostics')
    else:
        if record['returncode']!=97 or not errors:raise ValueError('missing target memory RED')
        for error in errors:
            frames=[frame.findtext('fn','') for frame in error.findall('./stack/frame')]
            if error.findtext('kind')!='InvalidRead' or not any(fn.startswith('php_conv_base64_encode_convert') for fn in frames) or not any('block of size 1 ' in value for value in error.itertext()):raise ValueError('unrelated memory diagnostic cannot supply target RED')

@contextmanager
def instance(binary,root,script,budget):
    root.mkdir();(root/'check.php').write_text(script)
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
            while not ((root/'fpm.sock').exists() and 'ready to handle connections' in common.read_fpm_logs(root)):
                if process.poll() is not None:raise ValueError('owned FPM startup exit')
                if time.monotonic()>=end:raise TimeoutError('owned FPM startup deadline')
                time.sleep(.03)
            yield
        finally:
            before=process.poll();cleanup=common.stop_owned(process)
            common.write_new(root/'process.json',{'command':command,'before_stop':before,'returncode':process.returncode,**cleanup})
            common.require_fpm_exit(before,process.returncode,cleanup['forced_cleanup'])

def request(root,budget):
    params={'REQUEST_METHOD':'GET','SCRIPT_FILENAME':str(root/'check.php'),'SCRIPT_NAME':'/check.php',
            'QUERY_STRING':'','REQUEST_URI':'/check.php','SERVER_PROTOCOL':'HTTP/1.1',
            'SERVER_NAME':'localhost','SERVER_PORT':'80','REMOTE_ADDR':'127.0.0.1','GATEWAY_INTERFACE':'CGI/1.1'}
    return fcgi.request(root/'fpm.sock',params,timeout=min(10,budget()))

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for side in ('parent','candidate'):
        for name in ('cli','fpm','source'):parser.add_argument('--'+side+'-'+name,type=Path,required=True)
    parser.add_argument('--valgrind',type=Path);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args(argv)
    root=common.new_run_directory(args.output);end=time.monotonic()+600
    def budget():
        remaining=end-time.monotonic()
        if remaining<=0:raise TimeoutError('whole stream-filter campaign deadline')
        return remaining
    report={'schema':1,'result':'FAIL','production':'NOT_ACCESSED','parent':{},'candidate':{}}
    try:
        if platform.system()!='Linux':report['result']='NOT_RUN';raise ValueError('Linux runtime required')
        valgrind=args.valgrind or shutil.which('valgrind')
        if not valgrind:report['result']='NOT_RUN';raise ValueError('Valgrind required for actual NUL-option memory differential')
        valgrind=Path(valgrind).resolve()
        if not valgrind.is_file():raise ValueError('Valgrind executable missing')
        version=common.command([valgrind,'--version'],root,'valgrind-version',min(10,budget()));common.require_command(version)
        if not version['stdout'].startswith('valgrind-') or version['stderr']:raise ValueError('unexpected memory checker identity')
        report['memory_checker']={'path':str(valgrind),'sha256':sources.sha256(valgrind),'version':version['stdout'].strip()}
        variants.manifest('stream-filters-20261115')
        template,want=fixture(sources.ROOT/'tests/fixtures/stream-filters-normal.phpt')
        app=template.replace('<?php\n','<?php\nob_start();header(\'Content-Type: text/plain\');echo \'PID=\',getmypid(),"\\n";\n',1)
        for side in ('parent','candidate'):
            directory=root/side;directory.mkdir();variant='fpm-log-20261114' if side=='parent' else 'stream-filters-20261115'
            cli,fpm,source=[getattr(args,side+'_'+name).resolve() for name in ('cli','fpm','source')]
            for raw in [getattr(args,side+'_cli'),getattr(args,side+'_fpm')]:
                if raw.is_symlink() or not raw.is_file():raise ValueError('regular trusted binaries required')
            identity=variants.verify_source(source,variant);binaries={'php':sources.sha256(cli),'php-fpm':sources.sha256(fpm)}
            build=json.loads((fpm.parent/'build.json').read_text())
            if build['variant']!=variant or build['source_identity']!=identity or build['binaries']!=binaries:raise ValueError('source/build/binary identity mismatch')
            common.write_new(directory/'build.json',build);observed=report[side];observed.update(source_identity=identity,binaries=binaries)
            version=common.command([cli,'-n','-r','echo PHP_VERSION,":",PHP_INT_SIZE;'],directory,'version',min(10,budget()));common.require_command(version)
            if version['stderr'] or not re.fullmatch(r'7\.0\.33[^:]*:(4|8)',version['stdout']):raise ValueError('unexpected PHP version/diagnostic')
            probe=directory/'memory-probe.php';probe.write_text(PROBE);xml=directory/'valgrind.xml'
            env=common.clean_env();env['USE_ZEND_ALLOC']='0'
            memory=common.command([valgrind,'--quiet','--xml=yes','--xml-file='+str(xml),'--error-exitcode=97','--leak-check=no',cli,'-n',probe],directory,'memory-probe',min(90,budget()),env)
            require_memory(memory,xml.read_text(),side);observed['nul_option_memory']='TARGET_INVALID_READ' if side=='parent' else 'NO_MEMORY_ERRORS'
            phpts=['normal','pending']+(['binary'] if side=='candidate' else [])
            for name in phpts:
                work=directory/('phpt-'+name);work.mkdir();path=work/('stream-filters-'+name+'.phpt');shutil.copyfile(sources.ROOT/'tests/fixtures'/path.name,path)
                env=common.clean_env();env.update(TEST_PHP_EXECUTABLE=str(cli),NO_INTERACTION='1',REPORT_EXIT_STATUS='1',TERM='dumb')
                checked=common.command([cli,'-n',source/'run-tests.php','-n','-q',path],work,'phpt',min(120,budget()),env)
                if side=='parent' and name=='pending':require_pending_red(checked,path.with_suffix('.out').read_bytes())
                else:common.require_command(checked);common.require_phpt_pass(checked,1)
                observed['phpt_'+name]='KNOWN_SPLIT_RED' if side=='parent' and name=='pending' else 'PASS'
            offsets={};pids=[];output=directory/'fpm'
            with case_workspace(output) as work:
                with instance(fpm,work,app,budget):
                    for trial in range(2):
                        response=request(work,budget);(work/('response-'+str(trial)+'.bin')).write_bytes(response['body']);(work/('stderr-'+str(trial)+'.bin')).write_bytes(response['stderr'])
                        pids.append(check_frame(response['body'].decode('ascii'),want));channels=log_delta(work,offsets);channels['fcgi']=response['stderr'].decode(errors='replace')
                        common.write_new(work/('diagnostics-'+str(trial)+'.json'),channels);require_quiet(channels)
                if len(set(pids))!=1:raise ValueError('worker changed across normal codec repetitions')
                channels=log_delta(work,offsets);common.write_new(work/'shutdown-diagnostics.json',channels);require_quiet(channels)
                require_quiet({name:(work/name).read_text(errors='replace') if (work/name).exists() else '' for name in ('php.log','fpm.log','process.log')})
            observed['fpm_normal']='NORMAL_CODEC_PASS'
            normal=common.command([sys.executable,'-B',sources.ROOT/'scripts/native-check.py','--fpm',fpm,'--cli',cli,'--output',directory/'native-36.json'],directory,'native-36',min(180,budget()));common.require_command(normal)
            benign=json.loads((directory/'native-36.json').read_text())
            if benign['result']!='BENIGN_RUNTIME_PASS' or sum(len(c['checks']) for c in benign['campaigns'])!=36:raise ValueError('existing normal36 regression failed')
            if variants.verify_source(source,variant)!=identity or {k:sources.sha256(cli if k=='php' else fpm) for k in binaries}!=binaries:raise ValueError('inputs changed during campaign')
        report['result']='PAIRED_STREAM_FILTERS_RUNTIME_PASS'
    except Exception as error:report['error']=type(error).__name__+': '+str(error)
    finally:common.write_new(root/'result.json',report)
    print(json.dumps({'result':report['result'],'error':report.get('error')}));return int(report['result']!='PAIRED_STREAM_FILTERS_RUNTIME_PASS')
