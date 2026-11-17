"""Opt-in, anonymous two-cycle Bot observation. Journals contain private tokens.

Uses the existing ChatGPT login, never an API-key fallback. The parent supplies
scope/acceptance and one initial task, not model answers or corrective values.
All later task selection is by the Bot under standing delegation.
"""
import argparse
import base64
import json
import secrets
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from gantry.agent_connection import PROFILES
from gantry.bot_worker import BotWorker, environment_manifest
from gantry.learning_evaluation_setup import LocalClient, profile
from gantry.model import Fault, require
from gantry.monthly_codex import infer_monthly
from gantry.project_sandbox import backend, runtime_roots
from gantry.runner import persist
from gantry.service import Service, token_hash


def setup(root, settings):
    service = Service(root/'ledger'); owner = LocalClient(service, service.bootstrap()['token'])
    tokens = {'owner': owner.token}
    for name in ('maintainer', 'reviewer'):
        tokens[name] = secrets.token_urlsafe(32)
        p = owner.call('propose', {'title':'Anonymous Bot delegation', 'changes':[{
            'id':name, 'type':'principal', 'data':{'kind':'agent', 'permissions':['read','record','work'],
            'zones':['root'], 'allowed_commands':sorted(PROFILES['bot']), 'token_hash':token_hash(tokens[name])}}]})
        ref = {'proposal_id':p['id'], 'version':p['version']}
        owner.call('submit', ref); owner.call('endorse', {**ref,'reason':'Isolated fixture scope'})
        owner.call('review_adoption', {**ref,'verdict':'approve','reason':'Authority only; no design adoption'})
        owner.call('commit', ref)
    files = {'controller.json':json.dumps({'offset':0}), 'calibration.json':json.dumps({'bias':2,'reference':3}),
        'evaluate.py':'''import json
from pathlib import Path
c=json.loads(Path('controller.json').read_text()); k=json.loads(Path('calibration.json').read_text())
measured=k['reference']+k['bias']; corrected=measured+c['offset']; error=abs(corrected-k['reference'])
print(json.dumps({'measured':measured,'corrected':corrected,'absolute_error':error,'passed':error<=0.01}))
raise SystemExit(0 if error<=0.01 else 1)
'''}
    snapshot = owner.call('capture_artifact', {'files':{p:base64.b64encode(v.encode()).decode() for p,v in files.items()}})['revision_id']
    acceptance = ['Frozen evaluate.py reports absolute_error <= 0.01 on the saved controller candidate.',
        'Record observations and unknowns; this scalar fixture proves no physical behavior.']
    session = owner.call('connect_development', {'title':'Anonymous persistent calibration responsibility', 'snapshot':snapshot,
        'requirements':acceptance, 'constraints':['Do not edit evaluator or calibration; no hardware or formal adoption'],
        'capture':{'scope':'Three anonymous fixture files','missing':['Physical system']}, 'unverified':['Physical behavior'],
        'mode':'execute','actors':['maintainer','reviewer'],'write_scope':['controller.json'],'recipes':{},
        'max_executions':None,'max_parallel':2,'timeout_seconds':3600})
    sid=session['id']
    state=owner.call('initialize_continuity', {'session_id':sid,'version':session['version'],
        'hierarchy':[{'id':'calibration','title':'Scalar calibration fixture','kind':'subsystem','paths':list(files),'editable':True}],
        'context':{'requirements':acceptance,'constraints':['Preserve evaluator and calibration'], 'decisions':[],
        'open_questions':['Physical behavior'],'environment':{'kind':'anonymous scalar fixture'}},'summary':'Uncorrected initial input'})
    goal='Maintain the recorded scalar calibration acceptance and carry conditional experience into subsequent work.'
    owner.call('configure_organization', {'organization_id':'example','version':0,'name':'Anonymous personal Bot team',
        'profile':profile(),'enabled':True,'share_reflections':True})
    for name in ('maintainer','reviewer'):
        p=profile();p['mission']=goal
        p['responsibilities'] = [
            'Own the continuing calibration responsibility; judge next work from saved outcomes and ask reviewer for independent checks.'
            if name=='maintainer' else 'Independently inspect and test the exact requested state; report evidence and limitations.']
        p['onboarding'] += [
            'Use commitment_create/update for responsibilities across tasks. A completed task does not itself close a continuing responsibility.',
            'An automatic continuation starts at the shared state; inspect linked prior tasks and their saved candidates before repeating work. Integrate a shared candidate if appropriate.',
            'Reflection creates conditional lessons. On subsequent work, inspect recalled experience and consider a procedure_decision. If preferring a procedure, first request reviewer through ask with memory_id and inspect the scoped tool evidence. Resolve answered questions before finishing.',
            'Use the installed evaluate tool for observations. Do not manufacture tool receipts or assume text proves correctness.']
        owner.call('configure_bot', {'bot_id':name,'organization_id':'example','version':0,'name':name,
            'parent_bot_id':None if name=='maintainer' else 'maintainer','profile':p,'enabled':True})
    owner.call('configure_bot_project', {'session_id':sid,'organization_id':'example','version':0,
        'goal':goal,'acceptance':acceptance,'lead_bot_id':'maintainer','enabled':True})
    configs={}
    for name in ('maintainer','reviewer'):
        owner.call('bind_development_bot', {'session_id':sid,'bot_id':name,'principal_id':name,'version':0,
            'write_scope':['controller.json'] if name=='maintainer' else [],'can_assign':name=='maintainer',
            'can_integrate':name=='maintainer','enabled':True})
        config={'bot_id':name,'name':name,'backend':'codex_subscription','workflow':'bot_development',
            'agent_loop':True,'experience_learning':True,'learning_mode':'selective','personal_continuity':True,
            'environment_definition':settings,'sandbox':backend(),'tool_runtime':runtime_roots(),
            'local_tools':{'evaluate':{'argv':[str(Path(sys.executable).resolve()),'-B','evaluate.py'],'timeout_seconds':20}}}
        configs[name]=config
        owner.call('configure_bot_runtime', {'bot_id':name,'version':0,'principal_id':name,'enabled':True,
            'environment':environment_manifest(config)})
    owner.call('set_bot_preference', {'session_id':sid,'bot_id':'maintainer','key':'report-style','version':0,
        'scope':'project','task_id':None,'text':'Report observed metrics before recommendations; explicitly separate unverified physical claims.',
        'reason':'Fixture owner review preference','enabled':True})
    owner.call('configure_bot_continuation', {'session_id':sid,'bot_id':'maintainer','version':0,'enabled':True,
        'write_scope':['controller.json'],'dependencies':['calibration.json','evaluate.py'],
        'completion':['Reassess saved responsibility and prior outcomes. Decide whether more work or independent checking is needed.',
            'Use applicable experience with recorded limits; reconcile completed responsibility explicitly. Do not create routine busywork.']})
    task=owner.call('assign_bot_task', {'session_id':sid,'bot_id':'maintainer','state_id':state['id'],'kind':'develop',
        'title':'Investigate and correct the scalar calibration, preserving a responsibility for outcome reassessment',
        'completion':acceptance+['Create a responsibility linked to this task; leave outcome reconciliation to the following continuation after this task finishes.'],
        'write_scope':['controller.json'],'dependencies':['calibration.json','evaluate.py'],'after_tasks':[]})
    persist(root/'credentials.json',tokens)
    persist(root/'setup.json',{'session_id':sid,'task_id':task['id'],'configs':configs,'settings':settings})
    return service, owner, tokens, sid, task['id'], configs


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True); parser.add_argument('--model')
    parser.add_argument('--reasoning-effort',default='low'); parser.add_argument('--seconds',type=int,default=1800)
    args=parser.parse_args(); root=Path(args.output).resolve()
    require(not root.exists() and not root.is_relative_to(Path(__file__).resolve().parents[1]),
        'scope_denied','Use a new private directory outside the source repository')
    root.mkdir(parents=True,mode=0o700); start=time.monotonic(); lock=threading.Lock(); errors=[]
    def event(kind,**values):
        with lock:
            with (root/'timeline.jsonl').open('a') as out:
                out.write(json.dumps({'elapsed':time.monotonic()-start,'kind':kind,**values})+'\n')
    service,owner,tokens,sid,tid,configs=setup(root,{'model':args.model,'reasoning_effort':args.reasoning_effort})
    event('parent_setup',description='Fixture, authority, preferences, one initial task and standing delegation. No repair values or model answers supplied.')
    for cycle in (1,2):
        stop=threading.Event()
        def run(name):
            client=LocalClient(service,tokens[name])
            def inference(context,schema,directory):
                if time.monotonic()-start>=args.seconds: raise Fault('observation_window_elapsed','End of declared observation window')
                event('inference_start',bot=name,cycle=cycle,operation=context.get('operation','action'))
                receipt=infer_monthly(context,schema,directory,model=args.model,reasoning_effort=args.reasoning_effort)
                event('inference_end',bot=name,cycle=cycle,action=receipt['output'].get('action'),provider=receipt['provider'])
                return receipt
            try:
                with BotWorker(client,configs[name],root/'journals',inference) as worker:
                    while not stop.is_set():
                        results=worker.tick()
                        for result in results:
                            event('worker_result',bot=name,cycle=cycle,result=result)
                            if result.get('status')=='held': errors.append({'bot':name,'cycle':cycle,'result':result});stop.set()
                        if name=='maintainer':
                            if cycle==1 and owner.call('get_bot_task',{'task_id':tid})['task']['status'] in {'completed','blocked','failed','cancelled'}:
                                stop.set()
                            elif cycle==2:
                                duties=owner.call('list_bot_commitments',{'session_id':sid,'bot_id':'maintainer'})['items']
                                if duties and all(d['status'] in {'completed','cancelled'} for d in duties):stop.set()
                        stop.wait(0.5)
            except Exception as exc:
                errors.append({'bot':name,'cycle':cycle,'type':type(exc).__name__,'message':str(exc)[:500]});stop.set()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(run,name) for name in configs]
            while not stop.wait(0.5):
                if time.monotonic()-start >= args.seconds:
                    errors.append({'reason':'observation_window_elapsed','cycle':cycle});stop.set()
            for f in futures:f.result()
        if errors:break
        if cycle==1:
            event('planned_restart',description='Close workers and reopen Core; no assignments, choices, memories or results inserted.')
            service=Service(root/'ledger');owner=LocalClient(service,tokens['owner'])
    final={'seconds':time.monotonic()-start,'errors':errors,'original_task':owner.call('get_bot_task',{'task_id':tid}),
        'tasks':owner.call('list_bot_tasks',{'session_id':sid,'limit':100}),
        'commitments':owner.call('list_bot_commitments',{'session_id':sid,'bot_id':'maintainer','limit':100}),
        'memories':owner.call('list_persistent_memories',{'bot_id':'maintainer','limit':100}),
        'verify':owner.call('verify'),'replay':owner.call('replay')}
    persist(root/'final.json',final)
    print(json.dumps({'seconds':final['seconds'],'errors':errors,'task_status':final['original_task']['task']['status'],
        'commitments':[d['status'] for d in final['commitments']['items']]}))


if __name__=='__main__':main()
