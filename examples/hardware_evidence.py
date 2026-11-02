"""Synthetic real-CAD demo: collision -> edit -> pass; strength remains unverified.

Run with CadQuery installed: python examples/hardware_evidence.py NEW_DIRECTORY
No external accounts, models, physical equipment or private project data.
"""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import secrets
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cadquery as cq
from gantry.service import Service
from gantry.continuity_adapter import capture_workspace
from gantry.cad_io import edit
from gantry.hardware import screen_report, publish


def main(destination):
    out=Path(destination);out.mkdir(parents=True,exist_ok=False)
    root=out/'candidate';root.mkdir()
    service=Service(out/'ledger');token=service.bootstrap()['token']
    class Client:
        def call(self,op,args=None,key=None):return service.call(token,op,args or {},key or secrets.token_hex(16))
    client=Client()
    for name,x in [('a',0),('b',5)]:cq.exporters.export(cq.Workplane().box(10,10,10).translate((x,0,0)),str(root/(name+'.step')))
    conditions={'unit':'mm','frame':'assembly','clearance':1,'overlap_tolerance':0.001,
                'pairs':[['a','b']],'parts':{'a':'a.step','b':'b.step'}}
    check={'id':'clearance','scope':'placement','components':['assembly'],'required':True,
        'inputs':['a.step','b.step'],'report':'collision.json','conditions':conditions,
        'evaluator':{'name':'gantry.cad-screen','version':'1'},'environment':{'cadquery':cq.__version__},
        'criteria':[{'metric':'violating_pairs','unit':'count','max':0}]}
    strength={**check,'id':'strength','scope':'structural','report':'strength.json',
        'conditions':{'load_N':100,'fixture':'not_yet_validated'},'evaluator':{'name':'external-FEA','version':'to-be-selected'},
        'environment':{'mesh':'not-yet-defined'},'criteria':[{'metric':'stress','unit':'MPa','max':50}]}
    plan={'version':1,'components':[{'id':'assembly','role':'mechanical_assembly','assembly':'robot','paths':['a.step','b.step']}],
          'checks':[check,strength]}
    (root/'physical-plan.json').write_text(json.dumps(plan,indent=2))
    artifact,_=capture_workspace(client,root,'initial')
    session=client.call('connect_development',{'title':'Synthetic CAD validation','snapshot':artifact['revision_id'],
        'capture':{'scope':'saved files','missing':[]},'unverified':['strength'],
        'mode':'record','actors':['admin'],'write_scope':['b.step','collision.json','cad-operation.json'],
        'recipes':{},'max_executions':3,'timeout_seconds':60,'max_parallel':1})
    state=client.call('initialize_continuity',{'session_id':session['id'],'version':session['version'],'summary':'Original assembly',
        'hierarchy':[{'id':'assembly','title':'Assembly','kind':'robot','paths':['a.step','b.step'],'editable':True}],
        'context':{'requirements':['Clearance at declared pose'],'constraints':['No physical operation'],
                   'decisions':[],'open_questions':['Strength'],'environment':{}}})
    change=client.call('begin_change',{'state_id':state['id'],'title':'Resolve static interference','purpose':'Verify real STEP loop',
        'write_scope':['b.step','collision.json','cad-operation.json'],'dependencies':['a.step','physical-plan.json'],'assignee':'admin'})
    def fingerprint(name):return hashlib.sha256((root/name).read_bytes()).hexdigest()
    def screen():
        request={k:conditions[k] for k in ('unit','frame','clearance','overlap_tolerance','pairs')}
        request['parts']=[{'id':n,'path':n+'.step','sha256':fingerprint(n+'.step')} for n in ['a','b']]
        result=screen_report(root,request,check)
        (root/'collision.json').write_text(json.dumps(result,indent=2))
    screen()
    failed=publish(client,state['id'],change['id'],change['version'],root,'physical-plan.json','collision')
    edit(root,{'unit':'mm','frame':'assembly','steps':[
        {'id':'old','op':'import_step','path':'b.step','sha256':fingerprint('b.step')},
        {'id':'b','op':'translate','source':'old','vector':[15,0,0]}],'export':['b']},out/'edited')
    shutil.copyfile(out/'edited/b.step',root/'b.step');shutil.copyfile(out/'edited/cad-operation.json',root/'cad-operation.json')
    screen()
    fixed=publish(client,failed['state']['id'],change['id'],failed['change']['version'],root,'physical-plan.json','fixed')
    views=[client.call('get_development_state',{'state_id':c['state']['id']}) for c in [failed,fixed]]
    statuses=[{c['id']:c['effective_status'] for c in v['engineering']['checks']} for v in views]
    assert statuses==[{'clearance':'fail','strength':'unknown'},{'clearance':'pass','strength':'unknown'}],statuses
    assert views[-1]['status']['adoption']=='unadopted'
    assert service.call(token,'replay',{},'replay')['matched']
    summary={'cadquery':cq.__version__,'checks':statuses,'states':[v['state']['id'] for v in views],
             'remaining_gaps':views[-1]['engineering']['review_gaps'],'adoption':views[-1]['status']['adoption'],
             'note':'Real static CAD computation. No FEA or physical prototype test executed.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))

if __name__=='__main__':main(sys.argv[1])
