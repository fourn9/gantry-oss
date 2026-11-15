"""Anonymous Core fixtures for derived engineering evidence, not physical validation."""
import copy
import unittest
from gantry.model import Fault
import test_requirement_traceability as fixtures


class EngineeringEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.TraceabilityIntegrationTests(); self.f.setUp(); self.addCleanup(self.f.tearDown)
        self.before=self.f.linked()
        self.after=self.f.checkpoint(self.f.begin(self.before))['state']

    def record(self,state,value,source=None,**field):
        source=source or state
        manifest=self.f.call('get_development_state',{'state_id':source['id']})['manifest']
        return self.f.call('record_evidence_view',{'state_id':state['id'],'subject_id':'robot',
            'profile':'fixture.geometry.v1','extractor':'anonymous-fixture',
            'sources':[{'revision_id':source['snapshot'],'path':'input.txt','sha256':manifest['input.txt']['hash'],'locator':'/travel'}],
            'fields':[{'name':'travel','value':value,'classification':'declared','source_index':0,'method':'submitted fixture','unit':'mm',**field}],
            'missing':[]})

    def assess(self):
        return self.f.call('get_design_assessment',{'baseline_state_id':self.before['id'],'state_id':self.after['id']})

    def test_field_diff_retains_provenance_without_claiming_verification(self):
        self.record(self.before,12); after=self.record(self.after,15)
        result=self.assess(); evidence=result['engineering_evidence']; row=evidence['fields'][0]
        self.assertEqual(row['subject'],{'namespace':'hierarchy','id':'robot'})
        self.assertEqual(row['status'],'changed'); self.assertEqual(row['delta'],3)
        provenance=row['after'][0]['provenance']
        self.assertEqual(provenance['request'],{'view_id':after['id'],'fields':['travel']})
        self.assertEqual(provenance['source']['locator'],'/travel')
        self.assertFalse(evidence['intent_prediction_supported'])
        self.assertTrue(result['open_checks']); self.assertFalse(result['formal_adoption'])

    def test_stale_sources_and_conflicting_views_are_not_selected_as_truth(self):
        self.record(self.before,12); self.record(self.after,15,source=self.before)
        result=self.assess(); row=result['engineering_evidence']['fields'][0]
        self.assertEqual(row['status'],'unknown')
        self.assertIn('engineering_evidence:stale_source',result['gaps'])
        self.record(self.after,15); self.record(self.after,16)
        result=self.assess(); evidence=result['engineering_evidence']
        self.assertEqual(evidence['fields'][0]['status'],'conflict')
        self.assertEqual(len(evidence['conflicts'][0]['view_ids']),2)
        self.assertIn('engineering_evidence:conflicting_observations',result['gaps'])

    def test_incompatible_frame_and_unknown_value_have_no_numeric_delta(self):
        self.record(self.before,12,frame='local'); self.record(self.after,15,frame='world')
        row=self.assess()['engineering_evidence']['fields'][0]
        self.assertEqual(row['status'],'unknown'); self.assertNotIn('delta',row)

    def test_dependency_paths_keep_component_and_hierarchy_namespaces_distinct(self):
        context=copy.deepcopy(self.before['context']); eng=context['environment']['engineering']
        h=eng['components'][0]['inputs']['input.txt']
        eng['components'].append({'id':'robot','role':'controller','assembly':'assembly','inputs':{'control.txt':'a'*64}})
        eng['dependencies']=[{'prerequisite':'arm','dependent':'robot','kind':'uses_geometry','status':'confirmed',
            'rationale':'Declared routing relation','inputs':{'input.txt':h}}]
        eng['checks'].append({'id':'routing','scope':'connection','required':True,'status':'unverified',
            'components':['robot'],'inputs':{'control.txt':'a'*64},'evidence':{}})
        self.before=self.f.checkpoint(self.f.begin(self.before),files={'input.txt':'initial'},context=context)['state']
        self.after=self.f.checkpoint(self.f.begin(self.before))['state']
        self.record(self.before,12); self.record(self.after,15)
        evidence=self.assess()['engineering_evidence']
        impact=next(i for i in evidence['impacts'] if i['target']['id']=='robot')
        self.assertEqual(impact['target']['namespace'],'engineering_component')
        self.assertEqual(impact['changed_inputs'],['input.txt'])
        self.assertEqual(impact['via'][0]['prerequisite'],'arm')
        self.assertIn('routing',impact['check_ids'])
        self.assertEqual(evidence['fields'][0]['subject']['namespace'],'hierarchy')

    def test_bounded_scan_discloses_followup_and_no_views_do_not_add_top_level_failure(self):
        result=self.assess()
        self.assertFalse(any(g.startswith('engineering_evidence:') for g in result['gaps']))
        for i in range(31): self.record(self.after,i)
        result=self.assess(); evidence=result['engineering_evidence']
        self.assertTrue(evidence['coverage']['partial']); self.assertTrue(result['partial'])
        request=evidence['coverage']['after']['next_request']
        self.assertEqual(request['state_id'],self.after['id']); self.assertIn('as_of_seq',request)
        self.assertTrue(self.f.call('query_evidence',request)['items'])

    def test_entire_assessment_is_stable_across_unrelated_ledger_writes(self):
        for with_views in (False,True):
            if with_views:
                self.record(self.before,12); self.record(self.after,15)
            first=self.assess()
            self.f.artifact({'unrelated.txt':'Unrelated saved artifact'})
            second=self.assess()
            self.assertEqual(first,second)

    def test_cross_session_denied_before_evidence_projection(self):
        self.f.session=self.f.connect(); self.after=self.f.initialize()
        with self.assertRaises(Fault) as caught:self.assess()
        self.assertEqual(caught.exception.code,'scope_denied')

    def test_large_values_are_retrievable_omissions_and_unbounded_numbers_do_not_crash(self):
        self.record(self.before,10**400); self.record(self.after,10**401)
        row=self.assess()['engineering_evidence']['fields'][0]
        self.assertEqual(row['status'],'changed'); self.assertNotIn('delta',row)
        self.record(self.after,'😀'*10000)
        result=self.assess(); evidence=result['engineering_evidence']
        from gantry.model import canonical
        self.assertLessEqual(len(canonical(evidence).encode()),24576)
        self.assertTrue(evidence['coverage']['partial'])
        omitted=next(v for v in evidence['fields'][0]['after'] if v.get('value_omitted'))
        exact=self.f.call('get_evidence_view',omitted['provenance']['request'])
        self.assertEqual(exact['fields'][0]['value'],'😀'*10000)


class ProjectionIdentityTests(unittest.TestCase):
    def test_hidden_scanned_field_changes_fingerprint_without_claiming_complete_coverage(self):
        from unittest.mock import patch
        from gantry.engineering_evidence import build
        def observation(value):
            return {'value':value,'unit':'mm','classification':'declared','applicable':True}
        left={('assembly','fixture','field%02d'%i):[observation(0)] for i in range(31)}
        right={key:[observation(1)] for key in left}
        coverage={'next_request':None,'fields_omitted':0,'source_fingerprint':'fixture'}
        def project():
            with patch('gantry.engineering_evidence._observations',side_effect=[(left,coverage.copy()),(right,coverage.copy())]):
                return build(None,{'seq':1},None,{'id':'before'},{'id':'after'},{},{},
                    {'components':[],'checks':[]},{'components':[],'checks':[]},[],[],None)[0]
        first=project(); right[('assembly','fixture','field30')]=[observation(2)]; second=project()
        self.assertEqual(first['fields'],second['fields'])
        self.assertTrue(first['coverage']['partial'])
        self.assertNotEqual(first['source_fingerprint'],second['source_fingerprint'])
