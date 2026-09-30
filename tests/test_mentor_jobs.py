import unittest
import test_change_review as review_fixture
from gantry.mentor_daemon import process_job
from gantry.mentor_jobs import JOB_SCHEMAS


class MentorJobsTests(unittest.TestCase):
    setUp=review_fixture.ChangeReviewTests.setUp
    tearDown=review_fixture.ChangeReviewTests.tearDown
    call=review_fixture.ChangeReviewTests.call
    artifact=review_fixture.ChangeReviewTests.artifact
    policy=review_fixture.ChangeReviewTests.policy
    connect=review_fixture.ChangeReviewTests.connect
    detail=review_fixture.ChangeReviewTests.detail
    fault=review_fixture.ChangeReviewTests.fault
    initialize=review_fixture.ChangeReviewTests.initialize
    begin=review_fixture.ChangeReviewTests.begin
    checkpoint=review_fixture.ChangeReviewTests.checkpoint
    setup_review=review_fixture.ChangeReviewTests.setup_review
    submit=review_fixture.ChangeReviewTests.submit
    output=review_fixture.ChangeReviewTests.output

    def setup_jobs(self):
        r=self.setup_review();d=self.detail()['session']
        self.call('configure_development',{'session_id':d['id'],'version':d['version'],'reason':'Allow fixture editing',
            **{**self.policy(),'actors':['admin','mentor'],'write_scope':['input.txt']}})
        self.call('configure_review_automation',{'session_id':d['id'],'version':0,'enabled':True,
            'max_rounds':1,'max_jobs':10,'developer_principal':'admin'})
        return r

    def jobs(self):return self.call('review_automation_status',{'session_id':self.session['id']})['jobs']
    def job(self,kind):return next(j for j in self.jobs() if j['kind']==kind and j['status']=='pending')
    def inference(self,ctx,schema,directory):
        r=ctx['review'];kind=ctx['task']
        if kind=='specialist':out={'summary':'Review input','evidence':[r['state_id']],'unresolved':[]}
        elif kind=='coordinator':
            out=self.output(r,'ok' if ctx['files']['input.txt']=='corrected' else 'changes_requested')
            out['engineering_plan']={'components':[],'checks':[],'limitations':['Fixture only; no engineering inference']}
        elif kind=='developer':out={'edits':[{'path':'input.txt','content':'corrected'}], 'summary':'Corrected field','hypothesis':'Preserve interface','rationale':'f1','unverified':['hardware']}
        else:out={'assessment':'inconclusive','observation':'File corrected, hardware untested','applicability':'input interface','limitations':['no physics measurement']}
        return {'output':out,'provider':{'kind':'fixture'}}

    def run_job(self,kind):
        job=self.job(kind);client=self.client if kind=='developer' else self.mentor
        return process_job(client,job['id'],self.root/'jobs',self.inference)

    def test_automatic_loop_records_real_edits_and_reuses_journal(self):
        self.setup_jobs()
        self.fault('review_pending',lambda:self.run_job('coordinator'))
        self.run_job('specialist');self.run_job('coordinator')
        result=self.run_job('developer');self.assertEqual(result['status'],'completed')
        self.run_job('reflection');self.run_job('specialist');self.run_job('coordinator')
        self.assertTrue(all(j['status']=='completed' for j in self.jobs()))
        views=self.call('list_change_reviews',{'session_id':self.session['id']})['items']
        self.assertEqual(len(views),2)
        self.assertEqual({r['output']['verdict'] for r in views},{'ok','changes_requested'})
        latest=next(r for r in views if r['output']['verdict']=='ok')
        view=self.call('get_change_review',{'submission_id':latest['id']})
        self.assertEqual(view['development']['status']['adoption'],'unadopted')
        self.assertEqual(view['development']['status']['verification'],'unverified')
        self.assertTrue(self.call('replay')['matched'])

    def test_claim_budget_identity_policy_and_stale(self):
        r=self.setup_jobs();job=self.job('specialist')
        self.fault('unauthorized',lambda:self.call('claim_mentor_job',{'job_id':job['id'],'lease_seconds':60}))
        claim=self.mentor.call('claim_mentor_job',{'job_id':job['id'],'lease_seconds':60})
        self.fault('conflict',lambda:self.mentor.call('claim_mentor_job',{'job_id':job['id'],'lease_seconds':60}))
        self.call('configure_review_automation',{'session_id':self.session['id'],'version':1,'enabled':False,
            'max_rounds':1,'max_jobs':1,'developer_principal':'admin'})
        self.fault('mode_disabled',lambda:self.mentor.call('finish_mentor_job',{'job_id':job['id'],'fence':claim['fence'],
            'output':{'summary':'test','evidence':[r['state_id']],'unresolved':[]},'provider':{'kind':'fixture'}}))

    def test_output_scope_and_round_limit(self):
        self.setup_jobs();self.run_job('specialist');self.run_job('coordinator')
        job=self.job('developer')
        def bad(ctx,schema,directory):return {'output':{'edits':[{'path':'../outside','content':'bad'}],
            'summary':'bad','hypothesis':'bad','rationale':'bad','unverified':[]},'provider':{'kind':'fixture'}}
        self.fault('scope_denied',lambda:process_job(self.client,job['id'],self.root/'bad',bad))
        self.assertFalse((self.root/'outside').exists())

    def test_coordinator_failure_updates_review_and_preserves_reports(self):
        r=self.setup_jobs();self.run_job('specialist')
        j=self.job('coordinator')
        claim=self.mentor.call('claim_mentor_job',{'job_id':j['id'],'lease_seconds':60})
        self.mentor.call('fail_mentor_job',{'job_id':j['id'],'fence':claim['fence'],'reason':'provider_failed'})
        view=self.call('get_change_review',{'submission_id':r['id']})
        self.assertEqual(view['status'],'failed')
        self.assertIn('mechanical',view['recovery']['completed_roles'])
        self.assertFalse(view['recovery']['automatic_retry'])
        listing=self.call('list_change_reviews',{'session_id':self.session['id']})
        self.assertEqual(listing['items'][0]['status'],'failed')
        self.assertTrue(self.call('replay')['matched'])
