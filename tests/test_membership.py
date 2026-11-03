import secrets
import unittest
from gantry.model import digest
from gantry.service import token_hash
import test_studio_workspace as fixtures

class MemberTests(unittest.TestCase):
    setUp=fixtures.WorkspaceTests.setUp
    tearDown=fixtures.WorkspaceTests.tearDown
    call=fixtures.WorkspaceTests.call
    artifact=fixtures.WorkspaceTests.artifact
    connect=fixtures.WorkspaceTests.connect
    policy=fixtures.WorkspaceTests.policy
    fault=fixtures.WorkspaceTests.fault
    imported=fixtures.WorkspaceTests.imported

    def request(self,role='contributor'):
        token=secrets.token_urlsafe(32)
        return token,{'member_id':'teammate','ledger_id':self.call('state')['ledger_id'],
             'role':role,'token_hash':token_hash(token),'zones':['root'],'valid_until':self.service.clock()+3600000}

    def grant(self,request,sessions=None,**kw):
        args={'request':request,'fingerprint':digest(request),'sessions':sessions or [],'reason':'Reviewed scoped membership',**kw}
        return self.call('grant_workspace_member',args,'grant-member')

    def test_grant_is_audited_scoped_and_repeatable_then_revoked(self):
        imported=self.imported();token,request=self.request()
        self.fault('unauthorized',lambda:self.service.call(token,'identity'))
        session=self.call('development_state',{'session_id':imported['change']['session_id']})['session']
        refs=[{'session_id':session['id'],'version':session['version']}]
        granted=self.grant(request,refs)
        self.assertEqual(granted,self.grant(request,refs))
        actor=self.service.call(token,'identity');self.assertNotIn('admin',actor['permissions'])
        self.assertEqual(actor['zones'],['root'])
        view=self.service.call(token,'studio_work',{'work_id':imported['change']['id']})
        self.assertFalse(view['can_update'])
        self.assertEqual(self.call('development_state',{'session_id':session['id']})['session']['recipes'],session['recipes'])
        self.fault('unauthorized',lambda:self.service.call(token,'workspace_members'))
        self.call('revoke_workspace_member',{'member_id':'teammate','expected_revision':granted['revision_id'],'reason':'End collaboration'})
        self.fault('unauthorized',lambda:self.service.call(token,'identity'))
        self.assertTrue(self.call('replay')['matched'])

    def test_forged_expired_cross_workspace_and_stale_grants_are_atomic(self):
        _,request=self.request()
        self.fault('stale_basis',lambda:self.grant(request,fingerprint='0'*64))
        self.fault('scope_denied',lambda:self.grant({**request,'ledger_id':'different'}))
        self.fault('expired',lambda:self.grant({**request,'valid_until':1}))
        self.fault('not_found',lambda:self.grant(request,[{'session_id':'missing','version':1}]))
        self.assertEqual(self.call('workspace_members')['members'][0]['id'],'admin')
        self.assertEqual(len(self.call('workspace_members')['members']),1)

    def test_agent_cannot_approve_membership_or_get_human_identity(self):
        token,request=self.request('agent-developer');self.grant(request)
        actor=self.service.call(token,'identity');self.assertEqual(actor['kind'],'agent')
        self.assertNotIn('grant_workspace_member',actor['allowed_commands'])
        self.assertNotIn('review_adoption',actor['allowed_commands'])
        self.fault('unauthorized',lambda:self.service.call(token,'grant_workspace_member',
            {'request':request,'fingerprint':digest(request),'sessions':[],'reason':'Self elevation'},'agent-grant'))

    def test_explicit_expiry_and_admin_revocation_guard(self):
        token,request=self.request();result=self.grant(request,expires_at=self.service.clock()+10000)
        self.assertIn('expires_at',self.service.call(token,'identity'))
        self.fault('scope_denied',lambda:self.call('revoke_workspace_member',{'member_id':'admin',
            'expected_revision':self.call('state')['entries']['admin']['revision_id'],'reason':'Remove owner'}))

    def test_existing_credential_cannot_be_rebound_to_another_identity(self):
        _,request=self.request();self.grant(request)
        other={**request,'member_id':'different-person'}
        self.fault('conflict',lambda:self.call('grant_workspace_member',{'request':other,
            'fingerprint':digest(other),'sessions':[],'reason':'Duplicate credential'},'duplicate'))
        self.assertEqual(len(self.call('workspace_members')['members']),2)
