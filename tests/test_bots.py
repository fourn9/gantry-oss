"""Synthetic customer-agent handoff; no external inference or private data."""
import copy
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_mentor_jobs as jobs_fixture
import test_project_connect as connect_fixture
from gantry.mentor_daemon import process_job
from gantry.service import Service
from gantry.model import Fault
from gantry.connection_policy import OPERATIONS
from gantry.project_connect import Project, owner_client
from gantry.project_mcp import dispatch
from test_development import LocalClient


def profile(mission='Preserve system interfaces'):
    return {'mission': mission, 'responsibilities': ['Report open integration risks'],
        'focus_paths': ['input.txt'], 'workflow': ['Check fixed inputs before editing'],
        'report_when': ['Before integration', 'When an assumption changes'],
        'style': 'Concise, cite measured evidence and unknowns', 'onboarding': ['Never equate partial and system acceptance']}


class BotTests(unittest.TestCase):
    setUp = jobs_fixture.MentorJobsTests.setUp
    tearDown = jobs_fixture.MentorJobsTests.tearDown
    call = jobs_fixture.MentorJobsTests.call
    artifact = jobs_fixture.MentorJobsTests.artifact
    policy = jobs_fixture.MentorJobsTests.policy
    connect = jobs_fixture.MentorJobsTests.connect
    detail = jobs_fixture.MentorJobsTests.detail
    fault = jobs_fixture.MentorJobsTests.fault
    initialize = jobs_fixture.MentorJobsTests.initialize
    begin = jobs_fixture.MentorJobsTests.begin
    checkpoint = jobs_fixture.MentorJobsTests.checkpoint
    setup_review = jobs_fixture.MentorJobsTests.setup_review
    submit = jobs_fixture.MentorJobsTests.submit
    output = jobs_fixture.MentorJobsTests.output
    setup_jobs = jobs_fixture.MentorJobsTests.setup_jobs
    jobs = jobs_fixture.MentorJobsTests.jobs
    job = jobs_fixture.MentorJobsTests.job
    inference = jobs_fixture.MentorJobsTests.inference
    run_job = jobs_fixture.MentorJobsTests.run_job

    def context(self, r, role='mechanical', client=None):
        return (client or self.mentor).call('get_bot_context',
            {'session_id': r['session_id'], 'state_id': r['state_id'], 'role': role})

    def memory(self, r, **extra):
        return self.mentor.call('record_bot_memory', {'session_id': r['session_id'], 'role': 'mechanical',
            'state_id': r['state_id'], 'visibility': 'role', 'observation': 'Interface assumptions need a consumer check',
            'applicability': 'Before integration', 'limitations': ['Synthetic observation'], 'evidence': [r['state_id']],
            'paths': ['input.txt'], 'assessment': 'inconclusive', **extra})

    def test_proposed_hierarchy_needs_owner_and_invalidates_old_work(self):
        r = self.setup_jobs()
        config = copy.deepcopy(self.team_args); config['version'] = 1
        config['members'][1]['profile'] = profile()
        proposal = self.mentor.call('propose_review_team', {'configuration': config,
            'reason': 'Explicit integration ownership', 'evidence': [r['state_id']]})
        self.assertEqual(proposal['status'], 'proposed')
        self.assertEqual(self.call('get_review_team', {'session_id': r['session_id']})['team']['version'], 1)
        self.fault('human_approval_required', lambda: self.mentor.call('activate_team_proposal', {'proposal_id': proposal['id']}))
        activated = self.call('activate_team_proposal', {'proposal_id': proposal['id']})
        self.assertEqual(activated['team']['version'], 2)
        self.assertEqual(self.context(r, 'integration')['profile']['mission'], profile()['mission'])
        self.fault('mode_disabled', lambda: self.run_job('specialist'))
        self.assertTrue(self.call('replay')['matched'])

    def test_three_levels_report_bottom_up_and_resume_in_another_worker(self):
        r = self.setup_jobs()
        config = copy.deepcopy(self.team_args); config['version'] = 1
        config['members'][2]['parent_role'] = 'engineering'
        config['members'][2]['profile'] = profile('Check geometry at subsystem boundaries')
        config['members'].append({'principal_id': 'mentor', 'side': 'gantry', 'role': 'engineering',
            'parent_role': 'integration', 'profile': profile('Reconcile subsystem reports')})
        self.call('configure_review_team', config)
        self.call('configure_review_automation', {'session_id': r['session_id'], 'version': 1, 'enabled': True,
            'max_rounds': 1, 'max_jobs': 20, 'developer_principal': 'admin'})
        r = self.submit(self.cp['change'])
        self.assertEqual(set(r['required_roles']), {'mechanical', 'engineering'})
        job = lambda role: next(j for j in self.jobs() if j['submission_id'] == r['id'] and j['role'] == role)
        self.fault('review_pending', lambda: self.mentor.call('claim_mentor_job', {'job_id': job('engineering')['id'], 'lease_seconds': 60}))
        seen = []
        def infer(ctx, schema, directory):
            seen.append(ctx['review']['bot_context'])
            return self.inference(ctx, schema, directory)
        process_job(self.mentor, job('mechanical')['id'], self.root/'personal-jobs', infer)
        # A fresh service/client has no worker conversation history.
        other = LocalClient(Service(self.service.store.directory, clock=self.service.clock), self.mentor_token)
        process_job(other, job('engineering')['id'], self.root/'personal-jobs', infer)
        process_job(other, job('integration')['id'], self.root/'personal-jobs', infer)
        self.assertEqual([x['role'] for x in seen], ['mechanical', 'engineering', 'integration'])
        self.assertEqual(seen[1]['profile']['mission'], 'Reconcile subsystem reports')
        self.assertTrue(self.call('replay')['matched'])

    def test_role_memory_is_durable_scoped_and_requires_rechecking_changed_inputs(self):
        r = self.setup_jobs(); memory = self.memory(r)
        personal = self.context(r)
        self.assertEqual(personal['memory']['items'][0]['id'], memory['id'])
        self.assertFalse(self.context(r, 'integration')['memory']['items'])
        self.fault('unauthorized', lambda: self.context(r, 'developer'))
        self.memory(r, visibility='team', assessment='contradicted', contradicts=memory['id'])
        self.assertEqual(len(self.context(r)['memory']['items']), 2)
        self.assertEqual(len(self.context(r, 'integration')['memory']['items']), 1)
        cp = self.checkpoint(self.cp['change'], {'input.txt': 'a different input'})
        changed = self.context({**r, 'state_id': cp['state']['id']})
        self.assertEqual(changed['memory']['items'][0]['application']['inputs'], 'changed_recheck_required')
        self.fault('invalid_input', lambda: self.memory(r, evidence=['missing-evidence']))
        self.fault('invalid_input', lambda: self.memory(r, paths=['missing.txt']))
        self.assertTrue(self.call('replay')['matched'])

    def test_reflection_is_reused_in_next_actual_inference_input(self):
        self.setup_jobs(); self.run_job('specialist'); self.run_job('coordinator'); self.run_job('developer')
        self.run_job('reflection')
        job = self.job('specialist'); seen = []
        def infer(ctx, schema, directory):
            seen.extend(ctx['review']['bot_context']['memory']['items'])
            return self.inference(ctx, schema, directory)
        process_job(self.mentor, job['id'], self.root/'next-worker', infer)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]['source'], 'review_reflection')
        self.assertEqual(seen[0]['status'], 'hypothesis')
        self.assertEqual(seen[0]['application']['inputs'], 'recorded_paths_unchanged')
        self.assertTrue(self.call('replay')['matched'])

    def test_question_answer_and_explicit_resolution_gate_ok(self):
        r = self.setup_jobs(); self.run_job('specialist')
        args = {'submission_id': r['id'], 'role': 'mechanical', 'to_role': 'developer',
            'kind': 'question', 'body': 'Is the interface contract preserved?', 'evidence': [r['state_id']], 'blocking': True}
        m = self.mentor.call('send_team_message', args, 'question-once')
        self.assertEqual(self.mentor.call('send_team_message', args, 'question-once'), m)
        answer = self.call('send_team_message', {**args, 'role': 'developer', 'to_role': 'mechanical',
            'kind': 'answer', 'body': 'Evidence attached; needs your confirmation', 'blocking': False, 'reply_to': m['id']})
        self.assertEqual(answer['reply_to'], m['id'])
        self.fault('unauthorized', lambda: self.mentor.call('send_team_message', {**args, 'role': 'developer'}))
        lease = self.mentor.call('claim_change_review', {'submission_id': r['id'], 'lease_seconds': 60})
        finish = lambda: self.mentor.call('complete_change_review', {'submission_id': r['id'], 'fence': lease['fence'],
            'context_fingerprint': self.call('get_change_review', {'submission_id': r['id']})['context_fingerprint'],
            'output': self.output(r, 'ok')})
        self.fault('review_pending', finish)
        self.mentor.call('resolve_team_message', {'message_id': m['id'], 'reason': 'Evidence addresses the interface', 'evidence': [r['state_id']]})
        self.assertEqual(finish()['output']['verdict'], 'ok')
        self.assertTrue(self.call('replay')['matched'])

    def test_new_question_invalidates_old_inference_and_blocks_execution(self):
        r = self.setup_jobs(); self.run_job('specialist')
        job = self.job('coordinator')
        claim = self.mentor.call('claim_mentor_job', {'job_id': job['id'], 'lease_seconds': 60})
        self.mentor.call('send_team_message', {'submission_id': r['id'], 'role': 'mechanical', 'to_role': 'integration',
            'kind': 'dependency', 'body': 'Consumer input changed', 'evidence': [r['state_id']], 'blocking': True})
        self.fault('stale_basis', lambda: self.mentor.call('finish_mentor_job', {'job_id': job['id'], 'fence': claim['fence'],
            'output': self.output(r), 'provider': {'kind': 'fixture'}}))

    def test_foreign_session_evidence_and_onboarding_are_rejected(self):
        r = self.setup_jobs()
        self.session = self.connect()
        other = self.initialize()
        self.fault('invalid_input', lambda: self.memory(r, evidence=[other['id']]))
        self.fault('unauthorized', lambda: self.context({**r, 'state_id': other['id']}))
        self.assertFalse(self.context(r)['memory']['items'])


class ProjectBotTests(unittest.TestCase):
    setUp = connect_fixture.ConnectTests.setUp
    attach = connect_fixture.ConnectTests.attach
    checkpoint = connect_fixture.ConnectTests.checkpoint

    def test_cli_owner_setup_upgrades_legacy_facade_without_expanding_file_scope(self):
        with patch('gantry.connections.OPERATIONS', [x for x in OPERATIONS if not x.startswith('connection_team')]):
            self.attach()
        before = self.project.context()['connection']['plan']
        with self.assertRaises(Fault): dispatch(self.project, 'project_bot', {})
        p = profile(); p['focus_paths'] = ['control.py']
        result = subprocess.run([sys.executable, '-m', 'gantry', 'project', 'team', '--root', str(self.root), '--input', '-',
            '--request-id', 'owner-team-1'], input=json.dumps({'version': 1, 'profiles': {'developer': p}}),
            text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([sys.executable, '-m', 'gantry', 'project', 'bot', '--root', str(self.root)],
            text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['profile']['mission'], p['mission'])
        self.assertEqual(self.project.context()['connection']['plan'], before)
        self.assertTrue(self.owner.call('replay')['matched'])

    def test_facade_cannot_change_role_scope_or_use_read_to_write(self):
        self.attach(ttl=60)
        with self.assertRaises(Fault) as error:
            self.project.client.call('connection_team', {'action': 'context', 'arguments': {'session_id': 'other'}})
        self.assertEqual(error.exception.code, 'scope_denied')
        with self.assertRaises(Fault) as error:
            self.project.client.call('connection_team_read', {'action': 'remember', 'arguments': {}})
        self.assertEqual(error.exception.code, 'invalid_input')
        with self.assertRaises(Fault) as error:
            self.project.client.call('configure_connection_team', {'connection_id': self.project.receipt['connection_id'],
                'version': 1, 'profiles': {'developer': profile()}})
        self.assertEqual(error.exception.code, 'unauthorized')
        expires = self.project.context()['connection']['plan']['expires_at']
        self.project.client.service.clock = lambda: expires + 1
        with self.assertRaises(Fault): dispatch(self.project, 'project_bot', {})

    def test_local_customer_agent_profiles_memory_and_handoff(self):
        self.attach(); self.checkpoint()
        owner = owner_client(self.project.meta)
        sid = self.project.context()['connection']['session_id']
        team = owner.call('get_review_team', {'session_id': sid})['team']
        p = profile(); p['focus_paths'] = []
        owner.call('configure_connection_team', {'connection_id': self.project.receipt['connection_id'],
            'version': team['version'], 'profiles': {'developer': p, 'mentor': p}})
        context = dispatch(self.project, 'project_bot', {})
        memory = dispatch(self.project, 'project_remember', {'visibility': 'team',
            'observation': 'Check the public function signature', 'applicability': 'When editing controller',
            'limitations': ['Fixture only'], 'evidence': [context['state']['id']], 'paths': ['control.py'],
            'assessment': 'inconclusive', 'request_id': 'lesson1'})
        resumed = Project(self.root)
        again = dispatch(resumed, 'project_bot', {})
        self.assertEqual(context['bot_id'], again['bot_id'])
        self.assertEqual(memory['id'], again['memory']['items'][0]['id'])
        review = dispatch(resumed, 'project_submit', {'question': 'Check the signature', 'request_id': 'review1'})
        prepared = dispatch(resumed, 'project_mentor_prepare', {'submission_id': review['id']})
        bot = prepared['context']['bot_context']
        self.assertEqual(bot['role'], 'mentor')
        self.assertEqual(bot['profile']['mission'], p['mission'])
        self.assertEqual(bot['memory']['items'][0]['id'], memory['id'])
        self.assertFalse(any('token' in key for key in bot))
        self.assertTrue(owner.call('replay')['matched'])
