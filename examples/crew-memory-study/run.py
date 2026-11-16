"""Private-case, three-Bot memory-availability study. Never publish raw outputs.

Both conditions retain learning/reflection. Only imported prior notes differ.
No engineering choices, evaluator repairs, or response retries are made here.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import sys
import threading
import time
import uuid

from gantry.adapters import restore_files
from gantry.agent_connection import PROFILES
from gantry.bot_worker import BotWorker, environment_manifest
from gantry.connection_policy import safe_path, clean_bytes, MAX_TOTAL, MAX_FILES
from gantry.development import in_scope
from gantry.crew_observe import observation_actions
from gantry.crew_experiment_timing import summarize as summarize_timing
from gantry.learning_evaluation_case import environment
from gantry.learning_evaluation_setup import LocalClient, profile
from gantry.model import Fault, canonical, digest, require
from gantry.monthly_codex import infer_monthly
from gantry.physical_evidence import evaluate
from gantry.project_sandbox import backend, execute, runtime_roots
from gantry.runner import persist
from gantry.service import Service, token_hash

BOTS=('lead','mechanical','control')
TERMINAL={'completed','failed','blocked','cancelled'}
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def load_case(path):
    case=json.loads(Path(path).read_text())
    required={'name','files','manifest','goal','acceptance','roles','tools','dependencies','experiences','final_verifier'}
    require(required<=set(case) and set(case)<=required|{'tool_evidence','audit_report','required_worker_bots'},'invalid_input','Unexpected case fields')
    require(set(case.get('required_worker_bots',[]))<=set(BOTS)-{'lead'},'invalid_input','Unknown required worker')
    require(set(case['roles'])==set(BOTS),'invalid_input','Exactly three explicit Bot roles required')
    require(0<len(case['files'])<=MAX_FILES and set(case['files'])==set(case['manifest']),'invalid_input','Exact bounded manifest required')
    total=0
    for name,value in case['files'].items():
        safe_path(name);raw=clean_bytes(base64.b64decode(value,validate=True));total+=len(raw)
        require(sha(raw)==case['manifest'][name],'stale_fixture','File hash mismatch')
    require(total<=MAX_TOTAL,'capture_incomplete','Fixture exceeds artifact limit')
    for role in case['roles'].values():
        require(set(role)=={'responsibilities','onboarding','write_scope'},'invalid_input','Explicit role contracts required')
        for name in role['write_scope']:safe_path(name,True)
    scope=case['roles']['lead']['write_scope']
    for role in case['roles'].values():
        require(all(in_scope(p,scope) for p in role['write_scope']),'scope_denied','Child scope exceeds lead scope')
    for name in case['dependencies']:safe_path(name);require(name in case['files'],'invalid_input','Missing dependency')
    require(case['final_verifier'] in case['tools'],'invalid_input','Missing final verifier')
    for tool in case['tools'].values():
        argv=tool['argv'];require(len(argv)==3 and argv[1]=='-B' and Path(argv[0]).resolve()==Path(sys.executable).resolve(),
            'invalid_input','Use this Python and one saved script, without shell arguments')
        safe_path(argv[2]);require(argv[2] in case['files'],'invalid_input','Tool script must be frozen')
        require(type(tool['timeout_seconds'])==int and 1<=tool['timeout_seconds']<=300,'invalid_input','Bounded tool timeout required')
    verifier=case['tools'][case['final_verifier']]['argv'][2]
    require(not in_scope(verifier,scope),'scope_denied','Final verifier must be read-only')
    for note in case['experiences']:
        require(set(note)=={'bot_id','observation','applicability','limitations','source'} and note['bot_id'] in BOTS,
            'invalid_input','Explicit sourced prior experience required')
    for mapping in case.get('tool_evidence',{}).values():
        plan=mapping['plan_path'];safe_path(plan)
        require(plan in case['files'] and not in_scope(plan,scope),'scope_denied','Frozen evidence plan required')
    if case.get('audit_report'):safe_path(case['audit_report'])
    return case


def approve(owner,changes):
    p=owner.call('propose',{'title':'Isolated experiment delegation','changes':changes});ref={'proposal_id':p['id'],'version':p['version']}
    owner.call('submit',ref);owner.call('endorse',{**ref,'reason':'User-authorized study setup'})
    owner.call('review_adoption',{**ref,'verdict':'approve','reason':'Identity only; no engineering adoption'})
    owner.call('commit',ref)


def assignment(case,sid,state,bot,title,scope=None):
    return {'session_id':sid,'bot_id':bot,'state_id':state,'kind':'develop','title':title,
        'completion':case['acceptance'],'write_scope':scope if scope is not None else case['roles'][bot]['write_scope'],
        'dependencies':case['dependencies'],'after_tasks':[]}


def setup(root,case,condition,model,seconds):
    require(condition in {'cold','recall'},'invalid_input','Unknown memory condition')
    service=Service(root/'ledger');owner=LocalClient(service,service.bootstrap()['token'])
    persist(root/'owner-private.json',{'token':owner.token});clients={};configs={}
    for bot in BOTS:
        token=secrets.token_urlsafe(32)
        approve(owner,[{'id':bot,'type':'principal','data':{'kind':'agent','permissions':['read','record','work'],
            'zones':['root'],'allowed_commands':sorted(PROFILES['bot']),'token_hash':token_hash(token)}}])
        clients[bot]=LocalClient(service,token);persist(root/(bot+'-private.json'),{'token':token})
    snapshot=owner.call('capture_artifact',{'files':case['files']})['revision_id']
    scope=case['roles']['lead']['write_scope']
    session=owner.call('connect_development',{'title':case['name'],'snapshot':snapshot,'requirements':case['acceptance'],
        'constraints':['Preserve read-only requirements, evaluator and safety premises. No physical operation, purchase or formal adoption.'],
        'capture':{'scope':'Explicit frozen project files','missing':['Unselected external services and physical measurements']},
        'unverified':['Physical safety and real-world performance'],'mode':'execute','actors':list(BOTS),'write_scope':scope,
        'recipes':{},'max_executions':None,'max_parallel':3,'timeout_seconds':min(3600,seconds)})
    state=owner.call('initialize_continuity',{'session_id':session['id'],'version':session['version'],
        'hierarchy':[{'id':'assembly','title':'Selected subsystem','kind':'subsystem','paths':list(case['files']),'editable':True}],
        'context':{'requirements':case['acceptance'],'requirement_refs':[],'constraints':['Frozen acceptance; no formal adoption'],
            'decisions':[],'open_questions':['Physical behavior remains unverified'],'environment':{'sandbox':backend()}},
        'summary':'Preserved existing project state; selected development gap remains unresolved'})
    sid=session['id'];owner.call('configure_organization',{'organization_id':'study','version':0,'name':'Study organization',
        'profile':profile(),'enabled':True,'share_reflections':True})
    for bot in BOTS:
        p=profile();p.update(mission=case['goal'],responsibilities=case['roles'][bot]['responsibilities'],
            onboarding=case['roles'][bot]['onboarding'],focus_paths=case['roles'][bot]['write_scope'])
        owner.call('configure_bot',{'bot_id':bot,'organization_id':'study','version':0,'name':bot,'parent_bot_id':None if bot=='lead' else 'lead','profile':p,'enabled':True})
    owner.call('configure_bot_project',{'session_id':sid,'organization_id':'study','version':0,'goal':case['goal'],
        'acceptance':case['acceptance'],'lead_bot_id':'lead','enabled':True})
    for bot in BOTS:
        owner.call('bind_development_bot',{'session_id':sid,'bot_id':bot,'principal_id':bot,'version':0,
            'write_scope':case['roles'][bot]['write_scope'],'can_assign':bot=='lead','can_integrate':bot=='lead','enabled':True})
        cfg={'bot_id':bot,'name':bot,'backend':'codex_subscription','workflow':'bot_development','agent_loop':True,
            'experience_learning':True,'learning_mode':'always','personal_continuity':True,
            'environment_definition':{'model':model,'reasoning_effort':'low','scope':'Frozen development study'},
            'local_tools':case['tools'],'tool_evidence':case.get('tool_evidence',{}),'tool_runtime':runtime_roots(),'sandbox':backend()}
        configs[bot]=cfg;owner.call('configure_bot_runtime',{'bot_id':bot,'version':0,'principal_id':bot,'enabled':True,'environment':environment_manifest(cfg)})
    imported=[]
    def no_inference(*args):raise AssertionError('Context import must not invoke a model')
    for bot in BOTS:
        seed=owner.call('assign_bot_task',assignment(case,sid,state['id'],bot,'Import declared historical context',[]))
        with BotWorker(clients[bot],configs[bot],root/'setup-journals',no_inference) as worker:
            claim=clients[bot].call('claim_bot_task',{'task_id':seed['id'],'version':seed['version'],'runtime_fence':worker.runtime['fence']})
            if condition=='recall':
                for note in case['experiences']:
                    if note['bot_id']!=bot:continue
                    memory=clients[bot].call('record_bot_experience',{'task_id':seed['id'],'fence':claim['task']['fence'],
                        'observation':note['observation']+'\nImported historical source: '+note['source'],
                        'applicability':note['applicability'],'limitations':note['limitations']+['Imported prior observation, not proof of this task or current applicability'],
                        'evidence':[seed['id']],'used_memories':[]})
                    imported.append({'bot_id':bot,'memory_id':memory['id'],'source':note['source']})
            owner.call('cancel_bot_task',{'task_id':seed['id'],'version':claim['task']['version'],'reason':'Context import complete; no engineering trial performed'})
    task=owner.call('assign_bot_task',assignment(case,sid,state['id'],'lead',case['goal']))
    persist(root/'setup.json',{'session_id':sid,'root_task_id':task['id'],'initial_state':state['id'],'configs':configs,
        'case_hash':digest(case),'file_manifest':case['manifest'],'imported_memories':imported,'condition':condition})
    return owner,clients,configs,task,imported


def identity(context,bot):
    packet=context.get('packet',{});task=context.get('task') or packet.get('task',{})
    return {'bot_id':bot,'task_id':task.get('id',packet.get('task_id')),'attempt':task.get('attempt',packet.get('attempt')),
        'round':context.get('round'),'operation':context.get('operation','action')}


def category(operation,output,task_id=None):
    if operation in {'plan_from_experience','reflect_on_experience'}:return 'judgment'
    action=output.get('action')
    if action in {'ask','resolve','team','inspect'}:return 'consultation'
    try:args=json.loads(output.get('arguments_json','{}'))
    except (ValueError,TypeError):args={}
    if action=='records' and args.get('task_id') and args['task_id']!=task_id:return 'consultation'
    if action=='observe':
        intents={r.get('action')=='inspect' for r in args.get('requests',[])}
        if intents=={True}:return 'consultation'
        if intents=={True,False}:return 'unknown'  # One model call mixes local and peer observations.
    if action=='finish':
        try:
            if json.loads(output.get('arguments_json','{}')).get('assignments'):return 'consultation'
        except (ValueError,TypeError):pass
    if action in {'edit','replace','tool','integrate','publish_physical'}:return 'work'
    return 'judgment'


def all_pages(client,name,args):
    result=[];after=None
    while True:
        page=client.call(name,{**args,**({'after':after} if after else {})});result.extend(page['items'])
        after=page.get('next_cursor')
        if not after:return result


def collect(owner,task,root):
    tasks=all_pages(owner,'list_bot_tasks',{'session_id':task['session_id'],'limit':100})
    views={t['id']:owner.call('get_bot_task',{'task_id':t['id']}) for t in tasks}
    records={t['id']:{kind:all_pages(owner,'get_bot_records',{'task_id':t['id'],'kind':kind,'limit':100})
        for kind in ['actions','decisions','learning_uses']} for t in tasks}
    reflections={bot:all_pages(owner,'list_bot_reflections',{'bot_id':bot,'limit':100}) for bot in BOTS}
    persist(root/'tasks.json',views);persist(root/'records.json',records);persist(root/'reflections.json',reflections)
    return views,records,reflections


def workflow_check(views,records,case):
    """Evidence of collaboration, independent of engineering acceptance."""
    lead_actions=[a for tid,v in views.items() if v['task']['bot_id']=='lead' for a in records[tid]['actions']]
    inspected=set();integrated=set()
    for action in observation_actions(lead_actions):
        args=json.loads(action.get('details',{}).get('arguments','{}'))
        result=action.get('details',{}).get('result',{})
        if action['kind'] in {'inspect','records'} and not result.get('error') and args.get('task_id'):
            inspected.add(args['task_id'])
        if action['kind']=='integrate' and result.get('integrated'):
            integrated.update(c['id'] for c in args.get('changes',[]))
    # Core saves reports only after finish-time integration succeeds. This is
    # the other supported integration route, not merely a model proposal.
    for view in views.values():
        if view['task']['bot_id']=='lead':
            for report in view['task'].get('reports',[]):
                integrated.update(c['id'] for c in report['report'].get('integrate_changes',[]))
    evidence=[]
    for bot in case.get('required_worker_bots',[]):
        completed=[]
        for tid,view in views.items():
            task=view['task'];change=view.get('own_change') or {}
            edits=[a['id'] for a in records[tid]['actions'] if a['kind'] in {'edit','replace'}
                and not a['details'].get('result',{}).get('error')
                and a['details'].get('workspace_before')!=a['details'].get('workspace_after')]
            if task['bot_id']==bot and task['status']=='completed' and task.get('parent_task_id') and edits:
                completed.append({'task_id':tid,'edit_actions':edits,'inspected':tid in inspected,'integrated':change.get('id') in integrated})
        evidence.append({'bot_id':bot,'tasks':completed,'accepted':any(t['inspected'] and t['integrated'] for t in completed)})
    return {'accepted':all(row['accepted'] for row in evidence),'workers':evidence,
        'meaning':'Requires completed delegated edits, explicit peer evidence retrieval and successful integration. Does not establish memory causality.'}


def runtime_spans(root):
    """Join saved leaf phase intervals to their immutable action inputs."""
    rows=[]
    for path in (root/'journals').rglob('timing/*.json'):
        row=json.loads(path.read_text())
        if row['phase']=='model':continue  # Inference wrapper includes planners/reflections as well.
        step=path.parent.parent;input_path=step/'input.json';marker=step/'action.json'
        if not input_path.exists():continue  # Report uncovered time rather than inventing an identity.
        ctx=json.loads(input_path.read_text());saved=json.loads(marker.read_text()) if marker.exists() else {}
        output=saved.get('receipt',{}).get('output',{})
        task=ctx.get('task',{});bot=task.get('bot_id')
        if not bot:continue
        phase=row['phase'];intent=category('action',output,task.get('id')) if phase=='action' else 'recording' if phase in {'record','checkpoint'} else 'judgment'
        rows.append({'id':str(path.relative_to(root)),'actor_type':'bot',**identity(ctx,bot),'category':intent,'phase':phase,
            'started_at_ns':row['started_at_ns'],'finished_at_ns':row['finished_at_ns'],
            'monotonic_seconds':row['monotonic_seconds'],'rework':None,'action':output.get('action')})
    return rows


def publication_ancestry(owner, final, publication_state_id, raw_check, cache):
    """Return a same-session immutable ancestry proof for this exact check.

    Current input/report hashes, effective dependency status and actual tool
    provenance are checked separately. An ancestor relationship alone is not
    sufficient to reuse a result. Missing ancestry is not silently inferred.
    """
    root=final['state'];session=root.get('session_id');frontier=[(root['id'],[])];seen=set()
    cache[root['id']]=final
    while frontier and len(seen)<1000:
        ident,path=frontier.pop()
        if ident in seen:continue
        seen.add(ident)
        if ident not in cache:cache[ident]=owner.call('get_development_state',{'state_id':ident})
        state=cache[ident]['state']
        if state.get('id')!=ident:continue
        if ident!=root['id'] and (not session or state.get('session_id')!=session):continue
        chain=path+[ident]
        if ident==publication_state_id:
            saved=state.get('context',{}).get('environment',{}).get('engineering',{}).get('checks',[])
            if raw_check in saved:return {'valid':True,'path':chain,'checked_states':len(seen)}
            return {'valid':False,'reason':'published_check_different','checked_states':len(seen)}
        for parent in state.get('parents',[]):frontier.append((parent,chain))
    return {'valid':False,'reason':'ancestor_not_proven' if not frontier else 'ancestry_limit','checked_states':len(seen)}


def final_audit(owner,view,records,case,root):
    state_id=view['task'].get('output_state',view['task']['state_id'])
    detail=owner.call('get_development_state',{'state_id':state_id});persist(root/'final-state.json',detail)
    workspace=root/'workspace';restore_files(owner,detail['state']['snapshot'],workspace)
    hashes={p.relative_to(workspace).as_posix():sha(p.read_bytes()) for p in workspace.rglob('*') if p.is_file() and '.gantry' not in p.parts}
    immutable={p:hashes.get(p)==h for p,h in case['manifest'].items() if not in_scope(p,case['roles']['lead']['write_scope'])}
    require(all(immutable.values()),'evaluation_tampered','Frozen source changed')
    audit=root/'final-audit';shutil.copytree(workspace,audit)
    tool=execute(case['tools'][case['final_verifier']],audit,runtime_roots(),backend(),lambda:None)
    result={'exit_code':tool['exit_code'],'reason':tool.get('reason'),'immutable':immutable,'checks':[],
        'tool_output':tool.get('output'),'final_hashes':hashes,'formal_adoption':False}
    mapping=case.get('tool_evidence',{}).get(case['final_verifier'])
    if mapping:
        plan=json.loads((workspace/mapping['plan_path']).read_text())
        actions=[a for value in records.values() for a in value['actions']]
        ancestry_cache={}
        for check in plan['checks']:
            if not check['required']:continue
            report=json.loads((audit/check['report']).read_text()) if (audit/check['report']).exists() else None
            observed=evaluate(check,report,hashes)
            saved=json.loads((workspace/check['report']).read_text()) if (workspace/check['report']).exists() else None
            submitted=evaluate(check,saved,hashes)
            audit_inputs_unchanged=all((audit/p).exists() and sha((audit/p).read_bytes())==hashes.get(p) for p in check['inputs'])
            linked=next((c for c in detail.get('engineering',{}).get('checks',[]) if c['id']==check['id']),{})
            execution=linked.get('physical_result',{}).get('execution',{})
            receipt=any(a['kind']=='tool' and a['input_state']==execution.get('input_state')
                and json.loads(a['details'].get('arguments','{}')).get('name')==case['final_verifier']
                and a['details'].get('result',{}).get('exit_code')==0
                and not a['details'].get('result',{}).get('reason')
                and a['details'].get('result',{}).get('output_artifact')==execution.get('output_artifact') for a in actions)
            raw_check=next((c for c in detail['state']['context']['environment'].get('engineering',{}).get('checks',[]) if c['id']==check['id']),{})
            publication_proofs=[]
            for action in actions:
                source=action['details'].get('result',{});publication=source.get('evidence_publication',{})
                if (action['kind']=='tool_evidence' and source.get('exit_code')==0
                    and check['report'] in source.get('refreshed_paths',[]) and raw_check in publication.get('checks',[])):
                    publication_proofs.append(publication_ancestry(owner,detail,publication.get('state_id'),raw_check,ancestry_cache))
            publication=any(proof['valid'] for proof in publication_proofs)
            linked_ok=bool(receipt and publication and execution.get('exit_code')==0 and execution.get('action_key') and linked.get('effective_status')=='pass'
                and linked.get('evidence',{}).get(check['report'])==hashes.get(check['report'])
                and all(linked.get('inputs',{}).get(p)==hashes.get(p) for p in check['inputs']))
            result['checks'].append({'id':check['id'],'fresh_evaluation':observed,'submitted_evaluation':submitted,'actual_tool_linked':linked_ok,
                'audit_inputs_unchanged':audit_inputs_unchanged,'publication_ancestry':publication_proofs})
    result['accepted']=bool(tool['exit_code']==0 and not tool.get('reason') and result['checks'] and
        all(c['fresh_evaluation']['status']=='pass' and c['submitted_evaluation']['status']=='pass' and c['actual_tool_linked']
            and c['audit_inputs_unchanged'] for c in result['checks']))
    persist(root/'final-audit.json',result);return result


def run(case,root,condition,model,seconds,infer_fn=infer_monthly):
    setup_start=time.time_ns();owner,clients,configs,task,imported=setup(root,case,condition,model,seconds)
    setup_end=time.time_ns();persist(root/'parent-interventions.json',[{'kind':'setup','started_at_ns':setup_start,'finished_at_ns':setup_end,
        'description':'Frozen source, acceptance, roles and prior-memory import. No engineering solution supplied.'}])
    persist(root/'environment.json',environment());started=time.time_ns();mono=time.monotonic();lock=threading.RLock()
    stop=threading.Event();abort=threading.Event();calls=[];errors=[];spans=[]
    def event(kind,**data):
        with lock:
            with (root/'timeline.jsonl').open('a') as f:f.write(canonical({'at_ns':time.time_ns(),'monotonic_ns':time.monotonic_ns(),'kind':kind,**data})+'\n')
    def remaining():return seconds-max(time.monotonic()-mono,(time.time_ns()-started)/1e9)
    def worker(bot):
        def infer(ctx,schema,directory):
            require(not abort.is_set(),'experiment_stopped','Another worker stopped; no further inference')
            require(remaining()>0,'observation_timeout','Equal observation window ended')
            ident=identity(ctx,bot);begin=time.time_ns();clock=time.monotonic();span_id=uuid.uuid4().hex
            call={**ident,'started_at_ns':begin,'directory':str(Path(directory).relative_to(root)),'status':'started'}
            event('model_start',**ident)
            output={}
            try:
                receipt=infer_fn(ctx,schema,directory,model=model,reasoning_effort='low',timeout_seconds=max(.1,min(180,remaining())))
                output=receipt['output'];call.update(status='completed',output=output,provider=receipt.get('provider'));return receipt
            except Exception as exc:
                call.update(status='failed',error=exc.code if isinstance(exc,Fault) else type(exc).__name__)
                abort.set();stop.set();raise
            finally:
                end=time.time_ns();call.update(finished_at_ns=end,seconds=time.monotonic()-clock)
                with lock:
                    calls.append(call);persist(root/'calls.json',calls)
                    spans.append({'id':span_id,'actor_type':'bot',**ident,'category':category(ident['operation'],output,ident['task_id']),
                        'phase':'model','started_at_ns':begin,'finished_at_ns':end,'monotonic_seconds':call['seconds'],'rework':None})
                event('model_end',**ident,status=call['status'],action=output.get('action'))
        try:
            with BotWorker(clients[bot],configs[bot],root/'journals',infer) as w:
                while not stop.is_set():
                    for item in w.tick():
                        event('worker_result',bot_id=bot,result=item)
                        if item.get('status')=='held':
                            with lock:errors.append({'bot_id':bot,'result':item})
                            abort.set();stop.set()
                    if not stop.is_set():
                        begin=time.time_ns();stop.wait(.25);end=time.time_ns()
                        with lock:spans.append({'id':uuid.uuid4().hex,'actor_type':'bot','bot_id':bot,'category':'waiting','phase':'wait',
                            'started_at_ns':begin,'finished_at_ns':end,'rework':None})
        except Exception as exc:
            with lock:errors.append({'bot_id':bot,'code':exc.code if isinstance(exc,Fault) else type(exc).__name__,'message':str(exc)})
            event('worker_error',bot_id=bot,error=errors[-1]);abort.set();stop.set()
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures=[pool.submit(worker,b) for b in BOTS]
        while not stop.wait(.25):
            view=owner.call('get_bot_task',{'task_id':task['id']})
            if view['task']['status'] in TERMINAL:
                event('root_terminal_before_reflections',status=view['task']['status']);stop.set()
            if remaining()<=0:
                errors.append({'code':'observation_timeout'});abort.set();stop.set()
        for f in futures:f.result()
    event('workers_drained')
    audit_start=time.time_ns();audit_clock=time.monotonic()
    views,records,reflections=collect(owner,task,root);validation=None
    try:validation=final_audit(owner,views[task['id']],records,case,root)
    except Exception as exc:errors.append({'phase':'final_audit','code':exc.code if isinstance(exc,Fault) else type(exc).__name__,'message':str(exc)})
    finished=time.time_ns()
    persist(root/'model-spans.json',spans)
    spans.extend(runtime_spans(root))
    spans.append({'id':'final-audit','actor_type':'parent','bot_id':None,'category':'work','phase':'tool',
        'started_at_ns':audit_start,'finished_at_ns':finished,'monotonic_seconds':time.monotonic()-audit_clock,'rework':False})
    persist(root/'normalized-spans.json',spans);persist(root/'timing-summary.json',summarize_timing(spans,started,finished))
    workflow=workflow_check(views,records,case);persist(root/'workflow-audit.json',workflow)
    result={'root_task_id':task['id'],'root_status':views[task['id']]['task']['status'],'condition':condition,'case_hash':digest(case),
        'model':model,'reasoning_effort':'low','started_at_ns':started,'finished_at_ns':finished,'wall_seconds':(finished-started)/1e9,
        'monotonic_seconds':time.monotonic()-mono,'setup_seconds':(setup_end-setup_start)/1e9,'errors':errors,'validation':validation,
        'pending_reflections':sum(x['status']!='completed' for values in reflections.values() for x in values),
        'model_calls':len(calls),'parent_semantic_interventions':[],'verify':owner.call('verify'),'replay':owner.call('replay')}
    result['engineering_accepted']=bool(validation and validation['accepted'])
    result['workflow_accepted']=workflow['accepted']
    result['within_observation_window']=result['wall_seconds']<=seconds and result['monotonic_seconds']<=seconds
    result['accepted']=bool(result['root_status']=='completed' and result['engineering_accepted'] and result['workflow_accepted']
        and result['within_observation_window'] and not errors and not result['pending_reflections']
        and result['verify']['valid'] and result['replay']['matched'])
    persist(root/'result.json',result);return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--case',type=Path,required=True)
    parser.add_argument('--condition',choices=['cold','recall'],required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--model',required=True);parser.add_argument('--seconds',type=int,default=1800);args=parser.parse_args()
    case=load_case(args.case);root=args.output.resolve()
    require(not root.exists() and not root.is_relative_to(Path(__file__).resolve().parents[2]),'scope_denied','New private output directory outside source required')
    require(60<=args.seconds<=3600 and args.model.strip(),'invalid_input','Choose explicit model and experimental observation window')
    os.umask(0o077);root.mkdir(parents=True,mode=0o700)
    persist(root/'case.json',case);persist(root/'protocol.json',{'condition':args.condition,'model':args.model,'seconds':args.seconds,'case_hash':digest(case),
        'source_hash':sha(Path(__file__).read_bytes()),'entry_point':'crew_memory_study'})
    result=run(case,root,args.condition,args.model,args.seconds)
    print(canonical({k:result[k] for k in ['condition','accepted','root_status','wall_seconds','model_calls','pending_reflections']}))

if __name__=='__main__':main()
