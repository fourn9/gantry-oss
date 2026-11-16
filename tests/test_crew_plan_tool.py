"""Experimental fusion preserves normal recorded plan/tool/evidence boundaries."""
import unittest
from unittest.mock import patch

from gantry import crew_plan_tool as fusion
from gantry.crew_runtime import SCHEMA
from gantry.model import Fault
import test_crew_tool_evidence as fixtures


class PlanToolTests(unittest.TestCase):
    def setUp(self):
        self.c=fixtures.CrewToolEvidenceTests(); self.c.setUp(); self.addCleanup(self.c.tearDown)
        self.c.configs['designer']['experimental_latency']='plan_tool'; self.c.configure_tool()
        self.args={'plan_path':'physical-plan.json','check_ids':['load'],'purpose':'Inspect saved fixture',
            'question':'Does this declared fixture meet the frozen limit?','assumptions':['Synthetic fixture'],
            'missing_inputs':[],'tool_name':'stress','expected_outputs':['stress.json'],
            'next_steps':{'pass':'Report scoped result','fail':'Inspect failure','unknown':'Get missing evidence'}}

    def run_case(self, lost_kind=None, missing=False):
        c=self.c; task=c.task('designer',write_scope=c.tool_scope); calls=[]; lost=[]
        client=c.clients['designer']
        class Lost:
            def call(self,name,args=None,key=None):
                value=client.call(name,args,key)
                if name=='record_bot_action' and args['kind']==lost_kind and not lost:
                    lost.append(value); raise OSError('lost acknowledgement')
                return value
        def infer(ctx,schema,directory):
            calls.append(ctx)
            self.assertIn('plan_and_tool',schema['properties']['action']['enum'])
            if len(calls)==1:return c.action('plan_and_tool',{**self.args,'missing_inputs':['unknown load'] if missing else []})
            return c.action('finish',c.answer())
        with c.worker('designer',infer,Lost()) as worker: result=worker.tick()[0]
        if lost_kind:
            self.assertEqual(result['status'],'held')
            with c.worker('designer',infer,Lost()) as worker:result=worker.recover(task['id'],'Reconcile persisted acknowledgement')
        self.assertEqual(result['task']['status'],'completed')
        self.assertEqual(len(calls),2)
        view=c.owner.call('get_bot_task',{'task_id':task['id']})
        kinds=[a['kind'] for a in view['actions']]
        self.assertEqual(kinds.count('plan_verification'),1)
        self.assertEqual(kinds.count('tool'),0 if missing else 1)
        self.assertEqual(kinds.count('tool_evidence'),0 if missing else 1)
        if not missing:
            check=c.check_from_context(calls[-1]);self.assertEqual(check['effective_status'],'pass')
            self.assertEqual(calls[-1]['last_result']['exit_code'],0)
        self.assertTrue(c.owner.call('replay')['matched'])

    def test_one_inference_produces_real_tool_and_two_durable_receipts(self): self.run_case()
    def test_lost_plan_ack_recovers_before_single_tool_execution(self): self.run_case('plan_verification')
    def test_lost_tool_ack_does_not_repeat_tool(self): self.run_case('tool')
    def test_unexecutable_plan_never_runs_tool(self): self.run_case(missing=True)

    def test_default_schema_unchanged_and_disabled_split_denied(self):
        self.assertNotIn('plan_and_tool',SCHEMA['properties']['action']['enum'])
        self.assertEqual(fusion.model_schema(SCHEMA,{}),SCHEMA)
        with self.assertRaises(Fault):fusion.split(self.c.action('plan_and_tool',self.args),{})

    def test_changed_basis_denies_queued_tool(self):
        queued={'input_state':'original','before':'hash','discussion_version':0}
        full={'development':{'state':{'id':'new'}},'task':{'discussion_version':0}}
        with self.assertRaises(Fault) as caught:
            fusion.resume(None,full,{'experimental_latency':'plan_tool'},None,queued,'hash')
        self.assertEqual(caught.exception.code,'stale_basis')

    def test_uncertain_tool_completion_is_held_without_reexecution(self):
        from gantry import crew_runtime
        c=self.c;task=c.task('designer',write_scope=c.tool_scope);runs=[];calls=[]
        original=crew_runtime._execute
        def execute(*args,**kwargs):
            result=original(*args,**kwargs)
            if args[4]=='tool':
                runs.append(result);raise OSError('Crash after local effect before durable completion')
            return result
        def infer(ctx,schema,directory):
            calls.append(ctx);return c.action('plan_and_tool',self.args)
        with patch.object(crew_runtime,'_execute',side_effect=execute):
            with c.worker('designer',infer) as worker:self.assertEqual(worker.tick()[0]['status'],'held')
            with c.worker('designer',infer) as worker:
                with self.assertRaises(Fault) as caught:
                    worker.recover(task['id'],'Preserve ambiguous completed tool')
        self.assertEqual(caught.exception.code,'outcome_unknown')
        self.assertEqual(len(runs),1)
        self.assertEqual(len(calls),1)
        self.assertEqual(runs[0]['exit_code'],0)
