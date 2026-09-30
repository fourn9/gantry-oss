"""Authenticated, branch-pinned PR review -> correction -> re-review."""
import secrets
import unittest
import test_continuity as fixtures
from test_development import LocalClient
from gantry.service import Service, token_hash


class ChangeReviewTests(unittest.TestCase):
    setUp = fixtures.ContinuityTests.setUp
    tearDown = fixtures.ContinuityTests.tearDown
    call = fixtures.ContinuityTests.call
    artifact = fixtures.ContinuityTests.artifact
    policy = fixtures.ContinuityTests.policy
    connect = fixtures.ContinuityTests.connect
    detail = fixtures.ContinuityTests.detail
    fault = fixtures.ContinuityTests.fault
    initialize = fixtures.ContinuityTests.initialize
    begin = fixtures.ContinuityTests.begin
    checkpoint = fixtures.ContinuityTests.checkpoint

    def setup_review(self):
        token = secrets.token_urlsafe(32)
        p = self.call('propose', {'title': 'Mentor delegation', 'changes': [{'id': 'mentor', 'type': 'principal', 'data': {
            'kind': 'agent', 'permissions': ['read', 'propose'], 'token_hash': token_hash(token), 'zones': ['root']}}]})
        args = {'proposal_id': p['id'], 'version': p['version']}
        self.call('submit', args); self.call('endorse', {**args, 'reason': 'test'})
        self.call('review_adoption', {**args, 'reason': 'test', 'verdict': 'approve'}); self.call('commit', args)
        self.mentor = LocalClient(self.service, token)
        self.mentor_token = token
        d = self.detail()['session']
        self.call('configure_development', {'session_id': d['id'], 'version': d['version'], 'reason': 'Review team',
            **{**self.policy(), 'actors': ['admin', 'mentor']}})
        self.team_args = {'session_id': d['id'], 'version': 0, 'coordinator': 'integration', 'required_roles': ['mechanical'], 'members': [
            {'principal_id': 'admin', 'side': 'user', 'role': 'developer'},
            {'principal_id': 'mentor', 'side': 'gantry', 'role': 'integration'},
            {'principal_id': 'mentor', 'side': 'gantry', 'role': 'mechanical', 'parent_role': 'integration'}]}
        self.call('configure_review_team', self.team_args)
        self.base = self.initialize()
        self.cp = self.checkpoint(self.begin(self.base))
        return self.submit(self.cp['change'])

    def submit(self, change):
        return self.call('submit_change_review', {'change_id': change['id'], 'version': change['version'],
            'question': 'Check interface', 'stage': 'preliminary', 'acceptance': ['input interface preserved'],
            'required_roles': ['mechanical']})

    def report(self, r):
        return self.mentor.call('submit_specialist_review', {'submission_id': r['id'], 'role': 'mechanical',
            'summary': 'Input checked', 'evidence': [r['state_id']], 'unresolved': []})

    def output(self, r, verdict='changes_requested'):
        return {'verdict': verdict, 'scope': 'input.txt interface', 'rationale': 'Compare pinned input',
            'evidence': [r['state_id']], 'unverified': [] if verdict == 'ok' else ['physical operation'],
            'prediction': 'Restoring the field preserves consumers', 'findings': [] if verdict == 'ok' else [{
                'id': 'f1', 'summary': 'Preserve field', 'paths': ['input.txt'], 'evidence': [r['state_id']],
                'proposed_change': 'Set input.txt to corrected', 'completion_condition': 'Compare field with consumer'}]}

    def claim(self, r):
        return self.mentor.call('claim_change_review', {'submission_id': r['id'], 'lease_seconds': 60})

    def complete(self, r, lease, verdict='changes_requested'):
        return self.mentor.call('complete_change_review', {'submission_id': r['id'], 'fence': lease['fence'],
            'output': self.output(r, verdict), 'context_fingerprint': self.call('get_change_review', {'submission_id': r['id']})['context_fingerprint']})

    def test_loop_and_replay(self):
        r = self.setup_review(); lease = self.claim(r)
        report = self.report(r); self.assertNotIn('fence', report)
        completed = self.complete(r, lease)
        self.assertEqual(completed['output']['verdict'], 'changes_requested')
        cp = self.checkpoint(self.cp['change'], {'input.txt': 'corrected'})
        response = self.call('respond_to_change_review', {'submission_id': r['id'], 'candidate_state': cp['state']['id'],
            'responses': [{'finding_id': 'f1', 'explanation': 'Restored field'}]})
        r2 = self.submit(cp['change']); self.report(r2); self.complete(r2, self.claim(r2), 'ok')
        self.mentor.call('reflect_change_review', {'submission_id': r['id'], 'response_id': response['id'],
            'assessment': 'inconclusive', 'observation': 'Re-review OK, no physical test',
            'applicability': 'This interface only', 'limitations': ['no runtime evidence']})
        view = self.call('get_change_review', {'submission_id': r2['id']})
        self.assertEqual(len(view['review_lessons']), 1)
        self.assertEqual(view['development']['status']['adoption'], 'unadopted')
        self.assertEqual(view['development']['status']['verification'], 'unverified')
        self.assertEqual(self.detail()['session']['active_state'], self.base['id'])
        self.assertTrue(self.call('replay')['matched'])
        restarted = LocalClient(Service(self.root / 'ledger'), self.token)
        self.assertEqual(restarted.call('get_change_review', {'submission_id': r2['id']})['output']['verdict'], 'ok')

    def test_finding_directory_paths_preserve_path_safety(self):
        r = self.setup_review(); lease = self.claim(r); self.report(r)
        output = self.output(r)
        args = {'submission_id': r['id'], 'fence': lease['fence'], 'output': output,
                'context_fingerprint': self.call('get_change_review', {'submission_id': r['id']})['context_fingerprint']}
        for unsafe in ('../outside/', '/tmp/', '/', 'candidate/../outside/'):
            output['findings'][0]['paths'] = [unsafe]
            self.fault('invalid_input', lambda: self.mentor.call('complete_change_review', args))
            self.assertEqual(self.call('get_change_review', {'submission_id': r['id']})['status'], 'running')
        output['findings'][0]['paths'] = ['candidate/architecture-package/', 'input.txt']
        completed = self.mentor.call('complete_change_review', args)
        self.assertEqual(completed['status'], 'completed')
        self.assertEqual(completed['output']['findings'][0]['paths'], output['findings'][0]['paths'])

    def test_fences_identity_and_required_specialists(self):
        r = self.setup_review(); lease = self.claim(r)
        self.fault('unauthorized', lambda: self.call('claim_change_review', {'submission_id': r['id'], 'lease_seconds': 60}))
        self.fault('conflict', lambda: self.claim(r))
        self.fault('review_pending', lambda: self.complete(r, lease))
        self.report(r)
        self.fault('conflict', lambda: self.complete(r, {**lease, 'fence': 'wrong'}))
        self.checkpoint(self.cp['change'], {'input.txt': 'changed again'})
        self.fault('stale_basis', lambda: self.complete(r, lease))
        self.assertFalse(self.call('get_change_review', {'submission_id': r['id']})['applicable'])

    def test_team_revocation_and_cross_candidate(self):
        r = self.setup_review(); self.report(r); self.complete(r, self.claim(r))
        unrelated = self.checkpoint(self.begin(self.base))
        self.fault('invalid_input', lambda: self.call('respond_to_change_review', {'submission_id': r['id'],
            'candidate_state': unrelated['state']['id'], 'responses': [{'finding_id': 'f1', 'explanation': 'bad'}]}))
        r2 = self.submit(self.cp['change']); lease = self.claim(r2); self.report(r2)
        self.call('configure_review_team', {**self.team_args, 'version': 1})
        self.fault('stale_basis', lambda: self.complete(r2, lease))

    def test_checkpoint_does_not_submit_and_legacy_disabled(self):
        r = self.setup_review()
        cp = self.checkpoint(self.cp['change'])
        self.assertEqual(len(self.call('list_change_reviews', {'session_id': self.session['id']})['items']), 1)
        from test_development import DevelopmentTests
        self.contract = lambda: DevelopmentTests.contract(self)
        self.fault('analysis_required', lambda: DevelopmentTests.propose(self))
        r2 = self.submit(cp['change']); self.assertNotEqual(r['id'], r2['id'])

    def test_expired_lease_and_idempotent_submission(self):
        r = self.setup_review(); lease = self.claim(r); self.report(r)
        old = self.service.clock; now = old(); self.service.clock = lambda: now + 61000
        newer = self.claim(r)
        self.fault('conflict', lambda: self.complete(r, lease))
        self.complete(r, newer)
        self.assertNotIn('fence', self.call('list_change_reviews', {'session_id': self.session['id']})['items'][0])

    def test_full_pr_diff_and_report_fingerprint(self):
        r = self.setup_review()
        cp2 = self.checkpoint(self.cp['change'], {'input.txt': 'modified\nsecond checkpoint'})
        r = self.submit(cp2['change']); self.report(r); lease = self.claim(r)
        context = self.call('get_change_review', {'submission_id': r['id']})
        self.assertIn('-initial', context['pr_diff'][0]['text'])
        self.assertIn('+modified', context['pr_diff'][0]['text'])
        self.mentor.call('submit_specialist_review', {'submission_id': r['id'], 'role': 'mechanical',
            'summary': 'New concern', 'evidence': [r['state_id']], 'unresolved': ['material strength']})
        self.fault('stale_basis', lambda: self.mentor.call('complete_change_review', {'submission_id': r['id'],
            'fence': lease['fence'], 'context_fingerprint': context['context_fingerprint'], 'output': self.output(r)}))

    def test_record_mode_and_owner_required_roles(self):
        r = self.setup_review()
        change = self.cp['change']
        r = self.call('submit_change_review', {'change_id': change['id'], 'version': change['version'],
            'question': 'Skip experts?', 'stage': 'preliminary', 'acceptance': ['a'], 'required_roles': []})
        self.assertEqual(r['required_roles'], ['mechanical'])
        d = self.detail()['session']
        self.call('configure_development', {'session_id': d['id'], 'version': d['version'], 'reason': 'Stop analysis',
            **{**self.policy('record'), 'actors': ['admin', 'mentor']}})
        self.fault('mode_disabled', lambda: self.claim(r))

    def test_team_activation_invalidates_old_contract(self):
        from test_development import DevelopmentTests
        self.contract = lambda: DevelopmentTests.contract(self)
        contract = DevelopmentTests.propose(self)
        self.assertTrue(self.call('check_execution', {'contract_id': contract['id']})['allowed'])
        self.setup_review()
        self.assertIn('stale_basis', self.call('check_execution', {'contract_id': contract['id']})['reasons'])

    def test_parallel_prs_and_dependency_change(self):
        r = self.setup_review(); self.report(r); lease = self.claim(r)
        branch = self.checkpoint(self.begin(self.base))
        other = self.submit(branch['change']); self.report(other); self.complete(other, self.claim(other), 'ok')
        self.complete(r, lease)
        self.assertEqual(self.detail()['session']['active_state'], self.base['id'])
        change = self.call('begin_change', {'state_id': self.base['id'], 'title': 'Read input', 'purpose': 'dependency',
            'write_scope': ['new.txt'], 'dependencies': ['input.txt'], 'assignee': 'admin'})
        cp = self.checkpoint(change, {'input.txt': 'initial', 'new.txt': 'derived'})
        r = self.submit(cp['change']); self.report(r); lease = self.claim(r)
        d = self.detail()['session']
        self.call('select_development_state', {'state_id': branch['state']['id'], 'version': d['version'], 'reason': 'Changed dependency'})
        self.fault('stale_basis', lambda: self.complete(r, lease))

    def test_submission_retry_and_worker_recovery(self):
        from gantry.review_worker import prepare_review, finish_review, review_once
        r = self.setup_review(); self.report(r)
        journal = self.root / 'review-worker'
        job = prepare_review(self.mentor, r['id'], journal)
        self.assertEqual(job['fence'], prepare_review(self.mentor, r['id'], journal)['fence'])
        output = self.output(r)
        real = self.mentor
        class LostAck:
            def call(inner, name, args=None, key=None):
                result = real.call(name, args, key)
                if name == 'complete_change_review': raise OSError('lost response')
                return result
        with self.assertRaises(OSError): finish_review(LostAck(), journal, output)
        restored = finish_review(real, journal, output)
        self.assertEqual(restored['status'], 'completed')
        self.assertEqual(finish_review(real, journal, output)['id'], r['id'])
        r2 = self.submit(self.cp['change']); self.report(r2)
        def fail(context): raise OSError('uncertain model response')
        with self.assertRaises(OSError): review_once(real, r2['id'], self.root / 'uncertain', fail)
        self.fault('outcome_unknown', lambda: review_once(real, r2['id'], self.root / 'uncertain', fail))

    def test_worker_waits_for_reports_before_inference(self):
        from gantry.review_worker import review_once
        r = self.setup_review(); calls = []
        def inference(context): calls.append(context); return self.output(r)
        self.fault('review_pending', lambda: review_once(self.mentor, r['id'], self.root / 'waiting', inference))
        self.assertEqual(calls, [])
        self.report(r)
        result = review_once(self.mentor, r['id'], self.root / 'waiting', inference)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(len(calls), 1)

    def test_review_contract_runs_and_binds_actual_output(self):
        import sys
        from gantry.model import digest
        from gantry.runner import run_contract
        r = self.setup_review()
        recipe = {'argv': [sys.executable, '-c', 'open("input.txt","w").write("corrected")'], 'timeout_seconds': 10}
        d = self.detail()['session']
        self.call('configure_development', {'session_id': d['id'], 'version': d['version'], 'reason': 'Permit local fixture correction',
            **{**self.policy(), 'actors': ['admin', 'mentor'], 'write_scope': ['input.txt'], 'recipes': {'fix': digest(recipe)}}})
        self.report(r); self.complete(r, self.claim(r))
        contract = {'title': 'Preserve field', 'input_snapshot': self.cp['state']['snapshot'],
            'write_scope': ['input.txt'], 'recipe': 'fix', 'recipe_hash': digest(recipe), 'expected_outputs': ['input.txt'],
            'completion': {'description': 'Corrected file saved', 'require_exit_zero': True, 'required_files': ['input.txt']},
            'dependencies': [], 'hypothesis': 'Consumers remain compatible', 'rationale': 'Review f1'}
        work = self.mentor.call('propose_review_work', {'submission_id': r['id'], 'finding_ids': ['f1'], 'contract': contract})
        self.assertEqual(work['status'], 'proposed')
        self.assertTrue(self.call('check_execution', {'contract_id': work['id']})['allowed'])
        run_contract(self.client, work['id'], {'fix': recipe}, self.root / 'actual-run')
        execution = next(e for e in self.detail()['executions'] if e['contract_id'] == work['id'])
        self.assertTrue(execution['valid'])
        self.assertEqual(execution['input_state'], r['state_id'])
        cp = self.call('checkpoint_change', {'change_id': self.cp['change']['id'], 'version': self.cp['change']['version'],
            'snapshot': execution['output_snapshot'], 'summary': 'Correction', 'rationale': 'Review f1',
            'unfinished': ['hardware verification'], 'work_status': 'paused', 'capture': {'scope': 'saved files', 'missing': []},
            'work_ids': [work['id']]})
        response = self.call('respond_to_change_review', {'submission_id': r['id'], 'candidate_state': cp['state']['id'],
            'responses': [{'finding_id': 'f1', 'explanation': 'Field restored'}], 'execution_id': execution['id']})
        self.assertEqual(response['execution_id'], execution['id'])
        work = next(c for c in self.detail()['contracts'] if c['id'] == work['id'])
        self.call('invalidate_submission', {'contract_id': work['id'], 'version': work['version'], 'reason': 'Evidence withdrawn'})
        self.fault('invalid_input', lambda: self.call('respond_to_change_review', {'submission_id': r['id'],
            'candidate_state': cp['state']['id'], 'execution_id': execution['id'],
            'responses': [{'finding_id': 'f1', 'explanation': 'Cannot claim revoked evidence'}]}))
        view = self.call('get_change_review', {'submission_id': r['id']})
        self.assertEqual(view['review_responses'][0]['execution_evidence'], 'withdrawn_or_invalid')
        self.assertEqual(self.detail()['session']['active_state'], self.base['id'])
        self.assertTrue(self.call('replay')['matched'])

    def test_pr_work_keeps_policy_but_does_not_wait_on_legacy_milestones(self):
        # Policy-level test: PR reviews replace only the legacy analysis gate.
        service = self.service
        d = {'id': 'dev', 'automation_project': 'project', 'automation_version': 1, 'generation': 1}
        s = {'automation_policies': {'project': {'enabled': True, 'version': 1,
             'session_template': {'actors': ['admin']}, 'max_daily_executions': 2}},
             'dev_milestones': {'failure': {'session_id': 'dev', 'generation': 1, 'status': 'pending', 'kind': 'failure'}}}
        self.assertIn('automation_review_pending', service._automation_execution_reasons(s, {'id': 'admin'}, d, {}))
        self.assertNotIn('automation_review_pending', service._automation_execution_reasons(s, {'id': 'admin'}, d, {'review_submission': 'r'}))
        s['automation_policies']['project']['enabled'] = False
        self.assertIn('automation_disabled', service._automation_execution_reasons(s, {'id': 'admin'}, d, {'review_submission': 'r'}))
