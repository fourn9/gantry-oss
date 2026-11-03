"""Real HTTP + saved native CAD + independent identity continuation. Anonymous fixture.
Run with an installed optional CadQuery runtime; no LLM, vendor CAD or physical test.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import secrets
import threading
import cadquery as cq
from gantry.service import Service, token_hash
from gantry.server import Server
from gantry.client import Client
from gantry.workspace import Workspace, import_workspace, continue_workspace
from gantry.cad_io import edit
from gantry.hardware import screen_report


def run(output,port=0,keep=False):
    output.mkdir(parents=True,exist_ok=False)
    service=Service(output/'ledger');token=service.bootstrap('designer')['token']
    path=output/'access.token';path.write_text(token);path.chmod(0o600)
    server=Server(('127.0.0.1',port),service);threading.Thread(target=server.serve_forever,daemon=True).start()
    client=Client('http://127.0.0.1:'+str(server.server_port),token)
    source=output/'source'
    for folder in ['cad','control','checks']:(source/folder).mkdir(parents=True,exist_ok=True)
    for name,offset in [('base',0),('carriage',5)]:
        shape=cq.Workplane().box(10,10,10).translate((offset,0,0))
        cq.exporters.export(shape,str(source/('cad/'+name+'.step')))
        cq.exporters.export(shape,str(source/('cad/'+name+'.stl')))
    (source/'control/motion.py').write_text('OFFSET_MM = 5\n')
    (source/'checks/README.md').write_text('Static clearance only. No strength or dynamic claims.\n')
    hashes=lambda names:{name:hashlib.sha256((source/name).read_bytes()).hexdigest() for name in names}
    inputs=hashes(['cad/base.step','cad/carriage.step','control/motion.py'])
    context={'requirements':['At least 1 mm static separation'], 'constraints':['No physical operations'],
        'decisions':[],'open_questions':['Dynamic behavior and structural strength'],
        'environment':{'cadquery':cq.__version__,'unit':'mm','frame':'assembly',
            'engineering':{'version':1,'components':[{'id':'head','role':'carriage and matching control',
                'assembly':'bench','inputs':inputs}], 'checks':[{'id':'clearance','scope':'placement',
                'required':True,'status':'unverified','components':['head'],'inputs':inputs}]}}}
    teammate=secrets.token_urlsafe(32)
    p=client.call('propose',{'title':'Add fixture teammate','changes':[{'id':'controls','type':'principal',
        'data':{'kind':'human','permissions':['read','record','work'],'token_hash':token_hash(teammate)}}]})
    ref={'proposal_id':p['id'],'version':p['version']}
    client.call('submit',ref);client.call('endorse',{**ref,'reason':'Isolated fixture'})
    client.call('review_adoption',{**ref,'reason':'Identity setup only','verdict':'approve'});client.call('commit',ref)
    manifest={'paths':['cad/','control/','checks/'],'name':'Bench assembly','description':'Anonymous connection acceptance',
        'title':'Separate the carriage','purpose':'Remove static interference','hierarchy':[
            {'id':'bench','title':'Bench assembly','kind':'assembly','paths':['cad/','control/','checks/'],'editable':True},
            {'id':'head','parent':'bench','title':'Carriage & controller','kind':'subsystem','paths':['cad/','control/'],'editable':True}],
        'context':context,'write_scope':['cad/','control/','checks/'],'dependencies':['cad/base.step'],'actors':['controls'],'missing':['Pre-import tool history']}
    (output/'project.json').write_text(json.dumps(manifest,indent=2))
    preview=import_workspace(client,source,manifest);assert preview['sent'] is False
    imported=import_workspace(client,source,manifest,True);w=Workspace(client,source)
    request={'unit':'mm','frame':'assembly','clearance':1,'overlap_tolerance':.001,
        'parts':[{'id':n,'path':'cad/'+n+'.step','sha256':inputs['cad/'+n+'.step']} for n in ('base','carriage')],
        'pairs':[['base','carriage']]}
    before=screen_report(source,request,{'inputs':['cad/base.step','cad/carriage.step']})
    assert before['measurements']['violating_pairs']['value']==1
    edit(source,{'unit':'mm','frame':'assembly','steps':[
        {'id':'a','op':'import_step','path':'cad/carriage.step','sha256':inputs['cad/carriage.step']},
        {'id':'moved','op':'translate','source':'a','vector':[10,0,0]}],'export':['moved']},output/'cad-edit')
    (source/'cad/carriage.step').write_bytes((output/'cad-edit/moved.step').read_bytes())
    cq.exporters.export(cq.importers.importStep(str(source/'cad/carriage.step')),str(source/'cad/carriage.stl'))
    cp=w.sync('Carriage moved 10 mm','Real STEP translation; controller still pending',['Align controller; retest'])
    w.share('Unfinished CAD ready for controls')
    other=Client(client.url,teammate)
    handoff=continue_workspace(other,imported['work_id'],cp['state_id'],output/'teammate','Align controller and verify',
        write_scope=['control/','checks/'],dependencies=['cad/base.step','cad/carriage.step'])
    continued=Path(handoff['workspace']);assert (continued/'cad/carriage.step').read_bytes()==(source/'cad/carriage.step').read_bytes()
    (continued/'control/motion.py').write_text('OFFSET_MM = 15\n')
    request['parts'][1]['sha256']=hashlib.sha256((continued/'cad/carriage.step').read_bytes()).hexdigest()
    report=screen_report(continued,request,{'inputs':['cad/base.step','cad/carriage.step']})
    assert report['measurements']['violating_pairs']['value']==0
    (continued/'checks/clearance.json').write_text(json.dumps(report))
    new_context=copy.deepcopy(context)
    new_inputs={p:hashlib.sha256((continued/p).read_bytes()).hexdigest() for p in inputs}
    new_context['environment']['engineering']['components'][0]['inputs']=new_inputs
    check=new_context['environment']['engineering']['checks'][0]
    check.update(inputs=new_inputs,status='pass',evidence={'checks/clearance.json':hashlib.sha256((continued/'checks/clearance.json').read_bytes()).hexdigest()})
    cw=Workspace(other,continued);tested=cw.sync('Controller aligned; static separation measured','Saved native geometry and report',['Dynamic/strength tests'],new_context)
    cw.share('Static check only; physical validation remains')
    detail=other.call('studio_work',{'work_id':handoff['work_id']})
    assert detail['selected']['engineering']['checks'][0]['effective_status']=='pass'
    (continued/'control/motion.py').write_text('OFFSET_MM = 16\n');cw.sync('Dependency changed','Probe stale evidence')
    changed=other.call('studio_work',{'work_id':handoff['work_id']})
    assert changed['selected']['engineering']['checks'][0]['effective_status']=='unknown'
    assert changed['selected']['status']['adoption']=='unadopted'
    assert client.call('replay')['matched']
    results={'transport':'real loopback HTTP','native_runtime':'CadQuery '+cq.__version__,
        'project_id':imported['project_id'],'mechanical_work':imported['work_id'],'controls_work':handoff['work_id'],
        'shared_state':cp['state_id'],'tested_state':tested['state_id'],
        'initial_violating_pairs':before['measurements']['violating_pairs']['value'],
        'updated_violating_pairs':report['measurements']['violating_pairs']['value'],
        'changed_input_check':'unknown','adoption':'unadopted','identity_handoff':'designer → controls',
        'model_calls':0,'limits':['Anonymous simple solids; not a product test','No licensed CAD API','No dynamics or strength test'],
        'url':client.url+'/#studio-work/'+handoff['work_id']}
    (output/'results.json').write_text(json.dumps(results,indent=2));print(json.dumps(results,indent=2),flush=True)
    if keep:
        try: threading.Event().wait()
        except KeyboardInterrupt: pass
    server.shutdown();server.server_close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--port',type=int,default=0);p.add_argument('--serve',action='store_true');a=p.parse_args();run(a.output,a.port,a.serve)
