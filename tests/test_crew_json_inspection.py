"""Anonymous bounded JSON inspection; no evaluation or model inference required."""
import base64
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zlib

from gantry.crew_runtime import _execute, action_schemas, SCHEMA
from gantry.model import Fault


def envelope(raw):
    return {'encoding': 'zlib-base64-json-v1', 'data': base64.b64encode(zlib.compress(raw)).decode(),
        'uncompressed_bytes': len(raw), 'uncompressed_sha256': hashlib.sha256(raw).hexdigest()}


class JsonInspectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve(); self.workspace = self.root/'workspace'; self.workspace.mkdir()
        self.context = {'task': {'write_scope': [], 'studio_mode': 'ask'}, 'zone': 'root'}

    def inspect(self, data=None, **args):
        if data is not None:
            (self.workspace/'report.json').write_text(json.dumps(data))
        return _execute(None, self.context, {}, {}, 'inspect_json',
            {'path': 'report.json', **args}, self.workspace, self.root, 'fixture')

    def test_plain_json_filter_pagination_preserves_original_indices_and_hash(self):
        rows = [{'id': 'a', 'failures': []}, {'id': 'b', 'failures': ['first']},
                {'id': 'c'}, {'id': 'd', 'failures': ['second']}]
        first = self.inspect({'cases': rows}, pointer='/cases', nonempty_at='/failures', limit=1)
        self.assertEqual(first['value'], [rows[1]])
        self.assertEqual(first['source_indices'], [1])
        self.assertEqual(first['source_total'], 4)
        self.assertEqual(first['total'], 2)
        self.assertEqual(first['filter_counts'], {'matched': 2, 'missing': 1, 'empty_or_false': 1})
        self.assertEqual(first['next_offset'], 1)
        second = self.inspect(pointer='/cases', nonempty_at='/failures', offset=1, limit=1)
        self.assertEqual(second['value'], [rows[3]])
        self.assertEqual(second['source_indices'], [3]); self.assertIsNone(second['next_offset'])
        raw = (self.workspace/'report.json').read_bytes()
        self.assertEqual(first['source']['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(first['source']['decoded_sha256'], first['source']['sha256'])
        self.assertEqual(first['source']['encoding'], 'json')

    def test_compressed_json_has_distinct_source_and_verified_decoded_hashes(self):
        raw = json.dumps({'a/b': {'x~y': ['one', 'two']}}).encode()
        result = self.inspect(envelope(raw), pointer='/a~1b/x~0y', offset=1, limit=1)
        self.assertEqual(result['value'], ['two'])
        self.assertEqual(result['source']['encoding'], 'zlib-base64-json-v1')
        self.assertEqual(result['source']['decoded_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(result['source']['decoded_bytes'], len(raw))
        self.assertNotEqual(result['source']['sha256'], result['source']['decoded_sha256'])

    def test_rejects_wrong_digest_and_lengths_without_echoing_payload(self):
        original = envelope(b'{"private-value":true}')
        for invalid in ({**original, 'uncompressed_sha256': '0'*64},
                        {**original, 'uncompressed_bytes': original['uncompressed_bytes']+1},
                        {**original, 'uncompressed_bytes': True},
                        {**original, 'uncompressed_bytes': 64*1024*1024+1}):
            with self.subTest(invalid=invalid.keys()), self.assertRaises(Fault) as caught:
                self.inspect(invalid)
            self.assertIn(caught.exception.code, ('invalid_input', 'capture_incomplete', 'integrity_error'))
            self.assertNotIn('private-value', str(caught.exception))

    def test_rejects_malformed_truncated_and_trailing_compressed_streams(self):
        original = envelope(b'{"value":1}'); encoded = zlib.compress(b'{"value":1}')
        inputs = [b'not-zlib', encoded[:-1], encoded+b'trailing', encoded+encoded]
        for raw in inputs:
            with self.subTest(size=len(raw)), self.assertRaises(Fault):
                self.inspect({**original, 'data': base64.b64encode(raw).decode()})
        with self.assertRaises(Fault): self.inspect({**original, 'data': '!invalid-base64!'})
        with self.assertRaises(Fault): self.inspect(envelope(b'{not json'))

    def test_bomb_is_bounded_by_declared_length_and_hard_limit(self):
        raw = b'"'+b'x'*(64*1024*1024)+b'"'
        compressed = envelope(raw)
        for declared in (16, 64*1024*1024):
            with self.subTest(declared=declared), self.assertRaises(Fault) as caught:
                self.inspect({**compressed, 'uncompressed_bytes': declared})
            self.assertEqual(caught.exception.code, 'capture_incomplete')

    def test_rejects_unsafe_paths_links_and_encoded_input_over_existing_bound(self):
        (self.workspace/'report.json').write_text('{}')
        for name in ('../outside.json', '/outside.json', '.env'):
            with self.subTest(path=name), self.assertRaises(Fault) as caught:
                self.inspect(path=name)
            self.assertEqual(caught.exception.code, 'scope_denied')
        (self.workspace/'report.json').unlink()
        (self.root/'outside.json').write_text('{"hidden":1}')
        (self.workspace/'report.json').symlink_to(self.root/'outside.json')
        with self.assertRaises(Fault) as caught: self.inspect()
        self.assertEqual(caught.exception.code, 'scope_denied')
        (self.workspace/'report.json').unlink()
        (self.workspace/'report.json').write_bytes(b'x'*(16*1024*1024+1))
        with self.assertRaises(Fault) as caught: self.inspect()
        self.assertEqual(caught.exception.code, 'capture_incomplete')

    def test_filter_requires_array_and_results_remain_bounded(self):
        with self.assertRaises(Fault): self.inspect({'failures': []}, nonempty_at='/failures')
        result = self.inspect({'text': 'x'*200000}, pointer='/text')
        self.assertLess(len(json.dumps(result)), 12000)
        self.assertEqual(result['total'], 200000)
        self.assertTrue(result['next_offset'])
        self.assertIn('sha256', result['source'])
        self.assertIn('inspect_json', SCHEMA['properties']['action']['enum'])
        self.assertIn('inspect_json', action_schemas())

    def test_rejects_nonfinite_values_and_excessive_nesting(self):
        for raw in (b'{"n":NaN}', b'{"n":Infinity}', b'{"n":1e9999}', b'['*200+b'0'+b']'*200):
            with self.subTest(prefix=raw[:12]), self.assertRaises(Fault) as caught:
                self.inspect(envelope(raw))
            self.assertEqual(caught.exception.code, 'invalid_input')

    def test_compression_does_not_bypass_credential_screening(self):
        raw = json.dumps({'note': '-----BEGIN PRIVATE KEY-----'}).encode()
        with self.assertRaises(Fault) as caught:
            self.inspect(envelope(raw))
        self.assertEqual(caught.exception.code, 'credential_detected')
        self.assertNotIn('BEGIN PRIVATE', str(caught.exception))

    def test_json_escaping_does_not_reveal_credentials_in_returned_values(self):
        raw = b'{"note":"\\u002d----BEGIN PRIVATE KEY-----"}'
        for compressed in (False, True):
            (self.workspace/'report.json').write_bytes(json.dumps(envelope(raw)).encode() if compressed else raw)
            with self.subTest(compressed=compressed):
                with self.assertRaises(Fault) as caught:
                    self.inspect()
                self.assertEqual(caught.exception.code, 'credential_detected')

    def test_missing_pointer_never_reveals_decoded_secret_keys(self):
        raw = b'{"\\u002d----BEGIN PRIVATE KEY-----":true}'
        for compressed in (False, True):
            (self.workspace/'report.json').write_bytes(json.dumps(envelope(raw)).encode() if compressed else raw)
            with self.subTest(compressed=compressed), self.assertRaises(Fault) as caught:
                self.inspect(pointer='/missing')
            self.assertEqual(caught.exception.code, 'credential_detected')
            self.assertNotIn('BEGIN PRIVATE', json.dumps(caught.exception.details))


class JsonInspectionActionLoopTests(unittest.TestCase):
    def test_readonly_worker_records_hash_bound_inspection_without_edits(self):
        import test_bot_development as fixtures
        from gantry.bot_worker import environment_manifest
        c = fixtures.BotDevelopmentTests(); original = c.artifact
        data = json.dumps(envelope(b'{"cases":[{"failures":[]},{"failures":["probe"]}]}'))
        c.artifact = lambda files: original({**files, 'report.json': data})
        c.setUp(); self.addCleanup(c.tearDown)
        c.configs['designer'].update(agent_loop=True)
        c.owner.call('configure_bot_runtime', {'bot_id': 'designer', 'version': 1,
            'principal_id': 'designer', 'enabled': True,
            'environment': environment_manifest(c.configs['designer'])})
        task = c.task('designer', kind='report', write_scope=[]); contexts = []

        def infer(context, schema, directory):
            contexts.append(context)
            if len(contexts) == 1:
                action, args = 'inspect_json', {'path': 'report.json', 'pointer': '/cases', 'nonempty_at': '/failures'}
            else:
                self.assertEqual(context['last_result']['value'], [{'failures': ['probe']}])
                action, args = 'finish', c.answer(summary='Inspected saved observations only')
            return {'output': {'action': action, 'arguments_json': json.dumps(args), 'rationale': 'Fixture inspection'}}

        with c.worker('designer', infer) as worker: result = worker.tick()[0]
        self.assertEqual(result['task']['status'], 'completed')
        self.assertEqual(len(contexts), 2)
        view = c.owner.call('get_bot_task', {'task_id': task['id']})
        receipt = next(a for a in view['actions'] if a['kind'] == 'inspect_json')['details']
        self.assertEqual(receipt['result']['source']['sha256'], hashlib.sha256(data.encode()).hexdigest())
        self.assertEqual(receipt['workspace_before'], receipt['workspace_after'])
        self.assertNotIn('output_state', view['task'])
        self.assertTrue(c.owner.call('replay')['matched'])
