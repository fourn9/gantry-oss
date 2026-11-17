"""Durable responsibilities through real Core and worker paths; fixture decisions."""
import unittest

import test_bot_continuity as continuity
import test_bot_development as development


class BotCommitmentTests(unittest.TestCase):
    setUp = development.BotDevelopmentTests.setUp
    tearDown = development.BotDevelopmentTests.tearDown
    scope = development.BotDevelopmentTests.scope
    artifact = development.BotDevelopmentTests.artifact
    fault = development.BotDevelopmentTests.fault
    assignment = development.BotDevelopmentTests.assignment
    task = development.BotDevelopmentTests.task
    worker = development.BotDevelopmentTests.worker
    answer = development.BotDevelopmentTests.answer
    infer = development.BotDevelopmentTests.infer
    claimed = continuity.BotContinuityTests.claimed
    permit = continuity.BotContinuityTests.permit
    pump = continuity.BotContinuityTests.pump
    enable_continuity = continuity.BotContinuityTests.enable_continuity

    def create(self, ref, **extra):
        return self.clients['designer'].call('create_bot_commitment', {**ref,
            'summary': 'Own the routing clearance follow-through',
            'completion': ['Record the resolved clearance or remaining constraint'],
            'priority': 'high', 'priority_reason': 'Routing depends on this answer',
            'due_at': None, 'task_ids': [ref['task_id']], **extra})

    def finish(self, ref, **extra):
        return self.clients['designer'].call('finish_bot_task', {**ref,
            'report': {k: v for k, v in self.answer(**extra).items() if k != 'edits'}})

    def update(self, ref, commitment, **extra):
        return self.clients['designer'].call('update_bot_commitment', {**ref,
            'commitment_id': commitment['id'], 'version': commitment['version'],
            'status': 'waiting', 'task_ids': commitment['task_ids'], 'due_at': None,
            'reason': 'Reassessed the recorded task outcome', 'evidence': [self.base['id']], **extra})

    def test_task_completion_preserves_commitment_until_explicit_reconciliation(self):
        self.enable_continuity(); self.permit()
        task = self.task('designer')
        with self.worker('designer') as worker:
            ref = self.claimed(worker, task)
            commitment = self.create(ref)
            self.fault('dependency_pending', lambda: self.update(ref, commitment, status='completed'))
            self.finish(ref)
            stored = self.owner.call('get_bot_commitment', {'commitment_id': commitment['id']})
            self.assertEqual(stored['status'], 'open')
            wake = self.pump(worker)['items'][0]
            self.assertEqual(wake['status'], 'queued')
            queued = self.owner.call('get_bot_task', {'task_id': wake['task_id']})
            self.assertEqual(queued['working_state']['commitments']['items'][0]['id'], commitment['id'])
            ref = self.claimed(worker, queued['task'])
            done = self.update(ref, commitment, status='completed', evidence=[task['id']])
            self.assertEqual(done['status'], 'completed')
            self.assertFalse(done['formal_adoption'])
            self.finish(ref)
            self.assertEqual(self.pump(worker)['items'][0]['status'], 'idle')
        self.assertTrue(self.owner.call('replay')['matched'])

    def test_commitment_read_and_link_authority(self):
        own = self.task('designer'); foreign = self.task('control')
        with self.worker('designer') as worker:
            ref = self.claimed(worker, own)
            self.fault('unauthorized', lambda: self.create(ref, task_ids=[foreign['id']]))
            commitment = self.create(ref)
            self.fault('unauthorized', lambda: self.clients['control'].call('get_bot_commitment',
                {'commitment_id': commitment['id']}))
            self.fault('unauthorized', lambda: self.clients['control'].call('list_bot_commitments',
                {'session_id': self.sid, 'bot_id': 'designer'}))
            self.fault('invalid_input', lambda: self.update(ref, commitment, task_ids=[]))
            self.fault('invalid_input', lambda: self.update(ref, commitment, evidence=['invented']))
            changed = self.update(ref, commitment)
            self.assertEqual(changed['version'], 2)
            self.fault('stale_basis', lambda: self.update(ref, commitment))
            first = self.owner.call('get_bot_commitment', {'commitment_id': commitment['id'], 'limit': 1})
            second = self.owner.call('get_bot_commitment', {'commitment_id': commitment['id'],
                'limit': 1, 'after': first['next_cursor']})
            self.assertEqual(first['history'][0]['kind'], 'created')
            self.assertEqual(second['history'][0]['kind'], 'reconciled')
            self.fault('invalid_input', lambda: self.owner.call('get_bot_commitment',
                {'commitment_id': commitment['id'], 'after': 'not-a-history-cursor'}))

    def test_due_resumes_after_restart_once_and_unrelated_reports_do_not_wake(self):
        self.enable_continuity(); self.permit()
        now = [self.service.clock()]; self.service.clock = lambda: now[0]
        task = self.task('designer')
        with self.worker('designer') as worker:
            ref = self.claimed(worker, task)
            self.create(ref, due_at=now[0] + 1000)
            self.finish(ref)
        calls = []
        def infer(ctx, schema, directory):
            calls.append(ctx)
            return {'output': self.answer(), 'provider': {'kind': 'fixture'}}
        with self.worker('designer', infer) as worker:
            self.assertEqual(len(worker.tick()), 1)
            self.assertEqual(worker.tick(), [])
        unrelated = self.task('control')
        with self.worker('control') as worker: worker.tick()
        with self.worker('designer', infer) as worker:
            self.assertEqual(worker.tick(), [])
            now[0] += 1000
            self.assertEqual(len(worker.tick()), 1)
        with self.worker('designer', infer) as worker: self.assertEqual(worker.tick(), [])
        self.assertEqual(len(calls), 2)
        self.assertNotIn(unrelated['id'], str(calls[-1]['working_state']['commitments']))

    def test_reassessment_after_linked_failure_preserves_reported_outcome(self):
        self.enable_continuity(); self.permit()
        task = self.task('designer')
        with self.worker('designer') as worker:
            ref = self.claimed(worker, task); commitment = self.create(ref)
            self.finish(ref, status='failed')
            wake = self.pump(worker)['items'][0]
            context = self.owner.call('get_bot_task', {'task_id': wake['task_id']})
            self.assertIn('commitment_changed', context['task']['continuation_reason'])
            item = context['working_state']['commitments']['items'][0]
            self.assertEqual(item['linked_tasks'][0]['status'], 'failed')
            self.assertEqual(item['status'], 'open')
            self.permit(version=1, enabled=False)
            self.fault('stale_basis', lambda: self.claimed(worker, context['task']))
        self.assertEqual(self.owner.call('get_bot_commitment', {'commitment_id': commitment['id']})['status'], 'open')

    def test_explicit_reconciliation_waits_without_waking_itself(self):
        self.enable_continuity(); self.permit()
        task = self.task('designer')
        with self.worker('designer') as worker:
            ref = self.claimed(worker, task); commitment = self.create(ref)
            self.finish(ref)
            wake = self.pump(worker)['items'][0]
            queued = self.owner.call('get_bot_task', {'task_id': wake['task_id']})['task']
            ref = self.claimed(worker, queued)
            # Retire completed work explicitly; an ongoing responsibility has no
            # lifetime cap imposed by the bounded active task-link list.
            changed = self.update(ref, commitment, task_ids=[])
            self.assertEqual(changed['task_ids'], [])
            self.finish(ref)
            self.assertEqual(self.pump(worker)['items'][0]['status'], 'idle')
            history = self.owner.call('get_bot_commitment', {'commitment_id': commitment['id']})['history']
            self.assertTrue(any(task['id'] in h['task_ids'] for h in history))

    def test_manager_can_link_delegated_work_but_specialist_cannot_take_peers(self):
        task = self.task('mechanical'); child = self.task('designer'); peer = self.task('control')
        c = self.clients['mechanical']
        with self.worker('mechanical') as worker:
            ref = self.claimed(worker, task, 'mechanical')
            args = {**ref, 'summary': 'Own mechanical delivery', 'completion': ['Check specialist outcome'],
                'priority': 'normal', 'priority_reason': 'Responsible manager', 'due_at': None,
                'task_ids': [child['id']]}
            created = c.call('create_bot_commitment', args, 'commitment-once')
            self.assertEqual(created, c.call('create_bot_commitment', args, 'commitment-once'))
            self.fault('unauthorized', lambda: c.call('create_bot_commitment', {**args, 'task_ids': [peer['id']]}))

    def test_context_prioritizes_open_responsibilities_and_list_pages_history(self):
        task = self.task('designer')
        with self.worker('designer') as worker:
            ref = self.claimed(worker, task)
            closed = self.create(ref, task_ids=[])
            self.update(ref, closed, status='completed')
            opened = self.create(ref, task_ids=[])
            ctx = self.clients['designer'].call('get_bot_working_state', {'session_id': self.sid, 'bot_id': 'designer'})
            self.assertEqual([v['id'] for v in ctx['commitments']['items']], [opened['id']])
            page = self.clients['designer'].call('list_bot_commitments', {'session_id': self.sid,
                'bot_id': 'designer', 'limit': 1})
            rest = self.clients['designer'].call('list_bot_commitments', {'session_id': self.sid,
                'bot_id': 'designer', 'limit': 1, 'after': page['next_cursor']})
            self.assertEqual({v['id'] for v in page['items'] + rest['items']}, {closed['id'], opened['id']})

    def test_owner_preference_add_edit_disable_wakes_once_without_working_note(self):
        self.enable_continuity(); self.permit()
        args = {'session_id': self.sid, 'bot_id': 'designer', 'key': 'reporting',
            'version': 0, 'scope': 'project', 'task_id': None, 'text': 'Lead with remaining uncertainty',
            'reason': 'Owner reporting preference', 'enabled': True}
        calls = []
        def infer(ctx, schema, directory):
            calls.append(ctx)
            return {'output': self.answer(), 'provider': {'kind': 'fixture'}}
        with self.worker('designer', infer) as worker:
            self.assertEqual(worker.tick(), [])
            self.owner.call('set_bot_preference', args)
            self.assertEqual(len(worker.tick()), 1)
            self.assertEqual(worker.tick(), [])
            self.assertEqual(calls[-1]['task']['continuation_reason'], ['preference_changed'])
            self.owner.call('set_bot_preference', {**args, 'version': 1, 'text': 'Lead with the evidence'})
            self.assertEqual(len(worker.tick()), 1)
            self.assertEqual(worker.tick(), [])
            self.owner.call('set_bot_preference', {**args, 'version': 2, 'enabled': False})
            self.assertEqual(len(worker.tick()), 1)
            self.assertEqual(calls[-1]['personal_preferences']['items'], [])
        with self.worker('designer', infer) as worker: self.assertEqual(worker.tick(), [])
        self.assertEqual(len(calls), 3)

    def test_new_assignment_can_reactivate_a_reconciled_responsibility(self):
        self.enable_continuity(); self.permit()
        source = self.task('designer')
        with self.worker('designer') as worker:
            ref = self.claimed(worker, source); commitment = self.create(ref, task_ids=[])
            self.finish(ref)
            wake = self.pump(worker)['items'][0]
            queued = self.owner.call('get_bot_task', {'task_id': wake['task_id']})['task']
            ref = self.claimed(worker, queued)
            commitment = self.update(ref, commitment)
            self.finish(ref)
            self.assertEqual(self.pump(worker)['items'][0]['status'], 'idle')
            assigned = self.task('designer'); ref = self.claimed(worker, assigned)
            self.update(ref, commitment, status='open', reason='New assigned facts require attention')
            self.finish(ref)
            self.assertEqual(self.pump(worker)['items'][0]['status'], 'queued')

    def test_handoff_tracks_successor_outcome_and_cannot_close_unfinished_work(self):
        self.permit(); source = self.task('designer')
        with self.worker('designer') as designer, self.worker('mechanical') as manager:
            ref = self.claimed(designer, source); commitment = self.create(ref)
            running = self.owner.call('get_bot_task', {'task_id': source['id']})['task']
            handoff = self.owner.call('request_bot_handoff', {'task_id': source['id'],
                'version': running['version'], 'to_bot_id': 'mechanical', 'reason': 'Manager continues work'})
            self.assertEqual(self.pump(designer)['items'][0]['status'], 'active')
            ready = self.owner.call('acknowledge_bot_handoff', {'handoff_id': handoff['id'],
                'version': handoff['version'], 'confirm_stopped': 'Fixture process stopped',
                'summary': 'Saved work is intact', 'unfinished': ['Manager must finish']})
            accepted = self.clients['mechanical'].call('accept_bot_handoff', {'handoff_id': ready['id'],
                'version': ready['version'], 'runtime_fence': manager.runtime['fence']})
            wake = self.pump(designer)['items'][0]
            queued = self.owner.call('get_bot_task', {'task_id': wake['task_id']})['task']
            ref = self.claimed(designer, queued)
            self.fault('dependency_pending', lambda: self.update(ref, commitment, status='completed'))
            successor = self.owner.call('get_bot_task', {'task_id': accepted['successor_task_id']})['task']
            mref = self.claimed(manager, successor, 'mechanical')
            self.clients['mechanical'].call('finish_bot_task', {**mref,
                'report': {k: v for k, v in self.answer().items() if k != 'edits'}})
            done = self.update(ref, commitment, status='completed', evidence=[successor['id']])
            self.assertEqual(done['linked_tasks'][0]['current_task_id'], successor['id'])
            self.assertEqual(done['linked_tasks'][0]['status'], 'completed')
            self.finish(ref)
            self.assertEqual(self.pump(designer)['items'][0]['status'], 'idle')

    def test_new_commitment_during_learning_inference_replans_saved_answer(self):
        from gantry.bot_learning_runtime import plan_task
        task = self.task('designer', title='Check clamp clearance'); calls = []; commitments = []
        with self.worker('designer') as worker:
            ref = self.claimed(worker, task)
            continuity.BotContinuityTests.seed(self, ref)
            context = self.clients['designer'].call('get_bot_task', {'task_id': task['id']})
            def infer(ctx, schema, directory):
                calls.append(ctx)
                if len(calls) == 1: commitments.append(self.create(ref))
                return {'output': continuity.BotContinuityTests.plan_output(self, ctx['packet']),
                    'provider': {'kind': 'fixture'}}
            result = plan_task(self.clients['designer'], ref, context, infer, self.root/'learning')
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0]['packet']['commitment_context']['items'], [])
            self.assertEqual(result['commitment_context']['items'][0]['id'], commitments[0]['id'])
        self.assertTrue(self.owner.call('replay')['matched'])

    def test_iterative_worker_pages_commitments_and_private_history(self):
        import json
        self.enable_continuity(agent_loop=True)
        source = self.task('designer')
        with self.worker('designer') as worker:
            ref = self.claimed(worker, source)
            one = self.create(ref, task_ids=[], summary='Private routing responsibility')
            two = self.create(ref, task_ids=[], summary='Private acceptance responsibility')
            self.finish(ref)
        task = self.task('designer'); seen = []
        def infer(ctx, schema, directory):
            if ctx['round'] == 0:
                action, args = 'commitments', {'active_only': True, 'limit': 1}
            elif ctx['round'] == 1:
                seen.extend(ctx['last_result']['items'])
                action, args = 'commitments', {'active_only': True, 'limit': 1,
                    'after': ctx['last_result']['next_cursor']}
            elif ctx['round'] == 2:
                seen.extend(ctx['last_result']['items'])
                action, args = 'commitment', {'commitment_id': seen[-1]['id'], 'limit': 1}
            else:
                self.assertEqual(ctx['last_result']['history'][0]['kind'], 'created')
                action, args = 'finish', self.answer()
            return {'output': {'action': action, 'arguments_json': json.dumps(args),
                'rationale': 'Fixture reads actual owned records'}, 'provider': {'kind': 'fixture'}}
        with self.worker('designer', infer) as worker:
            result = worker.tick()
            self.assertEqual(result[0]['task']['status'], 'completed', result)
        self.assertEqual({v['id'] for v in seen}, {one['id'], two['id']})
        peer = self.clients['control'].call('get_bot_records', {'task_id': task['id'], 'kind': 'actions'})
        self.assertNotIn('Private routing responsibility', json.dumps(peer))
        self.assertNotIn('Private acceptance responsibility', json.dumps(peer))



    def test_bot_reprioritizes_responsibility_with_reason_and_history(self):
        task=self.task('designer')
        with self.worker('designer') as worker:
            ref=self.claimed(worker,task); responsibility=self.create(ref)
            changed=self.update(ref,responsibility,priority='low',priority_reason='Upstream work is not ready; inspect other obligations first')
            self.assertEqual(changed['priority'],'low')
            history=self.owner.call('get_bot_commitment',{'commitment_id':responsibility['id']})['history']
            self.assertEqual([h['priority'] for h in history],['high','low'])
            self.fault('invalid_input',lambda:self.update(ref,changed,priority='high'))
        self.assertTrue(self.owner.call('replay')['matched'])
