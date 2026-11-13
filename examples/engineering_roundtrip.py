"""Real CadQuery + Core smoke test; no external accounts, inference or private data.

Run: python examples/engineering_roundtrip.py NEW_DIRECTORY
"""
import hashlib
import json
import secrets
import shutil
import sys
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from gantry import cad_kernel as cq
from gantry.service import Service
from gantry.model import digest
from gantry.cad_io import edit
from gantry.continuity_adapter import capture_workspace, restore_development_state
from gantry.engineering_workflow import checkout, bind_mapping, publish, link, status
from gantry.physical_execution import run, collect
from gantry.workflow_journal import timing_report, measure

EVALUATOR='''import hashlib,json
from pathlib import Path
from gantry.hardware import screen_report
plan=json.loads(Path('physical-plan.json').read_text())
check=plan['checks'][0]
c=check['conditions']
request={k:c[k] for k in ['unit','frame','clearance','overlap_tolerance','pairs']}
request['parts']=[{'id':i,'path':p,'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()} for i,p in c['parts'].items()]
Path(check['report']).write_text(json.dumps(screen_report('.',request,check)))
'''


def main(destination):
    out=Path(destination).resolve(); out.mkdir(parents=True,exist_ok=False)
    source=out/'source'; source.mkdir()
    for name,x in [('a',0),('b',5)]:
        cq.export_step(cq.box(10,10,10).translate((x,0,0)),str(source/(name+'.step')))
    (source/'evaluator.py').write_text(EVALUATOR)
    (source/'wire.json').write_text('{"clearance_model":"initial"}')
    (source/'control.py').write_text('LIMIT_MM = 5\n')
    check={'id':'clearance','scope':'placement','components':['assembly'],'required':True,
        'inputs':['a.step','b.step','evaluator.py'],'report':'collision.json',
        'conditions':{'unit':'mm','frame':'assembly','clearance':1,'overlap_tolerance':.001,
                      'pairs':[['a','b']],'parts':{'a':'a.step','b':'b.step'}},
        'evaluator':{'name':'gantry.cad-screen','version':'1'},'environment':{'cad_backend':cq.BACKEND},
        'criteria':[{'metric':'violating_pairs','unit':'count','max':0}]}
    components=[{'id':i,'role':i,'assembly':'robot','paths':paths} for i,paths in
                [('assembly',['a.step','b.step']),('wire',['wire.json']),('control',['control.py'])]]
    plan={'version':1,'components':components,'checks':[check]}
    (source/'physical-plan.json').write_text(json.dumps(plan))
    mapping={'version':1,'components':components,'dependencies':[
        {'prerequisite':a,'dependent':b,'kind':'uses_geometry','status':'confirmed',
         'rationale':'Synthetic declared dependency, not extracted from native hardware'}
        for a,b in [('assembly','wire'),('wire','control')]]}
    (source/'engineering-map.json').write_text(json.dumps(mapping))
    service=Service(out/'ledger'); token=service.bootstrap()['token']
    class Client:
        def call(self,name,args=None,key=None):return service.call(token,name,args or {},key or secrets.token_hex(12))
    client=Client(); artifact,_=capture_workspace(client,source,'initial')
    scope=['b.step','collision.json','cad-operation.json','.gantry-evidence/']
    session=client.call('connect_development',{'title':'Anonymous engineering roundtrip','snapshot':artifact['revision_id'],
        'capture':{'scope':'saved fixture files','missing':[]},'unverified':['dynamics','strength','electrical'],
        'mode':'record','actors':['admin'],'write_scope':scope,'recipes':{},'max_executions':3,'timeout_seconds':60,'max_parallel':1})
    base=client.call('initialize_continuity',{'session_id':session['id'],'version':session['version'],
        'summary':'Intersecting cubes before engineering','hierarchy':[{'id':'robot','title':'Fixture','kind':'robot',
        'paths':['a.step','b.step'],'editable':True}], 'context':{'requirements':['Static separation'],
        'constraints':['No physical operation'],'decisions':[],'open_questions':['Whole system validation'],'environment':{}}})
    root=Path(checkout(client,base['id'],out/'checkout','Clearance','Exercise complete path',scope,'admin','checkout')['workspace'])
    bind_mapping(client,root,'engineering-map.json','Register explicit fixture dependencies','bind')
    recipe={'argv':[sys.executable,'-I','-c',
        'import runpy,sys;sys.path.insert(0,sys.argv[1]);runpy.run_path("evaluator.py",run_name="__main__")',str(REPO)],
        'timeout_seconds':60}
    def evaluate(number):
        job=out/('job-'+str(number))
        receipt=run(root,'physical-plan.json','clearance',recipe,digest(recipe),job,link(client,root)['state_id'])
        old=hashlib.sha256((root/'collision.json').read_bytes()).hexdigest() if (root/'collision.json').exists() else None
        collect(job,root,old)
        return receipt
    first=evaluate(1); assert first['evaluation']['status']=='fail'
    failed=publish(client,root,'physical-plan.json','failed')
    prior=hashlib.sha256((root/'b.step').read_bytes()).hexdigest()
    with measure(root/'.gantry/engineering','editing',failed['state']['id'],'move-part'):
        edit(root,{'unit':'mm','frame':'assembly','steps':[
            {'id':'old','op':'import_step','path':'b.step','sha256':prior},
            {'id':'b','op':'translate','source':'old','vector':[15,0,0]}],'export':['b']},out/'edited')
        assert hashlib.sha256((root/'b.step').read_bytes()).hexdigest()==prior
        for name in ['b.step','cad-operation.json']: shutil.copyfile(out/'edited'/name,root/name)
    candidate=publish(client,root,'physical-plan.json','edited')
    assert candidate['state']['context']['environment']['engineering']['checks'][0]['status']=='unknown'
    second=evaluate(2); assert second['evaluation']['status']=='pass'
    class LostAck(Client):
        def call(self,name,args=None,key=None):
            result=super().call(name,args,key)
            if name=='checkpoint_change': raise ConnectionError('Synthetic lost acknowledgement after real commit')
            return result
    try: publish(LostAck(),root,'physical-plan.json','fixed')
    except ConnectionError: pass
    fixed=publish(client,root,'physical-plan.json','fixed')
    reopened=status(client,root)
    assert reopened['development']['engineering']['checks'][0]['effective_status']=='pass'
    assert reopened['development']['engineering']['dependency_impact']['affected_components']==['control','wire']
    restore_development_state(client,fixed['state']['id'],out/'restored','restore')
    assert (out/'restored/workspace/b.step').read_bytes()==(root/'b.step').read_bytes()
    assert reopened['development']['status']['adoption']=='unadopted'
    assert client.call('replay')['matched']
    summary={'runtime':{'python':sys.version.split()[0],'cad_backend':cq.BACKEND},
        'static_cad_results':[first['evaluation']['status'],second['evaluation']['status']],
        'downstream_reassessment':reopened['development']['engineering']['dependency_impact']['affected_components'],
        'lost_ack_recovered':True,'restored_bytes_match':True,'replay_matches':True,'adoption':'unadopted',
        'timings':{name:timing_report(path) for name,path in [('workflow',root/'.gantry/engineering'),('first_solver',out/'job-1'),('second_solver',out/'job-2')]},
        'limitations':['Real static geometry only; no dynamics/FEA/electrical/native commercial CAD run',
                      'Lost acknowledgement injected deliberately; no inference provider invoked',
                      'Functional evidence, not a development-speed comparison']}
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps({k:v for k,v in summary.items() if k!='timings'},indent=2))


if __name__=='__main__': main(sys.argv[1])
