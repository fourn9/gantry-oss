import json
from pathlib import Path
import unittest
import test_development as fixtures
import test_studio_workspace as workspace_fixtures


class WorkspaceClientTests(unittest.TestCase):
    setUp=fixtures.DevelopmentTests.setUp
    tearDown=fixtures.DevelopmentTests.tearDown
    call=fixtures.DevelopmentTests.call
    artifact=fixtures.DevelopmentTests.artifact
    connect=fixtures.DevelopmentTests.connect
    policy=fixtures.DevelopmentTests.policy
    fault=fixtures.DevelopmentTests.fault
    imported=workspace_fixtures.WorkspaceTests.imported

    def workspace(self):
        from gantry.workspace import Workspace
        root=self.root/'source';root.mkdir()
        for name,content in {'mechanical/part.step':'native','control/main.py':'offset=1','test.py':'test'}.items():
            p=root/name;p.parent.mkdir(exist_ok=True);p.write_text(content)
        r=self.imported();w=Workspace(self.client,root);w.bind(r['change']['id'])
        return w,r

    def test_capture_delta_and_repeated_sync_then_share(self):
        w,r=self.workspace()
        (w.root/'control/main.py').write_text('offset=2')
        (w.root/'mechanical/part.step').unlink()
        self.assertEqual(len(w.status()['changes']),2)
        result=w.sync('External save','Clearance adjustment',['Retest'])
        self.assertEqual(result['status'],'captured')
        self.assertEqual(w.sync()['status'],'up_to_date')
        self.assertEqual(w.share('Review this')['status'],'shared')
        v=self.call('studio_work',{'work_id':r['change']['id']})
        self.assertEqual(v['selected']['status']['verification'],'unverified')
        self.assertEqual(v['selected']['status']['adoption'],'unadopted')
        self.assertEqual(w.status()['pending'],False)

    def test_lost_response_replays_same_checkpoint_after_process_restart(self):
        from gantry.workspace import Workspace
        w,r=self.workspace();(w.root/'control/main.py').write_text('offset=3')
        original=self.client.call
        def lost(name,args=None,key=None):
            result=original(name,args,key)
            if name=='studio_sync_update': raise OSError('response lost')
            return result
        self.client.call=lost
        with self.assertRaises(OSError):w.sync()
        self.client.call=original
        resumed=Workspace(self.client,w.root);self.assertTrue(resumed.status()['pending'])
        resumed.sync()
        self.assertEqual(len(self.call('studio_work',{'work_id':r['change']['id']})['versions']),2)
        self.assertEqual(resumed.status()['changes'],[])

    def test_readonly_changes_and_remote_divergence_hold(self):
        w,r=self.workspace();(w.root/'test.py').write_text('weakened test')
        self.fault('scope_denied',w.sync)
        (w.root/'test.py').write_text('test')
        self.call('studio_sync_update',{'work_id':r['change']['id'],'version':1,'expected_state':r['state']['id'],
            'files':{'control/main.py':'b2Zmc2V0PTQ='},'deleted':[],'summary':'Other editor',
            'rationale':'Other editor','unfinished':[],'missing':[]})
        self.assertTrue(w.status()['remote_changed'])
        self.fault('stale_basis',w.sync)

    def test_symlink_or_secret_is_not_recorded_as_deletion(self):
        w,r=self.workspace();p=w.root/'control/main.py';p.unlink();p.symlink_to(w.root/'test.py')
        self.fault('capture_incomplete',w.sync)
        p.unlink();p.write_text('ghp_'+'x'*40)
        self.fault('capture_incomplete',w.sync)
        self.assertEqual(self.call('studio_work',{'work_id':r['change']['id']})['work']['version'],1)

    def test_continue_restores_exact_files_and_context_to_independent_work(self):
        from gantry.workspace import continue_workspace
        w,r=self.workspace();(w.root/'control/main.py').write_text('offset=2');w.sync();w.share('Ready for teammate')
        state=w.status()['state_id']
        result=continue_workspace(self.client,r['change']['id'],state,self.root/'continued','Control follow-up')
        new=Path(result['workspace']);self.assertEqual((new/'control/main.py').read_text(),'offset=2')
        self.assertEqual(json.loads((new.parent/'context.json').read_text())['state']['context']['requirements'],['Travel 10 mm'])
        self.assertNotEqual(result['work_id'],r['change']['id'])
        self.assertEqual(continue_workspace(self.client,r['change']['id'],state,self.root/'continued','Control follow-up')['work_id'],result['work_id'])

    def test_import_preview_then_apply_is_idempotent_and_watch_debounces(self):
        from gantry.workspace import Workspace, import_workspace, watch_workspace
        r=self.imported()
        args={'name':'New assembly','description':'Saved files','hierarchy':r['state']['hierarchy'],
              'context':r['state']['context'],'title':'Next task','purpose':'Continue development',
              'write_scope':['control/'],'dependencies':[],'actors':[],'paths':['control/'],'missing':[]}
        root=self.root/'initial';(root/'control').mkdir(parents=True);(root/'control/main.py').write_text('offset=1')
        preview=import_workspace(self.client,root,args)
        self.assertFalse(preview['sent']);self.assertFalse((root/'.gantry').exists())
        first=import_workspace(self.client,root,args,True)
        self.assertEqual(first,import_workspace(self.client,root,args,True))
        (root/'control/main.py').write_text('offset=5')
        events=list(watch_workspace(Workspace(self.client,root),interval=.25,iterations=2))
        self.assertEqual([e['status'] for e in events],['settling','captured'])
        view=self.call('studio_work',{'work_id':first['work_id']})
        self.assertEqual(len(view['versions']),2)
        self.assertEqual(view['selected']['status']['sharing'],'local')

    def test_browser_sharing_does_not_break_next_local_capture(self):
        w,r=self.workspace();(w.root/'control/main.py').write_text('offset=2');cp=w.sync()
        self.call('studio_share_update',{'work_id':r['change']['id'],'version':cp['version'],
            'state_id':cp['state_id'],'note':'Shared in browser'})
        (w.root/'control/main.py').write_text('offset=3')
        self.assertFalse(w.status()['remote_changed'])
        self.assertEqual(w.sync()['status'],'captured')

    def test_unreadable_directory_is_not_treated_as_deleted_files(self):
        from unittest.mock import patch
        w,r=self.workspace()
        original=__import__('os').walk
        def failed_walk(root, **kwargs):
            if kwargs.get('onerror'):
                kwargs['onerror'](PermissionError(13,'Unreadable',str(w.root/'mechanical')))
            for directory, folders, files in original(root, **kwargs):
                if Path(directory)==w.root: folders.remove('mechanical')
                yield directory,folders,files
        with patch('gantry.project_files.os.walk',failed_walk):
            self.fault('capture_incomplete',w.sync)
        self.assertEqual(self.call('studio_work',{'work_id':r['change']['id']})['work']['version'],1)

    def test_context_only_checkpoint_and_invalid_import_scope(self):
        from gantry.workspace import import_workspace
        import copy
        w,r=self.workspace();context=copy.deepcopy(r['state']['context'])
        context['decisions']=['Keep static geometry; investigate motion separately']
        self.assertEqual(w.sync(context=context)['status'],'captured')
        self.assertEqual(w.sync(context=context)['status'],'up_to_date')
        detail=self.call('studio_work',{'work_id':r['change']['id']})
        self.assertEqual(detail['selected']['state']['context'],context)
        self.assertEqual(detail['selected']['status']['verification'],'unverified')
        self.fault('invalid_input',lambda:import_workspace(self.client,w.root,{'paths':'control/'}))

    def test_malformed_context_does_not_poison_durable_outbox(self):
        w,r=self.workspace()
        self.fault('invalid_input',lambda:w.sync(context={'requirements':'incorrect type'}))
        self.assertFalse(w.saved()['pending'])
        (w.root/'control/main.py').write_text('offset=3')
        self.assertEqual(w.sync()['status'],'captured')
