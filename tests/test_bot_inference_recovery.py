import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from gantry.model import Fault
from gantry.monthly_codex import infer_monthly
from gantry.runner import persist


def failed_invocation(root, context=None, schema=None, message='HTTP 429 Too Many Requests'):
    root.mkdir(parents=True, exist_ok=True)
    persist(root/'inference.json', {'phase': 'started', 'context': context or {}, 'schema': schema or {}, 'pid': 99999999})
    (root/'events.jsonl').write_text(json.dumps({'type': 'turn.failed', 'error': {'message': message}})+'\n')


class MonthlyRecoveryTests(unittest.TestCase):
    def test_429_is_classified_without_repeating_request(self):
        class Process:
            pid = 99999999
            returncode = 1
            def __init__(self, argv, **kw): self.stream = kw['stdout']
            def communicate(self, prompt, timeout):
                self.stream.write(json.dumps({'type': 'turn.failed', 'error': {'message': 'HTTP 429 Too Many Requests'}})+'\n')
        with tempfile.TemporaryDirectory() as tmp, patch('gantry.monthly_codex.subprocess.run',
                return_value=SimpleNamespace(returncode=0, stdout='ChatGPT', stderr='')), \
                patch('gantry.monthly_codex.subprocess.Popen', side_effect=Process) as popen:
            for _ in range(2):
                with self.assertRaises(Fault) as error: infer_monthly({}, {}, tmp)
                self.assertEqual(error.exception.code, 'provider_rate_limited')
                self.assertTrue(error.exception.details['retry_at'])
            self.assertEqual(popen.call_count, 1)

    def test_explicit_retry_preserves_evidence_and_enforces_cooldown(self):
        from gantry.monthly_recovery import prepare_retry
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'model'; failed_invocation(root)
            with patch('gantry.monthly_recovery.time.time', return_value=100):
                with self.assertRaises(Fault) as error: infer_monthly({}, {}, root)
                self.assertEqual(error.exception.code, 'provider_rate_limited')
                with self.assertRaises(Fault) as error: prepare_retry(root, 'Previous process stopped')
                self.assertEqual(error.exception.code, 'provider_rate_limited')
            with patch('gantry.monthly_recovery.time.time', return_value=200):
                prepare_retry(root, 'Previous process stopped')
                prepare_retry(root, 'Retry interrupted before starting')
            self.assertEqual(json.loads((root/'inference.json').read_text())['phase'], 'retry_ready')
            archives = list((root/'recoveries').glob('*/events.jsonl'))
            self.assertEqual(len(archives), 1)
            self.assertIn('429', archives[0].read_text())

    def test_unknown_live_and_answered_invocations_cannot_be_reset(self):
        from gantry.monthly_recovery import prepare_retry
        for kind in ('unknown', 'live', 'answer', 'partial_answer', 'missing_pid'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); failed_invocation(root, message='HTTP 429' if kind != 'unknown' else 'connection lost')
                if kind == 'answer': (root/'answer.json').write_text('{}')
                if kind == 'partial_answer':
                    (root/'events.jsonl').write_text(json.dumps({'type': 'item.completed', 'item': {
                        'type': 'agent_message', 'text': 'partial'}})+'\n'+(root/'events.jsonl').read_text())
                if kind == 'live':
                    import os
                    state = json.loads((root/'inference.json').read_text()); state['pid'] = os.getpid()
                    persist(root/'inference.json', state)
                if kind == 'missing_pid':
                    state = json.loads((root/'inference.json').read_text()); state.pop('pid')
                    persist(root/'inference.json', state)
                with self.assertRaises(Fault) as error: prepare_retry(root, 'Stopped assertion is not enough')
                self.assertEqual(error.exception.code, 'outcome_unknown')
                self.assertFalse((root/'recoveries').exists())

    def test_reflection_unknown_monthly_call_is_not_repeated(self):
        from gantry.bot_reflection_recovery import recover_reflection
        class Client:
            def call(self, *args): return {'id': 'reflection', 'bot_id': 'bot', 'status': 'pending'}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); folder = root/'reflection'
            failed_invocation(folder/'inference/model', message='connection lost')
            persist(folder/'reflection.json', {'input': {}})
            with patch('gantry.bot_reflection_recovery.attempt_reflection') as continuation:
                with self.assertRaises(Fault) as error:
                    recover_reflection(Client(), 'bot', 'reflection', None, root, 'Stopped assertion', retry_inference=True)
                self.assertEqual(error.exception.code, 'outcome_unknown')
                continuation.assert_not_called()
                self.assertTrue((folder/'inference/model/inference.json').exists())


from test_crew_runtime import CrewRuntimeTests


class BotRetryTests(CrewRuntimeTests):
    def test_repeated_rate_limits_require_stopped_runtime_and_preserve_backoff(self):
        self.enable_loop('designer'); task = self.task('designer'); tries = []
        def infer(ctx, schema, directory):
            root = Path(directory); marker = root/'inference.json'
            if not marker.exists(): failed_invocation(root, ctx, schema)
            state = json.loads(marker.read_text())
            if state['phase'] == 'retry_ready':
                tries.append(True)
                if len(tries) == 2: return self.action('finish', self.answer())
                state.update(phase='started', pid=99999999); persist(marker, state)
            return infer_monthly(ctx, schema, directory)
        with self.worker('designer', infer) as worker:
            with patch('gantry.monthly_recovery.time.time', return_value=100): worker.tick()
            with patch('gantry.monthly_recovery.time.time', return_value=200):
                self.fault('conflict', lambda: worker.recover(task['id'], 'Runtime is still active', retry_inference=True))
        with self.worker('designer', infer) as worker:
            with patch('gantry.monthly_recovery.time.time', return_value=200):
                self.fault('provider_rate_limited', lambda: worker.recover(task['id'], 'CLI stopped', retry_inference=True))
        with self.worker('designer', infer) as worker:
            with patch('gantry.monthly_recovery.time.time', return_value=300):
                self.fault('provider_rate_limited', lambda: worker.recover(task['id'], 'Still cooling down', retry_inference=True))
            with patch('gantry.monthly_recovery.time.time', return_value=400):
                result = worker.recover(task['id'], 'CLI stopped again', retry_inference=True)
        self.assertEqual(result['task']['status'], 'completed')

    def test_explicit_retry_does_not_repeat_completed_action(self):
        self.enable_loop('designer'); task = self.task('designer'); inputs = []; count = []
        def infer(ctx, schema, directory):
            inputs.append(ctx)
            if ctx['round'] == 0:
                count.append('read'); return self.action('read', {'path': 'mechanical.txt'})
            root = Path(directory); marker = root/'inference.json'
            if not marker.exists(): failed_invocation(root, ctx, schema)
            saved = json.loads(marker.read_text())
            if saved['phase'] != 'retry_ready': return infer_monthly(ctx, schema, directory)
            self.assertEqual(saved['context'], ctx)
            return self.action('finish', self.answer())
        with patch('gantry.monthly_recovery.time.time', return_value=100):
            with self.worker('designer', infer) as worker: self.assertEqual(worker.tick()[0]['status'], 'held')
        with patch('gantry.monthly_recovery.time.time', return_value=200):
            with self.worker('designer', infer) as worker:
                result = worker.recover(task['id'], 'Previous process stopped', retry_inference=True)
        self.assertEqual(result['task']['status'], 'completed')
        self.assertEqual(count, ['read'])
        self.assertEqual(inputs[1], inputs[2])
        view = self.owner.call('get_bot_task', {'task_id': task['id']})
        self.assertEqual(len([a for a in view['actions'] if a['kind'] == 'read']), 1)


from test_bot_learning import BotLearningTests


class PlanningRetryTests(BotLearningTests):
    def test_rejected_reflection_receives_saved_error_and_previous_response(self):
        self.enable_learning(); self.task('designer'); contexts = []; reflection_inputs = []
        normal = self.learning_infer(contexts)
        def infer(ctx, schema, directory):
            result = normal(ctx, schema, directory)
            if ctx.get('operation') == 'reflect_on_experience':
                reflection_inputs.append(ctx)
                if len(reflection_inputs) == 1:
                    result['output']['feedback'] = [{'memory_id': 'unrecalled', 'outcome': 'unknown',
                        'reason': 'Invalid test citation', 'evidence': [ctx['packet']['task_id']]}]
                else:
                    self.assertEqual(ctx['validation_feedback']['code'], 'invalid_input')
                    self.assertEqual(ctx['previous_submission']['feedback'][0]['memory_id'], 'unrecalled')
            return result
        with self.worker('designer', infer) as worker:
            results = worker.tick(); held = results[1]
            self.assertEqual(held['status'], 'held')
            result = worker.recover_reflection(held['reflection_id'], 'Previous response completed but rejected', retry_inference=True)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(len(reflection_inputs), 2)
    def test_planning_failure_resumes_same_input_and_finishes_reflection(self):
        self.enable_learning(); task = self.task('designer'); contexts = []; plans = []
        normal = self.learning_infer(contexts)
        def infer(ctx, schema, directory):
            if ctx.get('operation') == 'plan_from_experience':
                plans.append(ctx); marker = Path(directory)/'inference.json'
                if not marker.exists(): failed_invocation(Path(directory), ctx, schema)
                if json.loads(marker.read_text())['phase'] != 'retry_ready': return infer_monthly(ctx, schema, directory)
            return normal(ctx, schema, directory)
        with patch('gantry.monthly_recovery.time.time', return_value=100):
            with self.worker('designer', infer) as worker: self.assertEqual(worker.tick()[0]['status'], 'held')
        with patch('gantry.monthly_recovery.time.time', return_value=200):
            with self.worker('designer', infer) as worker:
                result = worker.recover(task['id'], 'Provider stopped', retry_inference=True)
                worker.tick()
        self.assertEqual(result['task']['status'], 'completed')
        self.assertEqual(plans[0], plans[1])
        self.assertEqual(len([c for c in contexts if c.get('operation') == 'reflect_on_experience']), 1)
        self.assertTrue(self.owner.call('replay')['matched'])

    def test_running_planning_provider_blocks_recovery(self):
        import os
        self.enable_learning(); task = self.task('designer')
        def infer(ctx, schema, directory):
            persist(Path(directory)/'inference.json', {'phase': 'started', 'context': ctx, 'schema': schema, 'pid': os.getpid()})
            raise Fault('outcome_unknown', 'Still running')
        with self.worker('designer', infer) as worker: worker.tick()
        with self.worker('designer', infer) as worker:
            self.fault('outcome_unknown', lambda: worker.recover(task['id'], 'Unverified stopped assertion', retry_inference=True))
