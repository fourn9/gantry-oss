"""Local hardware adapter CLI. Reuses authenticated snapshot/checkpoint APIs."""
import copy
import json
from pathlib import Path
from .model import require
from .store import Store
from .model import digest
from .adapters import artifact_file_parts
from .continuity_adapter import capture_workspace
from .physical_evidence import evaluate
from .requirement_traceability import _subset_refs, REFS
from .contracts import validate


def publish(client, state_id, change_id, version, root, plan_path, key):
    """Pin a saved acceptance plan, capture bytes, evaluate those bytes, checkpoint."""
    Store.safe_name(plan_path)
    from .workflow_journal import freeze, measure
    endpoint = getattr(client, 'url', 'local')
    journal = Path(root).resolve()/'.gantry'/'hardware'/digest([endpoint, key])
    intent = [endpoint, state_id, change_id, version, plan_path]
    def prepare():
        before=client.call('get_development_state',{'state_id':state_id})
        state=before['state']
        listing=client.call('list_development_states',{'session_id':state['session_id']})
        change=next((c for c in listing['changes'] if c['id']==change_id),None)
        require(change and change['head']==state_id and change['version']==version,
                'stale_basis','Change head/version differs; restore the intended state')
        session=client.call('development_state',{'session_id':state['session_id']})['session']
        args=_physical_checkpoint(client,before,root,session['zone'],plan_path,key)
        return {'change_id':change_id,'version':version,**args}
    with measure(journal, 'capture', state_id, key):
        args=freeze(journal, key, intent, prepare)
    with measure(journal, 'publication', state_id, key):
        return client.call('checkpoint_change',args,key+':checkpoint')


def publish_bot(client, task_id, fence, root, plan_path, key):
    """Same adapter via the Bot's fenced, scoped checkpoint capability."""
    ref={'task_id':task_id,'fence':fence}
    client.call('check_bot_task',ref)
    context=client.call('get_bot_task',{'task_id':task_id})
    args=_physical_checkpoint(client,context['development'],root,context['zone'],plan_path,key)
    args.pop('work_status')
    return client.call('checkpoint_bot_task',{**ref,**args},key+':checkpoint')


def _physical_checkpoint(client, before, root, zone, plan_path, key):
    Store.safe_name(plan_path)
    state=before['state']
    artifact,missing=capture_workspace(client,root,key,zone)
    from .continuity_adapter import require_import_files
    require_import_files(before, artifact['data']['files'])
    manifest=artifact['data']['files']; hashes={p:v['hash'] for p,v in manifest.items()}
    require(plan_path in before['manifest'] and plan_path in manifest
            and before['manifest'][plan_path]['hash']==hashes[plan_path],
            'stale_basis','Acceptance plan must already be saved in the input state and remain unchanged')
    def read(name):
        Store.safe_name(name)
        require(name in manifest and manifest[name]['size']<=1024**2,'invalid_input','JSON evidence exceeds 1 MiB or is absent')
        raw=b''.join(artifact_file_parts(client,artifact['revision_id'],name,manifest[name]))
        return json.loads(raw)
    plan=read(plan_path)
    require(isinstance(plan,dict) and set(plan)=={'version','components','checks'} and plan['version']==1
            and isinstance(plan['components'],list) and 1<=len(plan['components'])<=100
            and isinstance(plan['checks'],list) and 1<=len(plan['checks'])<=100,
            'invalid_input','Bounded physical plan v1 required')
    context=copy.deepcopy(state['context'])
    engineering=context.setdefault('environment',{}).setdefault('engineering',{'version':1,'components':[],'checks':[]})
    components={c['id']:c for c in engineering['components']}; checkmap={c['id']:c for c in engineering['checks']}
    ids=set()
    for c in plan['components']:
        require(isinstance(c,dict) and set(c)=={'id','role','assembly','paths'}
                and isinstance(c['id'],str) and c['id'] and c['id'] not in ids
                and isinstance(c['paths'],list) and c['paths'] and all(isinstance(p,str) and p in hashes for p in c['paths']),
                'invalid_input','Distinct component IDs and saved paths required')
        ids.add(c['id'])
        old=components.get(c['id'])
        require(not old or (old['role']==c['role'] and old['assembly']==c['assembly'] and set(old['inputs'])==set(c['paths'])),
                'conflict','Plan cannot silently redefine an existing component')
        components[c['id']]={**(old or {}),'id':c['id'],'role':c['role'],'assembly':c['assembly'],'inputs':{p:hashes[p] for p in c['paths']}}
    check_ids=set()
    for c in plan['checks']:
        require(isinstance(c,dict) and set(c)-{'requirement_refs','source_check'}=={'id','scope','components','required','inputs','report','conditions','evaluator','environment','criteria'}
                and isinstance(c['id'],str) and c['id'] and c['id'] not in check_ids
                and isinstance(c['inputs'],list) and bool(c['inputs']) and all(isinstance(p,str) for p in c['inputs'])
                and isinstance(c['components'],list) and c['components'] and all(isinstance(x,str) and x in components for x in c['components']),
                'invalid_input','Distinct scoped physical checks required')
        check_ids.add(c['id']); Store.safe_name(c['report'])
        old=checkmap.get(c['id'])
        inferred = bool(old and old.get('provenance') == 'mentor_inferred' and not old.get('physical_plan')
            and c.get('source_check') == {'submission_id':old.get('source_submission'),'state_id':old.get('source_state')}
            and old.get('source_submission') and old.get('source_state')
            and all(old.get(k) == c.get(k) for k in ('scope','components','required'))
            and set(old.get('inputs', {})) <= set(c['inputs']))
        require(not old or inferred or old.get('physical_plan')=={'path':plan_path,'sha256':hashes[plan_path]},
                'conflict','Plan cannot overwrite another check definition')
        require(all(set(components[x]['inputs'])<=set(c['inputs']) for x in c['components']),
                'invalid_input','Check must bind every declared component input')
        report=None
        if c['report'] in manifest:
            try: report=read(c['report'])
            except (json.JSONDecodeError,UnicodeDecodeError): pass  # Preserve original malformed bytes; cannot pass.
        validate(c.get('requirement_refs', []), REFS)
        # Only frozen plan links (or unchanged legacy check links) define purpose.
        refs=_subset_refs(context.get('requirement_refs', []),
                          c.get('requirement_refs', (old or {}).get('requirement_refs', [])))
        require(not old or old.get('requirement_refs', []) == refs,
                'conflict', 'Requirement mapping changed; save a reassessed check in a new state first')
        result=evaluate({**c, 'requirement_refs': refs},report,hashes)
        checkmap[c['id']]={k:c[k] for k in ('id','scope','components','required')}
        if old and old.get('source_submission'):
            checkmap[c['id']].update({k:copy.deepcopy(old[k]) for k in ('source_submission','source_state','source_evidence','provenance') if k in old})
        checkmap[c['id']].update(requirement_refs=refs,status=result['status'],inputs={**result['inputs'],plan_path:hashes[plan_path]},
            evidence={c['report']:hashes[c['report']]} if c['report'] in manifest else {},
            physical_plan={'path':plan_path,'sha256':hashes[plan_path]},physical_result=result)
    engineering.update(components=list(components.values()),checks=list(checkmap.values()))
    unfinished=[x for x in state['unfinished'] if x not in {'physical-check:'+i for i in check_ids}]
    unfinished+=['physical-check:'+c['id'] for c in checkmap.values() if c['required'] and c['status']!='pass']
    return {
        'snapshot':artifact['revision_id'],'summary':'Hardware candidate and physical evidence captured',
        'rationale':'Compare captured reports against the unchanged acceptance plan',
        'unfinished':sorted(set(unfinished)),'work_status':'paused','context':context,
        'capture':{'scope':'saved CAD/code and external physical reports','missing':missing+['unsaved edits','independent physical certification']}}


def screen_report(root, request, check):
    """Run actual static CAD screening and emit the common measurement envelope."""
    import hashlib
    import cadquery as cq
    from .cad_screen import screen
    from .cad_io import source
    root=Path(root).resolve()
    require(request.get('unit')=='mm','invalid_input','Hardware screening uses millimeters')
    require(isinstance(check.get('inputs'),list) and check['inputs'],'invalid_input','Pinned check inputs required')
    hashes={}
    for name in check['inputs']:
        Store.safe_name(name)
        path=root/name
        require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root)
                and path.stat().st_size<=100*1024**2,'scope_denied','Bounded local input required')
        hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
        source(root,name,hashes[name])
    raw=screen(root,request)
    require(all(p['path'] in hashes and p['sha256']==hashes[p['path']] for p in raw['sources']),
            'stale_basis','All screened CAD inputs must be declared by the check')
    for name,h in hashes.items():source(root,name,h)
    return {'status':'completed','inputs':hashes,'requirement_refs':copy.deepcopy(check.get('requirement_refs', [])),
        'conditions':{'unit':'mm','frame':request['frame'],'clearance':request['clearance'],
            'overlap_tolerance':request['overlap_tolerance'],'pairs':request['pairs'],
            'parts':{p['id']:p['path'] for p in request['parts']}},
        'evaluator':{'name':'gantry.cad-screen','version':'1'},'environment':{'cadquery':cq.__version__},
        'measurements':{'violating_pairs':{'value':sum(not p['clearance_satisfied'] for p in raw['pairs']),'unit':'count'}},
        'limitations':raw['limitations'],'raw':raw}


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__); sub=parser.add_subparsers(dest='command',required=True)
    edit=sub.add_parser('edit'); edit.add_argument('--root',required=True);edit.add_argument('--request',required=True);edit.add_argument('--output',required=True)
    screen_parser=sub.add_parser('screen')
    for name in ('root','request','plan','check-id','output'):screen_parser.add_argument('--'+name,required=True)
    publish_parser=sub.add_parser('publish')
    for name in ('root','state-id','change-id','plan','key','url','token-file'):publish_parser.add_argument('--'+name,required=True)
    publish_parser.add_argument('--version',required=True,type=int)
    args=parser.parse_args()
    if args.command=='edit':
        from .cad_io import edit as run
        result=run(args.root,json.loads(Path(args.request).read_text()),args.output)
    elif args.command=='screen':
        plan=json.loads(Path(args.plan).read_text()); check=next((c for c in plan['checks'] if c['id']==args.check_id),None)
        require(check is not None,'not_found','Check ID not in plan')
        result=screen_report(args.root,json.loads(Path(args.request).read_text()),check)
        with Path(args.output).open('x') as f:json.dump(result,f,indent=2)
    else:
        from .client import Client
        result=publish(Client(args.url,Path(args.token_file).read_text().strip()),args.state_id,args.change_id,
                       args.version,args.root,args.plan,args.key)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
