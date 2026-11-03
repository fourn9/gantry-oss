"""Customer-PC saved-file connection to Studio. No editor execution or implicit sharing."""
import os
from pathlib import Path
import time
from .connection_policy import safe_path, covered
from .continuity_adapter import restore_development_state
from .model import require, uid, digest, Fault
from .project_connect import private_dir, save, load, locked, sync_dir
from .project_files import inventory


def changes(before, after):
    return [{'path':p,'kind':'added' if p not in before else 'deleted' if p not in after else 'modified'}
            for p in sorted(set(before)|set(after)) if before.get(p)!=after.get(p)]


def scan(root, scopes):
    require(isinstance(scopes,list) and 0<len(scopes)<=12000,'invalid_input','Explicit path list required (1–12000 entries)')
    for p in scopes: safe_path(p, True)
    try:
        files, hashes, missing=inventory(root,scopes)
        if any(m['reason']=='capture_incomplete' for m in missing): raise Fault('capture_incomplete','Use streaming capture')
    except Fault as exc:
        if exc.code!='capture_incomplete': raise
        from .workspace_stream import inspect
        hashes,missing=inspect(root,scopes)
        files=None
    failures=[]
    for item in missing:
        p=item['path']
        if item['reason']=='excluded_directory': continue
        # Match scopes without validating an unsafe filename a second time.
        if p=='.' or any(p==s or (s.endswith('/') and p.startswith(s)) or s.startswith(p+'/') for s in scopes):
            failures.append(item)
    require(not failures,'capture_incomplete','Unreadable, linked, unstable or sensitive scoped files; no checkpoint created',missing=failures)
    return files,hashes,missing


class Workspace:
    def __init__(self,client,root):
        self.client=client;self.root=Path(root).resolve()
        require(self.root.is_dir(),'invalid_input','Workspace directory must exist')
        self.meta=private_dir(self.root/'.gantry')
        sync_dir(self.root)
        # Keep queued source bytes/connection metadata out of any Git commit.
        save_ignore=self.meta/'.gitignore'
        require(not save_ignore.is_symlink() and (not save_ignore.exists() or save_ignore.stat().st_nlink==1),
                'scope_denied','Private ignore file must not be linked')
        if not save_ignore.exists() or save_ignore.read_text()!='*\n':
            with save_ignore.open('w') as f: os.chmod(save_ignore,0o600);f.write('*\n')
        self.path=self.meta/'studio-workspace.json'
        self.endpoint=getattr(client,'url','local-test')

    def saved(self):
        obj=load(self.path)
        require(obj['root']==str(self.root) and obj['endpoint']==self.endpoint,'scope_denied','Workspace is bound to another directory or server')
        return obj

    def bind(self,work_id):
        with locked(self.meta/'studio.lock'):
            if self.path.exists():
                obj=self.saved();require(obj['work_id']==work_id,'conflict','Directory is bound to another work; use a new directory')
                return {'work_id':work_id,'state_id':obj['state_id'],'status':'connected'}
            view=self.client.call('studio_work',{'work_id':work_id})
            require(view['can_update'],'unauthorized','Only a work author or assignee may connect; continue into your own work')
            state=view['selected'];scope=sorted(set(list(state['manifest'])+view['work']['write_scope']))
            scan(self.root,scope)
            obj={'root':str(self.root),'endpoint':self.endpoint,'work_id':work_id,'state_id':state['state']['id'],
                'version':view['work']['version'],'scope':scope,'write_scope':view['work']['write_scope'],
                'hashes':{p:i['hash'] for p,i in state['manifest'].items()},'pending':None,'last_error':None}
            save(self.path,obj)
            return {'work_id':work_id,'state_id':obj['state_id'],'status':'connected'}

    def status(self):
        obj=self.saved();_,hashes,missing=scan(self.root,obj['scope'])
        view=self.client.call('studio_work',{'work_id':obj['work_id']})
        delta=changes(obj['hashes'],hashes)
        return {'work_id':obj['work_id'],'state_id':obj['state_id'],'version':obj['version'],
            'remote_state':view['work']['head'],'remote_changed':view['work']['head']!=obj['state_id'],
            'changes':delta,'outside_scope':[d['path'] for d in delta if not covered(d['path'],obj['write_scope'])],
            'pending':bool(obj['pending']),'cleanup_pending':bool(obj.get('cleanup_stage')),
            'last_error':obj.get('last_error'),'missing':missing,
            'capture':'Saved files only; no unsaved CAD/editor operations', 'sharing':view['selected']['status']['sharing']}

    def _cleanup(self,obj,path=None):
        if not obj.get('cleanup_stage'):return
        from .workspace_stream import cleanup
        try:cleanup(self.meta,obj['cleanup_stage'])
        except (OSError,Fault):return  # Acknowledged work remains successful; retry cleanup on next sync.
        obj.pop('cleanup_stage');save(path or self.path,obj)

    def _send(self,obj):
        p=obj['pending']
        try:
            if p.get('stage') and 'snapshot' not in p['args']:
                from .workspace_stream import upload
                p['args']['snapshot']=upload(self.client,p['stage'],p['base'],p['hashes'],p['key'],p['zone'])
                save(self.path,obj)
            result=self.client.call(p['command'],p['args'],p['key'])
        except Exception as exc:
            obj['last_error']=exc.code if isinstance(exc,Fault) else type(exc).__name__;save(self.path,obj);raise
        obj.update(version=result['change']['version'],state_id=result['change']['head'],
                   hashes=p['hashes'],pending=None,last_error=None,last_sync=time.time())
        if p.get('stage'):obj['cleanup_stage']=p['stage']
        save(self.path,obj)
        self._cleanup(obj)
        return {'status':'shared' if p['command']=='studio_share_update' else 'captured',
                'work_id':obj['work_id'],'state_id':obj['state_id'],'version':obj['version'],
                'cleanup_pending':bool(obj.get('cleanup_stage'))}

    def sync(self,summary='Saved external edits',rationale='External tool save; intent not inferred',unfinished=None,context=None):
        with locked(self.meta/'studio.lock'):
            obj=self.saved()
            from .workspace_stream import recover_staging
            recover_staging(self.meta,'workspace-sync',[(obj.get('pending') or {}).get('stage'),obj.get('cleanup_stage')])
            if obj['pending']: return self._send(obj)
            self._cleanup(obj)
            require(not obj.get('cleanup_stage'),'cleanup_pending','Retry sync after local staging can be safely removed')
            files,hashes,missing=scan(self.root,obj['scope'])
            _,second,_=scan(self.root,obj['scope'])
            require(hashes==second,'capture_incomplete','Workspace is still being saved; retry')
            view=self.client.call('studio_work',{'work_id':obj['work_id']})
            require(view['work']['head']==obj['state_id'],'stale_basis','Remote work changed; inspect or continue in a new folder')
            require(view['can_update'],'unauthorized','Work is no longer writable')
            # Sharing the same immutable head does not invalidate local inputs.
            obj['version']=view['work']['version']
            delta=changes(obj['hashes'],hashes)
            require(all(covered(d['path'],obj['write_scope']) for d in delta),'scope_denied','Read-only dependency changed; start a work with the correct scope')
            if not delta and (context is None or context==view['selected']['state']['context']):
                save(self.path,obj);return {'status':'up_to_date','state_id':obj['state_id']}
            args={'work_id':obj['work_id'],'version':obj['version'],'expected_state':obj['state_id'],
                'files':{d['path']:files[d['path']] for d in delta if d['kind']!='deleted'} if files is not None else {},
                'deleted':[d['path'] for d in delta if d['kind']=='deleted'],'summary':summary,'rationale':rationale,
                'unfinished':unfinished if unfinished is not None else view['selected']['state']['unfinished'],
                'missing':[m['reason']+':'+m['path'] for m in missing],
                **({'context':context} if context is not None else {})}
            from .contracts import CONTRACTS, validate
            validate(args,CONTRACTS['studio_sync_update']['schema'])
            obj['pending']={'command':'studio_sync_update','args':args,'key':uid('workspace-sync'),'hashes':hashes}
            if files is None:
                from .workspace_stream import freeze
                pending=obj['pending'];args['deleted']=[]
                pending.update(stage=freeze(self.root,obj['scope'],hashes,self.meta/'uploads'/pending['key'],
                    {d['path'] for d in delta if d['kind']!='deleted'}),
                    base={'snapshot':view['selected']['state']['snapshot'],'manifest':view['selected']['manifest']},
                    zone=self.client.call('development_state',{'session_id':view['work']['session_id']})['session']['zone'])
            save(self.path,obj);return self._send(obj)

    def share(self,note=''):
        with locked(self.meta/'studio.lock'):
            obj=self.saved()
            if obj['pending']:
                require(obj['pending']['command']=='studio_share_update','conflict','Finish pending sync before sharing')
                return self._send(obj)
            view=self.client.call('studio_work',{'work_id':obj['work_id']})
            require(view['work']['head']==obj['state_id'],'stale_basis','Remote work advanced')
            require(view['can_update'],'unauthorized','Work is no longer writable')
            obj['version']=view['work']['version']
            _,hashes,_=scan(self.root,obj['scope'])
            require(hashes==obj['hashes'],'stale_basis','Sync local changes before sharing')
            if view['work']['sharing']=='shared':
                save(self.path,obj);return {'status':'shared','state_id':obj['state_id']}
            obj['pending']={'command':'studio_share_update','key':uid('workspace-share'),'hashes':hashes,
                'args':{'work_id':obj['work_id'],'version':obj['version'],'state_id':obj['state_id'],'note':note}}
            save(self.path,obj);return self._send(obj)


def continue_workspace(client,work_id,state_id,destination,title,write_scope=None,dependencies=None):
    view=client.call('studio_work',{'work_id':work_id,'state_id':state_id})
    actor=client.call('identity')['id']
    key='continue:'+digest([getattr(client,'url','local-test'),actor,work_id,state_id,str(Path(destination).absolute()),title,write_scope,dependencies])
    intent=Path(destination)/'continuation.json'
    if intent.exists():
        saved=load(intent);require(saved['key']==key,'conflict','Destination belongs to another continuation')
        result=saved['restore']
    else:
        result=restore_development_state(client,state_id,destination,key+':restore')
        save(intent,{'key':key,'restore':result})
    change=client.call('begin_change',{'state_id':state_id,'title':title,'purpose':'Continue '+view['work']['title'],
        'write_scope':write_scope if write_scope is not None else view['work']['write_scope'],
        'dependencies':dependencies if dependencies is not None else view['work'].get('dependencies',[]),'assignee':actor},key+':begin')
    w=Workspace(client,result['workspace']);binding=w.bind(change['id'])
    return {**result,**binding,'source_work':work_id,'source_state':state_id,'status':'ready_to_continue'}


def import_workspace(client,root,manifest,apply=False):
    """Preview is read-only on the server. Apply queues the exact validated saved bytes."""
    from .contracts import CONTRACTS, validate
    require(isinstance(manifest,dict) and 'paths' in manifest,'invalid_input','Manifest needs explicit paths')
    scopes=manifest['paths'];files,hashes,missing=scan(root,scopes)
    args={k:v for k,v in manifest.items() if k!='paths'}
    args.update(files=files or {},missing=sorted(set(manifest.get('missing',[])+[m['reason']+':'+m['path'] for m in missing])))
    validate(args,CONTRACTS['studio_import_project']['schema'])
    preview={'files':list(hashes),'hashes':hashes,'missing':args['missing'],
             'components':args['hierarchy'],'write_scope':args['write_scope'],'sent':False}
    if not apply: return preview
    w=Workspace(client,root)
    with locked(w.meta/'studio-import.lock'):
        journal=w.meta/'studio-import.json'
        intent={'endpoint':w.endpoint,'root':str(w.root),'manifest':manifest}
        if journal.exists():
            pending=load(journal)
            require(pending['intent']==intent,'conflict','A different import is recorded; use a new directory')
        else:pending=None
        from .workspace_stream import recover_staging
        recover_staging(w.meta,'workspace-import',[(pending or {}).get('stage'),(pending or {}).get('cleanup_stage')])
        if pending is None:
            _,second,_=scan(root,scopes)
            require(hashes==second,'capture_incomplete','Workspace changed during import')
            require(not w.path.exists(),'conflict','Already connected; use sync for saved changes')
            pending={'intent':intent,'args':args,'key':uid('workspace-import')}
            if files is None:
                from .workspace_stream import freeze
                pending.update(stage=freeze(root,scopes,hashes,w.meta/'uploads'/pending['key']),hashes=hashes)
            save(journal,pending)
        if 'result' not in pending:
            if pending.get('stage') and 'snapshot' not in pending['args']:
                from .workspace_stream import upload
                pending['args']['snapshot']=upload(client,pending['stage'],None,pending['hashes'],pending['key'],args.get('zone','root'))
                save(journal,pending)
            pending['result']=client.call('studio_import_project',pending['args'],pending['key']);save(journal,pending)
        result=pending['result'];w.bind(result['change']['id'])
        # No queued source bytes after confirmed import; native copies remain in the ledger.
        pending.pop('args',None)
        if pending.get('stage'):pending['cleanup_stage']=pending.pop('stage')
        save(journal,pending);w._cleanup(pending,journal)
        return {'project_id':result['project']['id'],'work_id':result['change']['id'],
                'state_id':result['state']['id'],'status':'connected','sent':True}


def watch_workspace(workspace,interval=2,iterations=0):
    """Two equal scoped observations debounce saves; errors never become deletions."""
    require(0.25<=interval<=60 and iterations>=0,'invalid_input','Interval 0.25–60 seconds; iterations >= 0')
    previous=None;count=0
    while not iterations or count<iterations:
        count+=1
        try:
            obj=workspace.saved()
            if obj['pending']:
                result=workspace.sync()
            else:
                _,hashes,_=scan(workspace.root,obj['scope']);fingerprint=digest(hashes)
                result=workspace.sync() if fingerprint==previous else {'status':'settling'}
                previous=fingerprint
            yield result
        except (Fault,OSError) as exc:
            code=exc.code if isinstance(exc,Fault) else 'connection_error'
            previous=None
            yield {'status':'held' if code in {'stale_basis','scope_denied','unauthorized'} else 'retry_pending','error':code}
            if code in {'stale_basis','scope_denied','unauthorized'}: return
        if not iterations or count<iterations: time.sleep(interval)
