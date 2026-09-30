"""Independent restart, delegation and verification-boundary regression tests."""
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import test_mentor_jobs as fixture
from gantry.mentor_daemon import process_job
from gantry.model import digest
from gantry import mentor_daemon


class MentorSafetyTests(fixture.MentorJobsTests):
    def developer_job(self):
        self.setup_jobs()
        self.run_job('specialist')
        self.run_job('coordinator')
        return self.job('developer')

    def permit_verification(self, recipe):
        d = self.detail()['session']
        self.call('configure_development', {'session_id': d['id'], 'version': d['version'],
            'reason': 'Authorize exact fixture verifier', **{**self.policy(),
            'actors': ['admin', 'mentor'], 'write_scope': ['input.txt'],
            'recipes': {'verify': digest(recipe)}}})

    def test_unregistered_verification_cannot_start_inference(self):
        job = self.developer_job()
        calls = []
        def infer(*args):
            calls.append(True)
            return self.inference(*args)
        self.fault('recipe_not_allowed', lambda: process_job(self.client, job['id'],
            self.root/'unregistered', infer, verification={'argv': [sys.executable, '-c', 'pass']}))
        self.assertEqual(calls, [])

    def test_revocation_after_claim_prevents_local_inference(self):
        job = self.developer_job()
        journal = self.root/'revoked'
        # Stop after durable claim but before local preparation/inference.
        with patch.object(mentor_daemon, 'restore_files', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):
                process_job(self.client, job['id'], journal, self.inference)
        self.call('configure_review_automation', {'session_id':self.session['id'], 'version':1,
            'enabled':False, 'max_rounds':1, 'max_jobs':10, 'developer_principal':'admin'})
        calls = []
        self.fault('mode_disabled', lambda: process_job(self.client, job['id'], journal,
            lambda *args: calls.append(True)))
        self.assertEqual(calls, [])

    def test_lost_finish_ack_replays_without_new_inference(self):
        job = self.developer_job(); calls = []
        def infer(*args):
            calls.append(True)
            return self.inference(*args)
        real = self.client
        class LostAck:
            def call(self, name, args=None, key=None):
                result = real.call(name, args, key)
                if name == 'finish_mentor_job':
                    raise OSError('response lost')
                return result
        journal = self.root/'lost-finish'
        with self.assertRaises(OSError):
            process_job(LostAck(), job['id'], journal, infer)
        result = process_job(real, job['id'], journal, infer)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(self.call('list_change_reviews', {'session_id':self.session['id']})['items']), 2)

    def test_resume_after_verification_does_not_reapply_edits(self):
        job = self.developer_job()
        recipe = {'argv':[sys.executable, '-c', 'open("input.txt","w").write("verified-transform")'],
                  'timeout_seconds':10}
        self.permit_verification(recipe)
        journal = self.root/'verified-restart'
        with patch.object(mentor_daemon, 'capture_workspace', side_effect=OSError('capture interrupted')):
            with self.assertRaises(OSError):
                process_job(self.client, job['id'], journal, self.inference, verification=recipe)
        workspace = journal/digest(job['id'])/'workspace'
        self.assertEqual((workspace/'input.txt').read_text(), 'verified-transform')
        result = process_job(self.client, job['id'], journal, self.inference, verification=recipe)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual((workspace/'input.txt').read_text(), 'verified-transform')

    def test_tampered_verified_bytes_are_not_captured_on_restart(self):
        job = self.developer_job()
        recipe = {'argv':[sys.executable, '-c', 'pass'], 'timeout_seconds':10}
        self.permit_verification(recipe)
        journal = self.root/'tampered'
        with patch.object(mentor_daemon, 'capture_workspace', side_effect=OSError('capture interrupted')):
            with self.assertRaises(OSError):
                process_job(self.client, job['id'], journal, self.inference, verification=recipe)
        (journal/digest(job['id'])/'workspace'/'input.txt').write_text('tampered')
        self.fault('stale_basis', lambda: process_job(self.client, job['id'], journal,
            self.inference, verification=recipe))

    def test_developer_claim_consumes_slot_and_execution_allowance_once(self):
        job = self.developer_job()
        before = self.detail()['session']['used_executions']
        args = {'job_id':job['id'], 'lease_seconds':60}
        first = self.client.call('claim_mentor_job', args, 'same-claim')
        replay = self.client.call('claim_mentor_job', args, 'same-claim')
        self.assertEqual(first['fence'], replay['fence'])
        self.assertEqual(self.detail()['session']['used_executions'], before+1)

    def test_api_key_login_never_falls_back_to_paid_inference(self):
        from gantry.monthly_codex import infer_monthly
        with patch('gantry.monthly_codex.subprocess.run', return_value=SimpleNamespace(
                returncode=0, stdout='Logged in using an API key', stderr='')) as status, \
             patch('gantry.monthly_codex.subprocess.Popen') as launch, \
             patch.dict('os.environ', {'OPENAI_API_KEY':'test-secret', 'CODEX_API_KEY':'test-secret'}):
            self.fault('subscription_login_required', lambda: infer_monthly({},
                {'type':'object'}, self.root/'api-key-login'))
            launch.assert_not_called()
            self.assertNotIn('OPENAI_API_KEY', status.call_args.kwargs['env'])
            self.assertNotIn('CODEX_API_KEY', status.call_args.kwargs['env'])

    def test_expired_cached_claim_does_not_invoke_model(self):
        job = self.developer_job(); journal = self.root/'expired'
        with patch.object(mentor_daemon, 'restore_files', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):
                process_job(self.client, job['id'], journal, self.inference)
        now = self.service.clock(); self.service.clock = lambda: now+901000
        calls = []
        self.fault('stale_basis', lambda: process_job(self.client, job['id'], journal,
            lambda *args: calls.append(True)))
        self.assertEqual(calls, [])

    def project_execution_fixture(self):
        now = 10 * 86400000 + 3600000
        self.service.clock = lambda: now
        current = {'id':'current', 'automation_project':'project', 'automation_version':1, 'generation':1}
        state = {'dev_sessions': {'current':current,
                   'other': {'id':'other', 'automation_project':'project'},
                   'unrelated': {'id':'unrelated', 'automation_project':'elsewhere'}},
                 'automation_policies': {'project': {'enabled':True, 'version':1,
                    'session_template': {'actors':['developer']}, 'max_daily_executions':20}},
                 'mentor_jobs': {}, 'dev_executions': {}, 'dev_contracts': {}}
        contract = {'review_submission':'submitted', 'write_scope':['cad/part.step']}
        return state, current, contract, now

    def test_cross_session_running_developer_job_blocks_overlapping_project_scope(self):
        state, current, contract, now = self.project_execution_fixture()
        state['mentor_jobs']['job'] = {'kind':'developer', 'session_id':'other',
            'status':'running', 'started_at':now, 'write_scope':['cad/']}
        reasons = self.service._automation_execution_reasons(state, {'id':'developer'}, current, contract)
        self.assertIn('project_write_conflict', reasons)
        for update in ({'status':'completed'}, {'status':'running', 'session_id':'unrelated'},
                       {'status':'running', 'session_id':'other', 'write_scope':['software/']}):
            state['mentor_jobs']['job'].update(update)
            self.assertNotIn('project_write_conflict',
                self.service._automation_execution_reasons(state, {'id':'developer'}, current, contract))

    def test_project_daily_limit_combines_runner_and_developer_jobs(self):
        state, current, contract, now = self.project_execution_fixture()
        state['automation_policies']['project']['max_daily_executions'] = 2
        state['dev_executions']['run'] = {'origin':'delegated', 'session_id':'other',
            'status':'completed', 'started_at':now}
        state['mentor_jobs']['job'] = {'kind':'developer', 'session_id':'other',
            'status':'failed', 'started_at':now, 'write_scope':['cad/']}
        self.assertIn('project_execution_budget',
            self.service._automation_execution_reasons(state, {'id':'developer'}, current, contract))
        # Failed executions still consume the allowance; unrelated jobs do not.
        for update in ({'started_at':now-86400000}, {'started_at':now, 'kind':'specialist'},
                       {'kind':'developer', 'session_id':'unrelated'}):
            state['mentor_jobs']['job'].update(update)
            self.assertNotIn('project_execution_budget',
                self.service._automation_execution_reasons(state, {'id':'developer'}, current, contract))

    def test_product_linked_sessions_also_detect_developer_scope_conflict(self):
        state, current, contract, now = self.project_execution_fixture()
        current.pop('automation_project')
        state['dev_sessions']['other'].pop('automation_project')
        state['product_sessions'] = {'current': {'project_id':'project'}, 'other': {'project_id':'project'}}
        state['mentor_jobs']['job'] = {'kind':'developer', 'session_id':'other',
            'status':'running', 'started_at':now, 'write_scope':['cad/']}
        self.assertIn('project_write_conflict',
            self.service._automation_execution_reasons(state, {'id':'developer'}, current, contract))

    def test_reflection_receives_returned_candidate_bytes_and_state(self):
        original = self.setup_jobs()
        self.run_job('specialist'); self.run_job('coordinator')
        returned = self.run_job('developer')['result']
        job = self.job('reflection'); observed = []
        def inspect(ctx, schema, directory):
            observed.append(ctx)
            self.assertEqual(ctx['files']['input.txt'], 'corrected')
            self.assertEqual(ctx['files_state_id'], returned['candidate'])
            self.assertEqual(ctx['review']['response']['state_id'], returned['candidate'])
            self.assertEqual(ctx['review']['returned_development']['state']['id'], returned['candidate'])
            self.assertEqual(ctx['review']['development']['state']['id'], original['state_id'])
            self.assertNotEqual(original['state_id'], returned['candidate'])
            self.assertEqual(len(ctx['review']['returned_observations']), 1)
            return self.inference(ctx, schema, directory)
        process_job(self.mentor, job['id'], self.root/'reflection-state', inspect)
        self.assertEqual(len(observed), 1)

    def test_nested_specialist_waits_for_required_child(self):
        self.setup_jobs()
        team = self.call('get_review_team', {'session_id':self.session['id']})['team']
        members = team['members'] + [{'principal_id':'mentor', 'side':'gantry',
            'role':'geometry', 'parent_role':'mechanical'}]
        self.call('configure_review_team', {'session_id':self.session['id'], 'version':team['version'],
            'coordinator':'integration', 'required_roles':['mechanical','geometry'], 'members':members})
        self.call('configure_review_automation', {'session_id':self.session['id'], 'version':1,
            'enabled':True, 'max_rounds':1, 'max_jobs':10, 'developer_principal':'admin'})
        r = self.submit(self.cp['change'])
        jobs = [j for j in self.jobs() if j['submission_id']==r['id']]
        parent = next(j for j in jobs if j['role']=='mechanical')
        child = next(j for j in jobs if j['role']=='geometry')
        self.fault('review_pending', lambda: process_job(self.mentor, parent['id'], self.root/'nested', self.inference))
        process_job(self.mentor, child['id'], self.root/'nested', self.inference)
        result = process_job(self.mentor, parent['id'], self.root/'nested', self.inference)
        self.assertEqual(result['status'], 'completed')

    def test_tick_scheduler_finishes_loop_without_duplicate_claims(self):
        from gantry.mentor_daemon import tick_mentor
        from test_development import LocalClient
        self.setup_jobs()
        dev_token = self.root/'developer-token'; dev_token.write_text(self.token)
        reviewer_token = self.root/'reviewer-token'; reviewer_token.write_text(self.mentor_token)
        config = {'url':'local-fixture', 'sessions':[self.session['id']], 'parallel':2,
                  'principals':{'admin':str(dev_token),'mentor':str(reviewer_token)}}
        calls = []
        def infer(*args):
            calls.append(args[0]['task'])
            return self.inference(*args)
        with patch.object(mentor_daemon, 'Client', side_effect=lambda url, token: LocalClient(self.service, token)):
            for _ in range(12):
                tick_mentor(config, self.root/'scheduler', infer)
                if all(j['status']=='completed' for j in self.jobs()):
                    break
            self.assertTrue(all(j['status']=='completed' for j in self.jobs()))
            count = len(calls)
            self.assertEqual(tick_mentor(config, self.root/'scheduler', infer), [])
            self.assertEqual(len(calls), count)
        self.assertEqual(calls.count('developer'), 1)
        self.assertEqual(calls.count('reflection'), 1)
        self.assertEqual(calls.count('specialist'), 2)
        self.assertEqual(calls.count('coordinator'), 2)
        self.assertEqual(self.call('review_automation_status', {'session_id':self.session['id']})['policy']['used_jobs'], 6)


if __name__ == '__main__':
    unittest.main()
