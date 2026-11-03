"""Operator provisioning and recipient-owned access requests; no public signup."""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import sys
import tempfile
import time
from .model import Fault,require,identifier,digest
from .project_connect import private_dir,save
from .service import Service,token_hash
from .store import Store


def _destination(root,slug):
    require(re.fullmatch('[a-z0-9][a-z0-9-]{0,47}',slug),'invalid_input','Invalid workspace slug')
    root=private_dir(root).resolve();dest=root/slug
    require(not dest.exists() and not dest.is_symlink(),'conflict','Workspace already exists; never overwrite it')
    return dest


def provision(root,slug,owner):
    dest=_destination(root,slug);identifier(owner)
    stage=Path(tempfile.mkdtemp(prefix='.provision-',dir=dest.parent))
    try:
        s=Service(stage);result=s.bootstrap(owner)
        with (stage/'admin.token').open('x') as f:
            os.chmod(f.name,0o600);f.write(result['token']+'\n');f.flush();os.fsync(f.fileno())
        ledger_id=s.call(result['token'],'state')['ledger_id']
        require(not dest.exists(),'conflict','Workspace appeared during provisioning')
        stage.rename(dest)
    finally:
        if stage.exists():shutil.rmtree(stage)
    return {'directory':str(dest),'ledger_id':ledger_id,'token_file':str(dest/'admin.token'),
            'workspace_path':'/w/'+slug+'/','feedback':'off','inference':'not configured'}


def make_request(member,ledger_id,role,zones,token_path,request_path):
    from .membership import REQUEST
    from .contracts import validate
    identifier(member);identifier(ledger_id)
    token_path=Path(token_path);request_path=Path(request_path)
    require(token_path.absolute()!=request_path.absolute(),'invalid_input','Use separate token and request files')
    require(not any(p.exists() or p.is_symlink() for p in (token_path,request_path)),'conflict','Output already exists')
    token=secrets.token_urlsafe(32)
    request={'member_id':member,'ledger_id':ledger_id,'role':role,'zones':zones,
             'token_hash':token_hash(token),'valid_until':int(time.time()*1000)+86400000}
    validate(request,REQUEST)
    for p in (token_path,request_path):p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with os.fdopen(os.open(token_path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as f:
        f.write(token+'\n');f.flush();os.fsync(f.fileno())
    with os.fdopen(os.open(request_path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as f:
        json.dump(request,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    return {'request_file':str(request_path.absolute()),'token_file':str(token_path.absolute()),
            'fingerprint':digest(request),'active':False,'note':'Share only the request file; keep the token on this device.'}


def _copy_verified(source,stage):
    source=Path(source).absolute()
    require(not source.is_symlink() and (source/'ledger.sqlite3').is_file() and not (source/'ledger.sqlite3').is_symlink(),
            'invalid_input','Existing ordinary ledger directory required')
    # SQLite backup pins a transaction-consistent database even while the server
    # writes. Immutable blobs are collected from that saved database, not HEAD.
    with closing(sqlite3.connect((source/'ledger.sqlite3').as_uri()+'?mode=ro',uri=True)) as src:
        with closing(sqlite3.connect(stage/'ledger.sqlite3')) as dst:src.backup(dst,pages=256)
    store=Store(stage)
    with closing(store.connect()) as con:
        checkpoint=store.verify(con=con);state=store.state(con)
        projection=digest(state)
        hashes={p['hash'] for e in state['revisions'].values() if e['type']=='artifact_snapshot'
                for info in e['data']['files'].values() for p in Store.file_parts(info)}
    require(not (source/'blobs').is_symlink(),'integrity_error','Linked blob directory denied')
    for h in sorted(hashes):
        require(re.fullmatch('[a-f0-9]{64}',h),'integrity_error','Invalid blob hash')
        path=source/'blobs'/h
        require(path.is_file() and not path.is_symlink(),'integrity_error','Missing or linked blob')
        raw=path.read_bytes();require(hashlib.sha256(raw).hexdigest()==h,'integrity_error','Blob hash mismatch')
        target=store.blobs/h
        with target.open('xb') as f:os.chmod(f.name,0o600);f.write(raw)
    # Independently reconstruct the event-derived state, not just its projection.
    with closing(store.connect()) as con:
        replay=store.state(con,state['seq'])
        require(digest(replay)==projection,'integrity_error','Projection differs from replay')
    return {'checkpoint':checkpoint,'projection_hash':projection,'blobs':len(hashes)}


def backup(source,destination):
    dest=Path(destination).absolute()
    require(not dest.exists() and not dest.is_symlink(),'conflict','Use a new backup directory')
    dest.parent.mkdir(parents=True,exist_ok=True,mode=0o700);stage=Path(tempfile.mkdtemp(prefix='.backup-',dir=dest.parent))
    try:
        result=_copy_verified(source,stage);save(stage/'backup.json',{'format':'gantry-cloud-backup-v1',**result})
        require(not dest.exists(),'conflict','Backup destination appeared');stage.rename(dest)
    finally:
        if stage.exists():shutil.rmtree(stage)
    return {**result,'directory':str(dest),'credentials':'Raw tokens and connector secrets are excluded; ledger hashes are preserved.'}


def restore(source,root,slug):
    source=Path(source).absolute();meta=source/'backup.json'
    require(meta.is_file() and not meta.is_symlink(),'invalid_input','Verified backup manifest required')
    expected=json.loads(meta.read_text())
    require(expected.get('format')=='gantry-cloud-backup-v1' and {'checkpoint','projection_hash'}<=set(expected),
            'invalid_input','Unsupported backup manifest')
    dest=_destination(root,slug);stage=Path(tempfile.mkdtemp(prefix='.restore-',dir=dest.parent))
    try:
        result=_copy_verified(source,stage)
        require(result['checkpoint']==expected['checkpoint'] and result['projection_hash']==expected['projection_hash'],
                'integrity_error','Backup checkpoint or state changed')
        require(not dest.exists(),'conflict','Restore destination appeared');stage.rename(dest)
    finally:
        if stage.exists():shutil.rmtree(stage)
    return {**result,'directory':str(dest),'tokens_restored':False}


def main():
    parser=argparse.ArgumentParser(description='Gantry workspace provisioning, membership and recovery')
    parser.add_argument('--url',default=os.getenv('GANTRY_URL','http://127.0.0.1:8765'))
    parser.add_argument('--token-file',default=os.getenv('GANTRY_TOKEN_FILE'))
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('provision');p.add_argument('--root',required=True);p.add_argument('--workspace',required=True);p.add_argument('--owner',required=True)
    p=sub.add_parser('request');p.add_argument('--member',required=True);p.add_argument('--ledger-id',required=True)
    from .membership import ROLES
    p.add_argument('--role',choices=ROLES,default='contributor');p.add_argument('--zone',action='append',required=True)
    p.add_argument('--output-token',required=True);p.add_argument('--output-request',required=True)
    sub.add_parser('members')
    p=sub.add_parser('grant');p.add_argument('--request',required=True);p.add_argument('--fingerprint',required=True)
    p.add_argument('--session',action='append',default=[],help='Explicit SESSION_ID:VERSION; repeat for participating sessions')
    p.add_argument('--reason',required=True);p.add_argument('--expires-at',type=int);p.add_argument('--apply',action='store_true')
    p=sub.add_parser('revoke');p.add_argument('--member',required=True);p.add_argument('--revision',required=True);p.add_argument('--reason',required=True)
    p=sub.add_parser('backup');p.add_argument('--data',required=True);p.add_argument('--destination',required=True)
    p=sub.add_parser('restore');p.add_argument('--source',required=True);p.add_argument('--root',required=True);p.add_argument('--workspace',required=True)
    a=parser.parse_args()
    try:
        if a.command=='provision':result=provision(a.root,a.workspace,a.owner)
        elif a.command=='request':result=make_request(a.member,a.ledger_id,a.role,a.zone,a.output_token,a.output_request)
        elif a.command=='backup':result=backup(a.data,a.destination)
        elif a.command=='restore':result=restore(a.source,a.root,a.workspace)
        else:
            from .client import Client
            require(a.token_file,'unauthorized','Owner token file required')
            path=Path(a.token_file);require(not path.is_symlink() and path.stat().st_mode&0o077==0,'unauthorized','Use an owner-only token file')
            client=Client(a.url,path.read_text().strip())
            if a.command=='members':result=client.call('workspace_members')
            elif a.command=='grant':
                request=json.loads(Path(a.request).read_text())
                require(digest(request)==a.fingerprint,'stale_basis','Access request differs from fingerprint')
                args={'request':request,'fingerprint':a.fingerprint,'reason':a.reason,
                    'sessions':[{'session_id':x.rsplit(':',1)[0],'version':int(x.rsplit(':',1)[1])} for x in a.session],
                    **({'expires_at':a.expires_at} if a.expires_at else {})}
                from .contracts import CONTRACTS,validate
                validate(args,CONTRACTS['grant_workspace_member']['schema'])
                info=client.call('workspace_members')
                require(request['ledger_id']==info['ledger_id'],'scope_denied','Wrong workspace')
                result=client.call('grant_workspace_member',args,'grant:'+digest(args)) if a.apply else {'applied':False,'review':args}
            else:
                args={'member_id':a.member,'expected_revision':a.revision,'reason':a.reason}
                result=client.call('revoke_workspace_member',args,'revoke:'+digest(args))
        print(json.dumps(result,indent=2))
    except (Fault,OSError,ValueError,KeyError,IndexError) as exc:
        print(json.dumps({'error':exc.as_dict() if isinstance(exc,Fault) else {'code':'invalid_input','message':'Operation failed; check paths, input and access'}}),file=sys.stderr)
        raise SystemExit(1)

if __name__=='__main__':main()
