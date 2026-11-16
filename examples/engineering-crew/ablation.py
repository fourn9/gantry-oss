"""Opt-in Gantry-only latency ablation. Prepare first; private outputs only."""
import argparse
import base64
import copy
import importlib.util
import json
import sys
import time
from pathlib import Path
from gantry.bot_worker import environment_manifest
from gantry.learning_evaluation_case import environment
from gantry.model import Fault, canonical, digest, require
from gantry.monthly_codex import infer_monthly
from gantry.runner import persist

spec=importlib.util.spec_from_file_location('engineering_comparison',Path(__file__).with_name('compare.py'))
compare=importlib.util.module_from_spec(spec);spec.loader.exec_module(compare)
CONDITIONS=['baseline','plan_tool','compact_schema','compact_context']
CASES=[(-2,6,1),(8,-1,-2),(3,4,4),(-7,2,-5)]
STOP_ERRORS={'provider_rate_limited','provider_usage_limited','subscription_login_required','provider_failed','stale_fixture'}


def schedule():
    return [{'index':case*4+position,'case':case,'position':position,'condition':CONDITIONS[(case+position)%4]}
            for case in range(4) for position in range(4)]


def source_hashes():
    return {p.name:compare.sha(p.read_bytes()) for p in [Path(__file__),*[Path(__file__).with_name(n) for n in ['compare.py','build.py','verify.py','controller.py']]]}


def new_root(path):
    root=Path(path).resolve()
    require(not root.exists() and not root.is_relative_to(Path(__file__).resolve().parents[2]),
            'scope_denied','Use a new private output directory outside source')
    root.mkdir(parents=True,mode=0o700);return root


def prepare(root, model):
    started=time.monotonic(); cases=[]
    for index,values in enumerate(CASES):
        directory=root/('case-'+str(index));directory.mkdir(mode=0o700)
        metrics=compare.Measurement(directory);frozen,tools=compare.prepare(directory,metrics)
        for path,key,value in zip(['design.json','control.json','calibration.json'],['carrier_x_mm','target_mm','offset_mm'],values):
            (directory/'initial'/path).write_text(canonical({key:value}))
        for name in ['build','verify']:
            result=compare.tool(directory/'initial',name,tools,metrics,phase='baseline')
            require(result['exit_code']==0 and not result['reason'],'fixture_failed','Native fixture tool failed')
        files=compare.files_at(directory/'initial')
        frozen.update(name='Engineering ablation case '+str(index),files={p:base64.b64encode(v).decode() for p,v in files.items()},manifest={p:compare.sha(v) for p,v in files.items()})
        frozen['acceptance_hash']=digest({'goal':compare.GOAL,'acceptance':compare.ACCEPTANCE,'plan':frozen['plan'],
            'immutable':{p:compare.sha(v) for p,v in files.items() if p not in compare.SCOPE}})
        frozen['fixture_manifest_hash']=digest(frozen['manifest']);persist(directory/'frozen.json',frozen)
        cases.append({'case':index,'frozen_hash':digest(frozen),'manifest_hash':frozen['fixture_manifest_hash'],'acceptance_hash':frozen['acceptance_hash']})
    protocol={'version':1,'model':model,'reasoning_effort':'low','schedule':schedule(),'cases':cases,
        'sources':source_hashes(),'implementation_hash':environment()['implementation_hash'],'setup_seconds':time.monotonic()-started,
        'window_seconds':compare.WINDOW,'interventions_after_start':[],
        'limitations':['Four parameter variants of one nominal CAD/software task family, not general robotics.',
            'Rotated order balances position, not full carryover or provider scheduling.',
            'Model setting is recorded; CLI_DEFAULT means explicitly unpinned backend default, not a reproducible resolved model.',
            'Inference time includes CLI/network/provider wait; no internal thinking-time measurement.',
            'No prior learning, Mentor, delegation or private project data in these runs.']}
    persist(root/'protocol.json',protocol);return protocol


def copy_fixture(prepared, row, root, protocol):
    frozen=json.loads((prepared/('case-'+str(row['case']))/'frozen.json').read_text())
    require(digest(frozen)==protocol['cases'][row['case']]['frozen_hash'],'stale_fixture','Prepared fixture was modified')
    require(source_hashes()==protocol['sources'],'stale_fixture','Experiment code changed after protocol freeze')
    env={**environment(),'executable':sys.executable};require(env['implementation_hash']==protocol['implementation_hash'],'stale_fixture','Gantry changed after freeze')
    for key in ['python','executable','executable_sha256','packages','sandbox','runtime','codex_cli']:
        require(digest(env[key])==digest(frozen['environment'][key]),'stale_fixture','Runtime changed: '+key)
    names={'build.py','verify.py','controller.py','design.json','control.json','calibration.json',
           'physical-plan.json','fixed.step','carrier.step','report.json','trace.json'}
    require(set(frozen['files'])==names and set(frozen['manifest'])==names,'invalid_fixture','Unexpected files')
    decoded={p:base64.b64decode(v,validate=True) for p,v in frozen['files'].items()}
    for name in ['build.py','verify.py','controller.py']:
        require(decoded[name]==Path(__file__).with_name(name).read_bytes(),'stale_fixture','Script differs')
    for path,key,value in zip(['design.json','control.json','calibration.json'],['carrier_x_mm','target_mm','offset_mm'],CASES[row['case']]):
        require(json.loads(decoded[path])=={key:value},'invalid_fixture','Starting parameters differ')
    from gantry import cad_kernel as cad
    plan=compare.physical_plan(cad.BACKEND)
    require(json.loads(decoded['physical-plan.json'])==plan and frozen['plan']==plan and frozen['goal']==compare.GOAL
            and frozen['acceptance']==compare.ACCEPTANCE and frozen['write_scope']==compare.SCOPE,
            'invalid_fixture','Acceptance or authority differs')
    workspace=root/'initial';workspace.mkdir(mode=0o700)
    for path,encoded in frozen['files'].items():
        from gantry.store import Store
        Store.safe_name(path);raw=base64.b64decode(encoded,validate=True)
        require(compare.sha(raw)==frozen['manifest'][path],'stale_fixture','Input hash mismatch')
        (workspace/path).write_bytes(raw)
    persist(root/'frozen.json',frozen)
    tools={name:{'argv':[sys.executable,'-B',name+'.py'],'timeout_seconds':60} for name in ['build','verify']}
    return frozen,tools


class Measurement(compare.Measurement):
    def __init__(self,root,condition,model):
        super().__init__(root);self.condition=condition;self.model=model

    def infer(self,context,schema,directory):
        from gantry.latency_context import transform
        self.active();started=time.monotonic();sent=transform(context,self.condition)
        call={'attempt':len(self.calls)+1,'started_at_ns':time.time_ns(),'status':'started','usage':None,
              'input_bytes_before':len(canonical(context).encode()),'input_bytes_after':len(canonical(sent).encode()),
              'sections_before':{k:len(canonical(v).encode()) for k,v in context.items()},
              'sections_after':{k:len(canonical(v).encode()) for k,v in sent.items()}}
        self.calls.append(call);self.event('inference_start',attempt=call['attempt'])
        try:
            receipt=infer_monthly(sent,schema,directory,timeout_seconds=max(.1,min(180,compare.WINDOW-self.elapsed())),
                model=None if self.model=='CLI_DEFAULT' else self.model,reasoning_effort='low')
            call.update(status='completed',provider=receipt['provider'],usage=receipt['provider'].get('usage'),action=receipt['output'].get('action'))
            self.active();return receipt
        except Exception as exc:
            call.update(status='failed',error=exc.code if isinstance(exc,Fault) else type(exc).__name__);raise
        finally:
            call.update(finished_at_ns=time.time_ns(),seconds=time.monotonic()-started)
            persist(self.root/'model-calls.json',self.calls);self.event('inference_end',**call)


def recorded_failure(root, calls):
    # BotWorker deliberately returns held receipts rather than raising provider
    # faults. Preserve that failure even if the subsequent audit also fails.
    failures=[{'code':c['error'],'message':'Inference failed; see model-calls.json'}
              for c in calls if c.get('status')=='failed' and c.get('error')]
    path=root/'worker-results.json'
    if path.exists():
        failures.extend({'code':r['reason'],'message':'Worker held; see worker-results.json'}
                        for r in json.loads(path.read_text())
                        if r.get('status')=='held' and r.get('reason'))
    return next((f for f in failures if f['code'] in STOP_ERRORS), failures[0] if failures else None)


def run_case(prepared,protocol,row,root):
    setup_start=time.monotonic();metrics=Measurement(root,row['condition'],protocol['model'])
    frozen,tools=copy_fixture(prepared,row,root,protocol)
    owner,client,config,task=compare.setup_b(root,frozen,tools,metrics)
    config['environment_definition'].update(model=None if protocol['model']=='CLI_DEFAULT' else protocol['model'],reasoning_effort='low')
    if row['condition']=='plan_tool':config['experimental_latency']='plan_tool'
    owner.call('configure_bot_runtime',{'bot_id':config['bot_id'],'version':2,'principal_id':config['bot_id'],
        'enabled':True,'environment':environment_manifest(config)})
    persist(root/'treatment.json',{'row':row,'model':protocol['model'],'config':config,'task_id':task['id']})
    setup_seconds=time.monotonic()-setup_start;metrics.begin();validation=None;error=None;status='error'
    try:
        workspace,status=compare.gantry(root,frozen,tools,metrics,(owner,client,config,task))
        validation=compare.final_check(root,workspace,frozen,tools,metrics)
    except Exception as exc:
        error={'code':exc.code if isinstance(exc,Fault) else type(exc).__name__,'message':str(exc)};metrics.event('run_error',**error)
    error=recorded_failure(root,metrics.calls) or error
    elapsed=(time.time_ns()-metrics.wall_start_ns)/1e9
    summary=compare.metrics_summary(root,metrics,elapsed)
    summary['retrieval_calls']=sum(c.get('action') in ['read','observe','inspect','context','records','inspect_json'] for c in metrics.calls)
    summary['input_bytes']=sum(c['input_bytes_after'] for c in metrics.calls)
    result={**row,'status':'accepted' if status=='completed' and validation and validation['accepted'] and elapsed<=compare.WINDOW else 'not_accepted',
        'task_status':status,'validation':validation,'error':error,'metrics':summary,'setup_seconds':setup_seconds,
        'manifest_hash':frozen['fixture_manifest_hash'],'acceptance_hash':frozen['acceptance_hash']}
    persist(root/'result.json',result);return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--prepare-only',action='store_true');parser.add_argument('--model')
    parser.add_argument('--prepared',type=Path);parser.add_argument('--index',type=int)
    args=parser.parse_args();root=new_root(args.output)
    if args.prepare_only:
        require(bool(args.model),'invalid_input','Choose a supported model or explicit CLI_DEFAULT sentinel')
        protocol=prepare(root,args.model);print(canonical({'status':'prepared','runs':len(protocol['schedule'])}));return
    require(args.prepared is not None,'invalid_input','Use a separately prepared frozen protocol')
    prepared=args.prepared.resolve();protocol=json.loads((prepared/'protocol.json').read_text())
    require(protocol['schedule']==schedule(),'invalid_input','Protocol schedule differs')
    require(args.index is None or 0<=args.index<len(protocol['schedule']),'invalid_input','Invalid schedule index')
    persist(root/'protocol.json',protocol);results=[]
    for row in protocol['schedule']:
        if args.index is not None and row['index']!=args.index:continue
        target=root/f"run-{row['index']:02d}-{row['condition']}";target.mkdir(mode=0o700)
        try:result=run_case(prepared,protocol,row,target)
        except Exception as exc:
            result={**row,'status':'setup_failed','error':{'code':exc.code if isinstance(exc,Fault) else type(exc).__name__,'message':str(exc)}}
            persist(target/'result.json',result)
        results.append(result);persist(root/'results.json',results)
        print(canonical({'index':row['index'],'condition':row['condition'],'status':result['status'],'seconds':result.get('metrics',{}).get('total_wall_seconds')}),flush=True)
        # Preserve failed samples; do not repeatedly hit an unavailable provider.
        if result.get('error') and result['error']['code'] in STOP_ERRORS:break

if __name__=='__main__':main()
