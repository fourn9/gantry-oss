import copy
import unittest
from gantry.model import Fault

class PhysicalEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.check={'id':'load','scope':'structural','components':['bracket'],'required':True,
            'inputs':['bracket.step','material.json'],'report':'stress.json',
            'conditions':{'load_N':100,'fixture':'fixed-base'},
            'evaluator':{'name':'solver','version':'1'},'environment':{'mesh':'m1'},
            'criteria':[{'metric':'stress','unit':'MPa','max':50}]}
        self.hashes={'bracket.step':'a'*64,'material.json':'b'*64}
        self.report={'status':'completed','inputs':self.hashes,'conditions':self.check['conditions'],
            'evaluator':self.check['evaluator'],'environment':self.check['environment'],
            'measurements':{'stress':{'value':40,'unit':'MPa'}},'limitations':['Static load only']}
    def evaluate(self, report=None):
        from gantry.physical_evidence import evaluate
        return evaluate(self.check,self.report if report is None else report,self.hashes)
    def test_fixed_criteria_pass_fail_and_missing(self):
        self.assertEqual(self.evaluate()['status'],'pass')
        self.report['measurements']['stress']['value']=60
        self.assertEqual(self.evaluate()['status'],'fail')
        self.report['measurements']={}
        self.assertEqual(self.evaluate()['status'],'unknown')
    def test_stale_conditions_units_and_failed_solver_never_pass(self):
        for key,value in [('inputs',{'bracket.step':'c'*64}),('conditions',{'load_N':1}),
                          ('evaluator',{'name':'solver','version':'2'}),('status','error'),
                          ('environment',{'mesh':'m2'}),('measurements',{'stress':{'value':1,'unit':'Pa'}}),
                          ('measurements',{'stress':{'value':float('nan'),'unit':'MPa'}})]:
            with self.subTest(key=key):
                r=copy.deepcopy(self.report);r[key]=value
                self.assertEqual(self.evaluate(r)['status'],'unknown')
    def test_empty_or_unbounded_acceptance_rejected(self):
        for criteria in [[],[{'metric':'stress','unit':'MPa'}],[{'metric':'stress','unit':'MPa','max':float('inf')}]]:
            self.check['criteria']=criteria
            with self.assertRaises(Fault):self.evaluate()
