import unittest
import test_service as fixtures
from gantry.model import Fault


class EvaluationBindingTests(unittest.TestCase):
    setUp=fixtures.LedgerTests.setUp
    tearDown=fixtures.LedgerTests.tearDown
    call=fixtures.LedgerTests.call
    proposal=fixtures.LedgerTests.proposal
    assertFault=fixtures.LedgerTests.assertFault
    def test_unbound_results_visible_without_becoming_current_or_historical(self):
        p=self.proposal();q=self.proposal(eid='unrelated')
        for label,basis in [('ours',p['candidate_id']),('other',q['candidate_id'])]:
            self.call('record',{'type':'eval_result','data':{'run_id':label,'verdict':'pass',
                'basis_design_revision':basis,'design_binding':{'status':'unverified','reasons':['dirty_source']}}})
        ctx=self.call('review_context',{'proposal_id':p['id']})
        self.assertEqual(ctx['results'],[]);self.assertEqual(ctx['historical_results'],[])
        self.assertEqual([e['data']['run_id'] for e in ctx['unbound_results']],['ours'])

    def test_unverified_binding_cannot_claim_candidate(self):
        p=self.proposal()
        for kind,data in [('eval_result',{'run_id':'wrong','design_revision':p['candidate_id']}),
                          ('configuration',{'slots':{'design':p['candidate_id']}})]:
            self.assertFault('invalid_input',lambda:self.call('record',{'type':kind,'data':{
                **data,'design_binding':{'status':'unverified'}}}))

    def test_verified_evaluation_requires_matching_immutable_configuration(self):
        p=self.proposal();proof={'status':'verified_inputs','evaluated_design_revision':p['candidate_id']}
        data={'run_id':'checked','design_revision':p['candidate_id'],'design_binding':proof,'verdict':'pass'}
        self.assertFault('invalid_input',lambda:self.call('record',{'type':'eval_result','data':data}))
        c=self.call('record',{'type':'configuration','data':{'slots':{'design':p['candidate_id']},'design_binding':proof}})
        self.call('record',{'type':'eval_result','data':{**data,'configuration':c['revision_id']}})
        self.assertEqual(len(self.call('review_context',{'proposal_id':p['id']})['results']),1)

    def test_correction_preserves_original_but_removes_false_validation(self):
        p=self.proposal();old=self.call('record',{'type':'eval_result','data':{'run_id':'legacy','verdict':'pass','design_revision':p['candidate_id']}})
        c=self.call('record',{'type':'configuration','data':{'slots':{},'basis_design_revision':p['candidate_id']}})
        new=self.call('record',{'type':'eval_result','id':old['id'],'expected_revision':old['revision_id'],'data':{
            'run_id':'legacy','verdict':'pass','configuration':c['revision_id'],'basis_design_revision':p['candidate_id'],
            'design_binding':{'status':'invalidated','reasons':['source_mismatch']},'correction_of':old['revision_id']}})
        ctx=self.call('review_context',{'proposal_id':p['id']})
        self.assertEqual(ctx['results'],[]);self.assertEqual(ctx['unbound_results'][0]['revision_id'],new['revision_id'])
        self.assertEqual(new['previous_revision'],old['revision_id'])
        self.assertTrue(self.call('verify')['valid']);self.assertTrue(self.call('replay')['matched'])
