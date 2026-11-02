import copy
import unittest
import test_change_review as fixtures


class DossierTests(unittest.TestCase):
    for name in ('setUp','tearDown','call','artifact','policy','connect','detail','fault','initialize',
                 'begin','checkpoint','setup_review','submit','report','output','claim','complete'):
        locals()[name]=getattr(fixtures.ChangeReviewTests,name)

    def test_dependency_gap_reaches_authenticated_mentor_and_blocks_ok(self):
        self.setup_review()
        context=copy.deepcopy(self.cp['state']['context'])
        manifest=self.call('get_development_state',{'state_id':self.cp['state']['id']})['manifest']
        h=manifest['input.txt']['hash']
        context['environment']['engineering']={'version':1,'components':[
            {'id':i,'role':i,'assembly':'robot','inputs':{'input.txt':h}} for i in ('mechanism','controller')],
            'dependencies':[{'dependent':'controller','prerequisite':'mechanism','kind':'uses_interface',
                'inputs':{'input.txt':'0'*64},'rationale':'Controller targets old interface','status':'confirmed'}],
            'checks':[{'id':'control','scope':'motion','components':['controller'],'required':True,
                      'status':'unverified','inputs':{'input.txt':h}}]}
        cp=self.checkpoint(self.cp['change'],context=context)
        r=self.submit(cp['change']);self.report(r);lease=self.claim(r)
        view=self.mentor.call('get_change_review',{'submission_id':r['id']})
        dossier=view['engineering_dossier']
        self.assertEqual(dossier['input_state'],cp['state']['id'])
        self.assertIn('controller',dossier['dependency_impact']['affected_components'])
        self.assertEqual(dossier['checks'][0]['action'],'reassess_dependency_then_validate')
        self.fault('review_pending',lambda:self.complete(r,lease,'ok'))
        completed=self.complete(r,lease,'changes_requested')
        self.assertEqual(completed['output']['findings'][0]['completion_condition'],'Compare field with consumer')
        self.assertTrue(self.call('replay')['matched'])
