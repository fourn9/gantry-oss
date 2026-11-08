"""Optional learning claims must not look like required task prerequisites."""
import json
import unittest

from gantry.bot_execution import _input
from gantry.bot_worker import environment_manifest
from gantry.model import Fault
import test_bot_learning as fixtures


class OptionalLearningUseGuidanceTests(unittest.TestCase):
    def setUp(self):
        self.c = fixtures.BotLearningTests()
        self.c.setUp()
        self.addCleanup(self.c.tearDown)

    def assert_optional_remedy(self, error):
        self.assertEqual(error.code, 'invalid_input')
        message = str(error).lower()
        for term in ('optional', 'experience_use', 'experience_uses', 'omit', 'finish', 'attempt'):
            self.assertIn(term, message)
        self.assertLess(len(message), 700)

    def no_completed_plan(self, pending=False):
        c = self.c; task = c.task('designer', title='Inspect saved interface')
        with c.worker('designer') as worker:
            ref = c.claimed(worker, task); memory = c.seed(ref)
            action = c.clients['designer'].call('record_bot_action', {
                **ref, 'kind': 'read', 'details': {'path': 'mechanical.txt'}})
            if pending:
                plan = c.clients['designer'].call('prepare_bot_learning', ref)
                self.assertEqual(plan['status'], 'pending')
            use = {'memory_id': memory['id'], 'action_ids': [action['id']],
                'change': 'Read before edit', 'condition_check': 'The saved interface still needs verification'}
            with self.assertRaises(Fault) as caught:
                c.clients['designer'].call('record_bot_learning_use', {**ref, **use})
            self.assert_optional_remedy(caught.exception)
            report = {k: v for k, v in c.answer().items() if k != 'edits'}
            with self.assertRaises(Fault) as caught:
                c.clients['designer'].call('finish_bot_task', {**ref,
                    'report': {**report, 'experience_uses': [use]}})
            self.assert_optional_remedy(caught.exception)
            view = c.clients['designer'].call('get_bot_task', {'task_id': task['id']})
            self.assertFalse(view['task']['reports'], 'Rejected claims must not silently complete work')
            self.assertFalse(view.get('learning_plan'), 'Do not invent a completed learning plan')
            self.assertFalse(c.clients['designer'].call('get_bot_records', {
                'task_id': task['id'], 'kind': 'learning_uses'})['items'])
            if pending:
                report['experience_uses'] = []
            finished = c.clients['designer'].call('finish_bot_task', {**ref, 'report': report})
            self.assertEqual(finished['task']['status'], 'completed')
            self.assertFalse(c.clients['designer'].call('get_bot_records', {
                'task_id': task['id'], 'kind': 'learning_uses'})['items'])
        self.assertTrue(c.owner.call('replay')['matched'])

    def test_no_plan_error_explains_omission_then_ordinary_finish_succeeds(self):
        self.no_completed_plan()

    def test_pending_plan_does_not_enable_claims_but_empty_annotation_can_finish(self):
        self.no_completed_plan(pending=True)

    def test_onboarding_explains_plan_scope_and_optional_finish_annotation(self):
        c = self.c; task = c.task('designer')
        workspace = c.root/'input-workspace'; workspace.mkdir()
        for name in ('mechanical.txt', 'control.txt'):
            (workspace/name).write_text('1')
        context = c.clients['designer'].call('get_bot_task', {'task_id': task['id']})
        instruction = _input(context, workspace)['instruction'].lower()
        for term in ('experience_use', 'experience_uses', 'optional', 'learning_plan', 'completed', 'attempt', 'omit'):
            self.assertIn(term, instruction)

    def test_completed_plan_still_rejects_invalid_links_and_accepts_actual_use(self):
        c = self.c; task = c.task('designer', title='Check clamp')
        with c.worker('designer') as worker:
            ref = c.claimed(worker, task)
            memory = c.seed(ref)
            rejected = c.seed(ref, 'Different assembly evidence; do not use')
            packet = c.clients['designer'].call('prepare_bot_learning', ref)
            plan = c.clients['designer'].call('submit_bot_learning_plan', {**ref, 'plan_id': packet['id'],
                'output': c.plan_output(packet, [{'memory_id': item['id'],
                    'use': 'recheck' if item['id'] == memory['id'] else 'reject',
                    'reason': 'Check applicability to this task'} for item in packet['recall']['items']])})
            self.assertEqual(plan['status'], 'completed')
            action = c.clients['designer'].call('record_bot_action', {
                **ref, 'kind': 'read', 'details': {'path': 'mechanical.txt'}})
            use = {'memory_id': memory['id'], 'action_ids': [action['id']],
                'change': 'Read before edit', 'condition_check': 'Saved interface inspected; physical behavior unverified'}
            for invalid in ({**use, 'memory_id': rejected['id']}, {**use, 'action_ids': ['invented-action']}):
                with self.assertRaises(Fault) as caught:
                    c.clients['designer'].call('record_bot_learning_use', {**ref, **invalid})
                self.assertEqual(caught.exception.code, 'invalid_input')
            report = {k: v for k, v in c.answer().items() if k != 'edits'}
            finished = c.clients['designer'].call('finish_bot_task', {
                **ref, 'report': {**report, 'experience_uses': [use]}})
            self.assertEqual(finished['task']['status'], 'completed')
            uses = c.clients['designer'].call('get_bot_records', {
                'task_id': task['id'], 'kind': 'learning_uses'})['items']
            self.assertEqual(len(uses), 1)
            self.assertEqual(uses[0]['plan_id'], plan['id'])
            self.assertEqual(uses[0]['memory_id'], memory['id'])
        self.assertTrue(c.owner.call('replay')['matched'])

    def test_action_loop_can_correct_optional_claim_and_complete_without_a_plan(self):
        c = self.c; source = c.task('designer')
        with c.worker('designer') as worker:
            ref = c.claimed(worker, source); memory = c.seed(ref)
            c.clients['designer'].call('finish_bot_task', {**ref,
                'report': {k: v for k, v in c.answer().items() if k != 'edits'}})
        c.configs['designer'].update(agent_loop=True, experience_learning=False)
        runtime = c.owner.call('get_persistent_bot', {'bot_id': 'designer'})['runtime']
        c.owner.call('configure_bot_runtime', {'bot_id': 'designer', 'version': runtime['version'],
            'principal_id': 'designer', 'enabled': True,
            'environment': environment_manifest(c.configs['designer'])})
        task = c.task('designer'); contexts = []

        def infer(context, schema, directory):
            contexts.append(context)
            if len(contexts) == 1:
                action, args = 'read', {'path': 'mechanical.txt'}
            else:
                action, args = 'finish', c.answer()
                if len(contexts) == 2:
                    actual = next(a for a in context['actions'] if a['kind'] == 'read')
                    args['experience_uses'] = [{'memory_id': memory['id'], 'action_ids': [actual['id']],
                        'change': 'Inspect before editing', 'condition_check': 'Needs verification'}]
                else:
                    self.assertEqual(len(contexts), 3)
                    self.assertEqual(context['last_result']['error'], 'invalid_input')
                    self.assertIn('optional', context['last_result']['message'].lower())
                    self.assertIn('omit finish.experience_uses', context['last_result']['message'])
            return {'output': {'action': action, 'arguments_json': json.dumps(args),
                'rationale': 'Deterministic protocol recovery fixture'}}

        with c.worker('designer', infer) as worker:
            result = worker.tick()[0]
        self.assertEqual(result['task']['status'], 'completed')
        self.assertEqual(len(contexts), 3)
        view = c.clients['designer'].call('get_bot_task', {'task_id': task['id']})
        self.assertFalse(view.get('learning_plan'))
        self.assertFalse(c.clients['designer'].call('get_bot_records', {
            'task_id': task['id'], 'kind': 'learning_uses'})['items'])
        self.assertTrue(any(a['kind'] == 'finish' and a['details'].get('stage') == 'core_validation'
            and a['details']['result']['error'] == 'invalid_input' for a in view['actions']))
