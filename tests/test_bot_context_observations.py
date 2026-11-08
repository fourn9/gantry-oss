import json
import unittest

from gantry.model import canonical
import test_crew_runtime as fixtures


class ContextObservationTests(unittest.TestCase):
    def action(self, n, value, **extra):
        return {'id': f'action-{n}', 'task_id': 'task', 'attempt': 1, 'kind': 'inspect',
                'input_state': 'saved-state', 'details': {'arguments': json.dumps({
                    'task_id': 'peer', 'pointer': '/saved/source', 'offset': n*6000}),
                    'result': {'value': value, 'total': 18000, 'next_offset': (n+1)*6000}}, **extra}

    def test_chunks_retain_requests_and_historical_provenance_with_bounded_packet(self):
        from gantry.bot_observations import recent_context
        context = {'task': {'id': 'task'}, 'actions': [self.action(n, chr(65+n)*6000) for n in reversed(range(3))]}
        packet = recent_context(context)
        self.assertEqual(len(packet['items']), 3)
        self.assertEqual([i['arguments']['offset'] for i in packet['items']], [0, 6000, 12000])
        self.assertEqual(''.join(i['result']['value'] for i in packet['items']), 'A'*6000+'B'*6000+'C'*6000)
        self.assertTrue(all(i['action_id'] and i['result_sha256'] and i['input_state'] == 'saved-state' for i in packet['items']))
        self.assertIn('historical', packet['meaning'])
        context['actions'] = [self.action(n, 'x'*6000) for n in reversed(range(100))]
        packet = recent_context(context)
        self.assertLessEqual(len(canonical(packet).encode()), 49152)
        self.assertLessEqual(len(packet['items']), 8)
        self.assertLessEqual(packet['coverage']['scanned_actions'], 32)

    def test_foreign_credential_and_oversized_results_are_not_reintroduced(self):
        from gantry.bot_observations import recent_context
        actions = [self.action(0, 'foreign content', task_id='other'),
                   self.action(1, '-----BEGIN PRIVATE KEY-----\nprivate\n-----END PRIVATE KEY-----'),
                   self.action(2, 'huge'*30000)]
        packet = recent_context({'task': {'id': 'task'}, 'actions': actions})
        self.assertEqual(packet['items'], [])
        self.assertNotIn('foreign content', canonical(packet))
        self.assertNotIn('PRIVATE KEY', canonical(packet))

    def test_actual_peer_inspection_accepts_string_limit_and_survives_unrelated_read(self):
        c = fixtures.CrewRuntimeTests(); c.setUp(); self.addCleanup(c.tearDown)
        c.enable_loop('designer'); c.task('designer'); seen=[]
        def infer(ctx, schema, directory):
            seen.append(ctx)
            if len(seen) == 1:
                self.assertIn('inspect', ctx['action_schemas'])
                return c.action('inspect', {'task_id': ctx['task']['id'], 'pointer':'/task/title', 'limit':6000})
            if len(seen) == 2:
                self.assertEqual(ctx['last_result']['value'], ctx['task']['title'])
                return c.action('read', {'path':'control.txt'})
            items=ctx['context_observations']['items']
            match=next(i for i in items if i['arguments'].get('pointer') == '/task/title')
            self.assertEqual(match['result']['value'], ctx['task']['title'])
            self.assertEqual(match['arguments']['task_id'], ctx['task']['id'])
            return c.action('finish', c.answer())
        with c.worker('designer', infer) as worker: result=worker.tick()[0]
        self.assertEqual(result['task']['status'], 'completed')
        self.assertTrue(c.owner.call('replay')['matched'])
