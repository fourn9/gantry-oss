import json
from urllib.request import urlopen
import unittest
import test_interfaces as fixtures


class WebTests(unittest.TestCase):
    setUp = fixtures.InterfaceTests.setUp
    tearDown = fixtures.InterfaceTests.tearDown

    def test_web_assets_have_content_security_policy_and_no_credentials(self):
        for path, mime in [('/', 'text/html'), ('/app.js', 'text/javascript'), ('/review_views.js', 'text/javascript'), ('/style.css', 'text/css')]:
            with urlopen(self.url + path) as response:
                text = response.read().decode()
                self.assertIn(mime, response.headers['Content-Type'])
                self.assertIn("script-src 'self'", response.headers['Content-Security-Policy'])
                self.assertNotIn(self.token, text)

    def test_review_context_is_version_fixed_and_redacts_identity(self):
        me = self.client.call('identity')
        self.assertEqual(me['kind'], 'human')
        self.assertNotIn('token_hash', me)
        p = self.client.call('propose', {'title': 'hand', 'changes': [
            {'id': 'hand', 'type': 'subsystem', 'data': {'finger_length_mm': 80}}]})
        context = self.client.call('review_context', {'proposal_id': p['id']})
        self.assertEqual(context['candidate']['id'], p['candidate_id'])
        self.assertIsNone(context['changes'][0]['before'])
        self.assertEqual(context['changes'][0]['after']['data']['finger_length_mm'], 80)
        self.assertTrue(context['can_human_review'])
        self.assertEqual(context['results'], [])
        changed = self.client.call('amend', {'proposal_id': p['id'], 'version': 1, 'changes': [
            {'id': 'hand', 'type': 'subsystem', 'data': {'finger_length_mm': 90}}]})
        self.assertNotEqual(changed['candidate_id'], context['candidate']['id'])
        self.assertEqual(context['changes'][0]['after']['data']['finger_length_mm'], 80)
        latest = self.client.call('review_context', {'proposal_id': p['id']})
        versions = latest['candidate_versions']
        self.assertEqual([v['version'] for v in versions], [1, 2])
        self.assertEqual([v['candidate_id'] for v in versions], [p['candidate_id'], changed['candidate_id']])
        old_design = self.client.call('design', {'design_id': versions[0]['candidate_id']})
        self.assertEqual(old_design['contents']['hand']['data']['finger_length_mm'], 80)


    def test_review_context_includes_unchanged_dependency_at_candidate_version(self):
        p = self.client.call('propose', {'title': 'initial hand', 'changes': [
            {'id': 'hand', 'type': 'subsystem', 'data': {'length': 80}},
            {'id': 'control', 'type': 'subsystem', 'data': {'length': 80}},
            {'id': 'dependency', 'type': 'relation', 'data': {
                'kind': 'depends_on', 'source': 'control', 'target': 'hand'}}]})
        args = {'proposal_id': p['id'], 'version': 1}
        self.client.call('submit', args)
        self.client.call('endorse', {**args, 'reason': 'test'})
        self.client.call('review_adoption', {**args, 'reason': 'test', 'verdict': 'approve'})
        self.client.call('commit', args)
        base = self.client.call('state')['entries']
        q = self.client.call('propose', {'title': 'longer fingers', 'changes': [
            {'id': 'hand', 'type': 'subsystem', 'data': {'length': 90},
             'expected_revision': base['hand']['revision_id']}]})
        ctx = self.client.call('review_context', {'proposal_id': q['id']})
        self.assertEqual(len(ctx['changes']), 1)
        self.assertEqual(ctx['candidate_contents']['dependency']['revision_id'], base['dependency']['revision_id'])
        self.assertEqual(ctx['changes'][0]['before']['data']['length'], 80)
        self.assertEqual(ctx['candidate_contents']['hand']['data']['length'], 90)
        self.assertEqual(ctx['candidate_contents']['control']['data']['length'], 80)

    def test_discussion_evidence_survives_candidate_revision_and_reaches_agent_context(self):
        p = self.client.call('propose', {'title': 'caster', 'changes': [
            {'id': 'caster', 'type': 'subsystem', 'data': {'radius': 15}}]})
        w = self.client.call('create_work', {'title': 'step trial', 'completion_condition': 'record result',
                                          'proposal_id': p['id'], 'design_id': p['candidate_id']})
        result = self.client.call('record', {'type': 'eval_result', 'data': {
            'run_id': 'stalled', 'verdict': 'fail', 'design_revision': p['candidate_id']}})
        message = self.client.call('discuss', {'target': p['id'], 'body': 'Rear caster stopped at the edge.',
            'evidence': [result['revision_id']], 'basis': {'source': 'simulation'}})
        self.client.call('discuss', {'target': w['id'], 'body': 'Test a larger rolling wheel.'})
        unrelated = self.client.call('create_work', {'title': 'other', 'completion_condition': 'other'})
        self.client.call('discuss', {'target': unrelated['id'], 'body': 'Unrelated work'})
        self.client.call('amend', {'proposal_id': p['id'], 'version': 1, 'changes': [
            {'id': 'caster', 'type': 'subsystem', 'data': {'radius': 30}}]})
        ctx = self.client.call('review_context', {'proposal_id': p['id']})
        self.assertEqual(len(ctx['discussions']), 2)
        note = next(e for e in ctx['discussions'] if e['id'] == message['id'])
        self.assertEqual(note['data']['design_revision'], p['candidate_id'])
        self.assertEqual(note['data']['evidence'], [result['revision_id']])
        self.assertEqual(note['data']['basis'], {'source': 'simulation'})
        self.assertEqual(note['actor'], self.client.call('identity')['id'])
        self.assertGreater(note['seq'], 0)
        self.assertEqual(len(self.client.call('context', {'work_id': w['id']})['discussions']), 2)


if __name__ == '__main__': unittest.main()
