import copy
import unittest
from gantry.engineering_context import assess
from test_change_review import ChangeReviewTests


class EngineeringContextTests(unittest.TestCase):
    def setUp(self):
        self.manifest={'tank.step':{'hash':'a'*64},'report.json':{'hash':'b'*64}}
        self.contract={'version':1,'components':[{'id':'tank','role':'fresh_water_storage','assembly':'fluid',
            'inputs':{'tank.step':'a'*64}}], 'checks':[
            {'id':'placement','scope':'placement','components':['tank'],'required':True,'status':'pass',
             'inputs':{'tank.step':'a'*64},'evidence':{'report.json':'b'*64}},
            {'id':'removal','scope':'service','components':['tank'],'required':True,'status':'unverified',
             'inputs':{'tank.step':'a'*64}}]}
    def check(self):return assess({'environment':{'engineering':self.contract}},self.manifest)
    def test_partial_pass_does_not_clear_service(self):
        self.assertEqual(self.check()['review_gaps'],['removal'])
    def test_changed_geometry_invalidates_pass(self):
        self.manifest['tank.step']['hash']='c'*64
        result=self.check()
        self.assertEqual(result['input_mismatches'],['tank.step'])
        self.assertEqual(result['checks'][0]['effective_status'],'unknown')
    def test_evidence_missing_or_replaced_is_unknown(self):
        del self.manifest['report.json']
        self.assertEqual(self.check()['checks'][0]['effective_status'],'unknown')
    def test_legacy_is_explicitly_undeclared(self):
        self.assertFalse(assess({},self.manifest)['configured'])


class EngineeringReviewTests(ChangeReviewTests):
    def test_required_service_check_blocks_ok_but_not_checkpoint(self):
        self.setup_review()
        context=copy.deepcopy(self.cp['state']['context'])
        manifest=self.call('get_development_state',{'state_id':self.cp['state']['id']})['manifest']
        context['environment']['engineering']={'version':1,'components':[
            {'id':'tank','role':'storage','assembly':'water','inputs':{'input.txt':manifest['input.txt']['hash']}}],
            'checks':[{'id':'removal','scope':'service','components':['tank'],'required':True,
                      'status':'unverified','inputs':{'input.txt':manifest['input.txt']['hash']}}]}
        cp=self.checkpoint(self.cp['change'],context=context)
        r=self.submit(cp['change']);self.report(r);lease=self.claim(r)
        self.fault('review_pending',lambda:self.complete(r,lease,'ok'))
        self.complete(r,lease,'changes_requested')
        self.assertTrue(self.call('replay')['matched'])
