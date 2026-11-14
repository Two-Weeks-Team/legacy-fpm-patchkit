"""Paired local PHP/FPM checks for synthetic cookie normalization fixtures."""
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

from . import advisory_runtime as common, fcgi, sources
from .multipart_runtime import case_workspace
from .cookie_cases import cases, flatten

PROVENANCE_SHA256='73fe27ba703a6770b5e3959e4c76ef72580609eb809ed02743aa9c2c9f0e7629'
LOGS=('php.log','fpm.log','process.log')
PHP_FUNCTION=r'''
function emit_tree($kind,$values,$prefix='') {
    foreach($values as $key=>$value) {
        $segment=is_int($key)?'I'.$key:'S'.bin2hex($key);
        $path=$prefix===''?$segment:$prefix.'/'.$segment;
        echo $kind,'|',$path,'=',is_array($value)?'A':'V'.bin2hex($value),"\n";
        if(is_array($value)){emit_tree($kind,$value,$path);}
    }
}
'''
# No session is opened and no real account/session cookies are supplied.
FPM_PHP="<?php\nob_start();\nheader('Content-Type: text/plain');\n"+PHP_FUNCTION+"echo 'PID=',getmypid(),\"\\n\";\nemit_tree('C',$_COOKIE);emit_tree('G',$_GET);emit_tree('P',$_POST);\necho \"COMPLETE=yes\\n\";\n"


def check_response(text,want):
    values={}
    for line in text.splitlines():
        if '=' not in line:raise ValueError('malformed fixture response')
        key,value=line.split('=',1)
        if key in values:raise ValueError('duplicate fixture response record')
        values[key]=value
    pid=values.get('PID','')
    if not re.fullmatch(r'[1-9][0-9]*',pid) or values.get('COMPLETE')!='yes':
        raise ValueError('missing worker identity or completion marker')
    expected={'PID':pid,'COMPLETE':'yes'}
    for kind in ('C','G','P'):
        expected.update({kind+'|'+key:value for key,value in flatten(want[kind]).items()})
    if values!=expected:raise ValueError('cookie/GET/POST map differs from exact literal fixture expectation')
    return pid


def log_delta(root,offsets):
    result={}
    for name in LOGS:
        data=(root/name).read_bytes() if (root/name).exists() else b''
        previous=offsets.get(name,0)
        if len(data)<previous:raise ValueError('owned diagnostic log was truncated')
        result[name]=data[previous:].decode(errors='replace')
        offsets[name]=len(data)
    return result


def require_quiet(channels):
    if channels.get('fcgi',''):raise ValueError('unexpected FastCGI stderr')
    for text in channels.values():
        if re.search(r'(?:PHP )?(?:Warning|Fatal|Parse|Notice|Deprecated)|\b(?:WARNING|ERROR|ALERT|EMERGENCY):',text):
            raise ValueError('unexpected request/startup/shutdown diagnostic')


def require_parent_phpt(run):
    if run['timed_out'] or run['forced_cleanup'] or run['output_budget_exceeded'] or run['stderr'] or run['returncode']!=1 or common.phpt_statuses(run['stdout'])!=['FAIL']:
        raise ValueError('parent PHPT did not produce exactly the clean expected FAIL')


def php_literal(value):
    return "'"+value.replace('\\','\\\\').replace("'","\\'")+"'"


def cli_fixture():
    script='<?php\n'+PHP_FUNCTION
    for case in cases():
        script+='echo '+php_literal('BEGIN='+case['name'])+',"\\n";\n'
        script+='parse_str('+php_literal(case['form'])+',$values);emit_tree(\'G\',$values);\n'
        script+='echo '+php_literal('END='+case['name'])+',"\\n";\n'
    return script


def check_cli(text,side):
    actual={};active=None
    for line in text.splitlines():
        key,sep,value=line.partition('=')
        if not sep:raise ValueError('malformed CLI fixture output')
        if key=='BEGIN':
            if active is not None or value in actual:raise ValueError('duplicate/interleaved CLI case')
            active=value;actual[active]={}
        elif key=='END':
            if active!=value:raise ValueError('CLI case completion mismatch')
            active=None
        else:
            if active is None or not key.startswith('G|') or key in actual[active]:raise ValueError('malformed/duplicate CLI map record')
            actual[active][key]=value
    if active is not None or set(actual)!={c['name'] for c in cases()}:raise ValueError('incomplete CLI cases')
    for case in cases():
        expected={'G|'+k:v for k,v in flatten(case[side]['G']).items()}
        if actual[case['name']]!=expected:raise ValueError('CLI literal map mismatch: '+case['name'])
    return actual


@contextmanager
def instance(binary,root,budget):
    root.mkdir();(root/'check.php').write_text(FPM_PHP)
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
php_admin_value[variables_order] = GPCS
'''.format(root=root,user=pwd.getpwuid(os.getuid()).pw_name)
    (root/'fpm.conf').write_text(config)
    command=[str(binary),'-n','-y',str(root/'fpm.conf'),'-F']+(['-R'] if os.getuid()==0 else [])
    with (root/'process.log').open('xb') as log:
        p=subprocess.Popen(command,env=common.clean_env(),stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
        try:
            end=time.monotonic()+min(12,budget())
            while True:
                if p.poll() is not None:raise ValueError('owned FPM exited during startup')
                logs=common.read_fpm_logs(root)
                if (root/'fpm.sock').exists() and 'ready to handle connections' in logs:break
                if time.monotonic()>=end:raise TimeoutError('owned FPM startup deadline')
                time.sleep(.03)
            yield
        finally:
            before=p.poll();cleanup=common.stop_owned(p)
            common.write_new(root/'process.json',{'command':command,'before_stop':before,'returncode':p.returncode,**cleanup})
            common.require_fpm_exit(before,p.returncode,cleanup['forced_cleanup'])


def request(root,case,budget):
    data=case['form'].encode()
    params={'REQUEST_METHOD':'POST','SCRIPT_FILENAME':str(root/'check.php'),'SCRIPT_NAME':'/check.php',
            'QUERY_STRING':case['form'],'REQUEST_URI':'/check.php?'+case['form'],'SERVER_PROTOCOL':'HTTP/1.1',
            'SERVER_NAME':'localhost','SERVER_PORT':'80','REMOTE_ADDR':'127.0.0.1','GATEWAY_INTERFACE':'CGI/1.1',
            'CONTENT_TYPE':'application/x-www-form-urlencoded','CONTENT_LENGTH':str(len(data)),'HTTP_COOKIE':case['cookie']}
    return fcgi.request(root/'fpm.sock',params,data,timeout=min(10,budget()))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for side in ('parent','candidate'):
        for name in ('cli','fpm','source'):parser.add_argument('--'+side+'-'+name,type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv);root=common.new_run_directory(args.output);end=time.monotonic()+600
    def budget():
        left=end-time.monotonic()
        if left<=0:raise TimeoutError('whole cookie campaign deadline')
        return left
    report={'schema':1,'result':'FAIL','production':'NOT_ACCESSED','parent':{},'candidate':{}}
    try:
        if platform.system()!='Linux':report['result']='NOT_RUN';raise ValueError('Linux runtime required')
        provenance=sources.ROOT/'provenance/variants/cookie-20261114.json'
        sources.verify_file(provenance,PROVENANCE_SHA256);manifest=json.loads(provenance.read_text())
        script=root/'cli.php';script.write_text(cli_fixture())
        for side in ('parent','candidate'):
            directory=root/side;directory.mkdir()
            cli,fpm,source=[getattr(args,side+'_'+name).resolve() for name in ('cli','fpm','source')]
            for raw in (getattr(args,side+'_cli'),getattr(args,side+'_fpm')):
                if raw.is_symlink() or not raw.is_file():raise ValueError('regular trusted binaries required')
            source_hash=sources.tree_digest(source,normalized=True)
            if source_hash!=manifest['baseline_source_sha256' if side=='parent' else 'candidate_source_sha256']:raise ValueError('whole source identity mismatch')
            binaries={'php':sources.sha256(cli),'php-fpm':sources.sha256(fpm)}
            build=json.loads((fpm.parent/'build.json').read_text())
            if build['normalized_source_sha256']!=source_hash or build['binaries']!=binaries:raise ValueError('build/binary/source identity mismatch')
            common.write_new(directory/'build.json',build)
            version=common.command([cli,'-n','-r','echo PHP_VERSION,":",PHP_INT_SIZE;'],directory,'version',min(10,budget()))
            common.require_command(version)
            if not re.fullmatch(r'7\.0\.33[^:]*:(4|8)',version['stdout']) or version['stderr']:raise ValueError('unexpected PHP version/diagnostic')
            observed=report[side];observed.update(source_sha256=source_hash,binaries=binaries,cases={})
            run=common.command([cli,'-n',script],directory,'cli-cases',min(20,budget()));common.require_command(run)
            if run['stderr']:raise ValueError('CLI diagnostics')
            observed['cli']=check_cli(run['stdout'],side)
            for case in cases():
                output=directory/case['name'];offsets={};responses=[];whole={}
                with case_workspace(output) as work:
                    with instance(fpm,work,budget):
                        common.write_new(work/'fixture.json',case)
                        for trial in range(2):
                            response=request(work,case,budget);text=response['body'].decode('ascii')
                            (work/('response-'+str(trial)+'.txt')).write_text(text)
                            errors=response['stderr'].decode(errors='replace');(work/('stderr-'+str(trial)+'.txt')).write_text(errors)
                            pid=check_response(text,case[side]);responses.append(pid)
                            channels=log_delta(work,offsets);channels['fcgi']=errors
                            common.write_new(work/('diagnostics-'+str(trial)+'.json'),channels);require_quiet(channels)
                    if responses[0]!=responses[1]:raise ValueError('worker changed during repeat')
                shutdown=log_delta(output,offsets)
                common.write_new(output/'shutdown-diagnostics.json',shutdown);require_quiet(shutdown)
                for name in LOGS:
                    whole[name]=(output/name).read_text(errors='replace') if (output/name).exists() else ''
                require_quiet(whole)
                observed['cases'][case['name']]='PASS'
            phpt=directory/'phpt';phpt.mkdir();fixture=phpt/'cookie-normalization.phpt'
            shutil.copyfile(sources.ROOT/'tests/fixtures/cookie-normalization.phpt',fixture)
            env=common.clean_env();env.update(TEST_PHP_EXECUTABLE=str(cli),NO_INTERACTION='1',REPORT_EXIT_STATUS='1',TERM='dumb')
            check=common.command([cli,'-n',source/'run-tests.php','-n','-q',fixture],phpt,'phpt',min(120,budget()),env)
            if side=='candidate':common.require_command(check);common.require_phpt_pass(check,1)
            else:require_parent_phpt(check)
            normal=common.command([sys.executable,'-B',sources.ROOT/'scripts/native-check.py','--fpm',fpm,'--cli',cli,'--output',directory/'native-36.json'],directory,'native-36',min(180,budget()))
            common.require_command(normal);result=json.loads((directory/'native-36.json').read_text())
            if result['result']!='BENIGN_RUNTIME_PASS' or sum(len(c['checks']) for c in result['campaigns'])!=36:raise ValueError('existing 36-check regression failed')
            if sources.tree_digest(source,normalized=True)!=source_hash or {k:sources.sha256(cli if k=='php' else fpm) for k in binaries}!=binaries:raise ValueError('source/binary changed during campaign')
        report['result']='PAIRED_COOKIE_RUNTIME_PASS'
    except Exception as error:report['error']=type(error).__name__+': '+str(error)
    finally:common.write_new(root/'result.json',report)
    print(json.dumps({'result':report['result'],'error':report.get('error')}))
    return 0 if report['result']=='PAIRED_COOKIE_RUNTIME_PASS' else 1
