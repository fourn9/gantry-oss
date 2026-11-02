"""Offline vendor handoff. Native APIs run locally; bundle validation is not CAD validation."""
import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from .model import require, digest, uid
from .store import Store
from .contracts import validate
from .continuity_adapter import SECRET, EXCLUDED

PRODUCTS = {
    'solidworks': {'api': 'SOLIDWORKS COM', 'driver': 'saved-native-capture', 'live_verified': False},
    'creo': {'api': 'Creo Parametric TOOLKIT / Object TOOLKIT', 'driver': 'external-sdk-required', 'live_verified': False},
    'catia-v5': {'api': 'CATIA V5 Automation / CAA', 'driver': 'saved-native-capture', 'live_verified': False},
    'altium': {'api': 'Altium Designer Scripting PCB/Sch Server', 'driver': 'external-sdk-required', 'live_verified': False},
    'cadence': {'api': 'Allegro SKILL / OrCAD edition-specific', 'driver': 'external-sdk-required', 'live_verified': False},
    'zuken-e3': {'api': 'E3.series COM', 'driver': 'external-sdk-required', 'live_verified': False},
    'capital': {'api': 'Capital module-specific Java/JavaScript/SOA', 'driver': 'external-sdk-required', 'live_verified': False},
    'solidworks-electrical': {'api': 'SOLIDWORKS Electrical API (separate from MCAD)', 'driver': 'external-sdk-required', 'live_verified': False},
}
S={'type':'string','minLength':1,'maxLength':4000}
STRINGS={'type':'array','maxItems':1000,'items':S}
COVERAGE={'type':'object','required':['captured','missing','inferred'],
          'properties':{k:STRINGS for k in ['captured','missing','inferred']},'additionalProperties':False}
OBS={'type':'object','required':['kind','source_id','attributes','source_path'],'properties':{
    'kind':{'enum':['component','connection','net','wire','parameter','document','diagnostic']},
    'source_id':S,'source_path':S,'attributes':{'type':'object'}},'additionalProperties':False}
RESULT={'type':'object','required':['schema_version','request_id','request_hash','product','version','operation','status','files','observations','coverage'],
    'properties':{'schema_version':{'enum':[1]},'request_id':S,'request_hash':S,'product':{'enum':list(PRODUCTS)},
        'version':S,'operation':{'enum':['capture']},'status':{'enum':['completed']},'files':{'type':'object'},
        'observations':{'type':'array','maxItems':10000,'items':OBS},'coverage':COVERAGE},'additionalProperties':False}


def safe_path(root, name):
    Store.safe_name(name)
    parts=Path(name).parts
    require(not any(p in EXCLUDED for p in parts) and not any(p.startswith('.env') for p in parts)
            and Path(name).suffix.lower() not in {'.token','.pem','.key'}
            and Path(name).name not in {'auth.json','credentials','credentials.json'},'credential_detected','Excluded file')
    root=Path(root).absolute();p=root
    require(not root.is_symlink(),'invalid_input','Symlink root denied')
    for part in parts:
        p=p/part
        require(not p.is_symlink(),'invalid_input','Symlink denied')
    require(p.resolve().is_relative_to(root.resolve()),'invalid_input','Path escape denied')
    return p


def read_safe(root,name,limit=64*1024*1024):
    p=safe_path(root,name);require(p.is_file(),'capture_incomplete','Missing regular file')
    before=p.stat();require(before.st_size<=limit,'invalid_input','File exceeds bridge limit')
    with p.open('rb') as f:raw=f.read(limit+1)
    after=p.stat()
    require(len(raw)<=limit and (before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns),
            'capture_incomplete','File changed while reading')
    require(not SECRET.search(raw),'credential_detected','Potential credential detected')
    return raw


def load(root,name):
    try:return json.loads(read_safe(root,name,4*1024*1024))
    except (ValueError,UnicodeError):
        from .model import Fault
        raise Fault('invalid_input','Invalid bundle JSON') from None


def prepare(source, names, destination, product, version, operation='capture'):
    require(product in PRODUCTS and operation=='capture','unsupported_operation','Only explicit saved-file capture is implemented')
    validate(version,S)
    require(0<len(names)<=1000 and len(names)==len(set(names)),'invalid_input','Select 1–1000 unique files')
    dest=Path(destination).absolute();require(not dest.exists(),'conflict','Use a new bundle directory')
    dest.parent.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix='.vendor-',dir=dest.parent))
    try:
        (staging/'input').mkdir();(staging/'output').mkdir();inputs={};total=0
        for name in names:
            raw=read_safe(source,name);total+=len(raw)
            require(total<=256*1024*1024,'invalid_input','Bundle exceeds 256 MiB')
            p=safe_path(staging/'input',name);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
            inputs[name]=hashlib.sha256(raw).hexdigest()
        request={'schema_version':1,'request_id':uid('vendor'),'product':product,'version':version,
                 'operation':operation,'inputs':inputs}
        request['request_hash']=digest(request)
        (staging/'request.json').write_text(json.dumps(request,indent=2))
        require(not dest.exists(),'conflict','Destination appeared')
        staging.rename(dest);return request
    finally:
        if staging.exists():shutil.rmtree(staging)


def collect(bundle,destination):
    root=Path(bundle);request=load(root,'request.json');result=load(root,'result.json')
    validate(result,RESULT)
    require(set(request)=={'schema_version','request_id','request_hash','product','version','operation','inputs'},'invalid_input','Invalid request fields')
    require(digest({k:v for k,v in request.items() if k!='request_hash'})==request['request_hash'],'integrity_error','Request changed')
    for field in ['schema_version','request_id','request_hash','product','version','operation']:
        require(result[field]==request[field],'stale_basis','Result does not match request')
    inputs=request['inputs'];files=result['files']
    require(isinstance(inputs,dict) and 0<len(inputs)<=1000 and 0<len(files)<=1000,'invalid_input','Invalid file manifest')
    for name,h in inputs.items():
        require(hashlib.sha256(read_safe(root/'input',name)).hexdigest()==h,'stale_basis','Input changed')
    actual=set()
    require(not (root/'output').is_symlink(),'invalid_input','Symlink output denied')
    for p in (root/'output').rglob('*'):
        require(not p.is_symlink(),'invalid_input','Symlink denied')
        if p.is_file():actual.add(p.relative_to(root/'output').as_posix())
    require(actual==set(files),'capture_incomplete','Output files differ from manifest')
    for obs in result['observations']:
        require(obs['source_path'] in files,'invalid_input','Observation source is missing')
    dest=Path(destination).absolute();require(not dest.exists(),'conflict','Use a new collection directory')
    dest.parent.mkdir(parents=True,exist_ok=True);staging=Path(tempfile.mkdtemp(prefix='.vendor-',dir=dest.parent))
    try:
        total=0
        for name,h in files.items():
            raw=read_safe(root/'output',name);total+=len(raw)
            require(total<=256*1024*1024,'invalid_input','Bundle exceeds 256 MiB')
            require(hashlib.sha256(raw).hexdigest()==h,'integrity_error','Output changed')
            p=safe_path(staging/'native',name);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
        (staging/'vendor-request.json').write_text(json.dumps(request,indent=2))
        (staging/'vendor-evidence.json').write_text(json.dumps(result,indent=2))
        require(not dest.exists(),'conflict','Destination appeared');staging.rename(dest);return dest
    finally:
        if staging.exists():shutil.rmtree(staging)


def publish(client, collection, key):
    """Capture a checked collection as an artifact, without adopting or replacing a project."""
    from .continuity_adapter import capture_workspace
    root=Path(collection);result=load(root,'vendor-evidence.json');validate(result,RESULT)
    request=load(root,'vendor-request.json')
    require(result['request_hash']==request.get('request_hash') and
            digest({k:v for k,v in request.items() if k!='request_hash'})==request.get('request_hash'),
            'integrity_error','Request binding changed')
    for field in ['product','version','operation','request_id','schema_version']:
        require(result[field]==request.get(field),'integrity_error','Result binding changed')
    expected={name:hashlib.sha256(read_safe(root,name)).hexdigest() for name in ['vendor-request.json','vendor-evidence.json']}
    for name,h in result['files'].items():
        require(hashlib.sha256(read_safe(root/'native',name)).hexdigest()==h,'integrity_error','Collection changed')
        expected['native/'+name]=h
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    require(actual==set(expected),'capture_incomplete','Collection has unlisted files')
    artifact,missing=capture_workspace(client,root,key)
    require(not missing and {n:i['hash'] for n,i in artifact['data']['files'].items()}==expected,
            'capture_incomplete','Captured bytes differ from validated collection')
    return {'artifact':artifact['revision_id'],'coverage':result['coverage'],'adopted':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('catalog')
    p=sub.add_parser('prepare');p.add_argument('--root',required=True);p.add_argument('--file',action='append',required=True)
    p.add_argument('--product',choices=PRODUCTS,required=True);p.add_argument('--version',required=True);p.add_argument('--output',required=True)
    p=sub.add_parser('collect');p.add_argument('--bundle',required=True);p.add_argument('--output',required=True)
    p=sub.add_parser('publish');p.add_argument('--collection',required=True);p.add_argument('--url',required=True)
    p.add_argument('--token-file',required=True);p.add_argument('--key',required=True)
    a=parser.parse_args()
    if a.command=='catalog':print(json.dumps(PRODUCTS,indent=2))
    elif a.command=='prepare':print(json.dumps(prepare(a.root,a.file,a.output,a.product,a.version),indent=2))
    elif a.command=='collect':print(collect(a.bundle,a.output))
    else:
        from .client import Client
        from .continuity_adapter import capture_workspace
        root=Path(a.collection).resolve();token=Path(a.token_file).resolve()
        require(not token.is_relative_to(root),'credential_detected','Credentials must be outside collection')
        # Upload only. Attaching to a development change uses existing checkpoint APIs.
        print(json.dumps(publish(Client(a.url,token.read_text().strip()),root,a.key)))

if __name__=='__main__':main()
