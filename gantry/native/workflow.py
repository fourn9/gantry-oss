"""Portable native-write journal and immutable captures; no POSIX runner import."""
import copy
import hashlib
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from ..model import Fault, canonical, digest, require
from ..integrations.bundle import make_bundle, write_bundle, read_bundle, read_file, safe_file
from ..integrations.transport import parse_json
from .catalog import PRODUCTS
from ..continuity_adapter import SECRET


READ = object()


def validate(config, value=READ):
    require(isinstance(config,dict) and config.get('product') in PRODUCTS,'unsupported','Unknown native product')
    product=config['product']
    require(PRODUCTS[product][1]=='direct','unsupported','This product requires a script or an unavailable SDK')
    fields={'product','document','selector','unit','version'}
    if product=='creo': fields.add('value_type')
    if product=='solidworks-electrical': fields={'product','project_id','environment','field','unit','version'}
    require(set(config)==fields,'invalid_input','Unexpected or missing native target fields')
    require(isinstance(config['version'],str) and 0<len(config['version'])<=100,'invalid_input','Explicit product version required')
    if product=='solidworks-electrical':
        require(isinstance(config['project_id'],str) and config['project_id'].isdigit()
                and isinstance(config['environment'],dict) and set(config['environment'])=={'hostname','working_folder'}
                and all(isinstance(s,str) and 0<len(s)<=500 for s in config['environment'].values())
                and type(config['field'])==int and 0<=config['field']<=1000 and config['unit']=='text',
                'invalid_input','Explicit Electrical environment/project/user-data field required')
    else:
        safe_file(config['document'])
        require(isinstance(config['selector'],str) and 0<len(config['selector'])<=256
                and all(ord(c)>=32 for c in config['selector']), 'invalid_input','Existing parameter name required')
        require(config['unit']==('SI' if product=='solidworks' else 'native'),'invalid_input','Use the documented native units')
        if product=='solidworks': require(config['document'].lower().endswith('.sldprt'),'unsupported','Part file required')
        if product=='catia-v5': require(config['document'].lower().endswith('.catpart'),'unsupported','CATPart required')
        if product=='creo': require(config['document'].lower().endswith('.prt'),'unsupported','Logical .prt name required')
    if product=='creo':require(config['value_type'] in {'double','integer','boolean','string'},'invalid_input','Scalar parameter type required')
    if value is READ:return
    kind=config.get('value_type','string' if product=='solidworks-electrical' else 'double')
    finite=type(value) in (int,float) and -1.7976931348623157e308<=value<=1.7976931348623157e308
    valid={'double':finite,
           'integer':type(value)==int and -(2**31)<=value<2**31 if type(value)==int else False,
           'boolean':type(value)==bool,'string':isinstance(value,str) and len(value)<=2000 and '\0' not in value}
    require(valid.get(kind,False),'invalid_input','Value does not match the native parameter type')
    canonical([config,value])


def root_path(root):
    path=Path(root).absolute()
    require(path.is_dir() and not path.is_symlink(),'scope_denied','Existing non-symlink operator root required')
    return path.resolve()


def root_identity(root):
    return digest(os.path.normcase(str(root_path(root))))


def observe(root, config, driver, verify_version=True):
    validate(config)
    root=root_path(root); metadata,paths=driver.inspect(config)
    original=copy.deepcopy(metadata); paths=list(paths)
    require(metadata['dirty'] is False or (config['product']=='solidworks-electrical' and metadata['dirty'] is None),
            'dirty_document','Save unrelated edits before planning or applying')
    if verify_version and metadata['application_version'] is not None:
        require(metadata['application_version']==config['version'],'stale_basis','Application version differs')
    if config['product']!='solidworks-electrical':
        require(Path(metadata['document']).resolve()==(root/config['document']).resolve(),
                'scope_denied','Active document differs from operator target')
    files={}
    for path in paths:
        path=Path(path)
        require(path.is_absolute() and path.resolve().is_relative_to(root),'scope_denied','Native file outside operator root')
        require(not any(p.is_symlink() for p in [path,*path.parents] if p.resolve().is_relative_to(root)),
                'scope_denied','Symlink native output denied')
        name=path.resolve().relative_to(root).as_posix()
        expected=root/config['document']
        require(not any(p.is_symlink() for p in [expected,*expected.parents] if p.is_relative_to(root)),
                'scope_denied','Symlink target denied')
        require(path.stat().st_nlink==1,'scope_denied','Hardlinked native file denied')
        files['native/'+name]=read_file(root,name)
    after,after_paths=driver.inspect(config)
    require(after==original and list(after_paths)==paths,'capture_incomplete','Native state changed during capture')
    metadata=copy.deepcopy(metadata)
    metadata['declared_version']=config['version']
    # Store portable relative identity, not the user's absolute home path.
    if config['product']!='solidworks-electrical': metadata['document']=config['document']
    metadata['files']={n:hashlib.sha256(b).hexdigest() for n,b in files.items()}
    require(metadata['unit']==config['unit'],'invalid_response','Unexpected native units')
    files['observation.json']=canonical(metadata).encode()
    require(all(not SECRET.search(raw) for raw in files.values()),'credential_detected','Potential credential in native capture')
    return metadata,files


def prepare(root,config,value,reason,refs,destination,driver):
    validate(config,value)
    require(isinstance(reason,str) and 0<len(reason)<=4000,'invalid_input','Reason required')
    before,files=observe(root,config,driver)
    validate(config,before['value'])
    plan={'version':1,'intent_id':secrets.token_hex(16),'target':copy.deepcopy(config),
          'value':value,'reason':reason,'requirement_refs':copy.deepcopy(refs), 'baseline':before,
          'operator_root':root_identity(root),
          'concurrency':'exclusive_operator_preflight_only'}
    h=digest(plan); files={'before/'+n:b for n,b in files.items()}
    files['plan.json']=canonical(plan).encode()
    bundle=make_bundle(config['product'],'native-'+h[:24],files,refs,
        source={'native_plan':h},missing=['Not applied','Dependencies outside selected native object'])
    write_bundle(destination,bundle)
    return {'plan_hash':h,'plan':plan,'native_write':False}


def load_plan(path):
    bundle=read_bundle(path);plan=parse_json(bundle['files']['plan.json']);h=digest(plan)
    require(set(plan)=={'version','intent_id','target','value','reason','requirement_refs','baseline','concurrency','operator_root'}
            and plan['version']==1 and plan['concurrency']=='exclusive_operator_preflight_only'
            and bundle['manifest']['source']=={'native_plan':h}
            and plan['requirement_refs']==bundle['manifest']['requirement_refs'], 'integrity_error','Invalid native plan')
    validate(plan['target'],plan['value'])
    require(isinstance(plan['intent_id'],str) and re.fullmatch('[0-9a-f]{32}',plan['intent_id'])
            and isinstance(plan['reason'],str) and 0<len(plan['reason'])<=4000
            and isinstance(plan['operator_root'],str) and re.fullmatch('[0-9a-f]{64}',plan['operator_root']),
            'integrity_error','Invalid plan identity or reason')
    require(plan['baseline']==parse_json(bundle['files']['before/observation.json']),
            'integrity_error','Native baseline differs from observation')
    for name,sha in plan['baseline']['files'].items():
        require(hashlib.sha256(bundle['files']['before/'+name]).hexdigest()==sha,'integrity_error','Native baseline bytes differ')
    return plan,h,bundle


@contextmanager
def journal(root):
    directory=root_path(root)/'.gantry-native'
    require(not directory.is_symlink(),'scope_denied','Journal must not be a symlink')
    directory.mkdir(mode=0o700,exist_ok=True)
    path=directory/'journal.sqlite3'
    for suffix in ('','-journal','-wal','-shm'):
        p=Path(str(path)+suffix)
        require(not p.is_symlink() and (not p.exists() or p.stat().st_nlink==1),'scope_denied','Unsafe journal file')
    con=sqlite3.connect(path,timeout=1,isolation_level=None)
    try:
        os.chmod(path,0o600);con.execute('PRAGMA synchronous=FULL')
        con.execute('CREATE TABLE IF NOT EXISTS receipts(hash TEXT PRIMARY KEY, target TEXT, body TEXT)')
        con.execute('CREATE TABLE IF NOT EXISTS holds(target TEXT PRIMARY KEY, hash TEXT)')
        yield con
    finally: con.close()


def receipt(con,h):
    row=con.execute('SELECT body FROM receipts WHERE hash=?',(h,)).fetchone()
    return parse_json(row[0]) if row else None


def persist(con,h,target,data,release=False):
    data.setdefault('history',[]).append({'status':data['status'],'at':datetime.now(timezone.utc).isoformat()})
    con.execute('BEGIN IMMEDIATE')
    try:
        con.execute('INSERT OR REPLACE INTO receipts VALUES(?,?,?)',(h,target,canonical(data)))
        if release: con.execute('DELETE FROM holds WHERE target=? AND hash=?',(target,h))
        con.commit()
    except BaseException: con.rollback();raise


def target_key(plan):
    c=plan['target']
    return digest([c['product'],os.path.normcase(c.get('document','')),c.get('environment'),c.get('project_id')])


def apply(path,expected_hash,root,driver,exclusive=False):
    plan,h,_=load_plan(path)
    require(plan['operator_root']==root_identity(root),'scope_denied','Use the operator root that prepared this plan')
    require(h==expected_hash,'integrity_error','Explicit matching plan hash required')
    require(exclusive is True,'nonatomic_write','Acknowledge single-operator preflight-only operation')
    target=target_key(plan)
    with journal(root) as con:
        prior=receipt(con,h)
        if prior: return prior
        # Persistent hold is committed before calling CAD; interruption cannot free it accidentally.
        con.execute('BEGIN IMMEDIATE')
        try:
            prior=receipt(con,h)
            if prior: con.rollback();return prior
            require(not con.execute('SELECT 1 FROM holds WHERE target=?',(target,)).fetchone(),
                    'conflict','Native target has an unresolved operation')
            current,_=observe(root,plan['target'],driver)
            require(current==plan['baseline'],'stale_basis','Native baseline changed')
            data={'plan_hash':h,'status':'dispatching','history':[]}
            con.execute('INSERT INTO holds VALUES(?,?)',(target,h))
            data['history'].append({'status':'dispatching','at':datetime.now(timezone.utc).isoformat()})
            con.execute('INSERT INTO receipts VALUES(?,?,?)',(h,target,canonical(data)));con.commit()
        except BaseException: con.rollback();raise
        try:
            if current['value']!=plan['value']: data['native_response']=driver.write(plan['target'],plan['value'])
            data['status']='applied_unverified';persist(con,h,target,data)
            return _readback(root,plan,h,target,con,data,driver,False)
        except Exception as exc:
            data.update(status='unknown',error=exc.code if isinstance(exc,Fault) else 'native_or_io_error')
            persist(con,h,target,data);return data


def _readback(root,plan,h,target,con,data,driver,recovered):
    observation,files=observe(root,plan['target'],driver)
    for key in ('document','configuration','environment','application_version'):
        require(observation.get(key)==plan['baseline'].get(key),'stale_basis','Native identity/configuration changed after dispatch')
    same=observation['value']==plan['value']
    data.update(status=('observed_desired' if recovered else 'verified') if same else 'readback_mismatch',
                after=observation,verification='selected_value_only_not_engineering_acceptance')
    # Capture bytes before releasing target; subsequent external edits cannot change evidence.
    import base64
    data['after_files']={n:base64.b64encode(b).decode() for n,b in files.items()}
    persist(con,h,target,data,release=same)
    return data


def reconcile(path,root,driver,writer_stopped=False):
    require(writer_stopped is True,'operation_pending','Confirm the earlier native writer has stopped before releasing its hold')
    plan,h,_=load_plan(path)
    require(plan['operator_root']==root_identity(root),'scope_denied','Use the original operator root')
    with journal(root) as con:
        data=receipt(con,h);require(data is not None,'not_found','No dispatch receipt')
        if data['status'] in {'verified','observed_desired'}:return data
        # Read only; no native writer or automatic rollback on recovery.
        return _readback(root,plan,h,target_key(plan),con,data,driver,True)


def evidence(path,root):
    import base64
    plan,h,bundle=load_plan(path)
    require(plan['operator_root']==root_identity(root),'scope_denied','Use the original operator root')
    with journal(root) as con: data=receipt(con,h)
    require(data is not None,'not_found','No dispatch receipt')
    files=dict(bundle['files']); data=copy.deepcopy(data)
    files.update({'after/'+n:base64.b64decode(b,validate=True) for n,b in data.pop('after_files',{}).items()})
    files['receipt.json']=canonical(data).encode()
    return make_bundle(plan['target']['product'],'native-'+h[:24],files,plan['requirement_refs'],
        source={'native_plan':h,'outcome':data['status']},
        missing=['Physical verification not performed','Unselected dependencies not captured',
                 'Database archive not captured' if plan['target']['product']=='solidworks-electrical' else 'Assembly restoration not verified'])
