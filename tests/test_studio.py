import base64
import secrets
from gantry.service import token_hash
import unittest
import test_continuity as fixtures


class StudioTests(unittest.TestCase):
    setUp = fixtures.ContinuityTests.setUp
    tearDown = fixtures.ContinuityTests.tearDown
    call = fixtures.ContinuityTests.call
    artifact = fixtures.ContinuityTests.artifact
    policy = fixtures.ContinuityTests.policy
    connect = fixtures.ContinuityTests.connect
    detail = fixtures.ContinuityTests.detail
    initialize = fixtures.ContinuityTests.initialize
    begin = fixtures.ContinuityTests.begin
    checkpoint = fixtures.ContinuityTests.checkpoint
    fault = fixtures.ContinuityTests.fault

    def setup_work(self):
        state = self.initialize()
        project = self.call('save_project', {'name':'Test assembly','description':'Anonymous fixture','baseline_state':state['id']})
        self.call('link_product_session', {'session_id':self.session['id'],'project_id':project['id']})
        return project, state, self.begin(state)

    def test_import_share_preserves_files_and_four_status_axes(self):
        self.snapshot=self.artifact({'input.txt':'initial','retained.txt':'keep this'})
        self.session=self.connect()
        project, state, work = self.setup_work()
        update = self.call('studio_import_update', {'work_id':work['id'],'version':work['version'],
            'files':{'input.txt':base64.b64encode(b'changed\nsecond line\n').decode()}, 'summary':'Saved edit'})
        view = self.call('studio_work', {'work_id':work['id']})
        self.assertIn('retained.txt',view['selected']['manifest'])
        self.assertEqual(view['selected']['status']['sharing'], 'local')
        self.assertEqual(view['selected']['status']['adoption'], 'unadopted')
        shared = self.call('studio_share_update', {'work_id':work['id'],'version':update['change']['version'],
            'state_id':update['state']['id'], 'note':'Please check this unfinished edit.'})
        view = self.call('studio_work', {'work_id':work['id']})
        self.assertEqual(view['selected']['status']['sharing'], 'shared')
        self.assertEqual(view['selected']['status']['verification'], 'unverified')
        self.assertEqual(view['selected']['status']['work'], 'working')
        self.assertEqual(shared['share']['note'], 'Please check this unfinished edit.')
        self.fault('stale_basis', lambda:self.call('studio_share_update', {'work_id':work['id'],
            'version':update['change']['version'],'state_id':state['id'],'note':''}))
        self.assertTrue(self.call('replay')['matched'])

    def test_comments_bind_exact_work_file_version_and_inbox(self):
        _, state, work = self.setup_work()
        cp = self.checkpoint(work, {'input.txt':'first\nsecond\n'})
        view = self.call('studio_work', {'work_id':work['id']})
        anchor = {'kind':'code','path':'input.txt','hash':view['selected']['manifest']['input.txt']['hash'],'line':2}
        comment = self.call('studio_comment', {'work_id':work['id'],'state_id':cp['state']['id'],
            'anchor':anchor,'body':'@admin Please inspect this line.','mentions':['admin']})
        inbox = self.call('studio_inbox')
        self.assertEqual(inbox['items'][0]['thread_id'], comment['thread_id'])
        self.assertEqual(inbox['items'][0]['state_id'], cp['state']['id'])
        self.fault('invalid_input', lambda:self.call('studio_comment', {'work_id':work['id'],
            'state_id':cp['state']['id'],'anchor':{**anchor,'hash':'f'*64},'body':'bad','mentions':[]}))
        self.fault('invalid_input', lambda:self.call('studio_comment', {'work_id':work['id'],
            'state_id':cp['state']['id'],'anchor':{**anchor,'line':200},'body':'bad','mentions':[]}))
        next_cp=self.checkpoint(cp['change'], {'input.txt':'new\n'})
        latest=self.call('studio_work', {'work_id':work['id']})
        self.assertEqual(latest['threads'], [])
        old=self.call('studio_work', {'work_id':work['id'],'state_id':cp['state']['id']})
        self.assertEqual(old['threads'][0]['id'], comment['thread_id'])
        other=self.begin(state)
        self.fault('invalid_input',lambda:self.call('studio_work',{'work_id':other['id'],'state_id':next_cp['state']['id']}))
        self.fault('invalid_input',lambda:self.call('studio_comment',{'work_id':work['id'],'state_id':next_cp['state']['id'],
            'anchor':{'kind':'work'},'body':'wrong version','mentions':[],'thread_id':comment['thread_id']}))

    def test_import_rejects_scope_escape_and_credentials(self):
        _, _, work=self.setup_work()
        for path,code in [('outside.txt','scope_denied'),('.env','credential_detected')]:
            self.fault(code,lambda:self.call('studio_import_update',{'work_id':work['id'],'version':work['version'],
                'files':{path:base64.b64encode(b'hello').decode()},'summary':'test'}))
        self.assertEqual(self.call('studio_work',{'work_id':work['id']})['work']['version'],work['version'])

    def test_overview_separates_project_and_work_and_records_actor(self):
        project,_,work=self.setup_work()
        overview=self.call('studio_overview')
        self.assertEqual(overview['projects'][0]['id'],project['id'])
        self.assertEqual(overview['works'][0]['id'],work['id'])
        self.assertEqual(overview['works'][0]['owner']['kind'],'human')
        self.assertEqual(overview['works'][0]['components'][0]['id'],'robot')
        self.assertNotIn('token_hash',str(overview))

    def test_mentions_are_personal_idempotent_and_unauthorized_access_is_hidden(self):
        project, state, work=self.setup_work()
        outsider=secrets.token_urlsafe(32)
        p=self.call('propose',{'title':'Separate identity','changes':[{'id':'other','type':'principal',
            'data':{'kind':'human','permissions':['read','record'],'token_hash':token_hash(outsider)}}]})
        ref={'proposal_id':p['id'],'version':p['version']}
        self.call('submit',ref);self.call('endorse',{**ref,'reason':'fixture'})
        self.call('review_adoption',{**ref,'reason':'fixture','verdict':'approve'});self.call('commit',ref)
        args={'work_id':work['id'],'state_id':state['id'],'anchor':{'kind':'work'},'body':'Inspect this','mentions':['admin']}
        message=self.call('studio_comment',args,'one-comment')
        self.assertEqual(message,self.call('studio_comment',args,'one-comment'))
        reply=self.call('studio_comment',{**args,'body':'Same selection, new message','mentions':[]})
        self.assertEqual(reply['thread_id'],message['thread_id'])
        inbox=self.call('studio_inbox')['items'];self.assertEqual(len(inbox),1)
        foreign=lambda name,args=None:self.service.call(outsider,name,args or {},secrets.token_hex(12))
        self.assertEqual(foreign('studio_inbox')['items'],[])
        self.assertEqual(foreign('studio_overview')['works'],[])
        self.fault('unauthorized',lambda:foreign('studio_work',{'work_id':work['id']}))
        self.fault('unauthorized',lambda:foreign('studio_work',{'work_id':work['id'],'activity_only':True}))
        self.fault('unauthorized',lambda:foreign('studio_acknowledge',{'notification_id':inbox[0]['id']}))
        self.fault('unauthorized',lambda:self.call('studio_comment',{**args,'mentions':['other']}))
        self.call('studio_acknowledge',{'notification_id':inbox[0]['id']})
        self.assertTrue(self.call('studio_inbox')['items'][0]['read'])
        self.assertTrue(self.call('replay')['matched'])

    def test_activity_tracks_old_discussions_without_moving_the_selected_state(self):
        _, state, work = self.setup_work()
        before = self.call('studio_work', {'work_id':work['id']})
        message = self.call('studio_comment', {'work_id':work['id'],'state_id':state['id'],
            'anchor':{'kind':'work'},'body':'Review this baseline','mentions':[]})
        activity = self.call('studio_work', {'work_id':work['id'],'activity_only':True})
        self.assertNotEqual(activity['activity_token'], before['activity_token'])
        self.assertNotIn('selected', activity)
        cp = self.checkpoint(work, {'input.txt':'new'})
        latest = self.call('studio_work', {'work_id':work['id']})
        self.assertEqual(latest['threads'], [])
        self.assertEqual(latest['discussion_index'][0]['state_id'], state['id'])
        self.assertEqual(latest['discussion_index'][0]['message_count'], 1)
        self.assertEqual(latest['discussion_index'][0]['id'], message['thread_id'])
        old = self.call('studio_work', {'work_id':work['id'],'state_id':state['id']})
        self.assertEqual(old['selected']['state']['id'], state['id'])
        self.assertEqual(old['work']['head'], cp['state']['id'])
        self.assertEqual(old['activity_token'], latest['activity_token'])
        self.assertEqual(self.call('studio_work', {'work_id':work['id'],'activity_only':True})['activity_token'], latest['activity_token'])
