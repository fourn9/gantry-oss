import unittest
import test_service as fixtures
from gantry.mcp import tool_list


class FocusedContextTests(unittest.TestCase):
    setUp = fixtures.LedgerTests.setUp
    tearDown = fixtures.LedgerTests.tearDown
    call = fixtures.LedgerTests.call
    assertFault = fixtures.LedgerTests.assertFault

    def scenario(self):
        changes = [{'id': key, 'type': 'subsystem', 'data': {'name': key}}
                   for key in ['cable', 'clamp', 'roof', 'camera']]
        for source, target in [('cable', 'clamp'), ('clamp', 'roof'), ('roof', 'cable'), ('camera', 'roof')]:
            changes.append({'id': source + '-on-' + target, 'type': 'relation',
                            'data': {'kind': 'depends_on', 'source': source, 'target': target}})
        p = self.call('propose', {'title': 'Assembly', 'changes': changes})
        w = self.call('create_work', {'title': 'Cable test', 'completion_condition': 'Evidence',
                       'design_id': p['candidate_id'], 'proposal_id': p['id']})
        return p, w

    def focused(self, w, **extra):
        return self.call('context', {'work_id': w['id'], 'view': 'focused', 'entry_ids': ['cable'], **extra})

    def test_follows_transitive_dependencies_in_cycle_not_reverse_impact(self):
        p, w = self.scenario()
        full = self.call('context', {'work_id': w['id']})
        result = self.focused(w)
        self.assertEqual(set(result['contents']), {'cable', 'clamp', 'roof',
                         'cable-on-clamp', 'clamp-on-roof', 'roof-on-cable'})
        self.assertEqual(result['scope']['dependency_paths']['roof'], ['cable', 'cable-on-clamp', 'clamp', 'clamp-on-roof', 'roof'])
        self.assertNotIn('changes', result['proposal'])
        self.assertIn('changes', full['proposal'])
        self.assertNotIn('scope', full)
        for key, entry in result['contents'].items():
            self.assertEqual(entry, full['contents'][key])
        self.assertEqual(self.call('context', {'work_id': w['id'], 'view': 'full'}), full)

    def test_pages_only_relevant_discussion_and_marks_candidate_mismatch(self):
        p, w = self.scenario()
        self.call('discuss', {'target': p['id'], 'body': 'old candidate'})
        changed = [{k: c[k] for k in ['id', 'type', 'data']} for c in p['changes']]
        new = self.call('amend', {'proposal_id': p['id'], 'version': p['version'], 'changes': changed})
        self.call('discuss', {'target': p['id'], 'body': 'new candidate'})
        for i in range(5):
            self.call('discuss', {'target': w['id'], 'body': f'work {i}'})
        other = self.call('create_work', {'title': 'Other', 'completion_condition': 'Other'})
        self.call('discuss', {'target': other['id'], 'body': 'unrelated'})
        page = self.focused(w, discussion_limit=2)
        self.assertEqual(page['design']['id'], p['candidate_id'])
        self.assertEqual(page['proposal']['candidate_id'], new['candidate_id'])
        self.assertFalse(page['scope']['proposal_current_candidate_matches_work'])
        self.assertEqual(page['scope']['omitted_other_candidate_discussion_count'], 1)
        rows = list(page['discussions'])
        while page['scope']['has_older_discussions']:
            page = self.focused(w, discussion_limit=2,
                                before_discussion_seq=page['scope']['next_before_discussion_seq'])
            rows += page['discussions']
        self.assertEqual(len(rows), 6)
        self.assertEqual(len({r['revision_id'] for r in rows}), 6)
        self.assertEqual({r['data']['body'] for r in rows}, {'old candidate', *[f'work {i}' for i in range(5)]})

    def test_operation_heads_and_open_questions_not_silently_dropped(self):
        _, w = self.scenario()
        op = self.call('record', {'type': 'development_operation', 'data': {
            'work_item': w['id'], 'tool': 'test', 'status': 'unknown', 'capture_scope': 'fixture'}})
        updated = self.call('record', {'type': 'development_operation', 'id': op['id'],
            'expected_revision': op['revision_id'], 'data': {'work_item': w['id'], 'tool': 'test', 'status': 'failed', 'capture_scope': 'fixture'}})
        question = self.call('record', {'type': 'open_question', 'data': {'description': 'Unrelated scope but possibly blocking'}})
        result = self.focused(w)
        self.assertEqual([x['revision_id'] for x in result['operations']], [updated['revision_id']])
        self.assertEqual(result['scope']['omitted_operation_revision_count'], 1)
        self.assertIn(question['id'], [x['id'] for x in result['questions']])

    def test_invalid_options_and_shared_mcp_schema(self):
        _, w = self.scenario()
        for extra in [{'view': 'focused'}, {'view': 'focused', 'entry_ids': ['missing']},
                      {'entry_ids': ['cable']}, {'view': 'focused', 'entry_ids': ['cable'], 'discussion_limit': 0}]:
            self.assertFault('invalid_input', lambda: self.call('context', {'work_id': w['id'], **extra}))
        schema = next(t for t in tool_list() if t['name'] == 'context')['inputSchema']['properties']['arguments']
        self.assertEqual(schema['properties']['view']['enum'], ['full', 'focused'])
        self.assertIn('entry_ids', schema['properties'])

    def test_legacy_unversioned_discussion_keeps_unknown_basis(self):
        p, w = self.scenario()
        legacy = self.call('record', {'type': 'discussion_entry', 'data': {'target': p['id'], 'body': 'Legacy'}})
        result = self.focused(w)
        row = next(item for item in result['discussions'] if item['id'] == legacy['id'])
        self.assertNotIn('design_revision', row['data'])
        self.assertEqual(result['scope']['unversioned_proposal_discussion_count'], 1)


if __name__ == '__main__':
    unittest.main()
