"""Exercise newest-first Core receipts beyond each bounded retention window."""
import copy
import hashlib
import json
import unittest

from gantry.bot_execution import _bounded_collections
from gantry.bot_observations import recent_context
import test_crew_runtime as fixtures


class ObservationRecencyTests(unittest.TestCase):
    def test_actual_worker_retains_latest_eight_source_reads(self):
        c = fixtures.CrewRuntimeTests(); c.setUp(); self.addCleanup(c.tearDown)
        c.enable_loop('designer'); c.task('designer'); seen = []
        content = ''.join(f'{i:05}: source\n' for i in range(600))
        def infer(ctx, schema, directory):
            n = len(seen); seen.append(ctx)
            if n == 0:
                return c.action('edit', {'path': 'mechanical.txt', 'content': content,
                    'expected_hash': hashlib.sha256(b'1').hexdigest()})
            if n <= 12:
                return c.action('read', {'path': 'mechanical.txt', 'offset': (n-1)*100, 'length': 100})
            offsets = [o['offset'] for o in ctx['read_observations']['items']]
            self.assertEqual(offsets, list(range(400, 1200, 100)))
            return c.action('finish', c.answer())
        with c.worker('designer', infer) as worker: result = worker.tick()[0]
        self.assertEqual(result['task']['status'], 'completed')
        self.assertTrue(c.owner.call('replay')['matched'])

    def test_peer_observations_choose_newest_window_and_deliver_oldest_to_newest(self):
        actions = [{'id': f'action-{n}', 'task_id': 'task', 'attempt': 1,
            'created_seq': n, 'kind': 'inspect', 'input_state': 'state',
            'details': {'arguments': json.dumps({'task_id': 'peer', 'pointer': '/task/title'}),
                        'result': {'value': f'Observation {n}'}}} for n in reversed(range(100))]
        packet = recent_context({'task': {'id': 'task'}, 'actions': actions})
        self.assertEqual([x['action_id'] for x in packet['items']], [f'action-{n}' for n in range(92, 100)])
        self.assertEqual(packet['coverage']['scanned_actions'], 8)

    def test_action_previews_keep_newest_but_reports_keep_latest_appended(self):
        context = {'actions': [{'id': f'action-{n}', 'text': 'x'*2000} for n in reversed(range(20))],
                   'task': {'reports': [{'attempt': n, 'text': 'x'*5000} for n in range(20)]}}
        source = copy.deepcopy(context)
        coverage = _bounded_collections(context, source)
        self.assertEqual(context['actions'][0]['id'], 'action-19')
        self.assertEqual(coverage['/actions']['source_indices'][0], 0)
        self.assertEqual(context['task']['reports'][-1]['attempt'], 19)
        self.assertEqual(source['actions'][0]['id'], 'action-19')
