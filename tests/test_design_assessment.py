import copy
import hashlib
import json
from test_requirement_traceability import TraceabilityIntegrationTests, CrewRequirementTests
from test_hardware_publish import HardwarePublishTests
from gantry.hardware import publish
from gantry.design_assessment import bounded, adjust_impacted_checks
import test_change_review as review_fixtures
from unittest import TestCase


class ImpactEvidenceTests(TestCase):
    def test_approved_runtime_includes_virtual_environment(self):
        from unittest.mock import patch
        from gantry.project_sandbox import runtime_roots
        with patch('gantry.project_sandbox.sys.prefix','/opt/test-venv'):
            self.assertIn('/opt/test-venv',runtime_roots())

    def test_changed_dependency_must_be_bound_by_selected_check(self):
        check = {'id':'motion','components':['control'],'inputs':{'control.py':'a'*64},
                 'effective_status':'pass','evidence':{'report.json':'b'*64}}
        eng = {'checks':[check]}
        adjust_impacted_checks(eng, {'control':{'mechanism.step'}}, {})
        self.assertEqual(check['effective_status'], 'unknown')
        self.assertEqual(check['impact_gaps'], ['impact_input_unbound:mechanism.step'])
        check['inputs']['mechanism.step'] = 'c'*64
        check['effective_status'] = 'pass'
        adjust_impacted_checks(eng, {'control':{'mechanism.step'}}, {})
        self.assertEqual(check['effective_status'], 'pass')

    def test_nested_payload_has_total_budget_and_explicit_omission(self):
        from gantry.model import canonical
        result = {'id':'assessment_test','status':'declared_checks_satisfied','partial':False,
                  'checks':[{'evidence':{'report':'x'*500000}}], 'requirements':{'items':[]},
                  'impact':{'reasons':{'component':['x'*500000]}}}
        view = bounded(result)
        self.assertLess(len(canonical(view).encode()), 98304)
        self.assertTrue(view['partial'])
        self.assertEqual(view['status'], 'needs_review')
        result.update(open_checks=[{'id':str(i),'reasons':['y'*1000]*100} for i in range(100)])
        view=bounded(result)
        self.assertLess(len(canonical(view).encode()),98304)
        self.assertTrue(view['open_checks'])
        result['open_checks']=[{'id':str(i),'reasons':['😀'*1000]*100} for i in range(100)]
        self.assertLess(len(canonical(bounded(result)).encode()),98304)


class DesignAssessmentTests(TraceabilityIntegrationTests):
    def assessment(self, before, after):
        return self.call('get_design_assessment', {'baseline_state_id': before['id'], 'state_id': after['id']})

    def test_cumulative_change_stales_requirements_and_preserves_missing_checks(self):
        base = self.linked(); change = self.begin(base, ['input.txt', 'result.json'])
        first = self.checkpoint(change, files={'input.txt': 'changed'})
        second = self.checkpoint(first['change'], files={'input.txt': 'changed', 'result.json': '{}'})
        result = self.assessment(base, second['state'])
        self.assertEqual([x['path'] for x in result['changes']], ['input.txt', 'result.json'])
        self.assertIn('arm', result['impact']['affected_components'])
        self.assertEqual(result['requirements']['items'][0]['before_status'], 'met')
        self.assertEqual(result['requirements']['items'][0]['status'], 'unverified')
        self.assertEqual({x['id'] for x in result['open_checks']}, {'travel', 'load'})
        self.assertIn('dependency_map_missing', result['gaps'])
        context = copy.deepcopy(second['state']['context'])
        context['environment']['engineering']['checks'] = []
        removed = self.checkpoint(second['change'], files={'input.txt': 'changed'}, context=context)
        result = self.assessment(base, removed['state'])
        self.assertTrue(all('check_removed' in x['reasons'] for x in result['open_checks']))
        self.assertFalse(result['formal_adoption'])
        reverted = self.checkpoint(removed['change'], files={'input.txt': 'initial'}, context=base['context'])
        result = self.assessment(base, reverted['state'])
        self.assertEqual(result['changes'], [])
        self.assertEqual(result['requirements']['items'][0]['status'], 'met')

    def test_requirement_revision_change_is_not_a_new_pass(self):
        base = self.linked(); previous = self.assessment(base, base)
        self.requirement(self.ref['revision_id'])
        result = self.assessment(base, base)
        self.assertEqual(result['requirements']['items'][0]['status'], 'needs_review')
        self.assertNotEqual(result['id'], previous['id'])
        self.assertIn('requirement:motion:needs_review', result['gaps'])

    def test_comparison_cannot_cross_sessions(self):
        base = self.linked(); self.session = self.connect(); other = self.initialize()
        self.fault('scope_denied', lambda: self.assessment(base, other))

    def test_mentor_gets_same_assessment(self):
        base = self.linked(); changed = self.checkpoint(self.begin(base))['state']
        self.call('select_development_state', {'state_id': changed['id'],
            'version': self.detail()['session']['version'], 'reason': 'Review current change'})
        context = self.call('mentor_context', {'session_id': self.session['id']})
        self.assertEqual(context['design_assessment']['state_id'], changed['id'])
        self.assertEqual(context['design_assessment']['baseline_state_id'], base['id'])

    def mapping(self, state, source=None):
        source = source or state
        meta = self.call('get_development_state', {'state_id':source['id']})
        evidence = self.call('record_evidence_view', {'state_id':state['id'], 'subject_id':'robot',
            'profile':'dependency.v1','extractor':'fixture', 'fields':[], 'missing':[],
            'sources':[{'revision_id':source['snapshot'],'path':'input.txt',
                'sha256':meta['manifest']['input.txt']['hash'],'locator':'whole'}]})
        return self.call('record_validation_map', {'state_id':state['id'],'evidence_views':[evidence['id']],
            'dependencies':[], 'geometry':[], 'coverage':{'robot':{'dependencies':'declared_complete','spatial':'not_applicable'}},
            'checks':[{'id':'travel','subjects':['robot'],'kind':'integration','recipe_hash':'a'*64,'estimated_cost_ms':1}]})

    def test_old_source_does_not_describe_candidate_map(self):
        base = self.linked(); candidate = self.checkpoint(self.begin(base))['state']
        self.mapping(base); self.mapping(candidate, base)
        result = self.assessment(base, candidate)
        self.assertIn('dependency_map_source_stale:input.txt', result['gaps'])
        self.assertIsNone(result['impact']['validation_maps'][1])

    def test_affected_check_without_changed_subject_inputs_is_not_requirement_pass(self):
        base = self.linked()
        context = copy.deepcopy(base['context'])
        h = hashlib.sha256(b'control').hexdigest()
        context['environment']['engineering']['components'].append(
            {'id':'control','role':'controller','assembly':'robot','inputs':{'control.py':h}})
        for c in context['environment']['engineering']['checks']:
            c.update(components=['control'], inputs={'control.py':h}, evidence={'control.py':h})
        prepared = self.checkpoint(self.begin(base,['control.py']),
            files={'input.txt':'initial','control.py':'control'}, context=context)['state']
        # One integration check names the whole hierarchy, including the changed mechanism.
        self.mapping(prepared)
        candidate = self.checkpoint(self.begin(prepared), files={'input.txt':'changed','control.py':'control'})['state']
        self.mapping(candidate)
        result = self.assessment(prepared, candidate)
        self.assertEqual(result['requirements']['items'][0]['status'], 'unverified')
        travel = next(c for c in result['checks'] if c['id']=='travel')
        self.assertIn('impact_input_unbound:input.txt', travel['reasons'])


class BotAssessmentTests(CrewRequirementTests):
    def test_agent_checkpoint_cannot_rebaseline_acceptance(self):
        from gantry.bot_worker import environment_manifest
        scope=['mechanical.txt','physical-plan.json','report.json']
        session=self.owner.call('development_state',{'session_id':self.sid})['session']
        self.owner.call('configure_development',{'session_id':self.sid,'version':session['version'],
            'reason':'Fixture adapter scope',**{**self.policy,'write_scope':scope+['control.txt']}})
        self.owner.call('bind_development_bot',{'session_id':self.sid,'bot_id':'designer','principal_id':'designer',
            'version':1,'write_scope':scope,'can_assign':False,'can_integrate':False,'enabled':True})
        plan=json.dumps({'version':1,'components':[],'checks':[]})
        c=self.owner.call('begin_change',{'state_id':self.base['id'],'title':'Save plan','purpose':'Frozen criteria',
            'write_scope':['physical-plan.json'],'dependencies':[],'assignee':'admin'})
        self.base=self.owner.call('checkpoint_change',{'change_id':c['id'],'version':c['version'],
            'snapshot':self.artifact({'mechanical.txt':'1','control.txt':'1','physical-plan.json':plan}),
            'summary':'Baseline','rationale':'Fixture','unfinished':[],'work_status':'paused',
            'capture':{'scope':'Fixture','missing':[]}})['state']
        config=self.configs['designer'];config['agent_loop']=True
        self.owner.call('configure_bot_runtime',{'bot_id':'designer','version':1,'principal_id':'designer',
            'enabled':True,'environment':environment_manifest(config)})
        self.task('designer',write_scope=scope);seen=[]
        def infer(ctx,schema,directory):
            seen.append(ctx)
            actions=[('edit',{'path':'physical-plan.json','content':plan+' ',
                'expected_hash':hashlib.sha256(plan.encode()).hexdigest()}),
                ('publish_physical',{'plan_path':'physical-plan.json'}),('finish',self.answer(status='blocked'))]
            action,args=actions[len(seen)-1]
            return {'output':{'action':action,'arguments_json':json.dumps(args),'rationale':'Test baseline pin'}}
        with self.worker('designer',infer) as worker: result=worker.tick()[0]
        self.assertEqual(len(seen),2)
        self.assertEqual(result['reason'],'stale_basis')
        self.assertEqual(result['status'],'held')

    def test_each_round_and_saved_report_receive_cumulative_assessment(self):
        from gantry.bot_worker import environment_manifest
        config = self.configs['designer']; config['agent_loop'] = True
        self.owner.call('configure_bot_runtime', {'bot_id': 'designer', 'version': 1,
            'principal_id': 'designer', 'enabled': True, 'environment': environment_manifest(config)})
        task = self.task('designer', requirement_refs=[]); seen = []
        def infer(context, schema, directory):
            seen.append(context)
            if len(seen) == 1:
                action, args = 'edit', {'path': 'mechanical.txt', 'content': '2',
                    'expected_hash': hashlib.sha256(b'1').hexdigest()}
            else: action, args = 'finish', self.answer()
            return {'output': {'action': action, 'arguments_json': json.dumps(args), 'rationale': 'Fixture action'}}
        with self.worker('designer', infer) as worker: result = worker.tick()[0]
        self.assertEqual(result['task']['status'], 'completed')
        self.assertEqual(seen[-1]['design_assessment']['changes'][0]['path'], 'mechanical.txt')
        self.assertEqual(seen[-1]['design_assessment']['task_requirement_refs'], [])
        report = result['task']['reports'][-1]
        self.assertEqual(report['design_assessment']['id'], seen[-1]['design_assessment']['id'])
        self.assertTrue(self.owner.call('replay')['matched'])


class FrozenPlanTests(HardwarePublishTests):
    def test_checkpoint_does_not_authorize_weaker_acceptance(self):
        base, change, root = self.prepare()
        # A legitimate write scope is not permission to redefine acceptance mid-work.
        change = self.begin(base, ['physical-plan.json', 'stress.json', 'bracket.step'])
        self.plan['checks'][0]['criteria'][0]['max'] = 9999
        (root/'physical-plan.json').write_text(json.dumps(self.plan))
        cp = self.checkpoint(change, files={p.name:p.read_text() for p in root.iterdir()})
        self.fault('stale_basis', lambda: publish(self.client, cp['state']['id'], change['id'],
            cp['change']['version'], root, 'physical-plan.json', 'weakened'))
        # Reassessment is an explicit new unit of work with the new baseline.
        new = self.begin(cp['state'],['bracket.step','stress.json'])
        out = publish(self.client, cp['state']['id'],new['id'],new['version'],root,'physical-plan.json','reassessed')
        self.assertEqual(out['state']['context']['environment']['engineering']['checks'][0]['status'],'pass')


class ReviewAssessmentTests(review_fixtures.ChangeReviewTests):
    def test_reasoned_not_applicable_check_preserves_existing_review_semantics(self):
        self.setup_review()
        context=copy.deepcopy(self.cp['state']['context'])
        h=self.call('get_development_state',{'state_id':self.cp['state']['id']})['manifest']['input.txt']['hash']
        context['environment']['engineering']={'version':1,
            'components':[{'id':'part','role':'support','assembly':'robot','inputs':{'input.txt':h}}],
            'checks':[{'id':'thermal','scope':'thermal','components':['part'],'required':True,
                'status':'not_applicable','reason':'Unpowered static fixture',
                'inputs':{'input.txt':h},'evidence':{}}]}
        cp=self.checkpoint(self.cp['change'],context=context)
        submission=self.submit(cp['change']);self.report(submission)
        self.assertEqual(self.complete(submission,self.claim(submission),'ok')['status'],'completed')

    def test_partial_assessment_cannot_be_approved_from_empty_preview(self):
        from unittest.mock import patch
        submission=self.setup_review();self.report(submission);lease=self.claim(submission)
        with patch('gantry.design_assessment.build',return_value={'partial':True,'open_checks':[]}):
            self.fault('review_pending',lambda:self.complete(submission,lease,'ok'))

    def test_new_map_invalidates_saved_review_input(self):
        submission=self.setup_review();self.report(submission);lease=self.claim(submission)
        old=self.mentor.call('get_change_review',{'submission_id':submission['id']})['context_fingerprint']
        DesignAssessmentTests.mapping(self,self.cp['state'])
        self.fault('stale_basis',lambda:self.mentor.call('complete_change_review',{
            'submission_id':submission['id'],'fence':lease['fence'],
            'output':self.output(submission),'context_fingerprint':old}))
