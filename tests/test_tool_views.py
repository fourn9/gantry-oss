import copy
import unittest
import test_evidence as fixture


class ToolViewTests(fixture.EvidenceTests):
    def setup_view(self):
        state = self.initialize()
        manifest = self.call('restore_artifact', {'revision_id': self.snapshot, 'metadata_only': True})['manifest']
        self.source = {'revision_id': self.snapshot, 'path': 'input.txt',
            'sha256': manifest['files']['input.txt']['hash'], 'locator': 'fixture'}
        self.view = self.call('record_evidence_view', {'state_id': state['id'], 'subject_id': 'robot',
            'profile': 'geometry', 'extractor': 'explicit-fixture', 'sources': [self.source], 'missing': ['temperature'],
            'fields': [{'name': 'position', 'value': [100, 200, 300], 'unit': 'mm', 'frame': 'body',
                'classification': 'declared', 'source_index': 0, 'method': 'fixture'},
                {'name': 'temperature', 'value': None, 'classification': 'unknown', 'source_index': 0, 'method': 'not acquired'}]})
        self.args = {'view_id': self.view['id'], 'state_id': state['id'],
            'profile': {'id': 'simulator-input', 'version': 1,
                'fields': [{'source': 'position', 'target': '/body/position', 'unit': 'm', 'frame': 'body'}]}}

    def test_selected_projection_preserves_native_and_evidence(self):
        self.setup_view(); result = self.call('render_evidence_view', self.args)
        self.assertEqual(result['data'], {'body': {'position': [.1, .2, .3]}})
        self.assertEqual(result['omitted_fields'], ['temperature'])
        self.assertEqual(result['provenance'][0]['source'], self.source)
        self.assertEqual(self.call('get_evidence_view', {'view_id': self.view['id']})['fields'][0]['value'], [100, 200, 300])
        self.assertEqual(self.call('restore_artifact', {'revision_id': self.snapshot})['files']['input.txt'], 'aW5pdGlhbA==')

    def test_missing_stays_unknown_and_frame_conversion_is_not_guessed(self):
        self.setup_view(); self.args['profile']['fields'].append({'source': 'temperature', 'target': '/temperature'})
        result = self.call('render_evidence_view', self.args)
        self.assertIsNone(result['data']['temperature']); self.assertEqual(result['missing'], ['/temperature'])
        self.args['profile']['fields'][0]['frame'] = 'world'
        self.fault('mapping_required', lambda: self.call('render_evidence_view', self.args))

    def test_wrong_state_and_overlapping_paths_are_rejected(self):
        self.setup_view(); bad = copy.deepcopy(self.args); bad['state_id'] = 'another-state'
        self.fault('stale_basis', lambda: self.call('render_evidence_view', bad))
        self.args['profile']['fields'].append({'source': 'position', 'target': '/body'})
        self.fault('invalid_input', lambda: self.call('render_evidence_view', self.args))
