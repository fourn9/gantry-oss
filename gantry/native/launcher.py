"""Pinned local Altium process dispatch; launch is not native completion."""
import base64
import copy
import hashlib
import os
import re
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from sys import platform
from ..model import Fault, canonical, require
from ..integrations.bundle import read_file, make_bundle
from .scripts import validated_script, collect_script
from .workflow import root_path, journal, receipt, target_key


def _public(data):
    return {k:v for k,v in data.items() if k!='capture'}


def _store_locked(con,h,target,data,release=False):
    data.setdefault('history',[]).append({'status':data['status'],'at':datetime.now(timezone.utc).isoformat()})
    con.execute('INSERT OR REPLACE INTO receipts VALUES(?,?,?)',(h,target,canonical(data)))
    if release:con.execute('DELETE FROM holds WHERE target=? AND hash=?',(target,h))
    con.commit()


def _executable(path, expected):
    path=Path(path)
    require(path.is_absolute() and path.name.lower()=='x2.exe'
            and not any(p.is_symlink() for p in [path,*path.parents]),
            'scope_denied','Explicit non-symlink Altium X2.EXE path required')
    require(isinstance(expected,str) and re.fullmatch('[0-9a-f]{64}',expected),
            'invalid_input','Expected executable SHA-256 required')
    with path.open('rb') as file:
        before=os.fstat(file.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 2<=before.st_size<=512*1024*1024,
                'scope_denied','Bounded ordinary executable required')
        require(file.read(2)==b'MZ','unsupported','Windows executable required');file.seek(0)
        sha=hashlib.file_digest(file,'sha256').hexdigest();after=os.fstat(file.fileno())
    fields=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')
    require(all(getattr(before,k)==getattr(after,k) for k in fields) and sha==expected,
            'integrity_error','Executable changed or digest differs')
    return path


def _command(executable, package):
    script=str(Path(package).absolute()/'operation.pas')
    require(all(32<=ord(c)<127 and c not in '"|()^' for c in script),
            'unsupported','Script path contains unsupported native process delimiters')
    # Official command-line process mechanism and RunScriptFile parameters:
    # https://resources.altium.com/p/continuous-integration-implementation-using-altium-designer
    # https://www.altium.com/documentation/altium-designer/scripting/running-scripts
    return [str(executable),f'-RScriptingSystem:RunScriptFile(FileName="{script}"|ProcName="GantryApply")']


def run_script(package,root,expected_hash,executable,executable_sha256,*,exclusive=False):
    require(platform=='win32','platform_unavailable','Licensed Altium Windows host required')
    require(exclusive is True,'nonatomic_write','Exclusive editor access acknowledgement required')
    plan,h,_=validated_script(package,root)
    require(h==expected_hash,'integrity_error','Explicit matching plan hash required')
    require(plan['version']==2 and plan['target']['product']=='altium',
            'unsupported','Automatic dispatch requires an Altium save/reload v2 plan')
    root=root_path(root);package=Path(package);target=target_key(plan)
    with journal(root) as con:
        con.execute('BEGIN IMMEDIATE')
        try:
            prior=receipt(con,h)
            if prior:con.rollback();return _public(prior)
            require(not con.execute('SELECT 1 FROM holds WHERE target=?',(target,)).fetchone(),
                    'conflict','Native target has an unresolved writer')
            require(not any((package/n).exists() for n in ('started','result.json','native-saved.PcbDoc')),
                    'operation_pending','Existing native outcome; collect it without redispatch')
            raw=read_file(root,plan['target']['document'])
            require(hashlib.sha256(raw).hexdigest()==plan['baseline_file_hash'],
                    'stale_basis','Native file changed since preparation')
            exe=_executable(executable,executable_sha256);argv=_command(exe,package)
            data={'plan_hash':h,'status':'dispatching','executable_sha256':executable_sha256,'history':[]}
            con.execute('INSERT INTO holds VALUES(?,?)',(target,h))
            _store_locked(con,h,target,data)
        except BaseException:con.rollback();raise
        try:
            child=subprocess.Popen(argv,shell=False,cwd=str(exe.parent),stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,close_fds=True,
                env={k:v for k,v in os.environ.items() if not k.upper().startswith('GANTRY_')})
            data.update(status='dispatched',launcher_pid=child.pid)
        except Exception:
            # Host may have received the command even if the client failed. Never resend.
            data.update(status='unknown',error='host_dispatch_failed')
        con.execute('BEGIN IMMEDIATE')
        latest=receipt(con,h)
        if latest['status']!='dispatching':con.rollback();return _public(latest)
        _store_locked(con,h,target,data)
        return _public(data)


def script_status(package,root,*,writer_stopped=False):
    plan,h,_=validated_script(package,root)
    with journal(root) as con:
        con.execute('BEGIN IMMEDIATE')
        data=receipt(con,h);require(data is not None,'not_found','No CLI dispatch receipt')
        if data['status']=='saved_and_reloaded':con.rollback();return _public(data)
        if not (Path(package)/'result.json').exists():con.rollback();return _public(data)
        if writer_stopped is not True:
            con.rollback()
            return {**_public(data),'status':'awaiting_writer_stop_confirmation'}
        try:
            bundle=collect_script(package,root)
            require(bundle['manifest']['source']['outcome']=='saved_and_reloaded',
                    'invalid_response','Saved/reloaded evidence required')
            data.update(status='saved_and_reloaded',verification='host_report_not_qualified_runtime',
                capture={'manifest':bundle['manifest'],
                         'files':{n:base64.b64encode(b).decode() for n,b in bundle['files'].items()}})
            data.pop('error',None)
            _store_locked(con,h,target_key(plan),data,release=True)
        except (Fault,OSError,ValueError,TypeError,KeyError):
            data.pop('capture',None);data.update(status='unknown',error='native_capture_failed')
            _store_locked(con,h,target_key(plan),data)
        return _public(data)


def script_evidence(package,root):
    plan,h,_=validated_script(package,root)
    with journal(root) as con:data=receipt(con,h)
    require(data is not None and data.get('capture'),'not_found','No frozen native result; reconcile the receipt first')
    data=copy.deepcopy(data);capture=data.pop('capture')
    files={n:base64.b64decode(b,validate=True) for n,b in capture['files'].items()}
    files['launcher-receipt.json']=canonical(data).encode()
    return make_bundle(plan['target']['product'],'native-'+h[:24],files,plan['requirement_refs'],
        source={'native_script_plan':h,'outcome':data['status']},missing=capture['manifest']['missing'])
