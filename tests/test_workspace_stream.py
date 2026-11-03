import unittest
from pathlib import Path
import test_workspace_client as fixtures
from gantry.model import Fault

class StreamTests(unittest.TestCase):
    setUp=fixtures.WorkspaceClientTests.setUp
    tearDown=fixtures.WorkspaceClientTests.tearDown
    call=fixtures.WorkspaceClientTests.call
    artifact=fixtures.WorkspaceClientTests.artifact
    connect=fixtures.WorkspaceClientTests.connect
    policy=fixtures.WorkspaceClientTests.policy
    fault=fixtures.WorkspaceClientTests.fault
    imported=fixtures.WorkspaceClientTests.imported
    workspace=fixtures.WorkspaceClientTests.workspace

    def test_large_file_and_many_paths_continue_with_frozen_lost_response(self):
        from gantry.workspace import Workspace,continue_workspace
        w,r=self.workspace()
        big=w.root/'mechanical/part.step';big.write_bytes(b'x'*(33*1024*1024))
        for i in range(1001):(w.root/f'control/p{i}.py').write_text(f'v={i}\n')
        original=self.client.call
        def lost(name,args=None,key=None):
            result=original(name,args,key)
            if name=='studio_sync_update':raise OSError('lost')
            return result
        self.client.call=lost
        with self.assertRaises(OSError):w.sync()
        stage=Path(w.saved()['pending']['stage']['directory'])
        self.assertTrue(stage.is_dir())
        big.write_bytes(b'next edit must not replace pending')
        self.client.call=original
        resumed=Workspace(self.client,w.root);resumed.sync()
        self.assertFalse(stage.exists())
        view=self.call('studio_work',{'work_id':r['change']['id']})
        self.assertEqual(view['selected']['manifest']['mechanical/part.step']['size'],33*1024*1024)
        self.assertEqual(len(view['versions']),2)
        self.assertEqual(len(view['selected']['manifest']),1004)
        self.assertTrue(resumed.status()['changes'])
        result=continue_workspace(self.client,r['change']['id'],view['selected']['state']['id'],self.root/'restored','Continue')
        self.assertEqual((Path(result['workspace'])/'mechanical/part.step').stat().st_size,33*1024*1024)
        self.assertEqual(view['selected']['status']['adoption'],'unadopted')
        self.assertTrue(self.call('replay')['matched'])

    def test_stream_capture_refuses_secret_link_and_wrong_scope(self):
        from gantry.workspace_stream import inspect
        w,r=self.workspace();p=w.root/'control/main.py'
        p.write_bytes(b'x'*(17*1024*1024)+b' ghp_'+b'a'*40)
        self.fault('capture_incomplete',w.sync)
        p.unlink();p.symlink_to(w.root/'test.py')
        self.fault('capture_incomplete',lambda:inspect(w.root,['control/']))
        self.assertEqual(self.call('studio_work',{'work_id':r['change']['id']})['work']['version'],1)

    def test_snapshot_sync_enforces_scope_and_exact_head(self):
        w,r=self.workspace();snap=self.artifact({'mechanical/part.step':'native','control/main.py':'offset=1','test.py':'weakened'})
        args={'work_id':r['change']['id'],'version':1,'expected_state':r['state']['id'],'snapshot':snap,
              'files':{},'deleted':[],'summary':'Bad scope','rationale':'Fixture','unfinished':[],'missing':[]}
        self.fault('scope_denied',lambda:self.call('studio_sync_update',args))
        self.assertEqual(self.call('studio_work',{'work_id':r['change']['id']})['work']['version'],1)

    def test_large_initial_import_and_checkpointed_source_are_restorable(self):
        from gantry.workspace import import_workspace
        root=self.root/'initial';root.mkdir();(root/'mechanical').mkdir()
        for i in range(1001):(root/f'mechanical/p{i}.step').write_text('saved fixture '+str(i))
        manifest={'name':'Large saved set','description':'Synthetic fixture','paths':['mechanical/'],
            'hierarchy':[{'id':'assembly','title':'Assembly','kind':'robot','paths':['mechanical/'],'editable':True}],
            'context':{'requirements':[],'constraints':[],'decisions':[],'open_questions':[],'environment':{}},
            'title':'Continue assembly','purpose':'Import saved work','write_scope':['mechanical/'],
            'dependencies':[],'actors':[],'missing':[]}
        self.assertEqual(len(import_workspace(self.client,root,manifest)['files']),1001)
        result=import_workspace(self.client,root,manifest,True)
        self.assertEqual(list((root/'.gantry/uploads').iterdir()),[])
        self.assertEqual(result,import_workspace(self.client,root,manifest,True))
        view=self.call('studio_work',{'work_id':result['work_id']})
        self.assertEqual(len(view['selected']['manifest']),1001)
        self.assertEqual(view['selected']['status']['verification'],'unverified')

    def test_cleanup_retries_after_durable_success_and_refuses_another_tree(self):
        from unittest.mock import patch
        from gantry.workspace_stream import freeze,cleanup
        from gantry.project_connect import save
        from gantry.workspace import scan
        w,r=self.workspace()
        _,hashes,_=scan(w.root,['control/'])
        stage=freeze(w.root,['control/'],hashes,w.meta/'uploads/workspace-sync_fixture')
        obj=w.saved();obj['cleanup_stage']=stage;save(w.path,obj)
        with patch('gantry.workspace_stream.cleanup',side_effect=OSError('busy')):
            self.fault('cleanup_pending',w.sync)
        self.assertIn('cleanup_stage',w.saved())
        w.sync()
        self.assertFalse(Path(stage['directory']).exists())
        self.assertNotIn('cleanup_stage',w.saved())
        outside=w.root/'keep';outside.mkdir();(outside/'saved.py').write_text('keep')
        forged={**stage,'directory':str(outside)}
        self.fault('scope_denied',lambda:cleanup(w.meta,forged))
        self.assertEqual((outside/'saved.py').read_text(),'keep')

    def test_failed_freeze_and_interrupted_pre_outbox_capture_are_recovered(self):
        from gantry.workspace_stream import freeze,recover_staging
        from gantry.workspace import scan
        w,r=self.workspace();_,hashes,_=scan(w.root,['control/'])
        target=w.meta/'uploads/workspace-sync_failed'
        self.fault('capture_incomplete',lambda:freeze(w.root,['control/'],{},target))
        self.assertFalse(target.exists())
        abandoned=freeze(w.root,['control/'],hashes,w.meta/'uploads/workspace-sync_abandoned')
        protected=freeze(w.root,['control/'],hashes,w.meta/'uploads/workspace-sync_pending')
        recover_staging(w.meta,'workspace-sync',[protected])
        self.assertFalse(Path(abandoned['directory']).exists())
        self.assertTrue(Path(protected['directory']).exists())
        # Simulate interruption between mkdir and the identity journal update.
        from gantry.project_connect import save
        empty=w.meta/'uploads/workspace-sync_empty';empty.mkdir(mode=0o700)
        save(empty.parent/('.'+empty.name+'.json'),{'directory':str(empty),'device':None,'inode':None})
        recover_staging(w.meta,'workspace-sync',[protected])
        self.assertFalse(empty.exists())
