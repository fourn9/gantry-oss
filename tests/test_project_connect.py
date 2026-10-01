import base64
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from gantry.model import Fault, digest
from gantry.project_connect import connect, discover, disconnect, Project, owner_client, load
from gantry.project_mcp import dispatch, run
from gantry.project_sandbox import backend
from gantry.service import Service, token_hash


class ConnectTests(unittest.TestCase):
    def test_mcp_review_recovery_preserves_input_and_delegation(self):
        self.attach(); self.checkpoint()
        submission = self.project.operate('submit', {'question': 'Review controller'}, 'recover-submit')
        prepared = dispatch(self.project, 'project_mentor_prepare', {'submission_id': submission['id']})
        service = self.project.client.service; now = service.clock()
        service.clock = lambda: now + 901000
        recovered = dispatch(self.project, 'project_mentor_recover',
            {'submission_id': submission['id'], 'reason': 'Previous reviewer stopped'})
        self.assertFalse(recovered['inference_repeated'])
        again = dispatch(self.project, 'project_mentor_prepare', {'submission_id': submission['id']})
        self.assertEqual(prepared, again)
        state = prepared['context']['state_id']
        output = {'verdict': 'conditional', 'scope': 'Saved source only', 'rationale': 'Needs testing',
            'evidence': [state], 'unverified': ['Runtime behavior'], 'findings': [], 'prediction': 'Unconfirmed'}
        result = dispatch(self.project, 'project_mentor_finish', {'submission_id': submission['id'], 'output': output})
        self.assertEqual(result['status'], 'completed')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root/'control.py').write_text('def clamp(x):\n    return min(x, 10)\n')
        (self.root/'tests').mkdir()
        (self.root/'tests/test_control.py').write_text('import unittest\nfrom control import clamp\nclass Check(unittest.TestCase):\n    def test_range(self): self.assertEqual(clamp(-1), 0)\n')

    def attach(self, **kw):
        self.prompts = []
        def confirm(value): self.prompts.append(value); return True
        self.result = connect(self.root, confirm=confirm, **kw)
        self.project = Project(self.root)
        self.owner = owner_client(self.root/'.gantry')
        return self.result

    def checkpoint(self, key='checkpoint', branch='main'):
        obj = self.project.context()['connection']
        state = obj['state_id'] if branch == 'main' else obj['branches'][branch]['state_id']
        return self.project.operate('checkpoint', {'expected_state': state, 'summary': 'Saved a milestone',
            'rationale': 'Continue scoped development', 'unfinished': ['Review physical assumptions'], 'branch': branch}, key)

    def test_one_confirmation_atomic_activation_audit_and_replay(self):
        self.attach()
        self.assertEqual(len(self.prompts), 1)
        obj = self.project.context()['connection']
        self.assertNotEqual(obj['zone'], 'root')
        self.assertEqual(obj['plan']['mode'], 'work-capable')
        self.assertNotIn('admin', self.project.client.call('identity')['permissions'])
        history = self.owner.call('history', {'limit': 100})
        raw = json.dumps(history)
        for command in ('propose', 'submit', 'endorse', 'review_adoption', 'commit', 'connect_development', 'initialize_continuity'):
            self.assertIn('"'+command+'"', raw)
        for name in ('admin.token', 'project-agent.token', 'project-mentor.token'):
            self.assertNotIn((self.root/'.gantry'/name).read_text().strip(), raw)
        self.assertTrue(self.owner.call('verify')['valid'])
        self.assertTrue(self.owner.call('replay')['matched'])
        self.assertTrue(connect(self.root, confirm=lambda _: self.fail('Second approval'))['resumed'])

    def test_prepare_no_token_then_exact_owner_approval(self):
        result = connect(self.root, prepare=True)
        self.assertFalse((self.root/'.gantry/project-agent.token').exists())
        with self.assertRaises(Fault): connect(self.root, approval='incorrect')
        self.assertFalse((self.root/'.gantry/admin.token').exists())
        result = connect(self.root, approval=result['preview']['approval_hash'])
        self.assertEqual(result['status'], 'connected')

    def test_oversized_manifest_refused_before_owner_approval(self):
        for i in range(999):
            (self.root/('part_'+str(i)+'.txt')).write_text('synthetic')
        with self.assertRaises(Fault) as error:
            connect(self.root, confirm=lambda _: self.fail('Oversized snapshot reached approval'))
        self.assertEqual(error.exception.code, 'capture_incomplete')
        self.assertFalse((self.root/'.gantry/admin.token').exists())

    def test_unapproved_token_and_activation_rollback(self):
        plan, files = discover(self.root)
        owner = owner_client(self.root/'.gantry'); token = secrets.token_urlsafe(32)
        req = owner.call('request_connection', {'plan': plan, 'token_hash': token_hash(token), 'mentor_token_hash': token_hash(secrets.token_urlsafe(32))})
        with self.assertRaises(Fault): owner.service.call(token, 'identity')
        before = owner.call('verify')['seq']
        with patch.object(owner.service, 'cmd_initialize_continuity', side_effect=Fault('injected_failure', 'test')):
            with self.assertRaises(Fault): owner.call('approve_connection', {'connection_id': req['id'], 'plan_hash': digest(plan), 'files': files})
        self.assertEqual(owner.call('verify')['seq'], before)
        with self.assertRaises(Fault): owner.service.call(token, 'identity')
        self.assertEqual(owner.call('inspect_connection', {'connection_id': req['id']})['connection']['status'], 'pending')

    def test_exclusions_and_content_secret_detection(self):
        (self.root/'.env').write_text('secret')
        (self.root/'local.token').write_text('secret')
        (self.root/'.venv').mkdir(); (self.root/'.venv/a.py').write_text('secret')
        (self.root/'unsafe.txt').write_text('api_key=' + 'z'*40)
        self.attach()
        manifest = self.project.context()['development']['manifest']
        self.assertEqual(set(manifest), {'control.py', 'tests/test_control.py'})
        self.assertIn('credential_detected:unsafe.txt', self.project.context()['connection']['plan']['missing'])
        args = {'path': 'control.py', 'content': 'api_key='+'z'*40, 'expected_hash': manifest['control.py']['hash']}
        with self.assertRaises(Fault): self.project.operate('edit', args, 'secret-write')

    def test_read_edit_checkpoint_revoke_and_scope_enforcement(self):
        self.attach()
        before = self.project.operate('read', {'path': 'control.py'}, 'read')
        edited = self.project.operate('edit', {'path': 'control.py', 'expected_hash': before['sha256'],
            'content': 'def clamp(x):\n    return max(0, min(x, 10))\n'}, 'edit')
        self.assertEqual(edited, self.project.operate('edit', {'path': 'control.py', 'expected_hash': before['sha256'],
            'content': 'def clamp(x):\n    return max(0, min(x, 10))\n'}, 'edit'))
        saved = self.checkpoint(); self.assertFalse(saved['formal_adoption'])
        self.assertEqual(self.project.context()['development']['status']['verification'], 'unverified')
        for path in ('../outside', '/etc/passwd', '.gantry/admin.token', 'new.py', './control.py'):
            with self.subTest(path=path), self.assertRaises(Fault): self.project.operate('read', {'path': path}, 'out-'+path)
        for command in ('state', 'capture_artifact', 'propose', 'commit', 'connect_development', 'configure_development', 'sync_integration', 'export'):
            with self.subTest(command=command), self.assertRaises(Fault): self.project.client.call(command, {})
        with self.assertRaises(Fault): self.project.operate('test', {'command': 'arbitrary'}, 'test-arbitrary')
        disconnect(self.root)
        with self.assertRaises(Fault): self.project.client.call('identity')
        self.assertTrue(self.owner.call('verify')['valid'])

    def test_record_only_can_checkpoint_but_not_edit_test_or_review(self):
        self.attach(mode='record-only')
        (self.root/'control.py').write_text('value = 2\n')
        self.checkpoint()
        for action, args in [('edit', {'path': 'control.py', 'expected_hash': 'absent', 'content': ''}),
                             ('test', {'command': 'test'}), ('submit', {'question': 'Review'})]:
            with self.subTest(action=action), self.assertRaises(Fault): self.project.operate(action, args, action)

    def test_symlink_hardlink_and_deletion_denied(self):
        self.attach()
        (self.root/'control.py').unlink(); (self.root/'control.py').symlink_to('/etc/passwd')
        with self.assertRaises((Fault, OSError)): self.project.operate('read', {'path': 'control.py'}, 'link')
        with self.assertRaises(Fault): self.checkpoint()
        (self.root/'control.py').unlink(); os.link(self.root/'tests/test_control.py', self.root/'control.py')
        with self.assertRaises(Fault): self.project.operate('read', {'path': 'control.py'}, 'hardlink')

    def test_expiry_and_changed_plan_fail_closed(self):
        self.attach()
        self.project.operate('read', {'path': 'control.py'}, 'cached-read')
        with self.assertRaises(Fault): connect(self.root, paths=['control.py'], confirm=lambda _: True)
        self.project.client.service.clock = lambda: 10**16
        with self.assertRaises(Fault): self.project.context()
        with self.assertRaises(Fault): self.project.operate('read', {'path': 'control.py'}, 'cached-read')

    def test_readonly_acceptance_changes_and_core_escalation_denied(self):
        self.attach(write_paths=['control.py'])
        before = self.project.operate('read', {'path': 'tests/test_control.py'}, 'read-test')
        with self.assertRaises(Fault):
            self.project.operate('edit', {'path': 'tests/test_control.py', 'expected_hash': before['sha256'],
                'content': 'pass\n'}, 'edit-test')
        (self.root/'tests/test_control.py').write_text('pass\n')
        with self.assertRaises(Fault) as error:
            self.project.operate('test', {'command': 'test'}, 'changed-tests')
        self.assertEqual(error.exception.code, 'stale_basis')
        obj = self.project.context()['connection']
        with self.assertRaises(Fault):
            self.project.client.call('approve_connection', {'connection_id': obj['id'],
                'plan_hash': obj['plan_hash'], 'files': {'control.py': base64.b64encode(b'pass\n').decode()}})
        self.assertEqual(self.project.context()['connection']['tests_used'], 0)

    def test_reviews_and_test_evidence_cannot_cross_connections_or_states(self):
        self.attach()
        self.checkpoint()
        obj = self.project.context()['connection']
        manifest = self.project.context()['development']['manifest']
        operation = self.project.client.call('authorize_connection_operation', {
            'operation': 'test', 'command': 'test', 'command_hash': digest(obj['plan']['commands']['test']),
            'input_hash': digest({p: v['hash'] for p, v in manifest.items()})})
        self.project.client.call('complete_connection_operation', {'operation_id': operation['id'],
            'status': 'completed', 'summary': 'Synthetic adapter report', 'output_hash': digest({'exit_code': 0}),
            'details': {'exit_code': 0, 'fixture': True}})
        old = self.project.operate('read', {'path': 'control.py'}, 'read')
        self.project.operate('edit', {'path': 'control.py', 'expected_hash': old['sha256'],
            'content': 'def clamp(x):\n    return max(0, min(x, 10))\n'}, 'edit')
        self.checkpoint('new-state')
        submission = self.project.operate('submit', {'question': 'Review the new state'}, 'submit')
        review = self.project.operate('review', {'submission_id': submission['id']})
        self.assertFalse(review.get('connection_evidence', {}).get('test_observations'))
        other = self.root/'another_project'; other.mkdir(); (other/'other.py').write_text('value = 1\n')
        connect(other, confirm=lambda _: True)
        with self.assertRaises(Fault):
            Project(other).operate('review', {'submission_id': submission['id']})

    def test_interrupted_operation_not_replayed(self):
        self.attach()
        args = {'path': 'control.py', 'expected_hash': 'absent', 'content': 'new'}
        with self.assertRaises(Fault): self.project.operate('edit', args, 'uncertain')
        with self.assertRaises(Fault) as error: self.project.operate('edit', args, 'uncertain')
        self.assertEqual(error.exception.code, 'operation_uncertain')

    def test_client_configuration_preserves_other_settings(self):
        (self.root/'.mcp.json').write_text(json.dumps({'mcpServers': {'existing': {'command': 'other'}}}))
        self.attach(client='claude')
        config = json.loads((self.root/'.mcp.json').read_text())
        self.assertEqual(config['mcpServers']['existing']['command'], 'other')
        self.assertIn('gantry_project', config['mcpServers'])
        self.assertNotIn('permissions', config)
        self.assertNotIn((self.root/'.gantry/project-agent.token').read_text().strip(), json.dumps(config))

    @unittest.skipUnless(shutil.which('git'), 'Git needed for metadata exclusion acceptance')
    def test_private_data_ignored_even_when_git_initialized_after_connect(self):
        self.attach()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True, capture_output=True)
        for path in ('.gantry/admin.token', '.gantry/project-agent.token', '.gantry/ledger.sqlite3'):
            result = subprocess.run(['git', '-C', str(self.root), 'check-ignore', '--no-index', '-q', path], capture_output=True)
            self.assertEqual(result.returncode, 0, path)

    def test_client_conflict_is_resumable_without_reapproval(self):
        (self.root/'.mcp.json').write_text(json.dumps({'mcpServers': {'gantry_project': {'command': 'different'}}}))
        self.attach(client='claude')
        self.assertEqual(self.result['status'], 'connected_client_setup_pending')
        (self.root/'.mcp.json').write_text('{}')
        resumed = connect(self.root, client='claude', confirm=lambda _: self.fail('Unexpected approval'))
        self.assertTrue(resumed['resumed'])

    def test_branches_have_common_baseline_and_isolated_files(self):
        self.attach()
        baseline = self.project.context()['connection']['state_id']
        for name in ('route_a', 'route_b'):
            self.project.operate('branch', {'name': name, 'base_state': baseline, 'purpose': 'Compare an alternative'}, name)
        old = self.project.operate('read', {'path': 'control.py', 'branch': 'route_a'}, 'a-read')
        self.project.operate('edit', {'path': 'control.py', 'branch': 'route_a', 'content': 'alternative = 1\n',
            'expected_hash': old['sha256']}, 'a-edit')
        self.checkpoint('a-save', 'route_a')
        other = self.project.operate('read', {'path': 'control.py', 'branch': 'route_b'}, 'b-read')
        self.assertEqual(other['sha256'], old['sha256'])
        self.assertEqual((self.root/'control.py').read_text(), base64.b64decode(other['base64']).decode())

    def test_meaningful_submission_review_response_loop(self):
        self.attach()
        self.checkpoint()
        submission = self.project.operate('submit', {'question': 'Check negative inputs to clamp'}, 'submit')
        prepared = dispatch(self.project, 'project_mentor_prepare', {'submission_id': submission['id']})
        properties = prepared['output_schema']['properties']
        self.assertIn('enum', properties['evidence']['items'])
        self.assertNotIn('enum', properties['unverified']['items'])
        self.assertNotIn('enum', properties['findings']['items']['properties']['paths']['items'])
        self.assertIn('control.py', prepared['context']['saved_file_previews'])
        state = prepared['context']['state_id']
        output = {'verdict': 'changes_requested', 'scope': 'control clamp', 'rationale': 'Negative inputs are not clamped',
            'evidence': [state], 'unverified': ['Hardware behavior'], 'prediction': 'Lower bound will hold',
            'findings': [{'id': 'lower-bound', 'summary': 'Clamp negative values', 'paths': ['control.py'],
                'evidence': [state], 'proposed_change': 'Use return max(0, min(x, 10))', 'completion_condition': 'clamp(-1) equals zero'}]}
        review = dispatch(self.project, 'project_mentor_finish', {'submission_id': submission['id'], 'output': output})
        self.assertEqual(review['status'], 'completed')
        test = self.project.operate('read', {'path': 'tests/test_control.py'}, 'test-read')
        with self.assertRaises(Fault):
            self.project.operate('edit', {'path': 'tests/test_control.py', 'expected_hash': test['sha256'],
                'content': 'pass\n', 'from_review': submission['id']}, 'outside-finding')
        old = self.project.operate('read', {'path': 'control.py'}, 'read-for-correction')
        self.project.operate('edit', {'path': 'control.py', 'expected_hash': old['sha256'],
            'content': 'def clamp(x):\n    return max(0, min(x, 10))\n', 'from_review': submission['id']}, 'correct')
        self.checkpoint('corrected')
        with self.assertRaises(Fault):
            self.project.operate('edit', {'path': 'control.py', 'expected_hash': 'stale', 'content': '',
                'from_review': submission['id']}, 'stale-review')
        response = self.project.operate('respond', {'submission_id': submission['id'],
            'responses': [{'finding_id': 'lower-bound', 'explanation': 'Added a zero lower bound; verification pending'}]}, 'respond')
        self.assertEqual(response['status'], 'awaiting_resubmission')
        self.assertEqual(Project(self.root).context()['development']['status']['adoption'], 'unadopted')

    def test_provisional_assumption_and_mcp_surface(self):
        self.attach()
        assumption = self.project.operate('assumption', {'statement': 'Prototype range is provisional', 'scope': ['control.py'],
            'evidence': ['Initial observation'], 'dependencies': ['controller range'], 'adoption_blocker': 'Confirm actuator range',
            'decision_owner': 'agent'}, 'assumption')
        self.assertFalse(assumption['data']['accepted_requirement'])
        self.checkpoint(); sub = self.project.operate('submit', {'question': 'Review with assumptions'}, 'submit')
        self.assertEqual(len(self.project.operate('review', {'submission_id': sub['id']})['connection_evidence']['assumptions']), 1)
        messages = [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-11-25'}},
                    {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                    {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
                    {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'project_status', 'arguments': {}}}]
        output = io.StringIO()
        with patch('sys.stdin', io.StringIO('\n'.join(map(json.dumps, messages)))), contextlib.redirect_stdout(output): run(self.root)
        lines = [json.loads(v) for v in output.getvalue().splitlines()]
        self.assertFalse(lines[-1]['result']['isError'])
        self.assertNotIn('commit', [t['name'] for t in lines[1]['result']['tools']])

    @unittest.skipUnless(backend() == 'macos-seatbelt', 'macOS runtime acceptance')
    def test_real_sandbox_test_and_escape_denials(self):
        outside = self.root.parent/('gantry-canary-'+secrets.token_hex(8))
        outside.write_text('private-canary'); self.addCleanup(lambda: outside.unlink(missing_ok=True))
        code = '''import errno, pathlib, socket
denied = []
for operation in (lambda: pathlib.Path(OUTSIDE).read_text(),
                  lambda: pathlib.Path(OUTSIDE).write_text('changed'),
                  lambda: socket.create_connection(('127.0.0.1', 9), timeout=1)):
    try: operation()
    except OSError as e:
        assert e.errno in (errno.EPERM, errno.EACCES), str(e)
        denied.append(True)
    else: raise AssertionError('escaped')
print('three_denials', len(denied))
'''.replace('OUTSIDE', repr(str(outside)))
        (self.root/'sandbox_check.py').write_text(code)
        self.attach(commands={'test': {'argv': [str(Path(sys.executable).resolve()), 'sandbox_check.py'], 'timeout_seconds': 5}})
        result = self.project.operate('test', {'command': 'test'}, 'sandbox')
        self.assertEqual(result['exit_code'], 0, result['output'])
        self.assertIn('three_denials 3', result['output'])
        self.assertEqual(outside.read_text(), 'private-canary')
        self.checkpoint(); sub = self.project.operate('submit', {'question': 'Review test evidence'}, 'submit')
        observations = self.project.operate('review', {'submission_id': sub['id']})['connection_evidence']['test_observations']
        self.assertEqual(observations[0]['details']['exit_code'], 0)

    def test_missing_sandbox_never_executes(self):
        self.attach()
        with patch('gantry.project_sandbox.backend', return_value='unavailable'), self.assertRaises(Fault) as error:
            self.project.operate('test', {'command': 'test'}, 'sandbox-missing')
        self.assertEqual(error.exception.code, 'sandbox_unavailable')


if __name__ == '__main__': unittest.main()
