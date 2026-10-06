"""Organization mechanics: model reasoning is separately exercised by live smoke."""
from test_bot_development import BotDevelopmentTests


class CrewCoordinationTests(BotDevelopmentTests):
    def claim(self, worker, task, name):
        return self.clients[name].call('claim_bot_task', {'task_id': task['id'],
            'version': task['version'], 'runtime_fence': worker.runtime['fence']})

    def test_directed_question_wakes_peer_and_requester(self):
        task = self.task('designer')
        with self.worker('designer') as worker:
            claim = self.claim(worker, task, 'designer')
            ref = {'task_id': task['id'], 'fence': claim['task']['fence']}
            request = self.clients['designer'].call('ask_bot', {**ref, 'to_bot_id': 'control',
                'question': 'Which interface can the controller support?', 'evidence': [self.base['id']]})
            report = self.answer(status='waiting'); report.pop('edits')
            self.clients['designer'].call('finish_bot_task', {**ref, 'report': report})
        reply_task = request['response_task']
        self.assertEqual(reply_task['write_scope'], [])
        with self.worker('control', lambda ctx, schema, directory: {'output': self.answer(summary='Interface 2 supported')}) as worker:
            worker.tick()
        view = self.clients['designer'].call('get_bot_task', {'task_id': task['id']})
        self.assertEqual(view['task']['status'], 'pending')
        self.assertTrue(any(m.get('reply_to') == request['message']['id'] for m in view['messages']))
        self.assertEqual(len(view['consultations']), 1)

    def test_decisions_are_attributed_and_cannot_grant_authority(self):
        task = self.task('lead'); child = self.task('designer')
        with self.worker('lead') as worker:
            claim = self.claim(worker, task, 'lead')
            decision = self.clients['lead'].call('record_bot_decision', {'task_id': task['id'],
                'fence': claim['task']['fence'], 'verdict': 'continue', 'targets': [child['id']],
                'rationale': 'Resolve interface before detailed geometry', 'evidence': [self.base['id']],
                'alternatives': ['Change controller only'], 'conditions': ['Keep the same baseline']})
            self.assertEqual(decision['bot_id'], 'lead')
            self.assertFalse(decision['formal_adoption'])
        with self.worker('designer') as worker:
            claim = self.claim(worker, child, 'designer')
            self.fault('unauthorized', lambda: self.clients['designer'].call('record_bot_decision', {
                'task_id': child['id'], 'fence': claim['task']['fence'], 'verdict': 'authorize',
                'targets': [task['id']], 'rationale': 'Attempt escalation', 'evidence': [],
                'alternatives': [], 'conditions': []}))

    def test_refresh_accepts_discussion_only_not_changed_authority(self):
        task = self.task()
        with self.worker('lead') as worker:
            claim = self.claim(worker, task, 'lead'); ref = {'task_id': task['id'], 'fence': claim['task']['fence']}
            self.clients['control'].call('send_bot_message', {'task_id': task['id'], 'from_bot_id': 'control',
                'kind': 'report', 'body': 'New controller evidence', 'blocking': False, 'evidence': []})
            self.fault('stale_basis', lambda: self.clients['lead'].call('check_bot_task', ref))
            refreshed = self.clients['lead'].call('refresh_bot_task', ref)
            self.assertEqual(len(refreshed['messages']), 1)
            self.clients['lead'].call('check_bot_task', ref)

    def team_proposal(self):
        from test_bots import profile
        return {'session_id': self.sid, 'organization_id': 'team', 'lead_bot_id': 'lead',
            'goal': 'Coordinate a shared interface', 'acceptance': ['Exact matched state'],
            'rationale': 'Keep the existing hierarchy and improve onboarding', 'members': [
                {'bot_id': name, 'name': name, 'parent_bot_id': None if name == 'lead' else 'mechanical' if name == 'designer' else 'lead',
                 'principal_id': name, 'profile': profile(name), 'write_scope': self.scope(name),
                 'can_assign': name in {'lead', 'mechanical'}, 'can_integrate': name == 'lead'} for name in self.clients]}

    def test_team_activation_is_owner_only_atomic_and_versioned(self):
        proposed = self.clients['lead'].call('propose_bot_team', self.team_proposal())
        self.fault('unauthorized', lambda: self.clients['lead'].call('activate_bot_team', {'proposal_id': proposed['id']}))
        out = self.owner.call('activate_bot_team', {'proposal_id': proposed['id']})
        self.assertEqual(out['status'], 'activated')
        invalid = self.team_proposal(); invalid['members'][-1]['write_scope'] = ['outside/']
        proposed = self.owner.call('propose_bot_team', invalid)
        before = self.owner.call('get_persistent_bot', {'bot_id': 'lead'})['bot']['version']
        self.fault('scope_denied', lambda: self.owner.call('activate_bot_team', {'proposal_id': proposed['id']}))
        self.assertEqual(before, self.owner.call('get_persistent_bot', {'bot_id': 'lead'})['bot']['version'])

    def test_explicit_experience_is_retrievable_and_attributed(self):
        task = self.task()
        with self.worker('lead') as worker:
            claimed = self.claim(worker, task, 'lead')
            memory = self.clients['lead'].call('record_bot_experience', {'task_id': task['id'], 'fence': claimed['task']['fence'],
                'observation': 'Check the shared interface before detailed geometry', 'applicability': 'This fixture baseline only',
                'limitations': ['Not physical evidence'], 'evidence': [self.base['id']], 'used_memories': []})
        view = self.clients['lead'].call('list_persistent_memories', {'bot_id': 'lead'})
        self.assertIn(memory['id'], [m['id'] for m in view['items']])

    def test_unanswered_consultation_cannot_be_resolved(self):
        task = self.task('designer')
        with self.worker('designer') as worker:
            claim = self.claim(worker, task, 'designer')
            ref = {'task_id': task['id'], 'fence': claim['task']['fence']}
            request = self.clients['designer'].call('ask_bot', {**ref, 'to_bot_id': 'control',
                'question': 'Check compatibility', 'evidence': []})
            args = {'message_id': request['message']['id'], 'reason': 'Not answered yet', 'evidence': []}
            self.fault('dependency_pending', lambda: self.clients['designer'].call('resolve_bot_question', {**ref, **args}))
            self.fault('dependency_pending', lambda: self.clients['designer'].call('resolve_bot_message', args))

    def test_action_history_is_paged_without_losing_details(self):
        task = self.task()
        with self.worker('lead') as worker:
            claim = self.claim(worker, task, 'lead'); ref = {'task_id': task['id'], 'fence': claim['task']['fence']}
            for i in range(32):
                self.clients['lead'].call('record_bot_action', {**ref, 'kind': 'read', 'details': {'round': i, 'result': 'x'*32768}})
        view = self.owner.call('get_bot_task', {'task_id': task['id']})
        self.assertEqual(len(view['actions']), 20)
        self.assertEqual(view['action_history']['total'], 32)
        rows = []; after = None
        while True:
            page = self.owner.call('get_bot_records', {'task_id': task['id'], 'kind': 'actions', 'limit': 7,
                **({'after': after} if after else {})})
            rows.extend(page['items']); after = page['next_cursor']
            if after is None: break
        self.assertEqual(len({r['id'] for r in rows}), 32)
        self.assertEqual({r['details']['round'] for r in rows}, set(range(32)))

    def test_decision_can_reference_scoped_tool_action_receipt(self):
        task = self.task()
        with self.worker('lead') as worker:
            claim = self.claim(worker, task, 'lead'); ref = {'task_id': task['id'], 'fence': claim['task']['fence']}
            action = self.clients['lead'].call('record_bot_action', {**ref, 'kind': 'tool', 'details': {'exit_code': 0}})
            decision = self.clients['lead'].call('record_bot_decision', {**ref, 'verdict': 'continue', 'targets': [task['id']],
                'rationale': 'Review exact execution receipt', 'evidence': [action['id']], 'alternatives': [], 'conditions': ['Fixture only']})
            self.assertEqual(decision['evidence'], [action['id']])
