"""Explicit, isolated sample workspace. No real engineering results or live agents.
Run with PYTHONPATH=. python examples/studio-demo/run.py --output /new/directory.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import secrets
from gantry.service import Service, token_hash
from gantry.server import Server


def box(x,y,z,dx,dy,dz):
    vs=[(x+i*dx,y+j*dy,z+k*dz) for i,j,k in [(0,0,0),(1,0,0),(1,1,0),(0,1,0),(0,0,1),(1,0,1),(1,1,1),(0,1,1)]]
    faces=[(0,2,1),(0,3,2),(4,5,6),(4,6,7),(0,1,5),(0,5,4),(1,2,6),(1,6,5),(2,3,7),(2,7,6),(3,0,4),(3,4,7)]
    return ''.join('facet normal 0 0 0\nouter loop\n'+''.join('vertex %s %s %s\n'%vs[i] for i in f)+'endloop\nendfacet\n' for f in faces)


def seed(root):
    root.mkdir(parents=True,exist_ok=False)
    service=Service(root/'ledger'); token=service.bootstrap('designer')['token']
    tokenfile=root/'access.token';tokenfile.write_text(token);tokenfile.chmod(0o600)
    def call(name,args=None):return service.call(token,name,args or {},secrets.token_hex(12))
    for aid,kind in [('controls-agent','agent'),('mechanical-reviewer','human')]:
        own=secrets.token_urlsafe(32);p=call('propose',{'title':'Demo participant','changes':[{'id':aid,'type':'principal','data':{'kind':kind,'permissions':['read','record','work'],'token_hash':token_hash(own)}}]})
        args={'proposal_id':p['id'],'version':p['version']};call('submit',args);call('endorse',{**args,'reason':'Isolated demo setup'});call('review_adoption',{**args,'reason':'Isolated demo setup','verdict':'approve'});call('commit',args)
        path=root/(aid+'.token');path.write_text(own);path.chmod(0o600)
    def mesh(body):return 'solid demo\n'+body+'endsolid demo\n'
    files={'cad/base.stl':mesh(box(-40,-35,0,80,70,8)+box(-15,-15,8,30,30,18)),
           'cad/carriage.stl':mesh(box(-12,-12,26,24,24,65)+box(-16,-16,80,32,32,22)+box(0,-10,88,70,20,18)+box(60,-14,84,24,28,26)),
           'cad/sensor-bracket.stl':mesh(box(64,-23,86,14,8,5)+box(64,-23,86,5,8,23)),
           'cad/gripper.stl':mesh(box(84,-15,89,15,30,16)+box(99,-15,89,25,6,16)+box(99,9,89,25,6,16)),
           'control/motion.py':'# Demo control interface — not robot-tested\nSETTLE_TIME = 0.15\n\ndef move_axis(axis, target):\n    axis.move_to(target)\n    axis.wait(SETTLE_TIME)\n    return axis.position()\n',
           'README.md':'# Isolated Studio sample\nInvented robot, geometry, people and results. No actual product or inference run.\n'}
    def capture(values):return call('capture_artifact',{'files':{p:base64.b64encode(v.encode()).decode() for p,v in values.items()},'source':{'type':'explicit_demo','repository':'example/desktop-robot-arm','commit':'sample-only'},'capture_scope':'generated sample files'})['revision_id']
    snapshot=capture(files)
    d=call('connect_development',{'title':'Demo desktop robot arm development','snapshot':snapshot,'capture':{'scope':'Sample saved artifacts','missing':['native CAD model','physical tests','live tools']},'unverified':['all physical behavior'],
        'mode':'record','actors':['designer','controls-agent','mechanical-reviewer'],'write_scope':['cad/','control/'],'recipes':{},'max_executions':0,'timeout_seconds':30,'max_parallel':1})
    hierarchy=[{'id':'robot','title':'Desktop robot arm','kind':'robot','paths':['cad/','control/'],'editable':True},
        {'id':'wrist','parent':'robot','title':'Arm & joints','kind':'assembly','paths':['cad/carriage.stl'],'editable':True},
        {'id':'structure','parent':'robot','title':'Base','kind':'mechanical','paths':['cad/base.stl'],'editable':True},
        {'id':'carriage','parent':'wrist','title':'Forearm','kind':'mechanical','paths':['cad/carriage.stl'],'editable':True},
        {'id':'gripper','parent':'robot','title':'Gripper','kind':'mechanical','paths':['cad/gripper.stl'],'editable':True},
        {'id':'sensor','parent':'wrist','title':'Sensor bracket','kind':'mechanical','paths':['cad/sensor-bracket.stl'],'editable':True},
        {'id':'control','parent':'robot','title':'Motion control','kind':'software','paths':['control/'],'editable':True}]
    state=call('initialize_continuity',{'session_id':d['id'],'version':d['version'],'hierarchy':hierarchy,
        'context':{'requirements':[],'constraints':[],'decisions':[],'open_questions':['Physical performance not tested'],'environment':{'studio_demo':True}},'summary':'Demo baseline'})
    project=call('save_project',{'name':'Desktop robot arm','description':'Explicit sample workspace. Not actual engineering evidence.','baseline_state':state['id']})
    call('link_product_session',{'session_id':d['id'],'project_id':project['id']})
    first=call('begin_change',{'state_id':state['id'],'title':'Refine the sensor bracket','purpose':'Share an unfinished clearance idea','assignee':'designer','write_scope':['cad/sensor-bracket.stl','control/motion.py'],'dependencies':['cad/base.stl']})
    new=dict(files);new['cad/sensor-bracket.stl']=mesh(box(62,-23,86,14,8,5)+box(62,-23,86,5,8,23));new['control/motion.py']=new['control/motion.py'].replace('0.15','0.25')
    cp=call('checkpoint_change',{'change_id':first['id'],'version':first['version'],'snapshot':capture(new),'summary':'Bracket moved inward; checks pending','rationale':'Sample hypothesis','unfinished':['Physical clearance'],'work_status':'working','capture':{'scope':'saved sample files','missing':['native model','tool history']}})
    shared=call('studio_share_update',{'work_id':first['id'],'version':cp['change']['version'],'state_id':cp['state']['id'],'note':'Sample intermediate update. Motion review still needed.'})
    call('studio_comment',{'work_id':first['id'],'state_id':cp['state']['id'],'anchor':{'kind':'cad','path':'cad/sensor-bracket.stl','part':'cad/sensor-bracket.stl','hash':hashlib.sha256(new['cad/sensor-bracket.stl'].encode()).hexdigest()},'body':'@designer Can we check this bracket through the full range of motion?','mentions':['designer']})
    second=call('begin_change',{'state_id':state['id'],'title':'Adjust the settling interval','purpose':'Coordinate the controller with the assembly','assignee':'controls-agent','write_scope':['control/'],'dependencies':[]})
    call('begin_change',{'state_id':state['id'],'title':'Review service access','purpose':'Check access before detailing fasteners','assignee':'mechanical-reviewer','write_scope':['cad/base.stl'],'dependencies':[]})
    (root/'motion.py').write_text(new['control/motion.py'].replace('0.25','0.30'))
    (root/'fixture.json').write_text(json.dumps({'project':project['id'],'work':first['id'],'state':cp['state']['id'],'other_work':second['id']}))
    return service


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--port',type=int,default=8793);args=parser.parse_args()
    service=seed(args.output)
    print(f'Sample Studio: http://127.0.0.1:{args.port}/#studio\nToken file: {args.output}/access.token',flush=True)
    Server(('127.0.0.1',args.port),service).serve_forever()
