"""Opt-in native CAD + control Crew experiment. Output contains private credentials."""
import argparse,base64,json,secrets,sys,threading,time,shutil,tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from gantry.agent_connection import PROFILES
from gantry.bot_worker import BotWorker,environment_manifest
from gantry.learning_evaluation_setup import LocalClient,profile
from gantry.monthly_codex import infer_monthly
from gantry.project_sandbox import backend,runtime_roots,execute
from gantry.runner import persist
from gantry.service import Service,token_hash
from gantry.hardware import publish
from gantry.model import require
from gantry import cad_kernel as cad


def approve(owner,changes):
    p=owner.call('propose',{'title':'Anonymous experiment delegation and acceptance','changes':changes})
    ref={'proposal_id':p['id'],'version':p['version']}
    owner.call('submit',ref);owner.call('endorse',{**ref,'reason':'Experiment setup'})
    owner.call('review_adoption',{**ref,'verdict':'approve','reason':'Requirements and authority only, not design adoption'})
    owner.call('commit',ref);return p


def fixture(owner,root,actors=None):
    p=approve(owner,[{'id':'placement','type':'requirement','zone':'root','data':{
        'description':'Nominal carrier clearance >=1 mm, overlap<=0.001 mm3, x in [11,20], CAD source/control error <=0.01 mm',
        'verification_checks':['interface']}}])
    refs=[{'requirement_id':'placement','revision_id':p['changes'][0]['revision_id']}]
    workspace=root/'initial';workspace.mkdir()
    files={p:Path(__file__).with_name(p).read_bytes() for p in ['build.py','verify.py','controller.py']}
    files.update({p:json.dumps(v).encode() for p,v in {'design.json':{'carrier_x_mm':5},'control.json':{'target_mm':5},'calibration.json':{'offset_mm':2}}.items()})
    inputs=['design.json','control.json','calibration.json','build.py','verify.py','controller.py','fixed.step','carrier.step']
    plan={'version':1,'components':[{'id':'carrier','role':'moving carrier','assembly':'assembly','paths':['design.json','carrier.step','fixed.step']},
          {'id':'control','role':'position command','assembly':'assembly','paths':['control.json','calibration.json','controller.py']}],
        'checks':[{'id':'interface','scope':'placement','components':['carrier','control'],'required':True,
            'inputs':inputs,'report':'report.json','conditions':{'unit':'mm','frame':'assembly','steps':80},
            'evaluator':{'name':'native-cad-control','version':'1'},'environment':{'cad_backend':cad.BACKEND},'requirement_refs':refs,
            'criteria':[{'metric':'overlap','unit':'mm3','max':.001},{'metric':'clearance','unit':'mm','min':1},
                {'metric':'carrier_x','unit':'mm','min':11,'max':20},{'metric':'cad_source_error','unit':'mm','max':.01},
                {'metric':'control_error','unit':'mm','max':.01}]}]}
    files['physical-plan.json']=json.dumps(plan).encode()
    for name,raw in files.items():(workspace/name).write_bytes(raw)
    tools={name:{'argv':[sys.executable,'-B',name+'.py'],'timeout_seconds':60} for name in ['build','verify']}
    for command in tools.values():
        with tempfile.TemporaryDirectory(dir=root) as temp:
            scratch=Path(temp)
            for source in workspace.iterdir():shutil.copy2(source,scratch/source.name)
            result=execute(command,scratch,runtime_roots(),backend(),lambda:None)
            for source in scratch.iterdir():
                if source.is_file() and not source.name.startswith('.'):shutil.copy2(source,workspace/source.name)
        require(result['exit_code']==0,'fixture_failed','Native setup failed',result=result)
    for name in ['fixed.step','carrier.step','report.json','trace.json']:files[name]=(workspace/name).read_bytes()
    snapshot=owner.call('capture_artifact',{'files':{p:base64.b64encode(v).decode() for p,v in files.items()}})['revision_id']
    scope=['design.json','control.json','fixed.step','carrier.step','report.json','trace.json']
    session=owner.call('connect_development',{'title':'Anonymous native engineering loop','snapshot':snapshot,
        'requirements':['Fixed nominal placement and command acceptance'],'constraints':['No hardware or adoption'],
        'capture':{'scope':'Editable CAD source, STEP, executable control and evaluator','missing':['Dynamics, strength, electrical and hardware tests']},
        'unverified':['Physical performance'],'mode':'execute','actors':actors or ['admin'],'write_scope':scope,
        'recipes':{},'max_executions':None,'max_parallel':3,'timeout_seconds':3600})
    state=owner.call('initialize_continuity',{'session_id':session['id'],'version':session['version'],
        'hierarchy':[{'id':'assembly','title':'Carrier assembly','kind':'subsystem','paths':list(files),'editable':True}],
        'context':{'requirements':['Fixed nominal placement and command acceptance'],'requirement_refs':refs,'constraints':['Do not weaken physical-plan or evaluator'],
            'decisions':[],'open_questions':['Physical feasibility'],'environment':{'cad_backend':cad.BACKEND}},'summary':'Existing native design with measured failures'})
    c=owner.call('begin_change',{'state_id':state['id'],'title':'Import baseline observations','purpose':'Capture actual native evidence',
        'write_scope':scope,'dependencies':[],'assignee':'admin'})
    state=publish(owner,state['id'],c['id'],c['version'],workspace,'physical-plan.json','baseline')['state']
    for path,field in [('design.json','carrier_x_mm'),('control.json','target_mm'),('calibration.json','offset_mm')]:
        owner.call('extract_json_evidence',{'state_id':state['id'],'subject_id':'assembly','path':path,'profile':'configuration.v1','fields':[{'name':field,'pointer':'/'+field,'unit':'mm','frame':'assembly','time_basis':'configuration'}]})
    return session['id'],state,scope,inputs,tools


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    parser.add_argument('--model');parser.add_argument('--reasoning-effort',default='low');args=parser.parse_args()
    root=Path(args.output).resolve()
    require(not root.exists() and not root.is_relative_to(Path(__file__).resolve().parents[2]),
        'scope_denied','Use a new private output directory outside the source repository')
    root.mkdir(parents=True,mode=0o700)
    start=time.monotonic();lock=threading.Lock()
    def event(kind,**values):
        with lock:
            with (root/'timeline.jsonl').open('a') as f:f.write(json.dumps({'elapsed':time.monotonic()-start,'kind':kind,**values})+'\n')
    service=Service(root/'ledger');owner=LocalClient(service,service.bootstrap()['token']);persist(root/'owner-private.json',{'token':owner.token})
    clients={};configs={}
    for name in ['lead','mechanical','control']:
        token=secrets.token_urlsafe(32);approve(owner,[{'id':name,'type':'principal','data':{'kind':'agent','permissions':['read','record','work'],'zones':['root'],'allowed_commands':sorted(PROFILES['bot']),'token_hash':token_hash(token)}}])
        clients[name]=LocalClient(service,token);persist(root/(name+'-private.json'),{'token':token})
    sid,state,scope,inputs,tools=fixture(owner,root,list(clients))
    goal='Resolve the recorded native CAD/control acceptance gaps. Compare plausible corrections, delegate by responsibility, integrate and verify the fixed requirements; report unknowns.'
    acceptance=['Frozen interface criteria pass on the final combined state with fresh actual tool evidence.',
        'Choose and record verification plans before testing; inspect peer evidence and retain physical limitations.',
        'Extract relevant saved JSON design/control/calibration values with source provenance before and after changes.']
    owner.call('configure_organization',{'organization_id':'example','version':0,'name':'Native engineering team','profile':profile(),'enabled':True,'share_reflections':True})
    for name in ['lead','mechanical','control']:
        p=profile();p['mission']=goal
        p['responsibilities']=[{'lead':'Compare options and direct cross-domain work; delegate implementation, inspect and integrate candidates, verify final state.',
            'mechanical':'Own design.json and native STEP geometry. Build CAD after source edits and return measurements.',
            'control':'Own control.json. Inspect executable controller and calibration, return scoped correction with evidence.'}[name]]
        p['onboarding']+=['Use plan_verification for a frozen physical-plan.json check before verify; available tools are build and verify. Tool verify automatically captures physical evidence.',
            'Component subject for extract_evidence is assembly. Native build creates STEP from design.json; verify reads STEP and executes controller.py.',
            'Do not edit evaluator, calibration, controller implementation or acceptance. A partial candidate may fail cross-domain checks: report this truthfully and let lead integrate.',
            'Delegate with finish waiting; inspect actual returned evidence, then integrate and verify. No response is a physical safety certificate.']
        owner.call('configure_bot',{'bot_id':name,'organization_id':'example','version':0,'name':name,'parent_bot_id':None if name=='lead' else 'lead','profile':p,'enabled':True})
    owner.call('configure_bot_project',{'session_id':sid,'organization_id':'example','version':0,'goal':goal,'acceptance':acceptance,'lead_bot_id':'lead','enabled':True})
    for name in clients:
        own=scope if name=='lead' else ['design.json','fixed.step','carrier.step','report.json','trace.json'] if name=='mechanical' else ['control.json','report.json','trace.json']
        owner.call('bind_development_bot',{'session_id':sid,'bot_id':name,'principal_id':name,'version':0,'write_scope':own,'can_assign':name=='lead','can_integrate':name=='lead','enabled':True})
        config={'bot_id':name,'name':name,'backend':'codex_subscription','workflow':'bot_development','agent_loop':True,'experience_learning':True,'learning_mode':'always','personal_continuity':True,
            'environment_definition':{'model':args.model,'reasoning_effort':args.reasoning_effort,'scope':'native static fixture'},'local_tools':tools,'tool_evidence':{'verify':{'plan_path':'physical-plan.json'}},'tool_runtime':runtime_roots(),'sandbox':backend()}
        configs[name]=config;owner.call('configure_bot_runtime',{'bot_id':name,'version':0,'principal_id':name,'enabled':True,'environment':environment_manifest(config)})
    task=owner.call('assign_bot_task',{'session_id':sid,'bot_id':'lead','state_id':state['id'],'kind':'develop','title':goal,'completion':acceptance,'write_scope':scope,'dependencies':inputs+['physical-plan.json'],'after_tasks':[]})
    event('parent_setup',seconds=time.monotonic()-start,task_id=task['id'],description='Fixture, fixed acceptance, roles, tool authorization and objective. No solution values or model outputs.')
    persist(root/'setup.json',{'session_id':sid,'task_id':task['id'],'baseline':state['id'],'configs':configs})
    stop=threading.Event();errors=[]
    def worker(name):
        def inference(ctx,schema,directory):
            t=time.monotonic();event('inference_start',bot=name,operation=ctx.get('operation','action'))
            receipt=infer_monthly(ctx,schema,directory,model=args.model,reasoning_effort=args.reasoning_effort)
            event('inference_end',bot=name,seconds=time.monotonic()-t,action=receipt['output'].get('action'),provider=receipt.get('provider'));return receipt
        try:
            with BotWorker(clients[name],configs[name],root/'journals',inference) as w:
                while not stop.is_set():
                    for result in w.tick():
                        event('worker_result',bot=name,result=result)
                        if result.get('status')=='held':errors.append({'bot':name,'result':result});stop.set()
                    stop.wait(1)
        except Exception as e:errors.append({'bot':name,'type':type(e).__name__,'message':str(e)});stop.set()
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures=[pool.submit(worker,n) for n in clients]
        while not stop.wait(2):
            view=owner.call('get_bot_task',{'task_id':task['id']})
            if view['task']['status'] in {'completed','failed','blocked','cancelled'}:stop.set()
            if time.monotonic()-start>1800:errors.append({'reason':'observation_window_elapsed'});stop.set()
        for future in futures:future.result()
    final={'task':owner.call('get_bot_task',{'task_id':task['id']}),'errors':errors,'seconds':time.monotonic()-start,'verify':owner.call('verify'),'replay':owner.call('replay')}
    persist(root/'final.json',final);print(json.dumps({'status':final['task']['task']['status'],'errors':errors,'seconds':final['seconds']}))
if __name__=='__main__':main()
