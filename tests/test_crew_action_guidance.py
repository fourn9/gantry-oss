"""Anonymous regressions for actionable, bounded Crew protocol feedback."""
import json
import unittest

from gantry.crew_runtime import _context_value, _execute
from gantry.model import Fault
import test_bot_development as fixtures


class CrewActionGuidanceTests(unittest.TestCase):
    def setUp(self):
        self.c = fixtures.BotDevelopmentTests()
        self.c.setUp()
        self.addCleanup(self.c.tearDown)

    def other_project(self):
        c = self.c
        session = c.owner.call('connect_development', {
            'title': 'Unrelated anonymous project', 'snapshot': c.base['snapshot'],
            'capture': {'scope': 'Anonymous files', 'missing': []}, 'unverified': [], **c.policy})
        state = c.owner.call('initialize_continuity', {'session_id': session['id'],
            'version': session['version'], 'hierarchy': [{'id': 'assembly', 'title': 'Other assembly',
                'kind': 'subsystem', 'paths': ['mechanical.txt', 'control.txt'], 'editable': True}], 'context': {
                'requirements': [], 'constraints': [], 'decisions': [],
                'open_questions': [], 'environment': {}}, 'summary': 'Other baseline'})
        return session, state

    def test_evidence_guidance_names_record_kinds_and_file_remedy_without_disclosure(self):
        c = self.c
        _, foreign = self.other_project()
        task = c.task('lead')
        rejected = ['private/input.txt', foreign['id'], 'unknown-private-record']
        failures = []
        with c.worker('lead') as worker:
            claim = c.clients['lead'].call('claim_bot_task', {'task_id': task['id'],
                'version': task['version'], 'runtime_fence': worker.runtime['fence']})
            args = {'task_id': task['id'], 'fence': claim['task']['fence'],
                'verdict': 'continue', 'targets': [task['id']], 'rationale': 'Inspect source evidence',
                'alternatives': [], 'conditions': []}
            for invalid in rejected:
                with self.assertRaises(Fault) as caught:
                    c.clients['lead'].call('record_bot_decision', {**args, 'evidence': [invalid]})
                self.assertEqual(caught.exception.code, 'invalid_input')
                failures.append(caught.exception.as_dict())
            # Valid saved references remain usable after the rejected requests.
            accepted = c.clients['lead'].call('record_bot_decision', {**args,
                'evidence': [c.base['id']], 'rationale': 'File mechanical.txt at its saved state and hash'})
            self.assertEqual(accepted['evidence'], [c.base['id']])
        self.assertTrue(all(failure == failures[0] for failure in failures))
        text = json.dumps(failures[0]).lower()
        for value in rejected:
            self.assertNotIn(value.lower(), text)
        self.assertLess(len(text), 4096)
        for term in ('state', 'task', 'message', 'action', 'decision', 'issue', 'path', 'hash', 'rationale'):
            self.assertIn(term, text)

    def test_bad_inspect_pointer_suggests_authorized_root_keys_not_values(self):
        c = self.c
        task = c.task('designer')
        view = c.clients['lead'].call('get_bot_task', {'task_id': task['id']})
        view['task']['reports'] = [{'report': {'summary': 'private-nested-value'}}]
        with self.assertRaises(Fault) as caught:
            _context_value(view, {'pointer': '/reports'})
        self.assertEqual(caught.exception.code, 'not_found')
        details = caught.exception.details
        self.assertIn('task', details.get('available_keys', []))
        self.assertTrue(set(details['available_keys']) <= set(view))
        self.assertNotIn('private-nested-value', json.dumps(details))
        self.assertNotIn(task['id'], json.dumps(details))

    def test_pointer_suggestions_are_bounded_even_for_large_authorized_objects(self):
        view = {'field-' + str(i) + '-' + 'x' * 1000: 'private-value' for i in range(500)}
        with self.assertRaises(Fault) as caught:
            _context_value(view, {'pointer': '/missing'})
        details = caught.exception.details
        self.assertTrue(details.get('available_keys'))
        self.assertLessEqual(len(details['available_keys']), 32)
        self.assertLess(len(json.dumps(details)), 4096)
        self.assertNotIn('private-value', json.dumps(details))

    def test_cross_project_inspect_does_not_offer_foreign_keys_or_records(self):
        c = self.c
        session, state = self.other_project()
        c.owner.call('configure_bot_project', {'session_id': session['id'], 'organization_id': 'team',
            'version': 0, 'lead_bot_id': 'lead', 'goal': 'Other work', 'acceptance': ['Other scope'], 'enabled': True})
        c.owner.call('bind_development_bot', {'session_id': session['id'], 'bot_id': 'lead',
            'principal_id': 'lead', 'version': 0, 'write_scope': c.scope('lead'),
            'can_assign': True, 'can_integrate': True, 'enabled': True})
        foreign = c.owner.call('assign_bot_task', {'session_id': session['id'],
            **c.assignment('lead', state_id=state['id'])})
        task = c.task('lead')
        context = c.clients['lead'].call('get_bot_task', {'task_id': task['id']})
        with self.assertRaises(Fault) as caught:
            _execute(c.clients['lead'], context, {}, {}, 'inspect',
                {'task_id': foreign['id'], 'pointer': '/reports'}, c.root, c.root, 'fixture-inspect')
        self.assertEqual(caught.exception.code, 'scope_denied')
        self.assertNotIn('available_keys', caught.exception.details)
        self.assertNotIn(foreign['id'], json.dumps(caught.exception.as_dict()))

    def test_escaped_keys_remain_navigable_and_unicode_suggestions_are_bounded(self):
        view = {'a/b~c': 'authorized value', **{'\u90e8\u54c1' * 1000 + str(i): 'hidden value' for i in range(40)}}
        self.assertEqual(_context_value(view, {'pointer': '/a~1b~0c'})['value'], 'authorized value')
        with self.assertRaises(Fault) as caught:
            _context_value(view, {'pointer': '/missing'})
        details = caught.exception.details
        self.assertIn('a/b~c', details['available_keys'])
        self.assertTrue(details['keys_omitted'])
        self.assertLess(len(json.dumps(details).encode()), 4096)
        self.assertNotIn('hidden value', json.dumps(details))
