"""Exact scoped replacements preserve source that is absent from a model turn."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from gantry.crew_runtime import _execute
from gantry.model import Fault


class CrewReplaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve(); self.workspace = self.root/'workspace'; self.workspace.mkdir()
        self.path = self.workspace/'source.txt'; self.path.write_bytes(b'prefix\r\nold\r\ntail\r\n')
        self.context = {'task': {'write_scope': ['source.txt']}, 'zone': 'root'}

    def replace(self, **extra):
        args = {'path': 'source.txt', 'expected_hash': hashlib.sha256(self.path.read_bytes()).hexdigest(),
                'old_text': 'old', 'new_text': 'new', **extra}
        return _execute(None, self.context, {}, {}, 'replace', args, self.workspace, self.root, 'fixture')

    def test_exact_replacement_preserves_unrelated_bytes_and_supports_deletion(self):
        result = self.replace(new_text='新しい')
        self.assertEqual(self.path.read_bytes(), 'prefix\r\n新しい\r\ntail\r\n'.encode())
        self.assertEqual(result['hash'], hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.replace(old_text='新しい', new_text='')
        self.assertEqual(self.path.read_bytes(), b'prefix\r\n\r\ntail\r\n')

    def test_stale_missing_empty_and_ambiguous_matches_never_write(self):
        for values, code in (({'expected_hash': '0'*64}, 'stale_basis'),
            ({'old_text': 'missing'}, 'invalid_input'), ({'old_text': ''}, 'invalid_input'),
            ({'old_text': '\r\n'}, 'invalid_input')):
            before = self.path.read_bytes()
            with self.subTest(values=values), self.assertRaises(Fault) as caught: self.replace(**values)
            self.assertEqual(caught.exception.code, code); self.assertEqual(self.path.read_bytes(), before)
        self.path.write_bytes(b'aaa')
        with self.assertRaises(Fault): self.replace(old_text='aa')
        self.assertEqual(self.path.read_bytes(), b'aaa', 'Overlapping matches are also ambiguous')

    def test_scope_readonly_and_symlink_checks_are_preserved(self):
        before = self.path.read_bytes()
        for values in ({'path': '../source.txt'}, {'path': 'other.txt'}, {'path': '.env'}):
            with self.subTest(values=values), self.assertRaises(Fault) as caught: self.replace(**values)
            self.assertEqual(caught.exception.code, 'scope_denied')
        self.context['task']['studio_mode'] = 'ask'
        with self.assertRaises(Fault) as caught: self.replace()
        self.assertEqual(caught.exception.code, 'scope_denied'); self.assertEqual(self.path.read_bytes(), before)
        del self.context['task']['studio_mode']
        outside = self.root/'outside.txt'; outside.write_bytes(before)
        self.path.unlink(); self.path.symlink_to(outside)
        with self.assertRaises(Fault) as caught: self.replace()
        self.assertEqual(caught.exception.code, 'scope_denied'); self.assertEqual(outside.read_bytes(), before)

    def test_credentials_and_non_utf8_sources_are_rejected_without_changes(self):
        before = self.path.read_bytes()
        with self.assertRaises(Fault) as caught: self.replace(new_text='-----BEGIN PRIVATE KEY-----')
        self.assertEqual(caught.exception.code, 'credential_detected'); self.assertEqual(self.path.read_bytes(), before)
        self.assertNotIn('PRIVATE KEY', str(caught.exception))
        self.path.write_bytes(b'old\xff')
        with self.assertRaises(Fault) as caught: self.replace()
        self.assertEqual(caught.exception.code, 'invalid_input'); self.assertEqual(self.path.read_bytes(), b'old\xff')


class CrewReplaceActionLoopTests(unittest.TestCase):
    def test_small_replacement_checkpoints_large_source_without_model_reemitting_tail(self):
        import test_bot_development as fixtures
        from gantry.bot_worker import environment_manifest
        c = fixtures.BotDevelopmentTests(); original = c.artifact
        source = 'setting = "old"\n' + '# hidden tail\n' * 6000
        c.artifact = lambda files: original({**files, 'mechanical.txt': source})
        c.setUp(); self.addCleanup(c.tearDown)
        c.configs['designer'].update(agent_loop=True)
        c.owner.call('configure_bot_runtime', {'bot_id': 'designer', 'version': 1,
            'principal_id': 'designer', 'enabled': True, 'environment': environment_manifest(c.configs['designer'])})
        task = c.task('designer'); contexts = []

        def infer(context, schema, directory):
            contexts.append(context)
            self.assertNotIn('mechanical.txt', context['files'], 'Large source is absent from inline previews')
            self.assertIn('replace', context['action_schemas'])
            if len(contexts) == 1:
                action, args = 'read', {'path': 'mechanical.txt', 'length': 100}
            elif len(contexts) == 2:
                self.assertIn('setting = "old"', context['last_result']['text'])
                action, args = 'replace', {'path': 'mechanical.txt',
                    'expected_hash': context['last_result']['hash'], 'old_text': 'setting = "old"',
                    'new_text': 'setting = "new"'}
            else:
                self.assertEqual(len(contexts), 3)
                self.assertEqual((Path(context['workspace'])/'mechanical.txt').read_bytes(),
                                 source.replace('setting = "old"', 'setting = "new"', 1).encode())
                action, args = 'finish', c.answer()
            return {'output': {'action': action, 'arguments_json': json.dumps(args), 'rationale': 'Anonymous exact edit'}}

        with c.worker('designer', infer) as worker: result = worker.tick()[0]
        self.assertEqual(result['task']['status'], 'completed')
        view = c.owner.call('get_bot_task', {'task_id': task['id']})
        receipt = next(a for a in view['actions'] if a['kind'] == 'replace')['details']
        self.assertNotEqual(receipt['workspace_before'], receipt['workspace_after'])
        self.assertEqual(len(view['own_change']['checkpoints']), 1)
        self.assertEqual(receipt['result']['hash'], hashlib.sha256(
            source.replace('setting = "old"', 'setting = "new"', 1).encode()).hexdigest())
        self.assertTrue(c.owner.call('replay')['matched'])
