"""Opt-in subscription model -> real sandboxed CadQuery -> HTTP Core -> next task.
Run with a Python environment containing Gantry and CadQuery. Output is private.
"""
import argparse
import base64
import json
from pathlib import Path
import secrets
import shutil
import sys
import threading
import time

from gantry.agent_connection import PROFILES
from gantry.bot_worker import BotWorker, environment_manifest
from gantry.client import Client
from gantry.continuity_adapter import restore_development_state
from gantry.hardware import publish
from gantry.learning_evaluation_setup import profile
from gantry.model import require
from gantry.monthly_codex import infer_monthly
from gantry.project_sandbox import backend, execute, runtime_roots
from gantry.runner import persist
from gantry.server import Server
from gantry.service import Service, token_hash


def commit(owner,changes):
    p=owner.call('propose',{'title':'Anonymous demonstration setup','changes':changes})
    ref={'proposal_id':p['id'],'version':p['version']}
    owner.call('submit',ref);owner.call('endorse',{**ref,'reason':'Explicit demonstration scope'})
    owner.call('review_adoption',{**ref,'verdict':'approve','reason':'Approve requirement/delegation, not the design'})
    owner.call('commit',ref)
    return p


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True);parser.add_argument('--model',required=True)
    parser.add_argument('--reasoning-effort',default='low');args=parser.parse_args()
    root=Path(args.output).resolve();root.mkdir(mode=0o700)
    service=Service(root/'ledger');owner_token=service.bootstrap()['token'];bot_token=secrets.token_urlsafe(32)
    server=Server(('127.0.0.1',0),service)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url='http://127.0.0.1:'+str(server.server_port)
    owner,bot=Client(url,owner_token),Client(url,bot_token)
    persist(root/'credentials.json',{'owner':owner_token,'bot':bot_token})
    evidence={'automatic':['HTTP Core, BotWorker, scoped sandbox, snapshot capture, evidence evaluation'],
              'manual':['Anonymous fixture, requirement definitions, assignment, calibration update between tasks'],
              'mock':[], 'model':args.model,'reasoning_effort':args.reasoning_effort,'runs':[]}
    try:
        p=commit(owner,[{'id':'developer','type':'principal','data':{'kind':'agent','permissions':['read','record','work'],
            'zones':['root'],'allowed_commands':sorted(PROFILES['bot']),'token_hash':token_hash(bot_token)}},
            {'id':'placement','type':'requirement','zone':'root','data':{
                'description':'Carrier clearance >= 1 mm, overlap <= 0.001 mm3, x in [11,20] mm; control agrees within 0.01 mm',
                'verification_checks':['interface']}}])
        refs=[{'requirement_id':'placement','revision_id':p['changes'][1]['revision_id']}]
        project=root/'input';project.mkdir()
        shutil.copy(Path(__file__).with_name('verify.py'),project/'verify.py')
        for name,data in {'design.json':{'carrier_x_mm':5},'control.json':{'target_mm':5},'calibration.json':{'offset_mm':0}}.items():
            (project/name).write_text(json.dumps(data))
        inputs=['design.json','control.json','calibration.json','verify.py','fixed.step','carrier.step']
        import cadquery as cq
        plan={'version':1,'components':[{'id':'carrier','role':'moving carrier','assembly':'assembly','paths':['design.json','carrier.step']},
            {'id':'control','role':'position command','assembly':'assembly','paths':['control.json','calibration.json']}],
            'checks':[{'id':'interface','scope':'placement','components':['carrier','control'],'required':True,
                'inputs':inputs,'report':'report.json','conditions':{'unit':'mm','frame':'assembly'},
                'evaluator':{'name':'anonymous-cad-interface','version':'1'},'environment':{'cadquery':cq.__version__},
                'requirement_refs':refs,'criteria':[{'metric':'overlap','unit':'mm3','max':0.001},
                    {'metric':'clearance','unit':'mm','min':1},{'metric':'carrier_x','unit':'mm','min':11,'max':20},
                    {'metric':'control_error','unit':'mm','max':0.01}]}]}
        (project/'physical-plan.json').write_text(json.dumps(plan))
        command={'argv':[sys.executable,'-B','verify.py'],'timeout_seconds':60}
        baseline_result=execute(command,project,runtime_roots(),backend(),lambda:None)
        require(baseline_result['exit_code']==0,'example_failed','Native baseline evaluator failed')
        files={p.name:base64.b64encode(p.read_bytes()).decode() for p in project.iterdir() if p.name in inputs+['report.json','physical-plan.json']}
        snapshot=owner.call('capture_artifact',{'files':files})['revision_id']
        scope=['design.json','control.json','carrier.step','fixed.step','report.json']
        session=owner.call('connect_development',{'title':'Anonymous CAD/control loop','snapshot':snapshot,
            'requirements':['Static clearance and command alignment'],'constraints':['No physical operation'],
            'capture':{'scope':'Saved anonymous source and native STEP files','missing':['Dynamic/load/tolerance evidence']},
            'unverified':['Whole product'],'mode':'execute','actors':['developer'],'write_scope':scope+['calibration.json'],
            'recipes':{},'max_executions':None,'max_parallel':1,'timeout_seconds':3600})
        state=owner.call('initialize_continuity',{'session_id':session['id'],'version':session['version'],
            'hierarchy':[{'id':'assembly','title':'Carrier assembly','kind':'subsystem','paths':list(files),'editable':True}],
            'context':{'requirements':['Static clearance and command alignment'],'requirement_refs':refs,
                'constraints':['Preserve acceptance and verifier; do not fabricate reports'],
                'decisions':[],'open_questions':['Dynamics/strength/tolerances not tested'],
                'environment':{'cadquery':cq.__version__}},'summary':'Import an existing failed design'})
        change=owner.call('begin_change',{'state_id':state['id'],'title':'Capture baseline evidence','purpose':'Known failed static check',
            'write_scope':scope,'dependencies':[],'assignee':'admin'})
        # Use only captured public inputs, excluding sandbox temp files.
        clean=root/'clean';clean.mkdir()
        for name in files:shutil.copy(project/name,clean/name)
        baseline=publish(owner,state['id'],change['id'],change['version'],clean,'physical-plan.json','baseline')['state']
        owner.call('configure_organization',{'organization_id':'example','version':0,'name':'Example team','profile':profile(),
            'enabled':True,'share_reflections':False})
        owner.call('configure_bot',{'bot_id':'developer','organization_id':'example','version':0,'name':'Development Bot',
            'parent_bot_id':None,'profile':profile(),'enabled':True})
        owner.call('configure_bot_project',{'session_id':session['id'],'organization_id':'example','version':0,
            'lead_bot_id':'developer','goal':'Correct measured CAD/control failures','acceptance':['All frozen checks pass; unknowns remain explicit'],'enabled':True})
        owner.call('bind_development_bot',{'session_id':session['id'],'bot_id':'developer','principal_id':'developer','version':0,
            'write_scope':scope,'can_assign':False,'can_integrate':False,'enabled':True})
        config={'bot_id':'developer','name':'Native CAD example','backend':'codex_subscription','workflow':'bot_development','agent_loop':True,
            'environment_definition':{'model':args.model,'reasoning_effort':args.reasoning_effort},
            'local_tools':{'verify':command},'tool_runtime':runtime_roots(),'sandbox':backend()}
        owner.call('configure_bot_runtime',{'bot_id':'developer','version':0,'principal_id':'developer','enabled':True,'environment':environment_manifest(config)})
        persist(root/'runtime-config.json',config)
        calls=[]
        def inference(context,schema,directory):
            start=time.monotonic()
            receipt=infer_monthly(context,schema,directory,model=args.model,reasoning_effort=args.reasoning_effort)
            calls.append({'seconds':time.monotonic()-start,'action':receipt['output'].get('action'),'provider':receipt['provider']})
            persist(root/'calls.json',calls)
            return receipt
        current=baseline
        for index in range(2):
            task=owner.call('assign_bot_task',{'session_id':session['id'],'bot_id':'developer','state_id':current['id'],'kind':'develop',
                'title':'Correct failed CAD/control requirement from saved evidence',
                'completion':['Read the recorded physical evidence and requirement coverage.',
                    'Choose edits within scope, run verify, then publish_physical using physical-plan.json.',
                    'Finish after linked requirement coverage is met, or report an explicit blocker. Preserve untested scope.'],
                'write_scope':scope,'dependencies':inputs+['physical-plan.json'],'after_tasks':[]})
            start=time.monotonic()
            # Different worker, process journal and restored workspace on the next task.
            with BotWorker(bot,config,root/('worker-'+str(index)),infer_fn=inference) as worker: result=worker.tick()[0]
            detail=owner.call('get_bot_task',{'task_id':task['id']})
            sid=result.get('task',{}).get('output_state',current['id'])
            view=owner.call('get_development_state',{'state_id':sid})
            evidence['runs'].append({'task_id':task['id'],'seconds':time.monotonic()-start,'result':result,
                'baseline':current['id'],'output':sid,'coverage':view['requirement_coverage'],
                'assessment':detail['design_assessment'],'actions':detail['actions']})
            persist(root/'result.json',evidence)
            require(view['requirement_coverage']['items'][0]['status']=='met','example_incomplete','Bot did not satisfy frozen requirement; retain evidence')
            require(view['status']['adoption']=='unadopted','example_failed','Unexpected formal adoption')
            current=view['state']
            if index==0:
                bundle=restore_development_state(owner,sid,root/'resumed','fresh-state')
                resumed=Path(bundle['workspace'])
                (resumed/'calibration.json').write_text(json.dumps({'offset_mm':1}))
                from gantry.continuity_adapter import checkpoint_workspace
                c=owner.call('begin_change',{'state_id':sid,'title':'Updated sensor calibration','purpose':'Recorded dependency change',
                    'write_scope':['calibration.json'],'dependencies':[],'assignee':'admin'})
                cp=checkpoint_workspace(owner,c['id'],c['version'],resumed,'Calibration changed','Example dependency update',[], 'paused','calibration')
                current=cp['state']
                evidence['dependency_change']=owner.call('get_design_assessment',{'baseline_state_id':sid,'state_id':current['id']})
                require(evidence['dependency_change']['requirements']['items'][0]['status']=='unverified','example_failed','Stale pass reused')
        evidence['replay']=owner.call('replay');evidence['calls']=calls
        evidence['native_environment']={'cadquery':cq.__version__,'python':sys.version,'sandbox':backend()}
        persist(root/'result.json',evidence)
        print(json.dumps({'result':str(root/'result.json'),'tasks':len(evidence['runs']),'model_calls':len(calls),'replay':evidence['replay']['matched']}))
    finally:server.shutdown();server.server_close();thread.join()


if __name__=='__main__':main()
