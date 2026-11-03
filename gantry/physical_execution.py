"""Run an operator-selected evaluator locally on frozen inputs, never a Mentor argv.

The copied workspace is not an OS sandbox. Use an isolated account/container for
untrusted tools. Licenses and native runtime installation remain operator tasks.
"""
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from .model import canonical, digest, require
from .store import Store
from .physical_evidence import evaluate
from .workflow_journal import connect, freeze, measure


def read(root, name, limit=100*1024**2):
    Store.safe_name(name)
    root=Path(root).resolve(); path=root/name
    require(not any((root/Path(*Path(name).parts[:i])).is_symlink() for i in range(1,len(Path(name).parts)+1))
            and path.is_file() and path.stat().st_size <= limit,
            'scope_denied', 'Bounded regular file required')
    before=path.stat()
    with path.open('rb') as f: raw=f.read(limit+1)
    after=path.stat()
    require(len(raw)<=limit and (before.st_size,before.st_mtime_ns,before.st_ino)==
            (after.st_size,after.st_mtime_ns,after.st_ino),'stale_basis','Input changed during acquisition')
    return raw


def run(root, plan_path, check_id, recipe, approved_hash, destination, state_id='local'):
    require(isinstance(recipe,dict) and set(recipe)=={'argv','timeout_seconds'}
            and isinstance(recipe['argv'],list) and 1<=len(recipe['argv'])<=100
            and all(isinstance(a,str) and 0<len(a)<=4000 for a in recipe['argv'])
            and type(recipe['timeout_seconds']) is int and 1<=recipe['timeout_seconds']<=7200,
            'invalid_input','Local argv and explicit 1–7200 second timeout required')
    require(digest(recipe)==approved_hash,'recipe_not_allowed','Approve the exact local recipe digest')
    executable=Path(recipe['argv'][0])
    require(executable.is_absolute() and executable.is_file(),'invalid_input','Absolute installed executable required')
    from .continuity_adapter import SECRET
    require(not SECRET.search(canonical(recipe).encode()),'credential_detected','Do not embed credentials in recipes')
    plan_raw=read(root,plan_path,1024**2); plan=json.loads(plan_raw); canonical(plan)
    require(isinstance(plan,dict) and plan.get('version')==1 and isinstance(plan.get('checks'),list),
            'invalid_input','Physical plan v1 required')
    checks=[c for c in plan['checks'] if isinstance(c,dict) and c.get('id')==check_id]
    require(len(checks)==1,'invalid_input','Select exactly one frozen check')
    check=checks[0]; names=check.get('inputs')
    require(isinstance(names,list) and 1<=len(names)<=100 and all(isinstance(n,str) for n in names) and len(set(names))==len(names),
            'invalid_input','1–100 distinct evaluator inputs required')
    Store.safe_name(check.get('report'))
    require(check['report'] not in [plan_path,*names],'invalid_input','Report cannot overwrite evaluator inputs')
    files={plan_path:plan_raw}; total=len(plan_raw)
    for name in names:
        raw=read(root,name); total+=len(raw)
        require(total<=256*1024**2,'acquisition_limit','Evaluator inputs exceed 256 MiB')
        files[name]=raw
    require(not any(SECRET.search(raw) for raw in files.values()),'credential_detected','Credential in evaluator input')
    hashes={name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()}
    evaluate(check,None,hashes)  # Validate criteria before launching anything.
    executable_hash=hashlib.sha256(executable.read_bytes()).hexdigest()
    intent={'inputs':hashes,'check_id':check_id,'recipe_hash':approved_hash,'executable_hash':executable_hash,
            'state_id':state_id,'plan_path':plan_path}
    destination=Path(destination).absolute()
    # Resolve the selected parent (e.g. macOS /var) but never a job symlink.
    require(not destination.is_symlink(),'scope_denied','Job directory cannot be a symlink')
    destination=destination.parent.resolve()/destination.name
    def prepare():
        workspace=destination/'workspace'
        require(not workspace.exists(),'conflict','Incomplete preparation; inspect this job and use a new destination')
        workspace.mkdir(mode=0o700)
        for name,raw in files.items():
            p=workspace/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(raw)
        return {'intent':intent,'check':check}
    job=freeze(destination,'prepare',intent,prepare)
    db=connect(destination)
    try:
        db.execute('CREATE TABLE IF NOT EXISTS execution (id INTEGER PRIMARY KEY, receipt TEXT)')
        db.execute('BEGIN IMMEDIATE')
        prior=db.execute('SELECT receipt FROM execution WHERE id=1').fetchone()
        if prior:
            require(prior[0] is not None,'execution_uncertain','Previously launched; do not launch twice. Inspect/reconcile this job.')
            return json.loads(prior[0])
        db.execute('INSERT INTO execution VALUES (1,NULL)'); db.commit()
        workspace=destination/'workspace'; problems=[]; code=None
        with measure(destination,'calculation',state_id,approved_hash):
            with (destination/'stdout.log').open('xb') as out, (destination/'stderr.log').open('xb') as err:
                proc=subprocess.Popen(recipe['argv'],cwd=workspace,stdout=out,stderr=err,
                    env={'PATH':os.defpath,'LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'},
                    start_new_session=(os.name=='posix'))
                started=time.monotonic()
                try:
                    while proc.poll() is None:
                        if time.monotonic()-started>recipe['timeout_seconds'] or max(out.tell(),err.tell())>8*1024**2:
                            problems.append('timeout_or_log_limit'); break
                        time.sleep(.05)
                finally:
                    if proc.poll() is None:
                        if os.name=='posix':
                            from .runner import stop_process
                            stop_process(proc)
                        else: proc.kill(); proc.wait()
                code=proc.returncode
                if os.name=='posix':
                    # A wrapper exiting is not solver completion if its children
                    # still own the process group and can change reports later.
                    import signal
                    try:
                        os.killpg(proc.pid,0)
                        problems.append('descendants_after_parent_exit')
                        os.killpg(proc.pid,signal.SIGKILL)
                    except ProcessLookupError: pass
                if os.name=='nt': problems.append('windows_child_process_lifecycle_unverified')
        receipt=_complete(destination,job,code,problems)
        db.execute('UPDATE execution SET receipt=? WHERE id=1',(canonical(receipt),)); db.commit()
        return receipt
    finally:
        db.close()


def _complete(destination, job, code, problems):
    workspace=destination/'workspace'; check=job['check']; intent=job['intent']; hashes=intent['inputs']
    if code!=0: problems.append('process_failed' if code is not None else 'process_outcome_unconfirmed')
    for name,h in hashes.items():
        try: unchanged=hashlib.sha256(read(workspace,name)).hexdigest()==h
        except Exception: unchanged=False
        if not unchanged: problems.append('input_changed_during_execution'); break
    report=None
    try:
        report=json.loads(read(workspace,check['report'],1024**2))
        canonical(report)
    except (ValueError,OSError): pass
    except Exception as exc:
        if getattr(exc,'code',None) not in {'scope_denied','invalid_input','stale_basis'}: raise
        report=None
    result=evaluate(check,report,hashes)
    if problems: result={**result,'status':'unknown','reasons':result['reasons']+problems}
    acquired={}
    for name,limit in [('stdout.log',8*1024**2),('stderr.log',8*1024**2),('workspace/'+check['report'],1024**2)]:
        raw,size=_acquire(destination,name,limit)
        if raw is not None:
            acquired[name]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'original_size':size,'truncated':size>len(raw)}
    return {'version':1,'intent':intent,'exit_code':code,'outcome':'failed' if problems else 'completed',
            'evaluation':result,'problems':problems,'report':report,'output_files':acquired,
            'limitations':['Local operator-authorized execution, not sandboxed','Physical model validity is not certified']}


def _acquire(root,name,limit):
    Store.safe_name(name); path=root/name
    require(not any((root/Path(*Path(name).parts[:i])).is_symlink() for i in range(1,len(Path(name).parts)+1)),
            'scope_denied','Output path cannot traverse a symlink')
    if not path.exists(): return None,0
    require(path.is_file(),'invalid_input','Regular output required')
    with path.open('rb') as f: return f.read(limit),path.stat().st_size


def reconcile(destination, process_stopped):
    require(process_stopped is True,'execution_uncertain','Operator must verify process and child processes stopped')
    destination=Path(destination).resolve()
    require((destination/'workflow.sqlite3').is_file(),'not_found','Execution journal missing')
    db=connect(destination)
    try:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT receipt FROM execution WHERE id=1').fetchone()
        require(row,'not_found','No launch intent recorded')
        if row[0]: return json.loads(row[0])
        job=json.loads(db.execute("SELECT args FROM requests WHERE key='prepare'").fetchone()[0])
        receipt=_complete(destination,job,None,['operator_confirmed_stopped'])
        db.execute('UPDATE execution SET receipt=? WHERE id=1',(canonical(receipt),)); db.commit()
        return receipt
    finally: db.close()


def collect(destination, target, replace_report_sha256=None):
    """Copy this execution's evidence back only while the exact inputs still match.

    A report claiming success from a failed process is preserved in receipt.report,
    but the report used by the physical adapter has status=error.
    """
    destination=Path(destination).resolve(); target=Path(target).resolve()
    require((destination/'workflow.sqlite3').is_file(),'not_found','Execution journal missing')
    db=connect(destination)
    try:
        row=db.execute('SELECT receipt FROM execution WHERE id=1').fetchone()
        require(row and row[0],'execution_uncertain','No terminal execution receipt; inspect process before retry')
        receipt=json.loads(row[0])
    finally: db.close()
    for name,h in receipt['intent']['inputs'].items():
        require(hashlib.sha256(read(target,name)).hexdigest()==h,'stale_basis','Candidate changed since evaluator input capture')
    plan=json.loads(read(target,receipt['intent']['plan_path'],1024**2))
    check=next(c for c in plan['checks'] if c['id']==receipt['intent']['check_id'])
    report=receipt['report'] if isinstance(receipt['report'],dict) else {'status':'error'}
    if receipt['problems']: report={**report,'status':'error','execution_problems':receipt['problems']}
    prefix='.gantry-evidence/'+digest(receipt['intent'])
    copies={prefix+'/receipt.json':canonical(receipt).encode()}
    for name,info in receipt['output_files'].items():
        raw,size=_acquire(destination,name,info['bytes'])
        require(raw is not None and size==info['original_size'] and hashlib.sha256(raw).hexdigest()==info['sha256'],
                'integrity_error','Acquired execution output changed after completion')
        label='raw-report.json' if name.startswith('workspace/') else name
        copies[prefix+'/'+label]=raw
    from .workflow_journal import timing_report
    copies[prefix+'/timing.json']=canonical(timing_report(destination)).encode()
    copies[check['report']]=canonical(report).encode()
    for name,raw in copies.items():
        Store.safe_name(name); p=target/name
        require(not any((target/Path(*Path(name).parts[:i])).is_symlink() for i in range(1,len(Path(name).parts)+1)),
                'scope_denied','Evidence path traverses symlink')
        if p.exists():
            existing=read(target,name)
            require(existing==raw or (name==check['report'] and replace_report_sha256 is not None
                    and hashlib.sha256(existing).hexdigest()==replace_report_sha256),
                    'conflict','Existing evidence differs; use a new candidate or approve the previous report hash')
    # Recoverable, idempotent local writes; each file is atomically replaced.
    import tempfile
    for name,raw in copies.items():
        p=target/name; p.parent.mkdir(parents=True,exist_ok=True)
        fd,tmp=tempfile.mkstemp(prefix='.gantry-collect-',dir=p.parent)
        try:
            with os.fdopen(fd,'wb') as f: f.write(raw); f.flush(); os.fsync(f.fileno())
            os.replace(tmp,p)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)
    return {'evidence_path':prefix,'report':check['report'],'evaluation':receipt['evaluation'],
            'state_id':receipt['intent']['state_id'],'adoption':'unadopted'}
