import base64
import json
import tempfile
import unittest
from pathlib import Path
from gantry.model import Fault
from gantry.integrations.transport import Response
from gantry.integrations.writes import prepare, apply, reconcile


class FakeGithub:
    def __init__(self):
        self.content = 'old\n'
        self.sha = 'a' * 40
        self.writes = 0
        self.lose_response = False
    def __call__(self, request, credential_ref):
        if request.method == 'PUT':
            body = json.loads(request.body)
            assert body['sha'] == self.sha
            assert body['branch'] == 'design'
            self.writes += 1
            self.content = base64.b64decode(body['content']).decode()
            self.sha = 'b' * 40
            if self.lose_response:
                raise Fault('remote_unavailable', 'Lost response')
            return Response(json.dumps({'content': {'sha': self.sha}}).encode(), {})
        return Response(json.dumps({'type': 'file', 'path': 'src/controller.py',
            'sha': self.sha, 'encoding': 'base64',
            'content': base64.b64encode(self.content.encode()).decode()}).encode(), {})


CONFIG = {'provider': 'github', 'operation': 'file.update',
          'repository': 'example/robot', 'branch': 'design', 'path': 'src/controller.py'}
CHANGE = {'content': 'new\n', 'message': 'Update controller'}


class WriteLifecycleTests(unittest.TestCase):
    def prepare(self, root, remote):
        return prepare(CONFIG, CHANGE, 'Adjust behavior', [], root/'plan', 'GANTRY_CONNECTOR_TEST', remote)
    def test_prepare_apply_capture_and_repeat(self):
        remote = FakeGithub()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); plan = self.prepare(root, remote)
            self.assertEqual(remote.writes, 0)
            result = apply(root/'plan', plan['plan_hash'], root/'journal', 'GANTRY_CONNECTOR_TEST', transport=remote)
            self.assertEqual(result['status'], 'verified')
            self.assertEqual(remote.content, 'new\n')
            repeated = apply(root/'plan', plan['plan_hash'], root/'journal', 'GANTRY_CONNECTOR_TEST', transport=remote)
            self.assertEqual(repeated, result)
            self.assertEqual(remote.writes, 1)
            from gantry.integrations.writes import evidence
            bundle = evidence(root/'plan', root/'journal')
            self.assertEqual(bundle['manifest']['adoption'], 'unadopted')
            self.assertIn('before.json', bundle['files'])
            self.assertIn('after.json', bundle['files'])
    def test_changed_baseline_blocks_without_mutation(self):
        remote = FakeGithub()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); plan=self.prepare(root,remote); remote.sha='c'*40
            with self.assertRaises(Fault) as exc:
                apply(root/'plan',plan['plan_hash'],root/'journal','GANTRY_CONNECTOR_TEST',transport=remote)
            self.assertEqual(exc.exception.code,'stale_basis')
            self.assertEqual(remote.writes,0)
    def test_lost_response_never_resends_and_reconciles(self):
        remote = FakeGithub()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); plan=self.prepare(root,remote); remote.lose_response=True
            result=apply(root/'plan',plan['plan_hash'],root/'journal','GANTRY_CONNECTOR_TEST',transport=remote)
            self.assertEqual(result['status'],'unknown')
            self.assertEqual(apply(root/'plan',plan['plan_hash'],root/'journal','GANTRY_CONNECTOR_TEST',transport=remote)['status'],'unknown')
            result=reconcile(root/'plan',root/'journal','GANTRY_CONNECTOR_TEST',transport=remote)
            self.assertEqual(result['status'],'observed_desired')
            self.assertEqual(remote.writes,1)
