import hashlib
import json
import sys
from pathlib import Path

from gantry.bot_worker import environment_manifest
from test_crew_coordination import CrewCoordinationTests


class CrewRuntimeTests(CrewCoordinationTests):
    def enable_loop(self, name, **extra):
        self.configs[name].update(agent_loop=True, **extra)
        self.owner.call('configure_bot_runtime', {'bot_id': name, 'version': 1, 'principal_id': name,
            'enabled': True, 'environment': environment_manifest(self.configs[name])})

    def test_model_revises_after_actual_tool_failure(self):
        from gantry.project_sandbox import backend, runtime_roots
        if backend() == 'unavailable': self.skipTest('OS sandbox unavailable')
        self.enable_loop('designer', local_tools={'check': {'argv': [sys.executable, '-c',
            "from pathlib import Path; assert Path('mechanical.txt').read_text() == '2'"],
            'timeout_seconds': 10}}, tool_runtime=runtime_roots(), sandbox=backend())
        task = self.task('designer'); observed = []
        def infer(ctx, schema, directory):
            observed.append(ctx)
            kinds = [('read', {'path': 'mechanical.txt'}), ('tool', {'name': 'check'}),
                ('edit', {'path': 'mechanical.txt', 'content': '2', 'expected_hash': hashlib.sha256(b'1').hexdigest()}),
                ('tool', {'name': 'check'}), ('finish', self.answer(summary='Fixed after actual failed check'))]
            kind, args = kinds[len(observed)-1]
            return {'output': {'action': kind, 'arguments_json': json.dumps(args), 'rationale': 'Fixture choice'}}
        with self.worker('designer', infer) as worker: result = worker.tick()[0]
        self.assertEqual(result['task']['status'], 'completed')
        self.assertNotEqual(observed[2]['last_result']['exit_code'], 0)
        self.assertEqual(observed[4]['last_result']['exit_code'], 0)
        view = self.owner.call('get_bot_task', {'task_id': task['id']})
        self.assertGreaterEqual(len(view['actions']), 5)
        self.assertTrue(view['task'].get('output_state'))
        checks = sorted((a for a in view['actions'] if a['kind'] == 'tool'), key=lambda a: a['details']['round'])
        self.assertEqual(checks[0]['input_state'], self.base['id'])
        self.assertEqual(checks[1]['input_state'], view['task']['output_state'])

    def test_loop_rejects_out_of_scope_edit_and_records_failure(self):
        self.enable_loop('designer'); self.task('designer'); calls = []
        def infer(ctx, schema, directory):
            calls.append(ctx)
            kind, args = ('edit', {'path': 'control.txt', 'content': 'oops', 'expected_hash': 'absent'}) if len(calls) == 1 else ('finish', self.answer())
            return {'output': {'action': kind, 'arguments_json': json.dumps(args), 'rationale': 'Test scope'}}
        with self.worker('designer', infer) as worker: result = worker.tick()[0]
        self.assertEqual(calls[1]['last_result']['error'], 'scope_denied')
        self.assertNotIn('output_state', result['task'])

    def test_prompt_history_does_not_repeat_large_read_results(self):
        self.enable_loop('designer'); self.task('designer'); sizes = []
        def infer(ctx, schema, directory):
            sizes.append(len(json.dumps(ctx).encode()))
            if len(sizes) == 1: kind, args = 'edit', {'path': 'mechanical.txt', 'content': 'x'*32768, 'expected_hash': hashlib.sha256(b'1').hexdigest()}
            elif len(sizes) <= 22: kind, args = 'read', {'path': 'mechanical.txt'}
            else: kind, args = 'finish', self.answer()
            return {'output': {'action': kind, 'arguments_json': json.dumps(args), 'rationale': 'Bounded input test'}}
        with self.worker('designer', infer) as worker: result = worker.tick()[0]
        self.assertEqual(result['task']['status'], 'completed')
        self.assertLess(max(sizes), 160000)

    def action(self, name, arguments):
        return {'output': {'action': name, 'arguments_json': json.dumps(arguments), 'rationale': 'Recovery fixture'}}

    def test_lost_api_acknowledgement_does_not_duplicate_consultation(self):
        from gantry.model import Fault
        for committed in (False, True):
            with self.subTest(committed=committed):
                # One isolated task per uncertain transport outcome.
                if not self.configs['designer'].get('agent_loop'): self.enable_loop('designer')
                task = self.task('designer'); client = self.clients['designer']; lost = []
                class Proxy:
                    def call(_, op, args=None, key=None):
                        if op == 'ask_bot' and not lost:
                            lost.append(True)
                            if committed: client.call(op, args, key)
                            raise Fault('temporarily_unavailable', 'Lost response')
                        return client.call(op, args, key)
                def infer(ctx, schema, directory):
                    if ctx['round'] == 0: return self.action('ask', {'to_bot_id': 'control', 'question': 'Interface?', 'evidence': []})
                    return self.action('finish', self.answer(status='waiting'))
                with self.worker('designer', infer, Proxy()) as worker:
                    self.assertEqual(worker.tick()[0]['status'], 'held')
                with self.worker('designer', infer, Proxy()) as worker:
                    result = worker.recover(task['id'], 'Previous process stopped')
                self.assertEqual(result['task']['status'], 'waiting')
                view = self.owner.call('get_bot_task', {'task_id': task['id']})
                self.assertEqual(len(view['consultations']), 1)
                self.assertEqual(len([t for t in self.owner.call('list_bot_tasks', {'session_id': self.sid})['items']
                                      if t.get('reply_request_id') == view['consultations'][0]['id']]), 1)

    def test_recovery_preserves_exact_saved_provider_input(self):
        from gantry.model import Fault
        from gantry.runner import persist
        self.enable_loop('designer'); task = self.task('designer'); contexts = []
        def infer(ctx, schema, directory):
            marker = Path(directory)/'fake-provider.json'
            contexts.append(ctx)
            if marker.exists():
                saved = json.loads(marker.read_text()); self.assertEqual(ctx, saved['input']); return saved['receipt']
            receipt = self.action('finish', self.answer())
            persist(marker, {'input': ctx, 'receipt': receipt})
            raise Fault('provider_unavailable', 'Crash after provider persisted receipt')
        with self.worker('designer', infer) as worker: self.assertEqual(worker.tick()[0]['status'], 'held')
        with self.worker('designer', infer) as worker: result = worker.recover(task['id'], 'Stopped fixture')
        self.assertEqual(result['task']['status'], 'completed')
        self.assertEqual(len(contexts), 2)

    def test_discussion_invalidates_inflight_finish(self):
        self.enable_loop('designer'); task = self.task('designer'); contexts = []
        def infer(ctx, schema, directory):
            contexts.append(ctx)
            if len(contexts) == 1:
                self.clients['control'].call('send_bot_message', {'task_id': task['id'], 'from_bot_id': 'control',
                    'kind': 'report', 'body': 'Changed evidence', 'blocking': False, 'evidence': []})
            return self.action('finish', self.answer(summary='Refreshed' if len(contexts) > 1 else 'Stale'))
        with self.worker('designer', infer) as worker: result = worker.tick()[0]
        self.assertEqual(result['task']['status'], 'completed')
        self.assertEqual(len(contexts), 2)
        self.assertEqual(len(contexts[1]['messages']), 1)
        self.assertEqual(result['task']['reports'][-1]['report']['summary'], 'Refreshed')

    def test_model_receives_authoritative_assignment_schema_and_error_path(self):
        self.enable_loop('lead'); self.task(); contexts = []
        def infer(ctx, schema, directory):
            contexts.append(ctx)
            self.assertEqual(ctx['action_schemas']['finish'], __import__('gantry.bot_development', fromlist=['BOT_ANSWER']).BOT_ANSWER)
            if len(contexts) == 1: return self.action('finish', self.answer(status='waiting', assignments=[self.assignment('designer', kind='invented')]))
            return self.action('finish', self.answer())
        with self.worker('lead', infer) as worker: result = worker.tick()[0]
        self.assertEqual(result['task']['status'], 'completed')
        self.assertEqual(contexts[1]['last_result']['details']['path'], 'arguments.assignments[0].kind')

    def test_manager_stop_is_fenced_against_new_discussion(self):
        self.enable_loop('lead'); task = self.task(); child = self.task('designer'); client = self.clients['lead']; injected = []
        class Proxy:
            def call(_, op, args=None, key=None):
                if op in {'cancel_bot_task', 'stop_bot_task'} and not injected:
                    injected.append(True)
                    self.clients['control'].call('send_bot_message', {'task_id': task['id'], 'from_bot_id': 'control',
                        'kind': 'report', 'body': 'New evidence before stopping', 'blocking': False, 'evidence': []})
                return client.call(op, args, key)
        def infer(ctx, schema, directory):
            return self.action('stop', {'task_id': child['id'], 'reason': 'Old manager decision'})
        with self.worker('lead', infer, Proxy()) as worker: result = worker.tick()[0]
        self.assertEqual(result['status'], 'held')
        self.assertEqual(self.owner.call('get_bot_task', {'task_id': child['id']})['task']['status'], 'pending')

    def test_unchanged_finish_does_not_duplicate_intermediate_checkpoint(self):
        self.enable_loop('designer'); task = self.task('designer'); calls = []
        def infer(ctx, schema, directory):
            calls.append(ctx)
            if len(calls) == 1: return self.action('edit', {'path': 'mechanical.txt', 'content': '2', 'expected_hash': hashlib.sha256(b'1').hexdigest()})
            return self.action('finish', self.answer())
        with self.worker('designer', infer) as worker: result = worker.tick()[0]
        view = self.owner.call('get_bot_task', {'task_id': task['id']})
        self.assertEqual(result['task']['status'], 'completed')
        self.assertEqual(len(view['own_change']['checkpoints']), 1)

    def test_consultation_reply_reenters_requester_reasoning_and_memory(self):
        self.enable_loop('designer'); self.enable_loop('control'); task = self.task('designer'); seen = []
        def requester(ctx, schema, directory):
            seen.append(ctx)
            if not ctx['consultations']:
                return self.action('ask', {'to_bot_id': 'control', 'question': 'Compatible?', 'evidence': [self.base['id']]})
            question = ctx['consultations'][0]
            if question['status'] == 'open': return self.action('finish', self.answer(status='waiting'))
            if question['status'] == 'answered':
                return self.action('resolve', {'message_id': question['id'], 'reason': 'Read peer limitations', 'evidence': [question['answer_id']]})
            return self.action('finish', self.answer(summary='Continued after peer answer; physical behavior unverified'))
        with self.worker('designer', requester) as worker: self.assertEqual(worker.tick()[0]['task']['status'], 'waiting')
        with self.worker('control', lambda c,s,d: self.action('finish', self.answer(summary='Compatible at this saved interface only'))) as worker:
            self.assertEqual(worker.tick()[0]['task']['status'], 'completed')
        with self.worker('designer', requester) as worker: result = worker.tick()[0]
        self.assertEqual(result['task']['status'], 'completed')
        self.assertEqual(result['task']['attempt'], 2)
        memories = self.clients['designer'].call('list_persistent_memories', {'bot_id': 'designer'})['items']
        self.assertTrue(any('Continued after peer answer' in m['observation'] for m in memories))
        self.assertTrue(self.owner.call('replay')['matched'])
