import unittest
import json
from gantry.model import canonical, digest, Fault
import test_bot_bounded_context as fixtures


class ActionInputBudgetTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.BotBoundedContextTests(); self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_final_prompt_includes_overhead_and_retains_contract(self):
        from gantry.crew_runtime import action_input
        f = self.fixture
        f.full['task']['completion'] = ['Required: ' + 'x' * 370000]
        last = {str(i): 'e' * 7000 for i in range(13)}
        result = action_input(f.full, f.workspace, {}, last, 2)
        self.assertLessEqual(len(canonical(result).encode()), 480000)
        self.assertEqual(result['task']['completion'], f.full['task']['completion'])
        self.assertEqual(result['last_result']['sha256'], digest(last))
        self.assertTrue(result['last_result']['truncated'])
        self.assertIn('get_bot_records', str(result['last_result']))

    def test_essential_config_is_not_silently_discarded(self):
        from gantry.crew_runtime import action_input
        f = self.fixture
        with self.assertRaises(Fault) as caught:
            action_input(f.full, f.workspace, {'local_tools': {'oversize': 'x'*490000}}, None, 0)
        self.assertEqual(caught.exception.code, 'context_limit')

    def test_real_worker_budgets_large_previous_receipt_before_inference(self):
        import test_bot_development as worker_fixtures
        from gantry.bot_worker import environment_manifest
        c=worker_fixtures.BotDevelopmentTests(); original=c.artifact
        payload={str(i):'e'*7000 for i in range(13)}
        c.artifact=lambda files:original({**files,'observations.json':json.dumps(payload)})
        c.setUp(); self.addCleanup(c.tearDown)
        c.configs['designer']['agent_loop']=True
        c.owner.call('configure_bot_runtime',{'bot_id':'designer','version':1,'principal_id':'designer',
            'enabled':True,'environment':environment_manifest(c.configs['designer'])})
        c.task('designer',kind='report',write_scope=[],completion=['Required: '+'x'*370000])
        contexts=[]
        def infer(context,schema,directory):
            contexts.append(context)
            self.assertLessEqual(len(canonical(context).encode()),480000)
            if len(contexts)==1: action,args='inspect_json',{'path':'observations.json'}
            else:
                self.assertTrue(context['last_result']['truncated'])
                self.assertEqual(context['task']['completion'],['Required: '+'x'*370000])
                action,args='finish',c.answer(summary='Fixture budget checked')
            return {'output':{'action':action,'arguments_json':json.dumps(args),'rationale':'Fixture budget check'}}
        with c.worker('designer',infer) as worker: result=worker.tick()[0]
        self.assertEqual(result['task']['status'],'completed')
        self.assertEqual(len(contexts),2)
