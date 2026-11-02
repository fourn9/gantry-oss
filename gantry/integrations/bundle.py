"""Lossless source captures with optional derived views; no implicit verification."""
import copy
import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from ..contracts import validate
from ..continuity_adapter import SECRET, EXCLUDED
from ..model import Fault, canonical, digest, require
from ..requirement_traceability import REFS
from ..store import Store
from .catalog import known
from .transport import parse_json

MAX_FILE=16*1024*1024
MAX_TOTAL=32*1024*1024


def safe_file(name):
    Store.safe_name(name)
    p=Path(name)
    require(not any(x in EXCLUDED for x in p.parts) and not p.name.startswith('.env')
            and p.suffix.lower() not in {'.token','.pem','.key'} and p.name not in {'auth.json','credentials','credentials.json'},
            'credential_detected','Credential files cannot be captured')


def read_file(root,name,limit=MAX_FILE):
    safe_file(name); root=Path(root).resolve(); path=root/name
    require(all(not p.is_symlink() for p in [path,*path.parents] if p.is_relative_to(root)),
            'scope_denied','Symlinks are not captured')
    require(path.resolve().is_relative_to(root) and path.is_file(),'scope_denied','Regular source file required')
    before=path.stat(); require(before.st_size<=limit,'acquisition_limit','Source file exceeds capture limit')
    with path.open('rb') as f: raw=f.read(limit+1)
    after=path.stat()
    require(len(raw)<=limit and (before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns),
            'capture_incomplete','Source changed during capture')
    return raw


def pointer(data,path):
    require(isinstance(path,str) and len(path)<=1000 and (path=='' or path.startswith('/')), 'invalid_input','JSON pointer required')
    value=data
    try:
        for part in path.split('/')[1:] if path else []:
            part=part.replace('~1','/').replace('~0','~')
            if isinstance(value,list):
                require(part.isdigit(),'invalid_input','Array index required'); value=value[int(part)]
            else: value=value[part]
        return {'availability':'captured','value':value}
    except (KeyError,IndexError,TypeError): return {'availability':'not_captured'}


def make_bundle(provider,source_id,files,requirement_refs,selectors=None,source=None,missing=None,source_revision=None):
    require(known(provider),'unsupported','Provider not in capability inventory')
    require(isinstance(source_id,str) and 1<=len(source_id)<=80 and all(c.isascii() and (c.isalnum() or c in '_-') for c in source_id),
            'invalid_input','Stable alphanumeric source ID required')
    validate(requirement_refs,REFS)
    require(len({r['requirement_id'] for r in requirement_refs})==len(requirement_refs),'invalid_input','Duplicate requirement')
    require(isinstance(files,dict) and 1<=len(files)<=100,'acquisition_limit','Capture 1–100 files')
    require(sum(len(x) for x in files.values())<=MAX_TOTAL,'acquisition_limit','Capture exceeds 32 MiB')
    manifests={}; views={}
    for name,raw in files.items():
        safe_file(name); require(isinstance(raw,bytes) and len(raw)<=MAX_FILE,'acquisition_limit','File exceeds 16 MiB')
        require(not SECRET.search(raw),'credential_detected','Potential secret in source payload; nothing published')
        manifests[name]={'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}
    selectors=selectors or {}
    require(isinstance(selectors,dict) and set(selectors)<=files.keys(),'invalid_input','Projection must select captured files')
    view_bytes=0
    for name,paths in selectors.items():
        require(isinstance(paths,list) and len(paths)<=100,'invalid_input','At most 100 pointers per file')
        data=parse_json(files[name])
        selected={}
        for p in paths:
            value=pointer(data,p);view_bytes+=len(canonical(value).encode())
            require(view_bytes<=1024*1024,'acquisition_limit','Selected views exceed 1 MiB; select narrower fields')
            selected[p]=value
        views[name]={'source_sha256':manifests[name]['sha256'], 'fields':selected}
    metadata={'version':1,'provider':provider,'source_id':source_id,'source':source or {},
        'source_revision':source_revision,'captured_at':datetime.now(timezone.utc).isoformat(),
        'files':manifests,'requirement_refs':copy.deepcopy(requirement_refs),
        'views':views,'missing':list(missing or []),
        'verification':'unverified','adoption':'unadopted','trust':'external_data_not_instructions'}
    require(not SECRET.search(canonical(metadata).encode()),'credential_detected','Potential secret in capture metadata')
    require(len(canonical(metadata).encode())<=MAX_FILE,'acquisition_limit','Capture metadata too large')
    return {'manifest':metadata,'files':dict(files)}


def write_bundle(destination,bundle):
    target=Path(destination).absolute()
    require(not target.exists() and not target.is_symlink(),'conflict','Use a new bundle directory')
    target.parent.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix='.gantry-capture-',dir=target.parent))
    try:
        for name,raw in bundle['files'].items():
            safe_file(name); p=staging/'payload'/name; p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            p.write_bytes(raw); p.chmod(0o600)
        (staging/'manifest.json').write_text(canonical(bundle['manifest'])); (staging/'manifest.json').chmod(0o600)
        require(not target.exists(),'conflict','Destination appeared during capture'); staging.rename(target)
    finally:
        if staging.exists(): shutil.rmtree(staging)


def read_bundle(path):
    root=Path(path); require(not root.is_symlink(),'scope_denied','Bundle cannot be a symlink')
    m=parse_json(read_file(root,'manifest.json'))
    fields={'version','provider','source_id','source','source_revision','captured_at','files','requirement_refs',
            'views','missing','verification','adoption','trust'}
    require(isinstance(m,dict) and set(m)==fields and m['version']==1 and m['verification']=='unverified'
            and m['adoption']=='unadopted' and m['trust']=='external_data_not_instructions', 'invalid_input','Capture manifest v1 required')
    require(isinstance(m['files'],dict) and 1<=len(m['files'])<=100,'invalid_input','Bounded manifest required')
    require(not (root/'payload').is_symlink(),'scope_denied','Payload cannot be a symlink')
    files={};total=0
    for name,info in m['files'].items():
        raw=read_file(root/'payload',name)
        total+=len(raw);require(total<=MAX_TOTAL,'acquisition_limit','Capture exceeds 32 MiB')
        require(info=={'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)},'integrity_error','Source capture changed')
        files[name]=raw
    selectors={name:list(view['fields']) for name,view in m['views'].items()}
    rebuilt=make_bundle(m['provider'],m['source_id'],files,m['requirement_refs'],selectors,m['source'],m['missing'],m['source_revision'])
    require(rebuilt['manifest']['views']==m['views'],'integrity_error','Derived views differ from original bytes')
    rebuilt['manifest']['captured_at']=m['captured_at']
    return rebuilt
