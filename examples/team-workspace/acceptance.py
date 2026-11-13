"""Actual local cloud HTTP + two identities + exact restore. Anonymous fixtures only."""
import argparse
import json
from pathlib import Path
import threading
import time
from gantry.cloud import provision,make_request,backup,restore
from gantry.client import Client
from gantry.model import digest,Fault
from gantry.server import CloudServer
from gantry.workspace import Workspace,import_workspace,continue_workspace


def run(output):
    output=Path(output).resolve();output.mkdir(mode=0o700,parents=True,exist_ok=False)
    p=provision(output/'cloud','team','owner');other=provision(output/'cloud','other','other-owner')
    server=CloudServer(('127.0.0.1',0),output/'cloud');thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url=f'http://127.0.0.1:{server.server_port}/w/team'
    owner=Client(url,Path(p['token_file']).read_text().strip())
    started=time.monotonic()
    try:
        source=output/'source';source.mkdir();(source/'control').mkdir();(source/'mechanical').mkdir()
        from gantry import cad_kernel as cq
        cq.export_step(cq.box(20,30,4),str(source/'mechanical'/'bracket.step'))
        (source/'control'/'main.py').write_text('offset_mm = 0\n')
        mapping={'name':'Bench assembly','description':'Anonymous local acceptance fixture','paths':['control/','mechanical/'],
          'hierarchy':[{'id':'bench','title':'Bench','kind':'robot','paths':['control/','mechanical/'],'editable':True}],
          'context':{'requirements':['Keep shared mechanical baseline'],'constraints':['No physical operation'],
                     'decisions':[],'open_questions':['Dynamic motion not tested'],'environment':{'cad_backend':cq.BACKEND}},
          'title':'Adjust controller','purpose':'Continue shared development','write_scope':['control/'],
          'dependencies':['mechanical/bracket.step'],'actors':[],'missing':['Earlier tool history']}
        imported=import_workspace(owner,source,mapping,True);w=Workspace(owner,source)
        (source/'control'/'main.py').write_text('offset_mm = 2\n');captured=w.sync();w.share('Unfinished handoff')
        view=owner.call('studio_work',{'work_id':imported['work_id']})
        sid=view['work']['session_id'];session=owner.call('development_state',{'session_id':sid})['session']
        generated=make_request('teammate',p['ledger_id'],'contributor',['root'],output/'member.token',output/'request.json')
        request=json.loads((output/'request.json').read_text())
        grant=owner.call('grant_workspace_member',{'request':request,'fingerprint':generated['fingerprint'],
            'sessions':[{'session_id':sid,'version':session['version']}],'reason':'Acceptance two-user collaboration'},'grant')
        teammate=Client(url,(output/'member.token').read_text().strip())
        continued=continue_workspace(teammate,imported['work_id'],captured['state_id'],output/'continuation','Control follow-up')
        restored=Path(continued['workspace'])
        assert (restored/'control'/'main.py').read_text()=='offset_mm = 2\n'
        shape=cq.import_step(str(restored/'mechanical'/'bracket.step'))
        assert abs(shape.Volume()-2400)<0.01
        new=Workspace(teammate,restored);(restored/'control'/'main.py').write_text('offset_mm = 3\n');new.sync();new.share()
        next_view=teammate.call('studio_work',{'work_id':continued['work_id']})
        assert next_view['selected']['status']['adoption']=='unadopted'
        assert next_view['selected']['status']['verification']=='unverified'
        try:Client(url.replace('/team','/other'),teammate.token).call('identity');raise AssertionError('cross-workspace access')
        except Fault as exc:assert exc.code=='unauthorized'
        copied=backup(p['directory'],output/'backup');recovered=restore(output/'backup',output/'recovery','team')
        recovery_server=CloudServer(('127.0.0.1',0),output/'recovery')
        rt=threading.Thread(target=recovery_server.serve_forever,daemon=True);rt.start()
        try:
            recovered_client=Client(f'http://127.0.0.1:{recovery_server.server_port}/w/team',teammate.token)
            assert recovered_client.call('studio_work',{'work_id':continued['work_id']})['selected']['manifest']==next_view['selected']['manifest']
        finally:recovery_server.shutdown();recovery_server.server_close();rt.join()
        owner.call('revoke_workspace_member',{'member_id':'teammate','expected_revision':grant['revision_id'],'reason':'End acceptance'},'revoke')
        try:teammate.call('identity');raise AssertionError('revoked access')
        except Fault as exc:assert exc.code=='unauthorized'
        assert owner.call('replay')['matched']
        report={'result':'pass','elapsed_seconds':round(time.monotonic()-started,3),
          'actual':['Cloud HTTP','CadQuery STEP save and reopened restored volume','member request/grant',
                    'scoped independent continuation','cross-workspace rejection','shared yet unverified/unadopted',
                    'backup and HTTP restore','revocation','ledger replay'],
          'not_tested':['public TLS/systemd','licensed native desktop APIs','real customer assembly','speedup'],
          'baseline_volume_mm3':2400,'restored_volume_mm3':shape.Volume(),'backup_blobs':copied['blobs']}
        (output/'results.json').write_text(json.dumps(report,indent=2)+'\n');return report
    finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    print(json.dumps(run(parser.parse_args().output),indent=2))
