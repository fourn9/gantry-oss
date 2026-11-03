import base64
import unittest
import test_studio as studio_fixtures

b64 = lambda s: base64.b64encode(s.encode()).decode()

class WorkspaceTests(unittest.TestCase):
    setUp=studio_fixtures.StudioTests.setUp
    tearDown=studio_fixtures.StudioTests.tearDown
    call=studio_fixtures.StudioTests.call
    artifact=studio_fixtures.StudioTests.artifact
    connect=studio_fixtures.StudioTests.connect
    policy=studio_fixtures.StudioTests.policy
    fault=studio_fixtures.StudioTests.fault

    def imported(self):
        return self.call('studio_import_project', {
            'name':'Bench assembly', 'description':'Existing saved development',
            'files':{'mechanical/part.step':b64('native'), 'control/main.py':b64('offset=1'), 'test.py':b64('test')},
            'hierarchy':[{'id':'assembly','title':'Assembly','kind':'robot','paths':['mechanical/','control/','test.py'],'editable':True}],
            'context':{'requirements':['Travel 10 mm'],'constraints':['No hardware execution'],
                'decisions':[], 'open_questions':['Routing clearance'], 'environment':{'python':'3.12'}},
            'title':'Adjust carriage', 'purpose':'Improve clearance', 'write_scope':['mechanical/','control/'],
            'dependencies':['test.py'], 'actors':[], 'missing':['Earlier history'],
        }, 'import-once')

    def test_import_creates_actual_studio_project_and_immutable_unverified_work(self):
        r=self.imported();self.assertEqual(r,self.imported())
        v=self.call('studio_work',{'work_id':r['change']['id']})
        self.assertEqual(v['work']['project_id'],r['project']['id'])
        self.assertEqual(v['selected']['state']['context']['requirements'],['Travel 10 mm'])
        self.assertEqual(v['selected']['status']['verification'],'unverified')
        self.assertEqual(v['selected']['status']['adoption'],'unadopted')
        self.assertEqual(len(self.call('studio_overview')['projects']),1)
        self.assertTrue(self.call('replay')['matched'])

    def sync(self,r,**kw):
        return self.call('studio_sync_update',{'work_id':r['change']['id'], 'version':r['change']['version'],
            'expected_state':r['state']['id'],'files':{'control/main.py':b64('offset=2')},'deleted':[],
            'summary':'Saved edits','rationale':'Clearance adjustment','unfinished':['Motion test'], 'missing':[], **kw})

    def test_incremental_update_retains_context_and_requires_exact_base(self):
        r=self.imported();cp=self.sync(r)
        v=self.call('studio_work',{'work_id':r['change']['id']})
        self.assertIn('mechanical/part.step',v['selected']['manifest'])
        self.assertEqual(v['selected']['state']['context'],r['state']['context'])
        self.fault('stale_basis',lambda:self.sync(r))
        self.fault('stale_basis',lambda:self.sync(cp,expected_state=r['state']['id']))
        self.assertEqual(v['selected']['status']['sharing'],'local')
        removed=self.sync(cp,files={},deleted=['mechanical/part.step'])
        detail=self.call('get_development_state',{'state_id':removed['state']['id']})
        self.assertNotIn('mechanical/part.step',detail['manifest'])
        self.assertEqual(detail['diffs'][0]['kind'],'deleted')
        self.assertTrue(self.call('replay')['matched'])

    def test_sync_rejects_scope_credentials_and_conflicting_operations_atomically(self):
        r=self.imported()
        self.fault('scope_denied',lambda:self.sync(r,deleted=['test.py']))
        self.fault('invalid_input',lambda:self.sync(r,deleted=['control/main.py']))
        self.fault('scope_denied',lambda:self.sync(r,files={'control/.env':b64('secret')}))
        self.fault('credential_detected',lambda:self.sync(r,files={'control/main.py':b64('ghp_'+'x'*40)}))
        v=self.call('studio_work',{'work_id':r['change']['id']})
        self.assertEqual(v['work']['version'],r['change']['version'])

    def test_other_identity_cannot_checkpoint_this_work(self):
        import secrets
        from gantry.service import token_hash
        r=self.imported();token=secrets.token_urlsafe(32)
        p=self.call('propose',{'title':'Independent teammate','changes':[{'id':'outsider','type':'principal',
            'data':{'kind':'human','permissions':['read','record','work'],'token_hash':token_hash(token)}}]})
        ref={'proposal_id':p['id'],'version':p['version']}
        self.call('submit',ref);self.call('endorse',{**ref,'reason':'Fixture'})
        self.call('review_adoption',{**ref,'reason':'Fixture','verdict':'approve'});self.call('commit',ref)
        args={'work_id':r['change']['id'],'version':1,'expected_state':r['state']['id'],
              'files':{'control/main.py':b64('offset=99')},'deleted':[],
              'summary':'Unrelated change','rationale':'Fixture','unfinished':[],'missing':[]}
        self.fault('unauthorized',lambda:self.service.call(token,'studio_sync_update',args,'outsider-sync'))
        self.assertEqual(self.call('studio_work',{'work_id':r['change']['id']})['work']['version'],1)
