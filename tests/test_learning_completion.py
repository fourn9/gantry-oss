"""Experience receipts travel with reports; real Core, explicitly fixture inference."""
import json

from gantry.bot_worker import environment_manifest
from test_bot_learning import BotLearningTests


class LearningCompletionTests(BotLearningTests):
    def link(self, memory, action):
        return {'memory_id': memory['id'], 'action_ids': [action['id']],
                'change': 'Read the fixed input before changing the route',
                'condition_check': 'Reading alone does not verify physical clearance'}

    def report(self, uses):
        return {k: v for k, v in self.answer(experience_uses=uses).items() if k != 'edits'}

    def prepared(self, worker, task):
        ref = self.claimed(worker, task); memory = self.seed(ref); self.plan(ref)
        action = self.clients['designer'].call('record_bot_action', {**ref, 'kind': 'read',
            'details': {'path': 'mechanical.txt', 'result': {'content': '1'}}})
        return ref, self.link(memory, action)

    def uses(self, task):
        return self.owner.call('get_bot_records', {'task_id': task['id'], 'kind': 'learning_uses'})['items']

    def test_report_atomically_links_experience_and_reflection_with_idempotent_retry(self):
        task = self.task('designer', title='Check clamp')
        with self.worker('designer') as worker:
            ref, use = self.prepared(worker, task)
            args = {**ref, 'report': self.report([use])}
            first = self.clients['designer'].call('finish_bot_task', args, 'finish-with-use')
            self.assertEqual(first, self.clients['designer'].call('finish_bot_task', args, 'finish-with-use'))
            self.assertEqual(first['task']['status'], 'completed')
            self.assertFalse(first['formal_adoption'])
            links = self.uses(task); self.assertEqual(len(links), 1)
            self.assertEqual(links[0]['action_ids'], use['action_ids'])
            self.assertEqual(links[0]['evidence_status'], 'reported_link_to_recorded_actions')
            pending = self.clients['designer'].call('list_bot_reflections', {'bot_id': 'designer'})['items'][0]
            packet = self.clients['designer'].call('get_bot_reflection', {'reflection_id': pending['id']})
            self.assertEqual(packet['experience_actions'], links)
        self.assertTrue(self.owner.call('replay')['matched'])

    def test_bad_second_link_rolls_back_first_link_and_completion(self):
        task = self.task('designer', title='Check clamp')
        with self.worker('designer') as worker:
            ref, use = self.prepared(worker, task)
            second = self.seed(ref, 'Second conditional clamp procedure'); self.plan(ref)
            for bad in ({**use, 'memory_id': 'invented'},
                        {**use, 'memory_id': second['id'], 'action_ids': ['invented']}):
                self.fault('invalid_input', lambda: self.clients['designer'].call('finish_bot_task',
                    {**ref, 'report': self.report([use, bad])}))
                self.assertEqual(self.uses(task), [])
                saved = self.owner.call('get_bot_task', {'task_id': task['id']})['task']
                self.assertEqual(saved['status'], 'running'); self.assertEqual(saved['reports'], [])
            invalid_report = {**self.report([use]), 'status': 'waiting'}
            self.fault('invalid_input', lambda: self.clients['designer'].call('finish_bot_task',
                {**ref, 'report': invalid_report}))
            self.assertEqual(self.uses(task), [])
            self.clients['designer'].call('finish_bot_task', {**ref, 'report': self.report([use])})
        self.assertTrue(self.owner.call('replay')['matched'])

    def test_foreign_action_and_stale_fence_cannot_be_bundled(self):
        other = self.task('control')
        with self.worker('control') as worker:
            ref = self.claimed(worker, other, 'control')
            foreign = self.clients['control'].call('record_bot_action', {**ref, 'kind': 'read', 'details': {}})
        task = self.task('designer', title='Check clamp')
        with self.worker('designer') as worker:
            ref, use = self.prepared(worker, task)
            self.fault('invalid_input', lambda: self.clients['designer'].call('finish_bot_task',
                {**ref, 'report': self.report([{**use, 'action_ids': [foreign['id']]}])}))
            self.fault('stale_basis', lambda: self.clients['designer'].call('finish_bot_task',
                {**ref, 'fence': 'obsolete', 'report': self.report([use])}))
            self.assertEqual(self.uses(task), [])

    def test_worker_needs_no_bookkeeping_turn_and_recovers_lost_finish_reply(self):
        import hashlib
        first = self.task('designer', title='Check clamp')
        with self.worker('designer') as worker:
            ref = self.claimed(worker, first); memory = self.seed(ref)
            current = self.owner.call('get_bot_task', {'task_id': first['id']})['task']
            self.owner.call('cancel_bot_task', {'task_id': first['id'], 'version': current['version'], 'reason': 'Seed only'})
        self.configs['designer'].update(experience_learning=True, agent_loop=True)
        self.owner.call('configure_bot_runtime', {'bot_id': 'designer', 'version': 1, 'principal_id': 'designer',
            'enabled': True, 'environment': environment_manifest(self.configs['designer'])})
        task = self.task('designer', title='Check clamp'); calls = []; observed = []
        ordinary = self.learning_infer([])
        def infer(ctx, schema, directory):
            calls.append(ctx.get('operation', 'action'))
            if ctx.get('operation'):
                if ctx['operation'] == 'reflect_on_experience':
                    observed.extend(ctx['packet']['experience_actions'])
                return ordinary(ctx, schema, directory)
            if ctx['round'] == 0: action, args = 'edit', {'path': 'mechanical.txt', 'content': '2',
                'expected_hash': hashlib.sha256(b'1').hexdigest()}
            else:
                self.assertEqual(ctx['round'], 1, 'No extra model turn for receipt bookkeeping')
                recorded = next(a for a in ctx['actions'] if a['kind'] == 'edit')
                action, args = 'finish', self.answer(experience_uses=[self.link(memory, recorded)])
            return {'output': {'action': action, 'arguments_json': json.dumps(args), 'rationale': 'Fixture choice'}}
        base = self.clients['designer']
        class LostReply:
            lost = False
            def call(proxy, name, args=None, key=None):
                result = base.call(name, args, key)
                if name == 'finish_bot_task' and not proxy.lost:
                    proxy.lost = True; raise OSError('Lost response after atomic commit')
                return result
        with self.worker('designer', infer, LostReply()) as worker:
            self.assertEqual(worker.tick()[0]['status'], 'held')
        with self.worker('designer', infer) as worker:
            self.assertEqual(worker.recover(task['id'], 'Previous fixture stopped')['task']['status'], 'completed')
            worker.tick()
        self.assertEqual(calls, ['plan_from_experience', 'action', 'action', 'reflect_on_experience'])
        self.assertEqual(len(self.uses(task)), 1); self.assertEqual(len(observed), 1)
        self.assertTrue(self.owner.call('get_bot_task', {'task_id': task['id']})['task']['output_state'])
        self.assertTrue(self.owner.call('replay')['matched'])

    def test_bundled_links_remain_private_in_reports_and_action_views(self):
        task = self.task('designer', title='Check clamp')
        with self.worker('designer') as worker:
            ref, use = self.prepared(worker, task)
            use['change'] = 'Private remembered routing strategy'
            report = self.report([use])
            self.clients['designer'].call('record_bot_action', {**ref, 'kind': 'finish',
                'details': {'arguments': json.dumps({**report, 'edits': []}), 'result': {'report': report}}})
            self.clients['designer'].call('finish_bot_task', {**ref, 'report': report})
        self.assertEqual(self.uses(task)[0]['change'], use['change'])
        self.fault('unauthorized', lambda: self.clients['control'].call('get_bot_records',
            {'task_id': task['id'], 'kind': 'learning_uses'}))
        for operation, args in [('get_bot_task', {'task_id': task['id']}),
            ('list_bot_tasks', {'session_id': self.sid}),
            ('get_bot_records', {'task_id': task['id'], 'kind': 'actions'})]:
            exposed = json.dumps(self.clients['control'].call(operation, args))
            self.assertNotIn(use['change'], exposed); self.assertNotIn(use['memory_id'], exposed)

    def test_all_bundled_links_reach_reflection_not_only_recent_twenty(self):
        task = self.task('designer', title='Check clamp')
        with self.worker('designer') as worker:
            ref = self.claimed(worker, task)
            memories = [self.seed(ref, 'Clamp procedure ' + str(i)) for i in range(40)]
            packet = self.clients['designer'].call('prepare_bot_learning', {**ref, 'limit': 40})
            self.clients['designer'].call('submit_bot_learning_plan', {**ref, 'plan_id': packet['id'],
                'output': self.plan_output(packet)})
            action = self.clients['designer'].call('record_bot_action', {**ref, 'kind': 'read', 'details': {}})
            self.clients['designer'].call('finish_bot_task', {**ref,
                'report': self.report([self.link(m, action) for m in memories])})
            item = self.clients['designer'].call('list_bot_reflections', {'bot_id': 'designer'})['items'][0]
            reflection = self.clients['designer'].call('get_bot_reflection', {'reflection_id': item['id']})
            self.assertEqual({u['memory_id'] for u in reflection['experience_actions']}, {m['id'] for m in memories})

    def test_empty_and_null_receipts_do_not_claim_use(self):
        for value in ([], None):
            task = self.task('designer')
            with self.worker('designer') as worker:
                ref = self.claimed(worker, task)
                result = self.clients['designer'].call('finish_bot_task', {**ref, 'report': self.report(value)})
                self.assertEqual(result['task']['status'], 'completed')
                self.assertEqual(self.uses(task), [])
