import unittest
import test_requirement_traceability as req
import test_bot_development as fixtures
import test_onboarding as onboarding
from gantry.model import Fault

class BotMappingTests(unittest.TestCase):
    def setUp(self):
        self.c=fixtures.BotDevelopmentTests();self.c.setUp();self.addCleanup(self.c.tearDown)
        self.call=self.c.owner.call
        self.ref=req.TraceabilityIntegrationTests.requirement(self)
    def test_proposed_links_use_real_candidate_and_reach_following_assignment(self):
        task=self.c.task();detail=self.call('get_development_state',{'state_id':self.c.base['id']})
        link={**self.ref,'rationale':'Saved mechanism addresses this requirement', 'evidence':[{'path':'mechanical.txt','hash':detail['manifest']['mechanical.txt']['hash']}]}
        with self.c.worker('lead') as worker:
            client=self.c.clients['lead'];claim=client.call('claim_bot_task',{'task_id':task['id'],'version':task['version'],'runtime_fence':worker.runtime['fence']})
            ref={'task_id':task['id'],'fence':claim['task']['fence']}
            result=client.call('propose_bot_requirements',{**ref,'links':[link],'summary':'Link existing motion requirement'},'mapping')
            self.assertEqual(result,client.call('propose_bot_requirements',{**ref,'links':[link],'summary':'Link existing motion requirement'},'mapping'))
            self.assertEqual(result['state']['context']['requirement_refs'],[self.ref])
            original=client.call('get_bot_task',{'task_id':task['id']})
            self.assertNotIn('output_state',original['task'])
            self.assertEqual(original['task']['requirement_refs'],[])
            self.assertEqual(result['change']['sharing'],'shared')
            child=self.c.assignment('control',state_id=result['state']['id'],requirement_refs=[self.ref])
            report=self.c.answer(status='waiting',assignments=[child]);report.pop('edits')
            done=client.call('finish_bot_task',{**ref,'report':report})
        v=self.call('get_bot_task',{'task_id':done['task']['children'][0]})
        self.assertEqual(v['task']['requirement_refs'],[self.ref])
        self.assertEqual(v['development']['requirement_coverage']['items'][0]['status'],'unverified')
        self.assertEqual(v['development']['status']['adoption'],'unadopted')
        self.assertTrue(self.call('replay')['matched'])
    def test_bot_can_discover_available_normative_requirement_ids(self):
        task=self.c.task()
        result=self.c.clients['lead'].call('get_bot_requirements',{'task_id':task['id'],'limit':1})
        self.assertEqual(result['items'][0]['reference'],self.ref)
        self.assertEqual(result['items'][0]['verification_checks'],['travel','load'])
        self.assertEqual(result['purpose'],'Available definitions, not assigned requirements or fulfillment')

    def test_requirement_catalog_is_a_read_without_a_request_key_or_ledger_mutation(self):
        task=self.c.task();before=self.call('state')['seq']
        result=self.c.service.call(self.c.tokens['lead'],'get_bot_requirements',{'task_id':task['id']})
        self.assertEqual(result['items'][0]['reference'],self.ref)
        self.assertEqual(self.call('state')['seq'],before)

    def test_stale_source_does_not_create_mapping(self):
        task=self.c.task()
        with self.c.worker('lead') as worker:
            client=self.c.clients['lead'];claim=client.call('claim_bot_task',{'task_id':task['id'],'version':task['version'],'runtime_fence':worker.runtime['fence']})
            args={'task_id':task['id'],'fence':claim['task']['fence'],'summary':'Invalid', 'links':[{**self.ref,'rationale':'Invalid source','evidence':[{'path':'mechanical.txt','hash':'0'*64}]}]}
            with self.assertRaises(Fault):client.call('propose_bot_requirements',args)
            self.assertNotIn('output_state',client.call('get_bot_task',{'task_id':task['id']})['task'])

    def test_requirement_revision_change_rejects_prepared_mapping(self):
        task=self.c.task();detail=self.call('get_development_state',{'state_id':self.c.base['id']})
        with self.c.worker('lead') as worker:
            client=self.c.clients['lead'];claim=client.call('claim_bot_task',{'task_id':task['id'],'version':task['version'],'runtime_fence':worker.runtime['fence']})
            req.TraceabilityIntegrationTests.requirement(self,self.ref['revision_id'])
            args={'task_id':task['id'],'fence':claim['task']['fence'],'summary':'Stale mapping','links':[{**self.ref,
                'rationale':'Prepared before requirement changed','evidence':[{'path':'mechanical.txt','hash':detail['manifest']['mechanical.txt']['hash']}]}]}
            with self.assertRaises(Fault) as e:client.call('propose_bot_requirements',args)
            self.assertEqual(e.exception.code,'stale_basis')
            self.assertNotIn('output_state',client.call('get_bot_task',{'task_id':task['id']})['task'])

class OnboardingMappingTests(onboarding.OnboardingTests):
    requirement=req.TraceabilityIntegrationTests.requirement
    def test_import_keeps_proposed_existing_links_only_after_owner_confirmation(self):
        ref=self.requirement();d=self.start()
        proposal={'nodes':[],'findings':[],'questions':[],'next_work':{'title':'Continue motion','purpose':'Measure travel'},'limitations':[],
            'requirement_links':[{**ref,'rationale':'Motion source','evidence':[{'path':'control/motion.py','hash':d['manifest']['control/motion.py']['hash']}]}]}
        d=self.call('propose_onboarding',{**self.ref(d),'snapshot':d['snapshot'],'proposal':proposal})
        self.assertEqual(self.call('studio_overview')['projects'],[])
        d=self.call('complete_onboarding',{**self.ref(d),'title':'Continue','purpose':'Validate motion'})
        self.assertEqual(d['result']['state']['context']['requirement_refs'],[ref])
        work=self.call('studio_work',{'work_id':d['result']['change']['id']})
        self.assertEqual(work['selected']['status']['adoption'],'unadopted')
