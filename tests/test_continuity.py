import copy
import unittest
import json
import sys
import test_development as fixtures


class ContinuityTests(unittest.TestCase):
    setUp = fixtures.DevelopmentTests.setUp
    tearDown = fixtures.DevelopmentTests.tearDown
    call = fixtures.DevelopmentTests.call
    artifact = fixtures.DevelopmentTests.artifact
    policy = fixtures.DevelopmentTests.policy
    connect = fixtures.DevelopmentTests.connect
    detail = fixtures.DevelopmentTests.detail
    fault = fixtures.DevelopmentTests.fault
    contract = fixtures.DevelopmentTests.contract
    propose = fixtures.DevelopmentTests.propose
    start = fixtures.DevelopmentTests.start
    finish = fixtures.DevelopmentTests.finish
    def initialize(self):
        return self.call('initialize_continuity', {'session_id': self.session['id'],
            'version': self.detail()['session']['version'], 'summary': 'Continue existing robot',
            'hierarchy': [{'id': 'robot', 'title': 'Robot', 'kind': 'robot', 'paths': ['input.txt'], 'editable': True}],
            'context': {'requirements': ['motion'], 'constraints': ['no hardware'],
                        'decisions': [], 'open_questions': ['physics'], 'environment': {'python': '3'}}})

    def begin(self, state, scope=None):
        return self.call('begin_change', {'state_id': state['id'], 'title': 'Improve', 'purpose': 'Continue design',
            'write_scope': scope or ['input.txt'], 'dependencies': [], 'assignee': 'admin'})

    def checkpoint(self, change, files=None, **extra):
        return self.call('checkpoint_change', {'change_id': change['id'], 'version': change['version'],
            'snapshot': self.artifact(files or {'input.txt': 'modified'}), 'summary': 'Unverified design saved',
            'rationale': 'Hypothesis pending test', 'unfinished': ['physics'], 'work_status': 'paused',
            'capture': {'scope': 'saved files', 'missing': ['unsaved edits']}, **extra})

    def test_immutable_checkpoint_share_and_restart(self):
        state = self.initialize(); change = self.begin(state); checkpoint = self.checkpoint(change)
        shared = self.call('share_change', {'change_id': change['id'], 'version': checkpoint['change']['version']})
        view = self.call('get_development_state', {'state_id': checkpoint['state']['id']})
        self.assertEqual(view['status'], {'work': 'paused', 'sharing': 'shared', 'verification': 'unverified',
            'verification_scope': [], 'adoption': 'unadopted'})
        self.assertEqual(self.call('get_development_state', {'state_id': state['id']})['state']['snapshot'], self.snapshot)
        self.fault('stale_basis', lambda: self.checkpoint(change))
        self.assertTrue(self.call('replay')['matched'])
        self.assertIsNone(self.call('state')['head'])

    def test_checkpoint_scope_and_hierarchy_cycle(self):
        state = self.initialize(); change = self.begin(state)
        self.fault('scope_denied', lambda: self.checkpoint(change, {'input.txt': 'modified', 'private': 'bad'}))

    def share(self, checkpoint):
        c = checkpoint['change']
        return self.call('share_change', {'change_id': c['id'], 'version': c['version']})['change']

    def integrate(self, state, changes):
        return self.call('integrate_changes', {'state_id': state['id'],
            'changes': [{'id': c['id'], 'version': c['version']} for c in changes], 'summary': 'Combine'})

    def test_parallel_integration_conflict_and_dependency(self):
        base = self.initialize()
        a = self.share(self.checkpoint(self.begin(base)))
        b = self.share(self.checkpoint(self.begin(base, ['control.py']), {'input.txt': 'initial', 'control.py': 'gain=2'}))
        result = self.integrate(base, [a, b]); self.assertTrue(result['integrated'])
        self.assertEqual(result['compatibility'], 'unknown')
        self.assertEqual(self.call('get_development_state', {'state_id': result['state']['id']})['status']['verification'], 'unverified')
        c = self.share(self.checkpoint(self.begin(base)))
        e = self.share(self.checkpoint(self.begin(base)))
        self.assertFalse(self.integrate(base, [c, e])['integrated'])
        dependent = self.call('begin_change', {'state_id': base['id'], 'title': 'Control', 'purpose': 'Use mechanism',
            'write_scope': ['control.py'], 'dependencies': ['input.txt'], 'assignee': 'admin'})
        dependent = self.share(self.checkpoint(dependent, {'input.txt': 'initial', 'control.py': 'gain=3'}))
        self.assertIn('dependency_changed', [x['reason'] for x in self.integrate(base, [c, dependent])['conflicts']])

    def test_evaluation_binding_adoption_and_old_api_invalidation(self):
        base = self.initialize()
        context = self.call('mentor_context', {'session_id': self.session['id']})
        milestone = context['milestones'][0]
        args = {'session_id': self.session['id'], 'milestone_id': milestone['id'], 'contract': self.contract()}
        self.fault('stale_basis', lambda: self.call('mentor_propose', args))
        c = self.call('mentor_propose', {**args, 'input_state': base['id'], 'evidence': [base['id']]})
        e = self.finish(self.start(c)['execution'])
        self.call('record_state_evaluation', {'state_id': base['id'], 'execution_id': e['id'], 'scope': 'Unit criterion only'})
        self.assertEqual(self.call('get_development_state', {'state_id': base['id']})['status']['verification'], 'pass')
        changed = self.checkpoint(self.begin(base))['state']
        view = self.call('get_development_state', {'state_id': changed['id']})
        self.assertEqual(view['status']['verification'], 'unverified')
        self.assertFalse(view['evaluations'][0]['applicable'])
        self.fault('invalid_input', lambda: self.call('record_state_evaluation', {'state_id': changed['id'], 'execution_id': e['id'], 'scope': 'Wrong'}))
        p = self.call('propose_state_adoption', {'state_id': base['id'], 'reason': 'Accept with documented limitations'})
        args = {'proposal_id': p['id'], 'version': p['version']}
        self.call('submit', args); self.call('endorse', {**args, 'reason': 'Review'})
        self.fault('human_approval_required', lambda: self.call('commit', args))
        self.call('review_adoption', {**args, 'reason': 'Accept scope', 'verdict': 'approve'})
        self.call('commit', args)
        self.assertEqual(self.call('get_development_state', {'state_id': base['id']})['status']['adoption'], 'human_adopted')
        d = self.detail()['session']
        self.call('advance_development', {'session_id': d['id'], 'version': d['version'], 'snapshot': self.snapshot,
            'reason': 'legacy update', 'capture': d['capture'], 'unverified': []})
        self.assertNotIn('active_state', self.detail()['session'])

    def test_change_can_replace_its_read_input_but_not_other_readers_basis(self):
        base = self.initialize()
        def mechanic():
            change = self.call('begin_change', {'state_id': base['id'], 'title': 'Move wire lane',
                'purpose': 'Read then update existing geometry', 'write_scope': ['input.txt'],
                'dependencies': ['input.txt'], 'assignee': 'admin'})
            return self.share(self.checkpoint(change))
        a = mechanic()
        result = self.integrate(base, [a])
        self.assertTrue(result['integrated'])
        self.assertEqual(self.call('get_development_state', {'state_id': result['state']['id']})['status']['verification'], 'unverified')
        b = mechanic()
        reader = self.call('begin_change', {'state_id': base['id'], 'title': 'Evaluate old lane',
            'purpose': 'Evaluation depends on the old geometry', 'write_scope': ['control.py'],
            'dependencies': ['input.txt'], 'assignee': 'admin'})
        reader = self.share(self.checkpoint(reader, {'input.txt': 'initial', 'control.py': 'old geometry check'}))
        blocked = self.integrate(base, [b, reader])
        self.assertFalse(blocked['integrated'])
        self.assertIn({'path': 'input.txt', 'reason': 'dependency_changed', 'change': reader['id']}, blocked['conflicts'])
        self.assertNotIn({'path': 'input.txt', 'reason': 'dependency_changed', 'change': b['id']}, blocked['conflicts'])
        stale = self.integrate(result['state'], [b])
        self.assertFalse(stale['integrated'])
        self.assertIn('concurrent_change', [x['reason'] for x in stale['conflicts']])
        self.assertTrue(self.call('replay')['matched'])

    def test_workspace_capture_restore_and_secret_exclusion(self):
        from gantry.continuity_adapter import checkpoint_workspace, restore_development_state, capture_workspace
        base = self.initialize(); change = self.begin(base)
        workspace = self.root / 'external'; workspace.mkdir()
        (workspace / 'input.txt').write_text('modified')
        (workspace / '.env').write_text('PRIVATE=do-not-copy')
        result = checkpoint_workspace(self.client, change['id'], 1, workspace, 'Pause', 'Need review', [], 'paused', 'save')
        bundle = restore_development_state(self.client, result['state']['id'], self.root / 'resumed', 'restore')
        self.assertEqual((self.root / 'resumed/workspace/input.txt').read_text(), 'modified')
        self.assertFalse((self.root / 'resumed/workspace/.env').exists())
        context = json.loads((self.root / 'resumed/context.json').read_text())
        self.assertIn('credential_file_excluded:.env', context['state']['capture']['missing'])
        self.assertEqual(bundle['receipt']['verification'], 'adapter_reported_file_hashes')
        retry = restore_development_state(self.client, result['state']['id'], self.root / 'resumed', 'restore')
        self.assertEqual(retry['receipt'], bundle['receipt'])
        (self.root / 'resumed/workspace/input.txt').write_text('local edit must survive')
        self.fault('integrity_error', lambda: restore_development_state(self.client, result['state']['id'], self.root/'resumed', 'new-receipt'))
        (workspace / 'input.txt').write_text('-----BEGIN PRIVATE KEY-----')
        self.fault('credential_detected', lambda: capture_workspace(self.client, workspace, 'bad'))

    def test_v1_mentor_host_runner_and_reflection(self):
        from gantry.runner import tick
        base = self.initialize()
        response = {'contract': self.contract(), 'input_state': base['id'], 'evidence': [base['id']],
                    'alternatives': ['skip check'], 'selection_reason': 'Need a recorded criterion'}
        provider = {'argv': [sys.executable, '-c',
            'import json,sys; c=json.load(sys.stdin); assert c["development"]; print('+repr(json.dumps(response))+')']}
        result = tick(self.client, self.session['id'], provider, {'test': self.recipe}, self.root / 'worker')
        self.assertEqual(result['execution']['engineering_verdict'], 'pass')
        c = result['mentor']['contract']
        self.call('mentor_reflect', {'session_id': self.session['id'], 'contract_id': c['id'],
            'summary': 'Criterion executed', 'lessons': ['Exact state retained'], 'limitations': ['Not a robot evaluation']})
        ctx = self.call('mentor_context', {'session_id': self.session['id']})
        self.assertEqual(ctx['reflections'][0]['evidence']['execution_id'], result['execution']['id'])
        self.assertTrue(self.call('replay')['matched'])

    def test_v1_export_import_and_state_bound_gate(self):
        from gantry.backup import restore_backup
        from gantry.service import Service
        state = self.initialize()
        milestone = self.detail()['milestones'][0]
        c = self.call('mentor_propose', {'session_id': self.session['id'], 'milestone_id': milestone['id'],
            'contract': self.contract(), 'input_state': state['id'], 'evidence': [state['id']]})
        checkpoint = self.checkpoint(self.begin(state))['state']
        self.call('select_development_state', {'state_id': checkpoint['id'],
            'version': self.detail()['session']['version'], 'reason': 'New input'})
        gate = self.start(c)
        self.assertFalse(gate['allowed']); self.assertIn('stale_state', gate['reasons'])
        self.assertEqual(self.detail()['session']['used_executions'], 0)
        before = self.call('get_development_state', {'state_id': checkpoint['id']})
        restore_backup(self.root/'imported', self.call('export'))
        after = Service(self.root/'imported').call(self.token, 'get_development_state', {'state_id': checkpoint['id']})
        self.assertEqual(before, after)
