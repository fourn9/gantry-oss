"""Project reviews continue past legacy quotas without expanding other rights."""
import copy
import json
import subprocess
import sys
import unittest

import test_project_connect as fixtures
from gantry.model import Fault, digest
from gantry.project_connect import connect, discover, disconnect
from gantry.project_mcp import dispatch


class UnlimitedReviewTests(unittest.TestCase):
    setUp = fixtures.ConnectTests.setUp
    attach = fixtures.ConnectTests.attach
    checkpoint = fixtures.ConnectTests.checkpoint

    def review_cycles(self, count):
        for i in range(count):
            self.checkpoint('save-' + str(i))
            request = {'question': 'Inspect the saved source', 'request_id': 'submit-' + str(i)}
            submission = dispatch(self.project, 'project_submit', request)
            self.assertEqual(dispatch(self.project, 'project_submit', request), submission)
            prepared = dispatch(self.project, 'project_mentor_prepare', {'submission_id': submission['id']})
            self.assertIn('does not cap', prepared['context']['review_count_policy'])
            output = {'verdict': 'conditional', 'scope': 'Synthetic source only',
                'rationale': 'Physical behavior is outside this fixture',
                'evidence': [prepared['context']['state_id']], 'unverified': ['Physical behavior'],
                'findings': [], 'prediction': 'Needs separate validation'}
            result = dispatch(self.project, 'project_mentor_finish',
                {'submission_id': submission['id'], 'output': output})
            self.assertEqual(result['status'], 'completed')
        self.assertEqual(self.project.context()['connection']['reviews_used'], count)
        self.assertEqual(self.project.context()['development']['status']['adoption'], 'unadopted')
        self.assertTrue(self.owner.call('verify')['valid'])
        self.assertTrue(self.owner.call('replay')['matched'])

    def test_new_connection_can_complete_five_reviews_without_reconnect(self):
        self.attach()
        original = self.project.context()['connection']
        self.assertIsNone(original['plan']['delegation']['max_reviews'])
        self.assertIsNone(self.prompts[0]['delegation']['max_reviews'])
        self.review_cycles(5)
        current = self.project.context()['connection']
        self.assertEqual(current['id'], original['id'])
        self.assertEqual(current['plan_hash'], original['plan_hash'])

    def test_legacy_connection_quota_is_ignored_without_rewriting_approval(self):
        plan, _ = discover(self.root)
        legacy = {**plan['delegation'], 'max_reviews': 3}
        self.attach(delegation=legacy)
        original = copy.deepcopy(self.project.context()['connection'])
        self.review_cycles(5)
        current = self.project.context()['connection']
        self.assertEqual(current['plan'], original['plan'])
        self.assertEqual(current['plan_hash'], digest(original['plan']))
        self.assertEqual(current['plan']['delegation']['max_reviews'], 3)
        self.assertIsNone(current['effective_delegation']['max_reviews'])
        self.assertTrue(connect(self.root, delegation={**legacy, 'max_reviews': None},
            confirm=lambda _: self.fail('No new scope or permission to approve'))['resumed'])

    def test_legacy_pending_plan_keeps_approval_hash_and_shows_effective_policy(self):
        plan, _ = discover(self.root)
        legacy = {**plan['delegation'], 'max_reviews': 3}
        prepared = connect(self.root, delegation=legacy, prepare=True)
        self.assertIsNone(prepared['preview']['delegation']['max_reviews'])
        self.assertIn('does not cap', prepared['preview']['review_count_policy'])
        approved = connect(self.root, delegation={**legacy, 'max_reviews': None},
            approval=prepared['preview']['approval_hash'])
        self.assertEqual(approved['status'], 'connected')

    def test_cli_default_and_explicit_delegations_show_no_review_cap(self):
        for extra in ([], ['--goal', 'Inspect control', '--done', 'Save evidence']):
            result = subprocess.run([sys.executable, '-m', 'gantry', 'connect', str(self.root),
                '--prepare', *extra], text=True, capture_output=True, check=True)
            preview = json.loads(result.stdout)['preview']
            self.assertIsNone(preview['delegation']['max_reviews'])
            self.assertIsNone(preview['delegation']['max_tests'])
            self.assertEqual(preview['delegation']['max_branches'], 3)
            disconnect(self.root)

    def test_test_counts_are_audit_only_explicit_expiry_and_revocation_still_apply(self):
        plan, _ = discover(self.root)
        self.attach(delegation={**plan['delegation'], 'max_tests': 1}, ttl=60)
        args = {'operation': 'test', 'input_hash': digest({}), 'command': 'test',
            'command_hash': digest(plan['commands']['test'])}
        self.project.client.call('authorize_connection_operation', args, 'first-test')
        self.project.client.call('authorize_connection_operation', args, 'second-test')
        self.assertEqual(self.project.context()['connection']['tests_used'], 2)
        self.checkpoint()
        clock = self.project.client.service.clock
        now = clock(); self.project.client.service.clock = lambda: now + 61000
        with self.assertRaises(Fault) as error:
            self.project.operate('submit', {'question': 'Expired'}, 'expired-review')
        self.assertEqual(error.exception.code, 'unauthorized')
        self.project.client.service.clock = clock
        disconnect(self.root)
        with self.assertRaises(Fault) as error:
            self.project.operate('submit', {'question': 'Revoked'}, 'revoked-review')
        self.assertEqual(error.exception.code, 'unauthorized')
