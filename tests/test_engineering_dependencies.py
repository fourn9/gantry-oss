import copy
import unittest
from gantry.engineering_context import assess
from gantry.model import Fault


class DependencyTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {p: {'hash': h*64} for p,h in [('cad.step','a'),('wire.json','b'),('control.py','c'),('result.json','d')]}
        components = [{'id': i, 'role': i, 'assembly': 'robot', 'inputs': {p:self.manifest[p]['hash']}}
                      for i,p in [('cad','cad.step'),('wire','wire.json'),('control','control.py')]]
        components[0]['native_refs'] = [{'provider':'cadquery','document':'assembly','object':'bracket',
            'revision':'1','unit':'mm','frame':'robot','source_path':'cad.step'}]
        edges = [{'dependent': b, 'prerequisite': a, 'kind':'uses_geometry', 'status':'confirmed',
                  'rationale':'Declared integration contract', 'inputs': {p:self.manifest[p]['hash']}}
                 for a,b,p in [('cad','wire','cad.step'),('wire','control','wire.json')]]
        check = {'id':'control-test','scope':'motion','components':['control'],'required':True,'status':'pass',
                 'inputs':{'control.py':'c'*64},'evidence':{'result.json':'d'*64}}
        self.context = {'environment':{'engineering':{'version':1,'components':components,'checks':[check],'dependencies':edges}}}

    def test_updated_cad_invalidates_transitive_control_result_even_after_component_refresh(self):
        self.manifest['cad.step']['hash'] = 'f'*64
        self.context['environment']['engineering']['components'][0]['inputs']['cad.step'] = 'f'*64
        result = assess(self.context, self.manifest)
        self.assertEqual(result['checks'][0]['effective_status'], 'unknown')
        self.assertEqual(result['checks'][0]['status'], 'pass')
        self.assertIn('control-test', result['review_gaps'])
        self.assertEqual(result['dependency_impact']['affected_components'], ['control','wire'])
        self.assertEqual(result['components'][0]['native_refs'][0]['object'], 'bracket')

    def test_unchanged_and_revalidated_dependencies_preserve_check(self):
        self.assertEqual(assess(self.context,self.manifest)['checks'][0]['effective_status'], 'pass')
        self.context['environment']['engineering']['dependencies'][0]['status'] = 'unverified'
        self.assertEqual(assess(self.context,self.manifest)['checks'][0]['effective_status'], 'unknown')

    def test_missing_native_source_and_unknown_nodes_rejected(self):
        broken=copy.deepcopy(self.context)
        broken['environment']['engineering']['components'][0]['native_refs'][0]['source_path']='unbound.step'
        with self.assertRaises(Fault): assess(broken,self.manifest)
        self.context['environment']['engineering']['dependencies'][0]['prerequisite']='missing'
        with self.assertRaises(Fault): assess(self.context,self.manifest)
