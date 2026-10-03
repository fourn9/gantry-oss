"""Unlimited local lifetime/test counts retain revocation, scopes and history."""
import copy
import json
import subprocess
import sys
import unittest

import test_project_connect as fixtures
from gantry.connection_policy import validate_plan
from gantry.model import Fault, digest
from gantry.project_connect import connect, discover, disconnect, Project
from gantry.project_mcp import dispatch, TOOLS
from gantry.project_sandbox import backend


class UnlimitedConnectionTests(unittest.TestCase):
    setUp = fixtures.ConnectTests.setUp
    attach = fixtures.ConnectTests.attach
    checkpoint = fixtures.ConnectTests.checkpoint

    def test_default_survives_long_idle_and_reviewer_still_works(self):
        self.attach(); self.checkpoint()
        before = self.project.context()['connection']
        self.assertIsNone(before['plan']['expires_at'])
        self.assertIsNone(before['effective_expires_at'])
        self.assertIsNone(before['effective_delegation']['max_tests'])
        self.assertIsNone(self.owner.call('development_state', {'session_id': before['session_id']})['session']['max_executions'])
        now = self.project.client.service.clock()
        self.project.client.service.clock = lambda: now + 365*24*3600000
        self.assertEqual(self.project.context()['connection']['session_id'], before['session_id'])
        r = dispatch(self.project, 'project_submit', {'question': 'Check stored source', 'request_id': 'after-idle'})
        prepared = dispatch(self.project, 'project_mentor_prepare', {'submission_id': r['id']})
        self.assertEqual(prepared['context']['state_id'], before['state_id'])
        self.assertTrue(self.owner.call('replay')['matched'])

    def test_ttl_can_exceed_eight_hours_and_explicit_ttl_remains_enforced(self):
        self.attach(ttl=72*3600)
        now = self.project.client.service.clock()
        self.project.client.service.clock = lambda: now + 9*3600000
        self.project.context()
        self.project.client.service.clock = lambda: now + 73*3600000
        with self.assertRaises(Fault) as error: self.project.context()
        self.assertEqual(error.exception.code, 'unauthorized')

    def test_legacy_count_never_blocks_and_duplicate_request_counts_once(self):
        plan, _ = discover(self.root)
        self.attach(delegation={**plan['delegation'], 'max_tests': 10})
        args = {'operation': 'test', 'input_hash': digest({}), 'command': 'test',
                'command_hash': digest(plan['commands']['test'])}
        for index in range(15):
            key = 'attempt-' + str(index)
            result = self.project.client.call('authorize_connection_operation', args, key)
            self.assertEqual(self.project.client.call('authorize_connection_operation', args, key), result)
        context = self.project.context()['connection']
        self.assertEqual(context['tests_used'], 15)
        self.assertEqual(context['plan']['delegation']['max_tests'], 10)
        self.assertIsNone(context['effective_delegation']['max_tests'])
        with self.assertRaises(Fault):
            self.project.client.call('authorize_connection_operation', {**args, 'command': 'unapproved'}, 'bad-command')
        self.assertEqual(self.project.context()['connection']['tests_used'], 15)
        self.assertTrue(self.owner.call('replay')['matched'])

    def test_thirteen_real_sandboxed_tests_and_retry(self):
        if not backend(): self.skipTest('Supported command sandbox unavailable')
        (self.root/'control.py').write_text('def clamp(x):\n    return max(0, min(x, 10))\n')
        self.attach()
        for index in range(13):
            self.project.operate('test', {'command': 'test'}, 'real-test-' + str(index))
        self.project.operate('test', {'command': 'test'}, 'real-test-12')
        inspected = self.owner.call('inspect_connection', {'connection_id': self.project.receipt['connection_id']})
        tests = [x for x in inspected['operations'] if x['operation'] == 'test']
        self.assertEqual(len(tests), 13)
        self.assertTrue(all(x['status'] == 'completed' for x in tests))
        self.assertEqual(inspected['connection']['tests_used'], 13)

    def test_expired_connection_owner_renewal_preserves_state_roles_and_original_approval(self):
        self.attach(ttl=60); self.checkpoint()
        before = self.project.context()['connection']; now = self.project.client.service.clock()
        bot = dispatch(self.project, 'project_bot', {})
        self.project.client.service.clock = lambda: now + 61000
        with self.assertRaises(Fault): self.project.context()
        renewed = self.owner.call('remove_connection_limits', {'connection_id': before['id']}, 'unlimit-once')
        self.assertIsNone(renewed['effective_expires_at'])
        for field in ('plan', 'plan_hash', 'principal', 'mentor', 'session_id', 'state_id'):
            self.assertEqual(renewed[field], before[field])
        self.assertEqual(dispatch(self.project, 'project_bot', {})['bot_id'], bot['bot_id'])
        self.assertEqual(self.owner.call('remove_connection_limits', {'connection_id': before['id']}, 'unlimit-once'), renewed)
        self.assertTrue(self.owner.call('verify')['valid'])
        self.assertTrue(self.owner.call('replay')['matched'])
        with self.assertRaises(Fault):
            self.project.client.call('remove_connection_limits', {'connection_id': before['id']})
        self.assertNotIn('project_unlimit', TOOLS)
        disconnect(self.root)
        with self.assertRaises(Fault):
            self.owner.call('remove_connection_limits', {'connection_id': before['id']}, 'cannot-revive')

    def test_cli_owner_removes_expiry_without_new_connection(self):
        self.attach(ttl=60)
        result = subprocess.run([sys.executable, '-m', 'gantry', 'project', 'unlimit', '--root', str(self.root),
            '--request-id', 'owner-unlimit'], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(json.loads(result.stdout)['effective_expires_at'])
        self.assertEqual(Project(self.root).context()['connection']['id'], self.project.receipt['connection_id'])

    def test_invalid_expiries_are_rejected_and_active_ttl_is_not_silently_ignored(self):
        plan, _ = discover(self.root)
        for value in (False, 'forever', 0):
            invalid = copy.deepcopy(plan); invalid['expires_at'] = value
            with self.assertRaises(Fault): validate_plan(invalid)
        self.attach()
        with self.assertRaises(Fault) as error: connect(self.root, ttl=3600)
        self.assertEqual(error.exception.code, 'reauthorization_required')
