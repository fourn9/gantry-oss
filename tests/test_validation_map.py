import copy
import unittest
from gantry.validation_map import select
import test_continuity as fixture

class PlanningTests(unittest.TestCase):
    def model(self):
        return {'dependencies':[{'prerequisite':'cable','dependent':'controller','kind':'electrical'}],
            'geometry':[{'subject_id':'cable','unit':'mm','frame':'robot','swept_bounds':[0,0,0,10,10,10]},
                        {'subject_id':'clamp','unit':'m','frame':'robot','swept_bounds':[.009,0,0,.011,.01,.01]}],
            'coverage':{x:{'dependencies':'declared_complete','spatial':'swept_envelope' if x in {'cable','clamp'} else 'not_applicable'} for x in ['cable','clamp','controller']},
            'checks':[{'id':'static','subjects':['cable','clamp'],'kind':'local','recipe_hash':'a'*64,'estimated_cost_ms':10},
                      {'id':'coupled','subjects':['cable','clamp','controller'],'kind':'integration','recipe_hash':'b'*64,'estimated_cost_ms':100}]}
    def test_distant_dependency_sweep_and_order(self):
        mp=self.model();result=select(mp,mp,{'cable'})
        self.assertEqual(result['affected'],['cable','clamp','controller'])
        self.assertEqual([c['id'] for c in result['checks']],['static','coupled'])
        self.assertIn('swept_proximity:cable',result['reasons']['clamp'])
        self.assertEqual(result['verification'],'unverified');self.assertFalse(result['execution_permission'])
    def test_removed_edges_and_unknown_coverage_not_silently_skipped(self):
        before=self.model();after=copy.deepcopy(before);after['dependencies']=[]
        after['coverage']['controller']['dependencies']='unknown'
        result=select(before,after,{'cable'})
        self.assertIn('controller',result['affected'])
        self.assertIn('unknown_dependencies:controller',result['gaps']);self.assertEqual(result['status'],'needs_review')
    def test_frame_and_retired_check_gaps(self):
        before=self.model();after=copy.deepcopy(before);after['geometry'][1]['frame']='cad_local';after['checks']=after['checks'][:1]
        result=select(before,after,{'cable'})
        self.assertIn('unresolved_coordinate_transforms',result['gaps'])
        self.assertIn('check_definition_changed:coupled',result['gaps'])
        self.assertIn('coupled',[c['id'] for c in result['checks']])

class MapContractTests(unittest.TestCase):
    setUp=fixture.ContinuityTests.setUp;tearDown=fixture.ContinuityTests.tearDown
    call=fixture.ContinuityTests.call;artifact=fixture.ContinuityTests.artifact;policy=fixture.ContinuityTests.policy
    connect=fixture.ContinuityTests.connect;detail=fixture.ContinuityTests.detail;initialize=fixture.ContinuityTests.initialize
    begin=fixture.ContinuityTests.begin;checkpoint=fixture.ContinuityTests.checkpoint
    def test_plan_is_saved_version_bound_and_unadopted(self):
        before=self.initialize();after=self.checkpoint(self.begin(before))['state']
        def mapping(state):
            meta=self.call('restore_artifact',{'revision_id':state['snapshot'],'metadata_only':True})
            evidence=self.call('record_evidence_view',{'state_id':state['id'],'subject_id':'robot','profile':'dependency.v1','extractor':'submitted-v1',
                'sources':[{'revision_id':state['snapshot'],'path':'input.txt','sha256':meta['manifest']['files']['input.txt']['hash'],'locator':'whole'}],
                'fields':[],'missing':['physical dependencies unverified']})
            return self.call('record_validation_map',{'state_id':state['id'],'evidence_views':[evidence['id']],
                'dependencies':[],'geometry':[],'coverage':{'robot':{'dependencies':'unknown','spatial':'unknown'}},
                'checks':[{'id':'integration','subjects':['robot'],'kind':'integration','recipe_hash':'a'*64,'estimated_cost_ms':100}]})
        a=mapping(before);b=mapping(after)
        plan=self.call('plan_validation',{'before_map':a['id'],'after_map':b['id']})
        self.assertEqual(plan['affected'],['robot']);self.assertEqual(plan['status'],'needs_review')
        got=self.call('get_validation_plan',{'plan_id':plan['id']});self.assertEqual(got['state_id'],after['id'])
        self.assertEqual(got['adoption'],'unadopted');self.assertTrue(self.call('replay')['matched'])
