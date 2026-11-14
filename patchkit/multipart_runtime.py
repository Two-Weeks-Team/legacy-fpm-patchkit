"""Small paired multipart fixtures for freshly built parent/candidate Linux FPM."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import platform
import pwd
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

from . import advisory_runtime as common, fcgi, sources

VARIANT='multipart-20261114'
PROVENANCE_SHA256='ceb74f54416dd9d4ffe3f668e5c1b7651565d7d7ac0bf69e6d17640a8e1ad2f4'
FILE_BYTES=b'ordinary-file\n\x00\xff'
PHP=r'''<?php
ob_start();
header('Content-Type: text/plain');
echo 'PID=',getmypid(),"\nLIMIT=",ini_get('max_multipart_body_parts'),"\n";
foreach($_POST as $key=>$value){echo 'POST:',$key,'=',bin2hex($value),"\n";}
foreach($_FILES as $key=>$file){
    $data=$file['error']===UPLOAD_ERR_OK ? file_get_contents($file['tmp_name']) : '';
    echo 'FILE:',$key,'=',$file['error'],',',$file['size'],',',hash('sha256',$data),"\n";
}
if(!session_start()){echo "SESSION=failed\n";}
echo 'PROGRESS=',isset($_SESSION['upload_progress_proof'])?'1':'0',"\n";
session_write_close();
echo "COMPLETE=yes\n";
'''


def field(name,value):return {'name':name,'data':value,'file':False}
def upload(name):return {'name':name,'data':FILE_BYTES,'file':True}


def expected(parts,limit):
    post={p['name']:p['data'].hex() for p in parts if not p['file']}
    files={p['name']:'0,%d,%s'%(len(p['data']),hashlib.sha256(p['data']).hexdigest()) for p in parts if p['file']}
    return {'post':post,'files':files,'limit':limit}


def cases():
    a,b,c=field('a',b'A'),field('b',b'B'),field('c',b'C')
    u,v=upload('u'),upload('v')
    rows=[]
    def add(name,parts,limit='3',vars='20',files='20',parent_parts=None,child_parts=None,parent_warnings=None,child_warnings=None,boundary=None,progress='On',uploads='On'):
        rows.append({'name':name,'parts':parts,'ini':{'max_multipart_body_parts':limit,'max_input_vars':vars,'max_file_uploads':files,'session.upload_progress.enabled':progress,'file_uploads':uploads},
            'parent':expected(parts if parent_parts is None else parent_parts,''),
            'candidate':expected(parts if child_parts is None else child_parts,limit),
            'parent_warnings':parent_warnings or {},'candidate_warnings':child_warnings or {},
            'boundary':boundary or 'ordinary-boundary'})
    add('parts-three',[a,u,b])
    add('parts-four',[a,u,b,c],child_parts=[a,u,b],child_warnings={'parts':1})
    add('parts-zero',[a],limit='0',child_parts=[],child_warnings={'parts':1})
    add('default-sum',[a,u,b,c],limit='-1',vars='2',files='1',parent_parts=[a,u,b],child_parts=[a,u,b],parent_warnings={'input':1},child_warnings={'parts':1})
    add('negative-default',[a,u,b,c],limit='-2',vars='2',files='1',parent_parts=[a,u,b],child_parts=[a,u,b],parent_warnings={'input':1},child_warnings={'parts':1})
    add('default-overflow',[a,u,b,c],limit='-1',vars='9223372036854775807',files='1')
    add('file-limit-preserved',[u,v,a],limit='6',files='1',parent_parts=[u,a],child_parts=[u,a],parent_warnings={'file':1},child_warnings={'file':1})
    add('variable-limit-preserved',[a,b,c],limit='6',vars='2',parent_parts=[a,b],child_parts=[a,b],parent_warnings={'input':1},child_warnings={'input':1})
    add('disabled-files-still-count',[u,a,b,c],uploads='Off',parent_parts=[a,b,c],child_parts=[a,b],child_warnings={'parts':1})
    progress=field('PHP_SESSION_UPLOAD_PROGRESS',b'proof')
    for enabled in ('On','Off'):
        add('progress-'+enabled.lower(),[progress,u,a,b],parent_parts=[progress,u,a,b],child_parts=[progress,u,a],child_warnings={'parts':1},progress=enabled)
    for n in (5115,5116,5117):
        add({5115:'boundary-below-cap',5116:'boundary-cap',5117:'boundary-over-cap'}[n],[a,u],limit='6',boundary='b'*n,
            child_parts=[] if n==5117 else [a,u],child_warnings={'boundary':1} if n==5117 else {})
    add('buffer-split',[field('a',b'X'*6144),u],limit='6')
    return rows


def body(case):
    out=bytearray();boundary=case['boundary'].encode()
    for p in case['parts']:
        out.extend(b'--'+boundary+b'\r\nContent-Disposition: form-data; name="'+p['name'].encode()+b'"')
        out.extend(b'; filename="sample.txt"\r\nContent-Type: text/plain' if p['file'] else b'')
        out.extend(b'\r\n\r\n'+p['data']+b'\r\n')
    return bytes(out+b'--'+boundary+b'--\r\n')


WARNING_PATTERNS={'parts':r'Multipart body parts limit exceeded [-0-9]+\.',
                  'boundary':r'Boundary too large in multipart/form-data POST data',
                  'input':r'Input variables exceeded [0-9]+\.',
                  'file':r'Maximum number of allowable file uploads has been exceeded'}


def check_warnings(channels,want):
    counts={kind:max([len(re.findall(pattern,text)) for text in channels.values()] or [0]) for kind,pattern in WARNING_PATTERNS.items()}
    if {k:v for k,v in counts.items() if v}!=want:
        raise ValueError('warning count mismatch: '+repr(counts)+' expected '+repr(want))
    for text in channels.values():
        for line in text.splitlines():
            if re.search(r'(?:PHP )?(?:Warning|Fatal|Parse|Notice|Deprecated)|\b(?:WARNING|ERROR|ALERT|EMERGENCY):',line):
                if not any(re.search(pattern,line) for pattern in WARNING_PATTERNS.values()):
                    raise ValueError('unexpected diagnostic: '+line)
    return counts


def check_response(text,want):
    values={}
    for line in text.splitlines():
        if '=' not in line:raise ValueError('malformed response')
        key,value=line.split('=',1)
        if key in values:raise ValueError('duplicate response record')
        values[key]=value
    if values.get('COMPLETE')!='yes' or values.get('PROGRESS')!='0' or not re.fullmatch(r'[1-9][0-9]*',values.get('PID','')):
        raise ValueError('incomplete response or upload-progress state remained')
    expected_values={'LIMIT':want['limit'],'PROGRESS':'0','COMPLETE':'yes','PID':values['PID']}
    expected_values.update({'POST:'+k:v for k,v in want['post'].items()})
    expected_values.update({'FILE:'+k:v for k,v in want['files'].items()})
    if values!=expected_values:raise ValueError('field/file/INI output differs from the fixture expectation')
    return values


def require_parent_phpt(run):
    if run['timed_out'] or run['forced_cleanup'] or run['output_budget_exceeded'] or run['stderr'] or run['returncode']!=1 or common.phpt_statuses(run['stdout'])!=['FAIL','FAIL']:
        raise ValueError('parent registration controls did not complete as exactly two clean expected failures')


@contextmanager
def case_workspace(output):
    # Long CI checkout/evidence paths exceed sockaddr_un.sun_path. Keep only
    # the owned socket/process workspace short and always copy its evidence out.
    with tempfile.TemporaryDirectory(prefix='pkmp-',dir='/tmp') as temporary:
        work=Path(temporary)/'case'
        try:yield work
        finally:
            if work.exists():shutil.copytree(work,output,ignore=shutil.ignore_patterns('fpm.sock'))


@contextmanager
def instance(binary,root,case,budget,candidate):
    root.mkdir();(root/'uploads').mkdir();(root/'sessions').mkdir()
    (root/'check.php').write_text(PHP)
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
php_admin_value[upload_tmp_dir] = {root}/uploads
php_admin_value[session.save_path] = {root}/sessions
php_admin_flag[session.upload_progress.cleanup] = on
'''.format(root=root,user=pwd.getpwuid(os.getuid()).pw_name)
    for name,value in case['ini'].items():
        if name=='max_multipart_body_parts' and not candidate:continue
        config+='php_admin_value['+name+'] = '+value+'\n'
    (root/'fpm.conf').write_text(config)
    argv=[str(binary),'-n','-y',str(root/'fpm.conf'),'-F']+(['-R'] if os.getuid()==0 else [])
    with (root/'process.log').open('xb') as log:
        process=subprocess.Popen(argv,env=common.clean_env(),stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
        try:
            end=time.monotonic()+min(12,budget())
            while not (root/'fpm.sock').exists():
                if process.poll() is not None or time.monotonic()>=end:raise ValueError('owned FPM did not start')
                time.sleep(.03)
            yield
        finally:
            before=process.poll();cleanup=common.stop_owned(process)
            common.write_new(root/'process.json',{'command':argv,'before_stop':before,'returncode':process.returncode,**cleanup})
            common.require_fpm_exit(before,process.returncode,cleanup['forced_cleanup'])


def request(socket_path,script,case,sid,budget):
    data=body(case)
    values={'REQUEST_METHOD':'POST','SCRIPT_FILENAME':str(script),'SCRIPT_NAME':'/check.php',
        'QUERY_STRING':'','REQUEST_URI':'/check.php','SERVER_PROTOCOL':'HTTP/1.1','SERVER_NAME':'localhost',
        'SERVER_PORT':'80','REMOTE_ADDR':'127.0.0.1','GATEWAY_INTERFACE':'CGI/1.1','CONTENT_LENGTH':str(len(data)),
        'CONTENT_TYPE':'multipart/form-data; boundary='+case['boundary'],'HTTP_COOKIE':'PHPSESSID='+sid}
    # Reuse the reviewed bounded Unix FastCGI transport; internal FILLUNIT
    # splits occur even though each small request fits in one STDIN record.
    return fcgi.request(socket_path,values,data,timeout=min(10,budget()))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for side in ('parent','candidate'):
        for name in ('cli','fpm','source'):parser.add_argument('--'+side+'-'+name,type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv);root=common.new_run_directory(args.output)
    end=time.monotonic()+600
    def budget():
        value=end-time.monotonic()
        if value<=0:raise TimeoutError('whole multipart campaign deadline exceeded')
        return value
    report={'schema':1,'result':'FAIL','production':'NOT_ACCESSED','parent':{},'candidate':{}}
    try:
        if platform.system()!='Linux':
            report['result']='NOT_RUN';raise ValueError('Linux runtime required')
        provenance=sources.ROOT/'provenance/variants/multipart-20261114.json'
        sources.verify_file(provenance,PROVENANCE_SHA256);manifest=json.loads(provenance.read_text())
        all_cases=cases()
        for side in ('parent','candidate'):
            directory=root/side;directory.mkdir()
            cli,fpm,source=[getattr(args,side+'_'+name).resolve() for name in ('cli','fpm','source')]
            for raw in (getattr(args,side+'_cli'),getattr(args,side+'_fpm')):
                if raw.is_symlink() or not raw.is_file():raise ValueError('regular trusted binaries required')
            expected_hash=manifest['baseline_source_sha256' if side=='parent' else 'candidate_source_sha256']
            actual_hash=sources.tree_digest(source,normalized=True)
            if actual_hash!=expected_hash:raise ValueError('whole source identity mismatch')
            build=json.loads((fpm.parent/'build.json').read_text())
            hashes={'php':sources.sha256(cli),'php-fpm':sources.sha256(fpm)}
            if build['normalized_source_sha256']!=actual_hash or build['binaries']!=hashes:raise ValueError('build/binary identity mismatch')
            common.write_new(directory/'build.json',build)
            version=common.command([cli,'-n','-r','echo PHP_VERSION,":",PHP_INT_SIZE;'],directory,'version',min(10,budget()))
            common.require_command(version)
            if not re.fullmatch(r'7\.0\.33[^:]*:8',version['stdout']) or version['stderr']:raise ValueError('this campaign requires the pinned 64-bit PHP7 build')
            report[side].update(source_sha256=actual_hash,binaries=hashes,cases={})
            for case in all_cases:
                work=directory/case['name'];observations=[];channels={};offsets={};per_request_warnings=[]
                with case_workspace(work) as actual:
                    with instance(fpm,actual,case,budget,side=='candidate'):
                        (actual/'request.body').write_bytes(body(case));sid=uuid.uuid4().hex
                        for trial in range(2):
                            response=request(actual/'fpm.sock',actual/'check.php',case,sid,budget)
                            text=response['body'].decode('ascii');(actual/('response-'+str(trial)+'.txt')).write_text(text)
                            values=check_response(text,case[side]);observations.append(values)
                            error_text=response['stderr'].decode(errors='replace');(actual/('stderr-'+str(trial)+'.txt')).write_text(error_text)
                            channels['fcgi']=channels.get('fcgi','')+error_text
                            deadline=time.monotonic()+min(1,budget())
                            while list((actual/'uploads').iterdir()) and time.monotonic()<deadline:time.sleep(.02)
                            if list((actual/'uploads').iterdir()):raise ValueError('request upload temporary file remained')
                            # PHP's dedicated error log is written before the
                            # completed response. Preserve each request's slice
                            # instead of accepting a misleading 2+0 total.
                            request_channels={'fcgi':error_text}
                            for name in ('php.log','fpm.log','process.log'):
                                data=(actual/name).read_bytes() if (actual/name).exists() else b''
                                offset=offsets.get(name,0)
                                if len(data)<offset:raise ValueError('owned diagnostic log was truncated')
                                request_channels[name]=data[offset:].decode(errors='replace')
                                offsets[name]=len(data)
                            common.write_new(actual/('warnings-'+str(trial)+'.json'),request_channels)
                            per_request_warnings.append(check_warnings(request_channels,case[side+'_warnings']))
                        if observations[0]['PID']!=observations[1]['PID']:raise ValueError('worker changed; counter reset was not tested in the same worker')
                tail_channels={}
                for name in ('php.log','fpm.log','process.log'):
                    data=(work/name).read_bytes() if (work/name).exists() else b''
                    offset=offsets.get(name,0)
                    if len(data)<offset:raise ValueError('owned diagnostic log was truncated')
                    channels[name]=data.decode(errors='replace')
                    tail_channels[name]=data[offset:].decode(errors='replace')
                common.write_new(work/'shutdown-warnings.json',tail_channels)
                check_warnings(tail_channels,{})
                # Keep the whole-case/shutdown check as well, so late or extra
                # diagnostics cannot disappear after the per-request checks.
                warn=check_warnings(channels,{k:v*2 for k,v in case[side+'_warnings'].items()})
                common.write_new(work/'observations.json',{'responses':observations,'warning_channels':channels,'per_request_warnings':per_request_warnings,'counts':warn,'result':'PASS'})
                report[side]['cases'][case['name']]='PASS'
            phpt_dir=directory/'phpt';phpt_dir.mkdir();phpt=[]
            for name in ('multipart-limit-ini.phpt','multipart-limit-default.phpt'):
                dest=phpt_dir/name;shutil.copyfile(sources.ROOT/'tests/fixtures'/name,dest);phpt.append(dest)
            env=common.clean_env();env.update(TEST_PHP_EXECUTABLE=str(cli),NO_INTERACTION='1',REPORT_EXIT_STATUS='1',TERM='dumb')
            run=common.command([cli,'-n',source/'run-tests.php','-n','-q']+phpt,phpt_dir,'ini-phpt',min(120,budget()),env)
            if side=='candidate':common.require_command(run);common.require_phpt_pass(run,2)
            else:require_parent_phpt(run)
            native=common.command([sys.executable,'-B',sources.ROOT/'scripts/native-check.py','--fpm',fpm,'--cli',cli,'--output',directory/'native-36.json'],directory,'native-36',min(180,budget()))
            common.require_command(native)
            result=json.loads((directory/'native-36.json').read_text())
            if result['result']!='BENIGN_RUNTIME_PASS' or sum(len(c['checks']) for c in result['campaigns'])!=36:raise ValueError('normal 36-check regression failed')
            if sources.tree_digest(source,normalized=True)!=actual_hash or {k:sources.sha256(cli if k=='php' else fpm) for k in hashes}!=hashes:
                raise ValueError('source/binary changed during campaign')
        report['result']='PAIRED_MULTIPART_RUNTIME_PASS'
    except Exception as error:report['error']=type(error).__name__+': '+str(error)
    finally:common.write_new(root/'result.json',report)
    print(json.dumps({'result':report['result'],'error':report.get('error')}))
    return 0 if report['result']=='PAIRED_MULTIPART_RUNTIME_PASS' else 1
