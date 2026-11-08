"""Explicit, answer-free timeout recovery; no live inference required."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from gantry.model import Fault
from gantry.monthly_codex import infer_monthly
from gantry.monthly_recovery import prepare_retry
from gantry.runner import persist


class MonthlyTimeoutRecoveryTests(unittest.TestCase):
    def state(self, root, **changes):
        state = {'phase': 'failed', 'code': 'provider_timeout', 'pid': 99999999,
                 'process_stopped': True, 'returncode': -15, 'failed_at': 100,
                 'failures': 1, 'context': {'task': 'anonymous'}, 'schema': {},
                 'inference_settings': {'model': 'fixture-model', 'reasoning_effort': 'low'}}
        state.update(changes)
        persist(root/'inference.json', state)
        (root/'events.jsonl').write_text('{"type":"turn.started"}\n')
        return state

    def test_adapter_records_timeout_only_after_confirmed_process_stop(self):
        class Process:
            pid = 99999999
            returncode = None
            def __init__(self, *args, **kwargs): pass
            def communicate(self, prompt, timeout): raise subprocess.TimeoutExpired('codex', timeout)
            def poll(self): return self.returncode
        def stop(proc): proc.returncode = -15
        with tempfile.TemporaryDirectory() as tmp, patch('gantry.monthly_codex.subprocess.run',
                return_value=SimpleNamespace(returncode=0, stdout='ChatGPT', stderr='')), \
                patch('gantry.monthly_codex.subprocess.Popen', Process), \
                patch('gantry.monthly_codex.stop_process', side_effect=stop) as stopper:
            with self.assertRaises(Fault) as caught:
                infer_monthly({'task': 'anonymous'}, {}, tmp, model='fixture-model', reasoning_effort='low')
            self.assertEqual(caught.exception.code, 'provider_timeout')
            state = json.loads(Path(tmp, 'inference.json').read_text())
            stopper.assert_called_once()
            self.assertEqual(state['phase'], 'failed')
            self.assertEqual(state['code'], 'provider_timeout')
            self.assertTrue(state['process_stopped'])
            self.assertEqual(state['returncode'], -15)
            self.assertEqual(state['context'], {'task': 'anonymous'})
            self.assertEqual(state['inference_settings']['model'], 'fixture-model')

    def test_explicit_timeout_retry_archives_exact_input_and_does_not_autoretry(self):
        with tempfile.TemporaryDirectory() as tmp, patch('gantry.monthly_codex.subprocess.Popen') as popen:
            root = Path(tmp); state = self.state(root)
            with self.assertRaises(Fault):
                infer_monthly(state['context'], state['schema'], root, model='fixture-model', reasoning_effort='low')
            popen.assert_not_called()
            prepare_retry(root, 'Verified old process stopped', check_only=True)
            self.assertEqual(json.loads((root/'inference.json').read_text()), state)
            self.assertFalse((root/'recoveries').exists())
            prepare_retry(root, 'Verified old process stopped')
            armed = json.loads((root/'inference.json').read_text())
            self.assertEqual(armed['phase'], 'retry_ready')
            for key in ('context', 'schema', 'inference_settings'):
                self.assertEqual(armed[key], state[key])
            archives = list((root/'recoveries').glob('*/inference.json'))
            self.assertEqual(len(archives), 1)
            self.assertEqual(json.loads(archives[0].read_text()), state)
            self.assertEqual(json.loads(archives[0].with_name('recovery.json').read_text())['failure_code'], 'provider_timeout')

    def test_unconfirmed_adapter_stop_preserves_uncertain_started_journal(self):
        class Process:
            pid = 99999999
            returncode = None
            def __init__(self, *args, **kwargs): pass
            def communicate(self, prompt, timeout): raise subprocess.TimeoutExpired('codex', timeout)
            def poll(self): return None
        with tempfile.TemporaryDirectory() as tmp, patch('gantry.monthly_codex.subprocess.run',
                return_value=SimpleNamespace(returncode=0, stdout='ChatGPT', stderr='')), \
                patch('gantry.monthly_codex.subprocess.Popen', Process), \
                patch('gantry.monthly_codex.stop_process'):
            with self.assertRaises(Fault) as caught: infer_monthly({}, {}, tmp)
            self.assertEqual(caught.exception.code, 'outcome_unknown')
            state = json.loads(Path(tmp, 'inference.json').read_text())
            self.assertEqual(state['phase'], 'started')
            self.assertNotIn('process_stopped', state)

    def test_timeout_with_answer_or_completed_response_remains_held(self):
        for kind in ('answer', 'partial', 'completed', 'malformed', 'missing_events'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); self.state(root)
                if kind == 'answer': (root/'answer.json').write_text('{}')
                if kind == 'partial': (root/'events.jsonl').write_text('{"type":"item.updated","item":{"type":"agent_message","text":"partial"}}\n')
                if kind == 'completed': (root/'events.jsonl').write_text('{"type":"turn.completed","usage":{}}\n')
                if kind == 'malformed': (root/'events.jsonl').write_text('{broken')
                if kind == 'missing_events': (root/'events.jsonl').unlink()
                with self.assertRaises(Fault) as caught: prepare_retry(root, 'Stopped assertion')
                self.assertEqual(caught.exception.code, 'outcome_unknown')
                self.assertFalse((root/'recoveries').exists())

    def test_bot_recovery_reuses_completed_action_and_exact_pending_input(self):
        import test_crew_runtime as fixtures
        c = fixtures.CrewRuntimeTests(); c.setUp(); self.addCleanup(c.tearDown)
        c.enable_loop('designer'); task = c.task('designer'); inputs = []; reads = []
        def infer(ctx, schema, directory):
            inputs.append(ctx)
            if ctx['round'] == 0:
                reads.append(True)
                return c.action('read', {'path': 'mechanical.txt'})
            root = Path(directory); marker = root/'inference.json'
            if not marker.exists():
                root.mkdir(parents=True, exist_ok=True)
                self.state(root, context=ctx, schema=schema, inference_settings={})
            saved = json.loads(marker.read_text())
            if saved['phase'] != 'retry_ready': return infer_monthly(ctx, schema, directory)
            self.assertEqual(saved['context'], ctx)
            return c.action('finish', c.answer())
        with c.worker('designer', infer) as worker:
            held = worker.tick()[0]
            self.assertEqual(held['status'], 'held')
            self.assertEqual(held['reason'], 'provider_timeout')
        with c.worker('designer', infer) as worker:
            result = worker.recover(task['id'], 'Previous timeout process stopped', retry_inference=True)
        self.assertEqual(result['task']['status'], 'completed')
        self.assertEqual(reads, [True])
        self.assertEqual(inputs[1], inputs[2])
        view = c.owner.call('get_bot_task', {'task_id': task['id']})
        self.assertEqual(len([a for a in view['actions'] if a['kind'] == 'read']), 1)
        self.assertTrue(c.owner.call('replay')['matched'])

    def test_unknown_live_missing_pid_or_unconfirmed_stop_remain_held(self):
        cases = [{'phase': 'started'}, {'pid': os.getpid()}, {'pid': None},
                 {'process_stopped': False}, {'returncode': None}, {'code': 'provider_failed'}]
        for changes in cases:
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); self.state(root, **changes)
                with self.assertRaises(Fault) as caught: prepare_retry(root, 'Stopped assertion')
                self.assertEqual(caught.exception.code, 'outcome_unknown')
                self.assertFalse((root/'recoveries').exists())
