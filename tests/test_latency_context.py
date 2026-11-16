import copy
import unittest

from gantry.latency_context import materialize, transform


class LatencyContextTests(unittest.TestCase):
    def test_baseline_and_plan_tool_do_not_change_inputs(self):
        source = {'task': {'scope': ['x']}, 'last_result': {'error': 'conflict'}}
        for condition in ('baseline', 'plan_tool'):
            out = transform(source, condition)
            self.assertEqual(out, source)
            out['task']['scope'].append('y')
            self.assertEqual(source['task']['scope'], ['x'])

    def test_description_treatment_preserves_exact_schemas_and_all_actions(self):
        source = {'action_schemas': {'read': {'properties': {'path': {'type': 'string'}, 'offset': {'type': 'integer'}}, 'required': ['path']}},
                  'action_guide': {'read': 'Read a saved file. ' * 70}, 'task': {'authority': 'read'}, 'instruction': 'Existing authority'}
        before = copy.deepcopy(source); out = transform(source, 'compact_schema')
        self.assertEqual(out['action_schemas'], source['action_schemas'])
        self.assertEqual(set(out['action_guide']), set(source['action_guide']))
        self.assertIn('path', out['action_guide']['read'])
        self.assertIn('offset', out['action_guide']['read'])
        self.assertEqual(source, before)
        self.assertEqual(out['task'], source['task'])
        self.assertEqual(out['instruction'], source['instruction'])

    def test_duplicate_data_is_lossless_including_escaped_keys_and_marker_data(self):
        value = {'hash': 'a'*64, 'measurement': list(range(400)), '$gantry_context_ref': 'native vendor field'}
        source = {'a/b~c': value, 'second': copy.deepcopy(value), 'third': [copy.deepcopy(value)],
                  'unknown': None, 'failure': {'status': 'fail'}, 'requirements': ['fixed'],
                  'action_schemas': {'source': copy.deepcopy(value)}}
        before = copy.deepcopy(source); out = transform(source, 'compact_context')
        self.assertEqual(materialize(out), before)
        self.assertIn('_gantry_dedup', out)
        self.assertEqual(out['second'], {'$gantry_context_ref': '/a~1b~0c'})
        self.assertEqual(out['action_schemas'], source['action_schemas'])
        self.assertEqual(source, before)

    def test_no_approximate_matching_or_added_metadata_for_small_data(self):
        source = {'before': {'value': 1}, 'after': {'value': 2}, 'status': 'unknown'}
        self.assertEqual(transform(source, 'compact_context'), source)

    def test_reserved_metadata_input_is_preserved_not_reinterpreted(self):
        source = {'_gantry_dedup': {'vendor': 'data'}, 'a': list(range(400)), 'b': list(range(400))}
        self.assertEqual(transform(source, 'compact_context'), source)

    def test_unknown_condition_rejected(self):
        with self.assertRaises(ValueError): transform({}, 'unexpected')

if __name__ == '__main__': unittest.main()
