import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch

import test_change_review as fixtures
from gantry.review_context import ReviewContextMixin, inspect_cad


class ReviewContextTests(unittest.TestCase):
    setUp = fixtures.ChangeReviewTests.setUp
    tearDown = fixtures.ChangeReviewTests.tearDown
    for name in ('call', 'artifact', 'policy', 'connect', 'detail', 'fault', 'initialize', 'begin',
                 'checkpoint', 'setup_review', 'submit', 'report', 'output', 'claim', 'complete'):
        locals()[name] = getattr(fixtures.ChangeReviewTests, name)

    def retrieve(self, review, **kwargs):
        with closing(self.service.store.connect()) as con:
            state = self.service.store.state(con)
            return ReviewContextMixin.cmd_related_review_context(self.service, state,
                state['principals']['mentor'], {'submission_id': review['id'], **kwargs}, [], [], con)

    def next_session_review(self, include_mentor=True):
        self.session = self.connect()
        self.call('configure_development', {'session_id': self.session['id'], 'version': self.session['version'],
            'reason': 'next team', **{**self.policy(), 'actors': ['admin', 'mentor'] if include_mentor else ['admin']}})
        self.call('configure_review_team', {**self.team_args, 'session_id': self.session['id']})
        self.base = self.initialize()
        self.cp = self.checkpoint(self.begin(self.base))
        return self.submit(self.cp['change'])

    def test_authorized_same_project_retrieval_and_no_cross_project_leak(self):
        first = self.setup_review(); self.report(first); self.complete(first, self.claim(first))
        project = self.call('save_project', {'name': 'Robot A', 'description': 'test'})
        self.call('link_product_session', {'project_id': project['id'], 'session_id': first['session_id']})
        second = self.next_session_review()
        self.assertEqual(self.retrieve(second)['items'], [])  # Unlinked session cannot roam.
        self.call('link_product_session', {'project_id': project['id'], 'session_id': second['session_id']})
        result = self.retrieve(second)
        self.assertEqual([x['reference_id'] for x in result['items']], [first['id']])
        self.assertEqual(result['items'][0]['provenance']['state_id'], first['state_id'])
        self.report(second); self.complete(second, self.claim(second))
        third = self.next_session_review()
        other = self.call('save_project', {'name': 'Robot B', 'description': 'isolated'})
        self.call('link_product_session', {'project_id': other['id'], 'session_id': third['session_id']})
        self.assertEqual(self.retrieve(third)['items'], [])

    def test_session_access_and_bounds(self):
        first = self.setup_review(); self.report(first); self.complete(first, self.claim(first))
        project = self.call('save_project', {'name': 'Robot', 'description': 'test'})
        self.call('link_product_session', {'project_id': project['id'], 'session_id': first['session_id']})
        second = self.next_session_review()
        self.call('link_product_session', {'project_id': project['id'], 'session_id': second['session_id']})
        limited = self.retrieve(second, scan_limit=1)
        self.assertTrue(limited['truncated']); self.assertEqual(limited['scanned_records'], 1)
        self.fault('invalid_input', lambda: self.retrieve(second, limit=51))
        old = self.call('development_state', {'session_id': first['session_id']})['session']
        self.call('configure_development', {'session_id': old['id'], 'version': old['version'],
            'reason': 'Revoke reviewer', **self.policy()})
        self.assertEqual(self.retrieve(second)['items'], [])


class CADInspectionTests(unittest.TestCase):
    def test_path_boundary_and_unsupported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'macro.py').write_text('raise Exception("must not execute")')
            self.assertEqual(inspect_cad(root, ['macro.py'])['files'][0]['current']['status'], 'unsupported')
            self.assertEqual(inspect_cad(root, ['absent.step'])['files'][0]['current']['status'], 'not_acquired')
            with self.assertRaises(ValueError): inspect_cad(root, ['../outside.step'])
            (root/'escape.step').symlink_to('/etc/passwd')
            with self.assertRaises(ValueError): inspect_cad(root, ['escape.step'])

    def test_timeout_retains_hash_and_does_not_claim_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'part.step'; path.write_text('bad step')
            with patch('gantry.review_context.subprocess.run', side_effect=subprocess.TimeoutExpired('cad', 1)):
                report = inspect_cad(tmp, ['part.step'])['files'][0]['current']
            self.assertEqual(report['status'], 'timeout'); self.assertEqual(len(report['sha256']), 64)

    def test_actual_cadquery_geometry_and_difference(self):
        import os
        configured = os.getenv('GANTRY_CAD_PYTHON')
        if not configured: self.skipTest('Set GANTRY_CAD_PYTHON to an optional CadQuery interpreter')
        interpreter = Path(configured)
        if not interpreter.is_file(): self.skipTest('Optional CadQuery interpreter not installed')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); before=root/'before'; after=root/'after'; before.mkdir(); after.mkdir()
            subprocess.run([str(interpreter), '-I', '-c',
                'import cadquery as c,sys; c.exporters.export(c.Workplane().box(2,3,4),sys.argv[1]); '
                'c.exporters.export(c.Workplane().box(2,3,5),sys.argv[2])',
                str(before/'part.step'), str(after/'part.step')], check=True, capture_output=True)
            report = inspect_cad(after, ['part.step'], before, interpreter)['files'][0]
            self.assertEqual(report['current']['status'], 'measured')
            self.assertTrue(report['current']['topology_valid'])
            self.assertAlmostEqual(report['difference']['volume_delta'], 6, places=5)
            self.assertEqual(report['current']['physical_acceptance'], 'not_evaluated')
            self.assertTrue(report['difference']['bounds_changed'])


if __name__ == '__main__': unittest.main()
