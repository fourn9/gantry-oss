"""Customer-local engineering workflow over existing authenticated Core APIs."""
import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path
from .model import canonical, digest, require
from .physical_execution import read
from .workflow_journal import connect, freeze, measure


def local(root):
    path=Path(root).resolve()/'.gantry'/'engineering'
    connect(path).close()
    return path


def save(path, value):
    path=Path(path)
    require(not path.is_symlink(),'scope_denied','Metadata cannot be a symlink')
    fd,tmp=tempfile.mkstemp(prefix='.workflow-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as f: f.write(canonical(value)); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def link(client, root):
    value=json.loads(read(local(root),'connection.json',1024**2))
    require(value['endpoint']==getattr(client,'url','local'),'conflict','Workspace belongs to another Gantry endpoint')
    return value


def advance(client, root, result):
    value=link(client,root)
    require(value['change_id']==result['change']['id'],'conflict','Another change owns this workspace')
    if value['version']<=result['change']['version']:
        value.update(state_id=result['state']['id'],version=result['change']['version'])
        save(local(root)/'connection.json',value)
    return result


def checkout(client, state_id, destination, title, purpose, scope, assignee, key):
    from .continuity_adapter import restore_development_state
    destination=Path(destination).absolute()
    intent={'state_id':state_id,'title':title,'purpose':purpose,'scope':scope,'assignee':assignee,
            'endpoint':getattr(client,'url','local'),'key':key}
    connection=destination/'workspace'/'.gantry'/'engineering'/'connection.json'
    if connection.is_file():
        value=link(client,destination/'workspace')
        require(value['checkout_intent']==intent,'conflict','Existing workspace has another checkout intent')
        return {'workspace':str(destination/'workspace'),**value}
    if not (destination/'context.json').is_file():
        restore_development_state(client,state_id,destination,key+':restore')
    else:
        saved=json.loads(read(destination,'context.json',16*1024**2))
        require(saved['state']['id']==state_id,'conflict','Restore destination belongs to another state')
    root=destination/'workspace'; journal=local(root)
    args=freeze(journal,'checkout',intent,lambda:{'state_id':state_id,'title':title,'purpose':purpose,
        'write_scope':scope,'dependencies':[],'assignee':assignee})
    change=client.call('begin_change',args,key+':begin')
    value={'endpoint':getattr(client,'url','local'),'state_id':state_id,'change_id':change['id'],
           'version':change['version'],'checkout_intent':intent}
    save(journal/'connection.json',value)
    return {'workspace':str(root),**value}


def status(client, root):
    value=link(client,root)
    view=client.call('get_development_state',{'state_id':value['state_id']})
    changed=[]
    for name,info in view['manifest'].items():
        try: same=hashlib.sha256(read(root,name)).hexdigest()==info['hash']
        except (OSError,ValueError): same=False
        except Exception as exc:
            if getattr(exc,'code',None)!='scope_denied': raise
            same=False
        if not same: changed.append(name)
    return {**value,'local_changes':changed,'development':view,
            'limitations':['Local changes lists saved tracked files; new files are collected at publication.',
                           'Opening status does not resume an external process.']}


def bind_mapping(client, root, mapping_path, reason, key):
    from .continuity_adapter import capture_workspace
    from .engineering_context import assess
    raw=read(root,mapping_path,1024**2); mapping=json.loads(raw)
    require(isinstance(mapping,dict) and set(mapping)=={'version','components','dependencies'}
            and mapping['version']==1 and isinstance(mapping['components'],list)
            and 1<=len(mapping['components'])<=100,'invalid_input','Explicit engineering mapping v1 required')
    require(isinstance(reason,str) and reason.strip(),'invalid_input','Reassessment reason required')
    info=link(client,root); journal=local(root)
    intent=[info['endpoint'],mapping_path,hashlib.sha256(raw).hexdigest(),reason]
    def prepare():
        before=client.call('get_development_state',{'state_id':info['state_id']})
        session=client.call('development_state',{'session_id':before['state']['session_id']})['session']
        artifact,missing=capture_workspace(client,root,key,session['zone'])
        from .continuity_adapter import require_import_files
        require_import_files(before,artifact['data']['files'])
        manifest=artifact['data']['files']; components=[]
        for c in mapping['components']:
            require(isinstance(c,dict) and set(c)<={'id','role','assembly','paths','native_refs'}
                    and {'id','role','assembly','paths'}<=set(c) and isinstance(c['paths'],list)
                    and c['paths'] and all(isinstance(p,str) and p in manifest for p in c['paths']),
                    'invalid_input','Component identity and captured source paths required')
            components.append({k:v for k,v in c.items() if k!='paths'}|
                              {'inputs':{p:manifest[p]['hash'] for p in c['paths']}})
        by_id={c['id']:c for c in components}; edges=[]
        require(isinstance(mapping['dependencies'],list) and len(mapping['dependencies'])<=1000,
                'invalid_input','Bounded dependency list required')
        for e in mapping['dependencies']:
            require(isinstance(e,dict) and set(e)=={'dependent','prerequisite','kind','status','rationale'}
                    and isinstance(e['prerequisite'],str) and e['prerequisite'] in by_id,
                    'invalid_input','Explicit known prerequisite required')
            edges.append({**e,'inputs':by_id[e['prerequisite']]['inputs']})
        context=copy.deepcopy(before['state']['context'])
        engineering=context['environment'].setdefault('engineering',{'version':1,'checks':[]})
        engineering.update(components=components,dependencies=edges)
        assess(context,manifest)
        return {'change_id':info['change_id'],'version':info['version'],'snapshot':artifact['revision_id'],
            'summary':'Cross-tool mapping reassessed','rationale':reason,'unfinished':before['state']['unfinished'],
            'work_status':'paused','context':context,'capture':{'scope':'saved sources and explicit mapping','missing':missing}}
    with measure(journal,'capture',info['state_id'],key): args=freeze(journal,'mapping:'+key,intent,prepare)
    with measure(journal,'publication',info['state_id'],key):
        result=client.call('checkpoint_change',args,key+':mapping-checkpoint')
    return advance(client,root,result)


def publish(client, root, plan_path, key):
    from .hardware import publish as physical_publish
    info=link(client,root); journal=local(root)
    args=freeze(journal,'publish:'+key,[info['endpoint'],plan_path],lambda:info)
    result=physical_publish(client,args['state_id'],args['change_id'],args['version'],root,plan_path,key)
    return advance(client,root,result)


def checkpoint(client, root, summary, reason, key):
    from .continuity_adapter import capture_workspace
    info=link(client,root); journal=local(root)
    def prepare():
        before=client.call('get_development_state',{'state_id':info['state_id']})
        session=client.call('development_state',{'session_id':before['state']['session_id']})['session']
        artifact,missing=capture_workspace(client,root,key,session['zone'])
        from .continuity_adapter import require_import_files
        require_import_files(before,artifact['data']['files'])
        return {'change_id':info['change_id'],'version':info['version'],'snapshot':artifact['revision_id'],
            'summary':summary,'rationale':reason,'unfinished':before['state']['unfinished'],'work_status':'paused',
            'capture':{'scope':'saved files at checkpoint','missing':missing+['unsaved tool state']}}
    with measure(journal,'capture',info['state_id'],key):
        args=freeze(journal,'checkpoint:'+key,[info['endpoint'],summary,reason],prepare)
    with measure(journal,'publication',info['state_id'],key):
        result=client.call('checkpoint_change',args,key+':file-checkpoint')
    return advance(client,root,result)


def capture(client, root, bundle, key):
    from .integrations.publication import publish as publish_bundle
    info=link(client,root); journal=local(root)
    args=freeze(journal,'capture:'+key,[info['endpoint'],str(Path(bundle).resolve())],lambda:info)
    with measure(journal,'publication',info['state_id'],key):
        result=publish_bundle(client,args['state_id'],args['change_id'],args['version'],bundle,key)
    return advance(client,root,result)
