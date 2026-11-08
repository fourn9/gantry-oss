"""A read cursor describes bytes actually delivered to the model, not hidden tails."""
import base64
import hashlib
import json
import unittest

from gantry.bot_worker import environment_manifest
from gantry.crew_runtime import _execute, result_preview
import test_bot_development as fixtures


class CrewReadDeliveryTests(unittest.TestCase):
    def reconstruct_from_model_turns(self, text, requested_length):
        raw = text.encode('utf-8')
        c = fixtures.BotDevelopmentTests(); original = c.artifact
        c.artifact = lambda files: original({**files, 'source.txt': text})
        c.setUp(); self.addCleanup(c.tearDown)
        c.configs['designer'].update(agent_loop=True)
        c.owner.call('configure_bot_runtime', {'bot_id': 'designer', 'version': 1,
            'principal_id': 'designer', 'enabled': True,
            'environment': environment_manifest(c.configs['designer'])})
        task = c.task('designer', kind='report', write_scope=[])
        received = bytearray(); offsets = []; contexts = []

        def infer(context, schema, directory):
            contexts.append(context)
            self.assertLess(len(contexts), 30, 'Read cursors must converge without rereading')
            if context['last_result'] is not None:
                result = context['last_result']
                self.assertEqual(result['hash'], hashlib.sha256(raw).hexdigest())
                self.assertEqual(result['size'], len(raw))
                if 'text' in result:
                    self.assertTrue(isinstance(result['text'], str), 'No preview wrapper may hide read bytes')
                    chunk = result['text'].encode('utf-8')
                else:
                    self.assertTrue(isinstance(result['base64'], str), 'The entire encoded chunk must reach the model')
                    chunk = base64.b64decode(result['base64'], validate=True)
                received.extend(chunk)
                self.assertEqual(bytes(received), raw[:len(received)], 'Byte boundaries must not corrupt UTF-8')
                if result['next_offset'] is None:
                    self.assertEqual(bytes(received), raw, 'End-of-file cannot hide an unread tail')
                    return {'output': {'action': 'finish', 'arguments_json': json.dumps(c.answer()),
                        'rationale': 'Fixture consumed exact saved source bytes'}}
                self.assertEqual(result['next_offset'], len(received))
            offsets.append(len(received))
            return {'output': {'action': 'read', 'arguments_json': json.dumps({
                'path': 'source.txt', 'offset': len(received), 'length': requested_length}),
                'rationale': 'Read the next exact source chunk'}}

        with c.worker('designer', infer) as worker: finished = worker.tick()[0]
        self.assertEqual(finished['task']['status'], 'completed')
        self.assertEqual(bytes(received), raw)
        self.assertEqual(len(offsets), len(set(offsets)))
        view = c.owner.call('get_bot_task', {'task_id': task['id']})
        reads = [a for a in view['actions'] if a['kind'] == 'read']
        self.assertEqual(len(reads), len(offsets))
        self.assertTrue(all(a['details']['workspace_before'] == a['details']['workspace_after'] for a in reads))
        self.assertNotIn('output_state', view['task'])
        self.assertTrue(c.owner.call('replay')['matched'])

    def test_large_ascii_file_is_complete_when_following_actual_read_cursors(self):
        self.reconstruct_from_model_turns('abcdefgh' * 3001, 20000)

    def test_multibyte_source_is_byte_exact_across_paginated_reads(self):
        self.reconstruct_from_model_turns('界🙂' * 7001, 8192)

    def test_arbitrary_large_results_keep_the_existing_preview_bound(self):
        preview = result_preview({'message': 'x' * 30000})
        self.assertTrue(preview['message']['truncated'])
        self.assertEqual(len(preview['message']['preview']), 8000)
        huge = result_preview({str(i): 'x' * 30000 for i in range(100)})
        self.assertTrue(huge['truncated'])
        self.assertLess(len(json.dumps(huge).encode()), 96000)


class ContextDeliveryTests(unittest.TestCase):
    def deliver(self, action, value, **args):
        context = {'task': {'write_scope': [], 'session_id': 'project'}, 'note': value}
        class Client:
            def call(self, operation, request): return context
        arguments = {'pointer': '/note', **args}
        if action == 'inspect': arguments['task_id'] = 'peer-task'
        return result_preview(_execute(Client(), context, {}, {}, action, arguments, None, None, 'fixture'))

    def test_context_and_peer_inspection_deliver_complete_unicode_string_pages(self):
        for action in ('context', 'inspect'):
            for source in ('a'*20001, '🙂'*20001):
                with self.subTest(action=action, ascii=source.isascii()):
                    received = ''; offset = 0
                    while True:
                        result = self.deliver(action, source, offset=offset, limit=100 if action == 'inspect' else 65536)
                        self.assertTrue(isinstance(result.get('value'), str), 'Preview must not hide a delivered page')
                        received += result['value']
                        if result['next_offset'] is None: break
                        self.assertEqual(result['next_offset'], len(received)); offset = result['next_offset']
                    self.assertEqual(received, source)

    def test_default_string_page_is_complete_before_next_cursor(self):
        for action in ('context', 'inspect'):
            source = 'x'*9000
            result = self.deliver(action, source)
            self.assertTrue(isinstance(result['value'], str))
            self.assertEqual(result['next_offset'], len(result['value']))

    def test_root_array_and_map_pages_never_skip_omitted_items(self):
        for action in ('context', 'inspect'):
            for source in (list(range(101)), {str(i): i for i in range(101)}):
                with self.subTest(action=action, kind=type(source).__name__):
                    offset = 0; received = []
                    while True:
                        result = self.deliver(action, source, offset=offset, limit=100)
                        page = result['value']
                        self.assertLessEqual(len(page), 30)
                        received.extend(list(page.items()) if isinstance(page, dict) else page)
                        if result['next_offset'] is None: break
                        self.assertEqual(result['next_offset'], len(received)); offset = result['next_offset']
                    self.assertEqual(received, list(source.items()) if isinstance(source, dict) else source)
