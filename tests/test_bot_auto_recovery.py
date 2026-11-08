"""Opt-in recovery against real Core state; inference is deterministic and local."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from gantry.bot_worker import environment_manifest
from gantry.model import Fault, digest
from gantry.runner import persist
import test_crew_runtime as fixtures


class BotAutoRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.c = fixtures.CrewRuntimeTests(); self.c.setUp()
        self.addCleanup(self.c.tearDown)

    def enable(self, max_attempts=1, **changes):
        self.c.enable_loop('designer', backend='codex_subscription', recovery_policy={
            'max_attempts': max_attempts, 'cooldown_seconds': 10}, **changes)

    def timeout(self, root, context, schema, **changes):
        root = Path(root); root.mkdir(parents=True, exist_ok=True)
        state = {'phase': 'failed', 'code': 'provider_timeout', 'pid': 99999999,
            'process_stopped': True, 'returncode': -15, 'failed_at': 1,
            'failures': 1, 'context': context, 'schema': schema}
        state.update(changes); persist(root/'inference.json', state)
        (root/'events.jsonl').write_text('{"type":"turn.started"}\n')

    def test_restart_resumes_stopped_timeout_without_repeating_completed_action(self):
        self.enable(); task = self.c.task('designer'); calls = []
        def infer(ctx, schema, directory):
            calls.append(ctx)
            if ctx['round'] == 0: return self.c.action('read', {'path': 'mechanical.txt'})
            marker = Path(directory)/'inference.json'
            if not marker.exists(): self.timeout(directory, ctx, schema)
            if json.loads(marker.read_text())['phase'] != 'retry_ready':
                raise Fault('provider_timeout', 'Synthetic stopped timeout')
            return self.c.action('finish', self.c.answer())
        with self.c.worker('designer', infer) as worker:
            old_fence = worker.runtime['fence']
            self.assertEqual(worker.tick()[0]['reason'], 'provider_timeout')
            worker.tick()  # Observe the held task and durably begin the cooldown.
        with patch('time.time', return_value=10**10):
            with self.c.worker('designer', infer) as worker:
                self.assertNotEqual(worker.runtime['fence'], old_fence)
                result = worker.tick()[0]
        self.assertEqual(result.get('task', {}).get('status'), 'completed', result)
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[1], calls[2])
        view = self.c.owner.call('get_bot_task', {'task_id': task['id']})
        self.assertEqual(len([a for a in view['actions'] if a['kind'] == 'read']), 1)
        from gantry.crew_timing import summarize
        timing = summarize(worker.root)['phases']
        self.assertEqual(timing.get('recovery', {}).get('count'), 1)
        self.assertEqual(timing['recovery']['failed'], 0)
        self.assertTrue(self.c.owner.call('replay')['matched'])

    def test_policy_is_bound_to_owner_approved_environment(self):
        original = environment_manifest(self.c.configs['designer'])
        self.c.configs['designer']['recovery_policy'] = {'max_attempts': 1, 'cooldown_seconds': 10}
        self.assertNotEqual(environment_manifest(self.c.configs['designer']), original)
        self.c.fault('stale_basis', lambda: self.c.worker('designer').__enter__())

    def test_policy_rejects_unbounded_or_ambiguous_settings(self):
        for value in (None, {}, {'max_attempts': 0, 'cooldown_seconds': 10},
                      {'max_attempts': 4, 'cooldown_seconds': 10},
                      {'max_attempts': True, 'cooldown_seconds': 10},
                      {'max_attempts': 1, 'cooldown_seconds': 0},
                      {'max_attempts': 1, 'cooldown_seconds': 86401},
                      {'max_attempts': 1, 'cooldown_seconds': 10, 'enabled': True}):
            with self.subTest(policy=value):
                self.c.configs['designer']['recovery_policy'] = value
                self.c.fault('invalid_input', lambda: self.c.worker('designer'))

    def stopped_infer(self, calls, **changes):
        def infer(ctx, schema, directory):
            calls.append(ctx); self.timeout(directory, ctx, schema, **changes)
            raise Fault('provider_timeout', 'Synthetic stopped timeout')
        return infer

    def observe(self, worker):
        self.assertEqual(worker.tick()[0]['status'], 'held')
        return worker.tick()[0]

    def test_default_does_not_recover_or_restart(self):
        self.c.enable_loop('designer'); self.c.task('designer'); calls = []
        infer = self.stopped_infer(calls)
        with self.c.worker('designer', infer) as worker: self.observe(worker)
        with patch('time.time', return_value=10**10):
            with self.c.worker('designer', infer) as worker:
                self.assertEqual(worker.tick()[0]['reason'], 'explicit_recovery_required')
                self.assertFalse(worker.restart.is_set())
        self.assertEqual(len(calls), 1)

    def test_attempt_cap_and_cooldown_survive_restarts(self):
        self.enable(); self.c.task('designer'); calls = []; infer = self.stopped_infer(calls)
        with patch('time.time', return_value=100):
            with self.c.worker('designer', infer) as worker:
                self.assertEqual(self.observe(worker)['reason'], 'recovery_cooldown')
                self.assertFalse(worker.restart.is_set())
        with patch('time.time', return_value=109):
            with self.c.worker('designer', infer) as worker:
                self.assertEqual(worker.tick()[0]['reason'], 'recovery_cooldown')
        with patch('time.time', return_value=110):
            with self.c.worker('designer', infer) as worker:
                self.assertEqual(worker.tick()[0]['reason'], 'provider_timeout')
        with patch('time.time', return_value=1000):
            with self.c.worker('designer', infer) as worker:
                self.assertEqual(worker.tick()[0]['reason'], 'recovery_limit')
                self.assertFalse(worker.restart.is_set())
        self.assertEqual(len(calls), 2)

    def test_same_fence_requests_service_restart_without_replaying_inference(self):
        self.enable(); self.c.task('designer'); calls = []; infer = self.stopped_infer(calls)
        with self.c.worker('designer', infer) as worker:
            with patch('time.time', return_value=100): self.observe(worker)
            with patch('time.time', return_value=110):
                self.assertEqual(worker.tick()[0]['reason'], 'recovery_restart_required')
            self.assertTrue(worker.restart.is_set())
            receipt = json.loads(next(worker.root.rglob('auto-recovery.json')).read_text())
            self.assertEqual(receipt['attempts'], 0)
            self.assertEqual(receipt['restart_fence'], digest(worker.runtime['fence']))
            self.assertNotIn('context', receipt)
        self.assertEqual(len(calls), 1)

    def test_unknown_invocation_and_live_pid_remain_held(self):
        import os
        self.enable(); task = self.c.task('designer'); calls = []
        with self.c.worker('designer', self.stopped_infer(calls)) as worker:
            self.observe(worker)
            marker = next(worker.root.rglob('model/inference.json')); original = json.loads(marker.read_text())
        cases = ({'phase': 'started'}, {'pid': os.getpid()}, {'pid': None}, {'process_stopped': False},
                 {'returncode': None}, {'code': 'provider_failed'}, {'phase': 'retry_ready'}, {'pid': False},
                 {'code': 'provider_rate_limited', 'pid': None, 'retry_at': 1})
        for changes in cases:
            with self.subTest(changes=changes):
                persist(marker, {**original, **changes})
                with patch('time.time', return_value=10**10):
                    with self.c.worker('designer', self.stopped_infer(calls)) as worker:
                        self.assertEqual(worker.tick()[0]['reason'], 'outcome_unknown')
                        self.assertFalse(worker.restart.is_set())
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.c.owner.call('get_bot_task', {'task_id': task['id']})['task']['status'], 'held')

    def test_unknown_tool_or_edit_is_never_repeated(self):
        self.enable(); self.c.task('designer'); calls = []
        with self.c.worker('designer', self.stopped_infer(calls)) as worker:
            self.observe(worker)
            directory = next(worker.root.rglob('task.json')).parent
        for action in ('tool', 'edit'):
            with self.subTest(action=action):
                persist(directory/'actions'/'0'/'action.json', {'phase': 'executing',
                    'receipt': {'output': {'action': action, 'arguments_json': '{}'}}})
                with patch('time.time', return_value=10**10), patch('gantry.crew_runtime._execute') as execute:
                    with self.c.worker('designer', self.stopped_infer(calls)) as worker:
                        self.assertEqual(worker.tick()[0]['reason'], 'outcome_unknown')
                        self.assertFalse(worker.restart.is_set())
                    execute.assert_not_called()
        self.assertEqual(len(calls), 1)

    def test_changed_authority_stays_held_before_provider_is_retried(self):
        self.enable(); task = self.c.task('designer'); calls = []
        with self.c.worker('designer', self.stopped_infer(calls)) as worker: self.observe(worker)
        self.c.owner.call('bind_development_bot', {'session_id': self.c.sid, 'bot_id': 'designer',
            'principal_id': 'designer', 'version': 1, 'write_scope': ['mechanical.txt'],
            'can_assign': False, 'can_integrate': False, 'enabled': True})
        with patch('time.time', return_value=10**10):
            with self.c.worker('designer', self.stopped_infer(calls)) as worker:
                self.assertEqual(worker.tick()[0]['reason'], 'stale_basis')
                self.assertFalse(worker.restart.is_set())
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.c.owner.call('get_bot_task', {'task_id': task['id']})['task']['status'], 'held')

    def test_lease_loss_recovers_saved_response_under_fresh_fence(self):
        self.enable(); task = self.c.task('designer'); launches = []
        now = self.c.service.clock()
        def infer(ctx, schema, directory):
            marker = Path(directory)/'inference.json'
            if marker.exists(): return json.loads(marker.read_text())['receipt']
            launches.append(True)
            persist(marker, {'phase': 'completed', 'context': ctx, 'schema': schema,
                'receipt': self.c.action('finish', self.c.answer())})
            self.c.service.clock = lambda: now + 61000
            raise Fault('runtime_offline', 'Synthetic lease expired after saved response')
        with self.c.worker('designer', infer) as worker:
            old_fence = worker.runtime['fence']
            self.assertEqual(worker.tick()[0]['reason'], 'runtime_offline')
            self.c.fault('stale_basis', worker.tick)
        with self.c.worker('designer', infer) as worker:
            self.assertNotEqual(worker.runtime['fence'], old_fence)
            with patch('time.time', return_value=100):
                self.assertEqual(worker.tick()[0]['reason'], 'recovery_cooldown')
            with patch('time.time', return_value=110): result = worker.tick()[0]
            self.c.fault('stale_basis', lambda: self.c.clients['designer'].call('heartbeat_bot_runtime',
                {'bot_id': 'designer', 'fence': old_fence}))
        self.assertEqual(result['task']['status'], 'completed')
        self.assertEqual(launches, [True])
        self.assertTrue(self.c.owner.call('replay')['matched'])

    def test_corrupt_counter_cannot_reset_recovery_budget(self):
        self.enable(); self.c.task('designer'); calls = []
        with self.c.worker('designer', self.stopped_infer(calls)) as worker:
            self.observe(worker); marker = next(worker.root.rglob('auto-recovery.json'))
        for malformed in ([], {'attempts': -1, 'observed_at': 0}, {'attempts': False, 'observed_at': 0}):
            with self.subTest(malformed=malformed):
                persist(marker, malformed)
                with patch('time.time', return_value=10**10):
                    with self.c.worker('designer', self.stopped_infer(calls)) as worker:
                        self.assertEqual(worker.tick()[0]['reason'], 'recovery_journal_invalid')
        self.assertEqual(len(calls), 1)

    def test_changed_requirement_or_dependency_remains_held(self):
        import test_requirement_traceability as requirements
        self.enable(); self.call = self.c.owner.call
        reference = requirements.TraceabilityIntegrationTests.requirement(self)
        change = self.call('begin_change', {'state_id': self.c.base['id'], 'title': 'Link requirement',
            'purpose': 'Fixture requirement scope', 'write_scope': ['mechanical.txt'], 'dependencies': [], 'assignee': 'admin'})
        linked = self.call('checkpoint_change', {'change_id': change['id'], 'version': change['version'],
            'snapshot': self.c.base['snapshot'], 'summary': 'Linked fixture', 'rationale': 'Known requirement',
            'unfinished': ['Physical behavior'], 'work_status': 'paused', 'capture': {'scope': 'fixture', 'missing': []},
            'context': {**self.c.base['context'], 'requirement_refs': [reference]}})['state']
        dependency = self.c.task('control', state_id=linked['id'], requirement_refs=[reference])
        with self.c.worker('control', lambda *args: {'output': self.c.answer()}) as worker:
            self.assertEqual(worker.tick()[0]['task']['status'], 'completed')
        task = self.c.task('designer', after_tasks=[dependency['id']]); calls = []
        with self.c.worker('designer', self.stopped_infer(calls)) as worker: self.observe(worker)
        requirements.TraceabilityIntegrationTests.requirement(self, reference['revision_id'])
        with patch('time.time', return_value=10**10):
            with self.c.worker('designer', self.stopped_infer(calls)) as worker:
                self.assertEqual(worker.tick()[0]['reason'], 'stale_basis')
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.call('get_bot_task', {'task_id': task['id']})['task']['status'], 'held')

    def test_monthly_rate_limit_backoff_is_preserved(self):
        self.enable(); self.c.task('designer'); calls = []
        def infer(ctx, schema, directory):
            calls.append(ctx); marker = Path(directory)/'inference.json'
            if marker.exists() and json.loads(marker.read_text())['phase'] == 'retry_ready':
                return self.c.action('finish', self.c.answer())
            self.timeout(directory, ctx, schema, code='provider_rate_limited', retry_at=200)
            raise Fault('provider_rate_limited', 'Synthetic provider cooldown')
        with patch('time.time', return_value=100):
            with self.c.worker('designer', infer) as worker:
                self.assertEqual(self.observe(worker)['reason'], 'provider_rate_limited')
        with patch('time.time', return_value=199):
            with self.c.worker('designer', infer) as worker:
                self.assertEqual(worker.tick()[0]['reason'], 'provider_rate_limited')
                self.assertFalse(worker.restart.is_set())
        with patch('time.time', return_value=200):
            with self.c.worker('designer', infer) as worker:
                self.assertEqual(worker.tick()[0]['task']['status'], 'completed')
        self.assertEqual(len(calls), 2)

    def test_symlink_journal_is_held_without_writing_target(self):
        self.enable(); self.c.task('designer'); calls = []
        with self.c.worker('designer', self.stopped_infer(calls)) as worker:
            self.observe(worker); marker = next(worker.root.rglob('auto-recovery.json'))
        target = self.c.root/'private-target.json'; target.write_text('{"keep":"unchanged"}')
        marker.unlink(); marker.symlink_to(target)
        with patch('time.time', return_value=10**10):
            with self.c.worker('designer', self.stopped_infer(calls)) as worker:
                self.assertEqual(worker.tick()[0]['reason'], 'scope_denied')
        self.assertEqual(target.read_text(), '{"keep":"unchanged"}')
        self.assertEqual(len(calls), 1)

    def test_service_exits_after_one_recorded_restart_request(self):
        import contextlib
        import io
        from gantry.bot_worker import BotWorker, run_bot
        self.enable(); self.c.task('designer'); calls = []; ticks = []
        def factory(client, config, journal):
            worker = BotWorker(client, config, journal, self.stopped_infer(calls))
            tick = worker.tick
            def observed_tick():
                ticks.append(True)
                with patch('time.time', return_value=100 if len(ticks) < 3 else 110): return tick()
            worker.tick = observed_tick
            return worker
        with patch('gantry.bot_worker.configured_client', return_value=self.c.clients['designer']), \
                patch('gantry.bot_worker.BotWorker', side_effect=factory), contextlib.redirect_stdout(io.StringIO()):
            self.c.fault('runtime_reconnect_required', lambda: run_bot(self.c.configs['designer'],
                self.c.root/'workers', iterations=10, interval=1))
        self.assertEqual(len(ticks), 3)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.c.owner.call('get_persistent_bot', {'bot_id': 'designer'})['runtime']['presence'], 'offline')

    def test_three_attempt_policy_cannot_restart_forever(self):
        self.enable(max_attempts=3); self.c.task('designer'); calls = []; infer = self.stopped_infer(calls)
        with patch('time.time', return_value=100):
            with self.c.worker('designer', infer) as worker: self.observe(worker)
        for index in range(3):
            with patch('time.time', return_value=110 + index*10):
                with self.c.worker('designer', infer) as worker:
                    self.assertEqual(worker.tick()[0]['reason'], 'provider_timeout')
        for _ in range(2):
            with patch('time.time', return_value=1000):
                with self.c.worker('designer', infer) as worker:
                    self.assertEqual(worker.tick()[0]['reason'], 'recovery_limit')
                    self.assertFalse(worker.restart.is_set())
        self.assertEqual(len(calls), 4)

    def test_rate_limit_receipt_with_later_response_evidence_is_held(self):
        self.enable(); self.c.task('designer'); calls = []
        infer = self.stopped_infer(calls, code='provider_rate_limited', retry_at=1)
        with self.c.worker('designer', infer) as worker:
            self.observe(worker); marker = next(worker.root.rglob('model/inference.json'))
        (marker.parent/'answer.json').write_text('{"late":"answer"}')
        with patch('time.time', return_value=10**10):
            with self.c.worker('designer', infer) as worker:
                self.assertEqual(worker.tick()[0]['reason'], 'outcome_unknown')
        self.assertEqual(len(calls), 1)
