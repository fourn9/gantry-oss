"""Selected JSON values from immutable bytes, not inferred engineering semantics."""
import json
import math
import re
from .model import Fault, require
from .connection_policy import SECRET


def extract(service, s, actor, a, fx, n, con):
    service.allowed(actor, 'record')
    state=service._continuity_state(s,actor,a['state_id'])
    manifest=service._manifest(s,state['snapshot']); info=manifest.get(a['path'])
    require(info and info['size']<=1024**2,'invalid_input','Saved JSON source up to 1 MiB required')
    raw=b''.join(service.store.verified_parts(info))
    def pairs(items):
        result={}
        for k,v in items:
            require(k not in result,'invalid_input','Duplicate JSON key')
            result[k]=v
        return result
    def constant(value): raise Fault('invalid_input','Nonfinite JSON constant')
    try: data=json.loads(raw,object_pairs_hook=pairs,parse_constant=constant)
    except (ValueError,UnicodeError,RecursionError) as exc: raise Fault('invalid_input','Valid bounded JSON required') from exc
    require(not SECRET.search(json.dumps(data).encode()),'credential_detected','Potential credential; content not retained')
    sources=[];fields=[];missing=[]
    for item in a['fields']:
        pointer=item['pointer']
        require(pointer=='' or pointer.startswith('/'),'invalid_input','JSON pointer must be empty or start with slash')
        require(not re.search(r'~(?![01])',pointer),'invalid_input','Invalid JSON pointer escape')
        value=data
        for part in ([] if pointer=='' else pointer[1:].split('/')):
            key=part.replace('~1','/').replace('~0','~')
            if isinstance(value,list):
                require(bool(re.fullmatch(r'0|[1-9][0-9]*',key)),'invalid_input','Canonical array index required')
                value=value[int(key)] if len(key)<10 and int(key)<len(value) else None
            elif isinstance(value,dict):value=value.get(key)
            else:value=None
        require(value is None or type(value) in (str,int,float,bool),'invalid_input','Select scalar fields, not entire documents')
        require(type(value) is not float or math.isfinite(value),'invalid_input','Finite numeric field required')
        sources.append({'revision_id':state['snapshot'],'path':a['path'],'sha256':info['hash'],'locator':pointer or 'whole-document'})
        fields.append({k:v for k,v in item.items() if k!='pointer'} | {'value':value,
            'classification':'unknown' if value is None else 'declared','source_index':len(sources)-1,
            'method':'json-pointer/v1; source value extracted; units/frame/time supplied by caller'})
        if value is None:missing.append(item['name']+': missing or null at '+pointer)
    return service.cmd_record_evidence_view(s,actor,{
        'state_id':state['id'],'subject_id':a['subject_id'],'profile':a['profile'],
        'extractor':'saved-json-pointer/v1','sources':sources,'fields':fields,'missing':missing,
        'extensions':{'coverage':'selected scalar pointers only','unselected_native_data':'preserved in source artifact',
            'semantics':'caller-declared units/frame/time; not physical verification'}},fx,n,con)
