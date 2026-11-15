"""Real Core staleness with deterministic inference; no model-quality assertion."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from gantry.bot_learning_runtime import plan_task
from gantry.model import Fault
import test_bot_learning as fixtures


class LearningRefreshTests(unittest.TestCase):
    def setUp(self):
        self.c = fixtures.BotLearningTests(); self.c.setUp(); self.addCleanup(self.c.tearDown)

    def test_working_note_changed_during_inference_refreshes_commitments(self):
        c = self.c; task = c.task('designer'); calls = []; notes = []
        with c.worker('designer') as worker:
            ref = c.claimed(worker, task)
            context = c.clients['designer'].call('get_bot_task', {'task_id': task['id']})
            def infer(ctx, schema, directory):
                calls.append(ctx)
                if len(calls) == 1:
                    notes.append(c.clients['designer'].call('update_bot_working_state', {**ref,
                        'version': 0, 'focus': 'Check changed routing', 'next_steps': ['Inspect clamp'],
                        'commitments': ['Retain clearance uncertainty'], 'unknowns': ['Physical fit'],
                        'watch_paths': ['mechanical.txt'], 'watch_tasks': [], 'due_at': None}))
                return {'output': c.plan_output(ctx['packet']), 'provider': {'kind': 'fixture'}}
            root = c.root/'learning'
            result = plan_task(c.clients['designer'], ref, context, infer, root)
            self.assertEqual(len(calls), 2)
            self.assertIsNone(calls[0]['working_state'])
            self.assertEqual(calls[1]['working_state']['content'], notes[0]['content'])
            self.assertEqual(calls[1]['working_state']['version'], notes[0]['version'])
            self.assertEqual(result['working_state'], calls[1]['working_state'])
            self.assertEqual(json.loads((root/'refresh.json').read_text())['history'][0]['reason'],
                             'working_context_changed')
        self.assertTrue(c.owner.call('replay')['matched'])

    def test_restart_after_refresh_pointer_commit_keeps_original_answer(self):
        from gantry import bot_learning_refresh
        c = self.c; task = c.task('designer'); calls = []
        with c.worker('designer') as worker:
            ref = c.claimed(worker, task)
            context = c.clients['designer'].call('get_bot_task', {'task_id': task['id']})
            def infer(ctx, schema, directory):
                calls.append(ctx)
                if len(calls) == 1: c.seed(ref)
                return {'output': c.plan_output(ctx['packet']), 'provider': {'kind': 'fixture'}}
            advance = bot_learning_refresh.advance
            def crash_after_advance(root, reason):
                advance(root, reason)
                raise OSError('Simulated crash after durable refresh pointer commit')
            root = c.root/'learning'
            with patch.object(bot_learning_refresh, 'advance', crash_after_advance):
                with self.assertRaisesRegex(OSError, 'durable refresh pointer'):
                    plan_task(c.clients['designer'], ref, context, infer, root)
            original = (root/'plan.json').read_bytes()
            receipt = (root/'inference'/'receipt.json').read_bytes()
            self.assertEqual(json.loads((root/'refresh.json').read_text())['generation'], 1)
            self.assertFalse((root/'replans'/'1'/'plan.json').exists())
            result = plan_task(c.clients['designer'], ref, context, infer, root)
            self.assertEqual(result['status'], 'completed')
            self.assertEqual(len(calls), 2)
            self.assertEqual((root/'plan.json').read_bytes(), original)
            self.assertEqual((root/'inference'/'receipt.json').read_bytes(), receipt)
            self.assertEqual(plan_task(c.clients['designer'], ref, context, infer, root), result)
            self.assertEqual(len(calls), 2)
        self.assertTrue(c.owner.call('replay')['matched'])

    def test_recover_task_retries_only_active_generation_and_finishes_once(self):
        from gantry.runner import persist
        c = self.c; c.enable_learning(); task = c.task('designer'); plans = []; contexts = []
        normal = c.learning_infer(contexts)
        def infer(ctx, schema, directory):
            directory = Path(directory)
            if ctx.get('operation') == 'plan_from_experience':
                plans.append(ctx)
                if len(plans) == 1:
                    claim = json.loads((directory.parents[2]/'task.json').read_text())['claim']['task']
                    c.seed({'task_id': claim['id'], 'fence': claim['fence']})
                else:
                    marker = directory/'inference.json'
                    if not marker.exists():
                        persist(marker, {'phase': 'failed', 'code': 'provider_timeout', 'pid': 99999999,
                            'process_stopped': True, 'returncode': -15, 'failures': 1,
                            'context': ctx, 'schema': schema})
                        (directory/'events.jsonl').write_text('{"type":"turn.started"}\n')
                    if json.loads(marker.read_text())['phase'] != 'retry_ready':
                        raise Fault('provider_timeout', 'Fixture provider stopped without an answer')
            return normal(ctx, schema, directory)
        with c.worker('designer', infer) as worker:
            self.assertEqual(worker.tick()[0]['reason'], 'provider_timeout')
            learning = next(worker.root.glob('jobs/development/*/1/learning'))
            old_plan = (learning/'plan.json').read_bytes()
            old_receipt = (learning/'inference'/'receipt.json').read_bytes()
        with c.worker('designer', infer) as worker:
            result = worker.recover(task['id'], 'Fixture provider confirmed stopped', retry_inference=True)
            self.assertEqual(result['task']['status'], 'completed')
            self.assertEqual(worker.recover(task['id'], 'Reconcile completed recovery'), result)
            worker.tick()
        self.assertEqual(len(plans), 3)
        self.assertEqual(plans[1], plans[2], 'Recovery must retain the exact refreshed inference input')
        self.assertEqual((learning/'plan.json').read_bytes(), old_plan)
        self.assertEqual((learning/'inference'/'receipt.json').read_bytes(), old_receipt)
        self.assertEqual(len(list((learning/'replans'/'1'/'inference'/'model'/'recoveries').glob('*'))), 1)
        self.assertFalse((learning/'inference'/'model'/'recoveries').exists())
        self.assertEqual(len([ctx for ctx in contexts if not ctx.get('operation')]), 1)
        self.assertEqual(len([ctx for ctx in contexts if ctx.get('operation') == 'reflect_on_experience']), 1)
        self.assertTrue(c.owner.call('replay')['matched'])

    def test_memory_added_during_inference_replans_and_preserves_old_answer(self):
        c = self.c; task = c.task('designer', title='Recheck routing', dependencies=['mechanical.txt']); calls = []
        with c.worker('designer') as worker:
            ref = c.claimed(worker, task)
            context = c.clients['designer'].call('get_bot_task', {'task_id':task['id']})
            def infer(ctx, schema, directory):
                calls.append(ctx)
                if len(calls) == 1: c.seed(ref, 'New routing observation while planning')
                return {'output':c.plan_output(ctx['packet']), 'provider':{'kind':'fixture'}}
            root = c.root/'learning'
            result = plan_task(c.clients['designer'], ref, context, infer, root)
            self.assertEqual(len(calls), 2)
            self.assertEqual(len(result['output']['decisions']), 1)
            original = json.loads((root/'plan.json').read_text())
            self.assertEqual(original['receipt']['output']['decisions'], [])
            self.assertNotIn('result', original)
            self.assertEqual(plan_task(c.clients['designer'], ref, context, infer, root), result)
            self.assertEqual(len(calls), 2, 'Completed refreshed plan must not reinfer on reconnect')
        self.assertTrue(c.owner.call('replay')['matched'])

    def test_revocation_during_inference_is_not_replanned(self):
        c=self.c;task=c.task('designer'); calls=[]
        with c.worker('designer') as worker:
            ref=c.claimed(worker,task);context=c.clients['designer'].call('get_bot_task',{'task_id':task['id']})
            def infer(ctx,schema,directory):
                calls.append(ctx)
                c.owner.call('bind_development_bot',{'session_id':c.sid,'bot_id':'designer','principal_id':'designer',
                    'version':1,'write_scope':c.scope('designer'),'can_assign':False,'can_integrate':False,'enabled':False})
                return {'output':c.plan_output(ctx['packet']),'provider':{'kind':'fixture'}}
            with self.assertRaises(Fault): plan_task(c.clients['designer'],ref,context,infer,c.root/'learning')
            self.assertEqual(len(calls),1)

    def test_churning_memory_is_bounded_across_restart(self):
        c=self.c;task=c.task('designer');calls=[]
        with c.worker('designer') as worker:
            ref=c.claimed(worker,task);context=c.clients['designer'].call('get_bot_task',{'task_id':task['id']})
            def infer(ctx,schema,directory):
                calls.append(ctx);c.seed(ref,'New memory '+str(len(calls)))
                return {'output':c.plan_output(ctx['packet']),'provider':{'kind':'fixture'}}
            root=c.root/'learning'
            for _ in range(2):
                with self.assertRaises(Fault) as error:plan_task(c.clients['designer'],ref,context,infer,root)
                self.assertEqual(error.exception.code,'stale_basis')
            self.assertEqual(len(calls),4, 'One initial plan and three refreshes, no reset on reconnect')

    def test_new_generation_is_the_pending_recovery_target(self):
        from gantry.bot_inference_recovery import pending_inference
        c=self.c; task=c.task('designer');calls=[]
        with c.worker('designer') as worker:
            ref=c.claimed(worker,task);context=c.clients['designer'].call('get_bot_task',{'task_id':task['id']})
            directory=c.root/'attempt';root=directory/'learning'
            def infer(ctx,schema,path):
                calls.append(ctx)
                if len(calls)==1:
                    c.seed(ref)
                    return {'output':c.plan_output(ctx['packet']),'provider':{'kind':'fixture'}}
                raise Fault('provider_timeout','Stopped test inference; no automatic model retry')
            with self.assertRaises(Fault) as error:plan_task(c.clients['designer'],ref,context,infer,root)
            self.assertEqual(error.exception.code,'provider_timeout')
            target=pending_inference(directory,{'phase':'inference'},{'experience_learning':True})
            self.assertEqual(target,root/'replans'/'1'/'inference'/'model')
            self.assertTrue((root/'inference'/'receipt.json').exists())
            self.assertEqual(len(calls),2)

    def test_invalid_apply_is_not_a_refresh_signal(self):
        c=self.c;task=c.task('designer',title='Check clamp',dependencies=['mechanical.txt']);calls=[]
        with c.worker('designer') as worker:
            ref=c.claimed(worker,task);c.seed(ref)
            context=c.clients['designer'].call('get_bot_task',{'task_id':task['id']})
            def infer(ctx,schema,path):
                calls.append(ctx)
                decisions=[{'memory_id':m['id'],'use':'apply','reason':'Unchecked assumption'} for m in ctx['packet']['recall']['items']]
                return {'output':c.plan_output(ctx['packet'],decisions),'provider':{'kind':'fixture'}}
            with self.assertRaises(Fault) as error:plan_task(c.clients['designer'],ref,context,infer,c.root/'learning')
            self.assertEqual(error.exception.code,'stale_basis')
            self.assertNotIn('replan_reason',error.exception.details)
            self.assertEqual(len(calls),1)

    def test_refresh_submit_lost_ack_reconciles_without_model_repeat(self):
        c=self.c;task=c.task('designer');calls=[];submits=[]
        with c.worker('designer') as worker:
            ref=c.claimed(worker,task);client=c.clients['designer']
            context=client.call('get_bot_task',{'task_id':task['id']});root=c.root/'learning'
            def infer(ctx,schema,path):
                calls.append(ctx)
                if len(calls)==1:c.seed(ref)
                return {'output':c.plan_output(ctx['packet']),'provider':{'kind':'fixture'}}
            class LostAck:
                def call(self,name,args=None,key=None):
                    result=client.call(name,args,key)
                    if name=='submit_bot_learning_plan' and not submits:
                        submits.append(result);raise OSError('Acknowledgement lost after successful submit')
                    return result
            with self.assertRaises(OSError):plan_task(LostAck(),ref,context,infer,root)
            result=plan_task(client,ref,context,infer,root)
            self.assertEqual(result['id'],submits[0]['id'])
            self.assertEqual(len(calls),2)
