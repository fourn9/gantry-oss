"""Real independent Bot execution and storage; explicitly fixture reasoning."""
import base64
import copy
import json
import secrets
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from gantry.agent_connection import PROFILES
from gantry.backup import restore_backup
from gantry.bot_worker import BotWorker, environment_manifest
from gantry.model import Fault, digest
from gantry.service import Service, token_hash
from test_development import LocalClient
from test_bots import profile


class BotDevelopmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.service = Service(self.root/'ledger'); self.token = self.service.bootstrap()['token']
        self.owner = LocalClient(self.service, self.token); self.clients = {}; self.configs = {}; self.tokens = {}
        for name in ('lead', 'mechanical', 'designer', 'control'):
            token = secrets.token_urlsafe(32); self.tokens[name] = token
            proposal = self.owner.call('propose', {'title': 'Fixture delegation', 'changes': [{'id': name,
                'type': 'principal', 'data': {'kind': 'agent', 'permissions': ['read', 'record', 'work'],
                    'token_hash': token_hash(token), 'zones': ['root'], 'allowed_commands': sorted(PROFILES['bot'])}}]})
            ref = {'proposal_id': proposal['id'], 'version': proposal['version']}
            self.owner.call('submit', ref); self.owner.call('endorse', {**ref, 'reason': 'Fixture owner scope'})
            self.owner.call('review_adoption', {**ref, 'reason': 'Fixture delegation', 'verdict': 'approve'})
            self.owner.call('commit', ref)
            self.clients[name] = LocalClient(self.service, token)
        snapshot = self.artifact({'mechanical.txt': '1', 'control.txt': '1'})
        self.policy = {'mode': 'execute', 'actors': list(self.clients), 'write_scope': ['mechanical.txt', 'control.txt'],
            'recipes': {}, 'max_executions': None, 'timeout_seconds': 300, 'max_parallel': 4}
        self.session = self.owner.call('connect_development', {'title': 'Synthetic development', 'snapshot': snapshot,
            'constraints': ['No physical operation'], 'requirements': ['Matched interface'],
            'capture': {'scope': 'fixture saved files', 'missing': ['earlier history']}, 'unverified': ['physical behavior'], **self.policy})
        self.sid = self.session['id']
        self.base = self.owner.call('initialize_continuity', {'session_id': self.sid, 'version': self.session['version'],
            'hierarchy': [{'id': 'assembly', 'title': 'Assembly', 'kind': 'subsystem', 'paths': ['mechanical.txt', 'control.txt'], 'editable': True}],
            'context': {'requirements': ['Matched interface'], 'constraints': ['No physical operation'],
                'decisions': [], 'open_questions': ['physical behavior'], 'environment': {'kind': 'fixture'}}, 'summary': 'Existing baseline'})
        self.owner.call('configure_organization', {'organization_id': 'team', 'version': 0, 'name': 'Synthetic team',
            'profile': profile(), 'enabled': True, 'share_reflections': True})
        for name in self.clients:
            self.owner.call('configure_bot', {'bot_id': name, 'organization_id': 'team', 'version': 0,
                'name': name, 'parent_bot_id': None if name == 'lead' else 'mechanical' if name == 'designer' else 'lead',
                'profile': profile(name), 'enabled': True})
        self.project = self.owner.call('configure_bot_project', {'session_id': self.sid, 'organization_id': 'team',
            'version': 0, 'lead_bot_id': 'lead', 'goal': 'Update a cross-domain interface',
            'acceptance': ['Both files agree; physical behavior stays unverified'], 'enabled': True})
        for name in self.clients:
            self.owner.call('bind_development_bot', {'session_id': self.sid, 'bot_id': name, 'principal_id': name,
                'version': 0, 'write_scope': self.scope(name), 'can_assign': name in {'lead', 'mechanical'},
                'can_integrate': name == 'lead', 'enabled': True})
            config = {'bot_id': name, 'name': name, 'backend': 'external_agent', 'workflow': 'bot_development',
                'environment_definition': 'deterministic fixture bridge', 'tools': ['local files']}
            self.configs[name] = config
            self.owner.call('configure_bot_runtime', {'bot_id': name, 'version': 0, 'principal_id': name,
                'enabled': True, 'environment': environment_manifest(config)})

    def tearDown(self): self.temp.cleanup()
    def scope(self, name):
        return ['mechanical.txt', 'control.txt'] if name == 'lead' else ['control.txt'] if name == 'control' else ['mechanical.txt']
    def artifact(self, files):
        return self.owner.call('capture_artifact', {'files': {p: base64.b64encode(v.encode()).decode() for p, v in files.items()}})['revision_id']
    def fault(self, code, fn):
        with self.assertRaises(Fault) as caught: fn()
        self.assertEqual(caught.exception.code, code, str(caught.exception))
    def assignment(self, name, **extra):
        return {'bot_id': name, 'state_id': self.base['id'], 'kind': 'plan' if name in {'lead', 'mechanical'} else 'develop',
            'title': name + ' work', 'completion': ['Return evidence and unknowns'], 'write_scope': self.scope(name),
            'dependencies': [], 'after_tasks': [], **extra}
    def task(self, name='lead', **extra):
        return self.owner.call('assign_bot_task', {'session_id': self.sid, **self.assignment(name, **extra)})
    def worker(self, name, infer=None, client=None):
        return BotWorker(client or self.clients[name], self.configs[name], self.root/'workers', infer or self.infer)
    def answer(self, **extra):
        return {'summary': 'Fixture development report', 'rationale': 'Recorded fixture requirement',
            'status': 'completed', 'unverified': ['Physical behavior'], 'edits': [], 'assignments': [], 'integrate_changes': [], **extra}
    def infer(self, ctx, schema, directory):
        name = ctx['bot']['id']; children = ctx['task']['children']
        if name == 'lead' and not children:
            out = self.answer(status='waiting', assignments=[self.assignment('mechanical'), self.assignment('control')])
        elif name == 'mechanical' and not children:
            out = self.answer(status='waiting', assignments=[self.assignment('designer')])
        elif name == 'lead':
            changes = [x['change'] for x in ctx['candidate_changes'] if x['status'] == 'completed']
            out = self.answer(integrate_changes=[{'id': c['id'], 'version': c['version']} for c in changes])
        elif name == 'mechanical': out = self.answer(summary='Mechanical report references the child candidate')
        else: out = self.answer(edits=[{'path': self.scope(name)[0], 'content': '2'}])
        return {'output': out, 'provider': {'kind': 'fixture'}}

    def test_hierarchy_parallel_edits_integration_memory_without_mentor(self):
        root = self.task()
        with patch.object(Service, 'cmd_claim_mentor_job', side_effect=AssertionError('Mentor must not run')):
            with self.worker('lead') as lead: self.assertEqual(lead.tick()[0]['task']['status'], 'waiting')
            with self.worker('mechanical') as manager: manager.tick()
            with self.worker('designer') as mechanical, self.worker('control') as control:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(lambda w: w.tick(), [mechanical, control]))
                self.assertTrue(all(r[0]['task']['status'] == 'completed' for r in results), results)
            with self.worker('mechanical') as manager: manager.tick()
            with self.worker('lead') as lead:
                result = lead.tick()[0]; self.assertEqual(result['task']['status'], 'completed', result)
        state_id = result['task']['output_state']
        state = self.owner.call('get_development_state', {'state_id': state_id})
        self.assertEqual(state['status']['adoption'], 'unadopted')
        self.assertEqual(state['status']['verification'], 'unverified')
        self.assertEqual(state['state']['compatibility'], 'unknown')
        from gantry.continuity_adapter import restore_development_state
        restored = restore_development_state(self.clients['lead'], state_id, self.root/'restored', 'restore-1')
        self.assertEqual((Path(restored['workspace'])/'mechanical.txt').read_text(), '2')
        self.assertEqual((Path(restored['workspace'])/'control.txt').read_text(), '2')
        history = self.owner.call('export')
        raw = json.dumps(history)
        self.assertNotIn('claim_mentor_job', raw)
        self.assertEqual(self.owner.call('review_automation_status', {'session_id': self.sid})['jobs'], [])
        self.assertIsNone(self.owner.call('get_review_team', {'session_id': self.sid})['team'])
        self.assertTrue(self.owner.call('replay')['matched'])
        seen = []
        self.task('designer', state_id=state_id)
        fresh = LocalClient(Service(self.root/'ledger'), self.tokens['designer'])
        def remember(ctx, schema, directory):
            seen.extend(ctx['memory']['items']); return {'output': self.answer(), 'provider': {'kind': 'fixture'}}
        with self.worker('designer', remember, fresh) as worker: worker.tick()
        self.assertTrue(any(m['bot_id'] == 'designer' for m in seen))

    def test_claim_is_atomic_scoped_and_not_a_review(self):
        task = self.task('designer')
        with self.worker('designer') as worker:
            args = {'task_id': task['id'], 'version': task['version'], 'runtime_fence': worker.runtime['fence']}
            self.fault('unauthorized', lambda: self.clients['control'].call('claim_bot_task', args))
            claim = self.clients['designer'].call('claim_bot_task', args, 'once')
            self.assertEqual(claim, self.clients['designer'].call('claim_bot_task', args, 'once'))
            self.fault('conflict', lambda: self.clients['designer'].call('claim_bot_task', args))
            self.fault('unauthorized', lambda: self.clients['designer'].call('claim_mentor_job', {'job_id': 'any', 'lease_seconds': 10}))

    def test_manager_cannot_assign_outside_hierarchy_or_scope(self):
        self.fault('unauthorized', lambda: self.clients['mechanical'].call('assign_bot_task',
            {'session_id': self.sid, 'requested_by_bot': 'mechanical', **self.assignment('control')}))
        self.fault('scope_denied', lambda: self.task('designer', write_scope=['control.txt']))
        self.fault('unauthorized', lambda: self.clients['designer'].call('assign_bot_task',
            {'session_id': self.sid, 'requested_by_bot': 'designer', **self.assignment('designer')}))

    def test_dependency_wait_and_changed_baseline_hold(self):
        first = self.task('designer'); second = self.task('control', after_tasks=[first['id']])
        with self.worker('control') as worker:
            self.assertEqual(worker.tick()[0]['reason'], 'dependency_pending')
        with self.worker('designer') as worker: worker.tick()
        d = self.owner.call('development_state', {'session_id': self.sid})['session']
        self.owner.call('advance_development', {'session_id': self.sid, 'version': d['version'],
            'snapshot': d['snapshot'], 'reason': 'Input premise changed', 'capture': d['capture'], 'unverified': d['unverified']})
        with self.worker('control') as worker: self.assertEqual(worker.tick()[0]['reason'], 'stale_basis')

    def test_actual_customer_tool_execution_and_native_capture(self):
        task = self.task('designer')
        def bridge(ctx, schema, directory):
            subprocess.run([sys.executable, '-c', 'from pathlib import Path; p=Path("mechanical.txt"); p.write_text(str(int(p.read_text())+1)); assert p.read_text()=="2"'],
                           cwd=ctx['workspace'], check=True)
            return {'output': self.answer(summary='Fixture subprocess edited and verified saved file'), 'provider': {'kind': 'fixture_tool_bridge'}}
        with self.worker('designer', bridge) as worker: result = worker.tick()[0]
        self.assertEqual(result['task']['status'], 'completed', result)
        view = self.owner.call('get_development_state', {'state_id': result['task']['output_state']})
        self.assertEqual(view['status']['verification'], 'unverified')
        self.assertIn('Intermediate tool calls', ' '.join(view['state']['capture']['missing']))

    def test_direct_tool_bridge_out_of_scope_is_rejected(self):
        self.task('designer')
        def bad(ctx, schema, directory):
            (Path(ctx['workspace'])/'control.txt').write_text('outside scope')
            return {'output': self.answer(), 'provider': {'kind': 'fixture'}}
        with self.worker('designer', bad) as worker:
            result = worker.tick()[0]; self.assertEqual(result['reason'], 'scope_denied')
        tasks = self.owner.call('list_bot_tasks', {'session_id': self.sid})['items']
        self.assertNotIn('output_state', tasks[0])

    def test_recovery_reuses_saved_answer_and_rejects_old_fence(self):
        task = self.task('designer'); calls = []
        from gantry.runner import persist
        def interrupted(ctx, schema, directory):
            marker = Path(directory)/'saved.json'
            if marker.exists(): return json.loads(marker.read_text())
            calls.append('inference'); receipt = self.infer(ctx, schema, directory); persist(marker, receipt)
            raise Fault('provider_unavailable', 'Fixture interruption after model receipt')
        with self.worker('designer', interrupted) as worker:
            result = worker.tick()[0]; self.assertEqual(result['status'], 'held')
        with self.worker('designer', interrupted) as worker:
            self.assertEqual(worker.tick()[0]['reason'], 'explicit_recovery_required')
            result = worker.recover(task['id'], 'Previous fixture process stopped')
            self.assertEqual(result['task']['status'], 'completed', result)
        self.assertEqual(calls, ['inference'])
        self.assertTrue(self.owner.call('replay')['matched'])

    def test_revocation_during_model_call_blocks_apply(self):
        self.task('designer')
        def revoke(ctx, schema, directory):
            receipt = self.infer(ctx, schema, directory)
            self.owner.call('configure_organization', {'organization_id': 'team', 'version': 1,
                'name': 'Stopped', 'profile': profile(), 'enabled': False})
            return receipt
        with self.worker('designer', revoke) as worker:
            result = worker.tick()[0]; self.assertEqual(result['reason'], 'mode_disabled')
            files = list(worker.root.rglob('workspace/mechanical.txt'))
            self.assertEqual(files[0].read_text(), '1')

    def test_cross_department_messages_block_completion_and_change_context(self):
        task = self.task('designer')
        message = self.clients['control'].call('send_bot_message', {'task_id': task['id'], 'from_bot_id': 'control',
            'kind': 'dependency', 'body': 'Confirm the interface', 'blocking': True, 'evidence': [self.base['id']]})
        with self.worker('designer') as worker:
            result = worker.tick()[0]; self.assertEqual(result['reason'], 'dependency_pending')
        self.fault('unauthorized', lambda: self.clients['designer'].call('resolve_bot_message',
            {'message_id': message['id'], 'reason': 'Ignore other department', 'evidence': [self.base['id']]}))
        self.clients['control'].call('resolve_bot_message', {'message_id': message['id'],
            'reason': 'Interface checked against fixed input', 'evidence': [self.base['id']]})
        with self.worker('designer') as worker:
            self.fault('stale_basis', lambda: worker.recover(task['id'], 'Previous fixture stopped'))

    def test_disabled_bot_project_does_not_require_disabling_review_service(self):
        self.task('designer')
        self.owner.call('configure_bot_project', {**{k: self.project[k] for k in
            ('session_id', 'organization_id', 'goal', 'acceptance', 'lead_bot_id')}, 'version': 1, 'enabled': False})
        self.assertFalse(self.owner.call('bot_inbox', {'bot_id': 'designer'})['jobs'])
        self.assertTrue(self.owner.call('verify')['valid'])

    def test_mcp_profiles_are_disjoint_in_execution_authority(self):
        from gantry.mcp import tool_list
        bot = {t['name'] for t in tool_list('bot')}; review = {t['name'] for t in tool_list('review')}
        self.assertIn('assign_bot_task', bot); self.assertNotIn('claim_mentor_job', bot)
        self.assertIn('claim_change_review', review); self.assertNotIn('claim_bot_task', review)
        self.assertNotIn('configure_bot_project', bot)

    def test_new_service_entry_points(self):
        for entry, included, excluded in [('bots_main', 'bot-worker', 'mentor-worker'), ('review_main', 'mentor-worker', 'bot-worker')]:
            out = subprocess.run([sys.executable, '-c', f'from gantry.cli import {entry}; {entry}()', '--help'],
                capture_output=True, text=True, check=True).stdout
            self.assertIn(included, out); self.assertNotIn(excluded, out)

    def test_bot_worker_never_dispatches_or_recovers_legacy_review(self):
        task = self.task('designer'); base_client = self.clients['designer']
        class MixedInbox:
            def call(_, name, args=None, key=None):
                result = base_client.call(name, args, key)
                if name == 'bot_inbox':
                    result['jobs'].append({'id': 'legacy-review', 'status': 'pending'})
                return result
        with patch('gantry.mentor_daemon.process_job') as legacy_run, \
                patch('gantry.mentor_recovery.recover_job') as legacy_recover:
            with self.worker('designer', client=MixedInbox()) as worker:
                results = worker.tick()
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0]['task']['id'], task['id'])
                self.fault('scope_denied', lambda: worker.recover('legacy-review', 'Previous process stopped'))
            legacy_run.assert_not_called(); legacy_recover.assert_not_called()

    def test_legacy_worker_cannot_recover_independent_bot_assignment(self):
        config = {**self.configs['designer'], 'workflow': 'legacy_review'}
        worker = BotWorker(self.clients['designer'], config, self.root/'legacy-worker', self.infer)
        worker.runtime = {'fence': 'fixture'}
        with patch('gantry.bot_execution.recover_bot_task') as recover:
            self.fault('scope_denied', lambda: worker.recover('btask_fixture', 'Previous process stopped'))
            recover.assert_not_called()

    def test_service_mcp_config_defaults_match_service(self):
        token = self.root/'fixture.token'; token.write_text('test-only'); token.chmod(0o600)
        for entry, profile_name in [('bots_main', 'bot'), ('review_main', 'review')]:
            output = self.root/(entry + '.json')
            subprocess.run([sys.executable, '-c', f'from gantry.cli import {entry}; {entry}()',
                'agent-config', '--client', 'generic', '--agent-token-file', str(token),
                '--executable', sys.executable, '--output', str(output)],
                capture_output=True, text=True, check=True)
            argv = json.loads(output.read_text())['mcpServers']['gantry']['args']
            self.assertEqual(argv[argv.index('--profile') + 1], profile_name)

    def test_bot_entrypoint_does_not_reinterpret_legacy_runtime(self):
        config = self.root/'legacy.json'
        config.write_text(json.dumps({**self.configs['designer'], 'workflow': 'legacy_review'}))
        result = subprocess.run([sys.executable, '-c', 'from gantry.cli import bots_main; bots_main()',
            'bot-worker', '--config', str(config), '--journal', str(self.root/'journal'), '--manifest'],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('scope_denied', result.stderr)

    def test_unknown_runtime_workflow_is_rejected(self):
        config = {**self.configs['designer'], 'workflow': 'bot_developmnt'}
        self.fault('invalid_input', lambda: BotWorker(self.clients['designer'], config,
            self.root/'invalid-worker', self.infer))

    def test_independent_background_service_preserves_workflow(self):
        import plistlib
        from gantry.bot_worker import service_manifest
        config = self.root/'worker.json'; config.write_text(json.dumps({'bot_id': 'designer'}))
        self.fault('scope_denied', lambda: service_manifest(config, self.root/'journal',
            sys.executable, 'launchd', workflow='bot_development'))
        config.write_text(json.dumps(self.configs['designer']))
        manifest = service_manifest(config, self.root/'journal', sys.executable, 'launchd',
            workflow='bot_development')
        command = plistlib.loads(manifest.encode())['ProgramArguments']
        self.assertEqual(command[command.index('--config') + 1], str(config.resolve()))
        self.assertEqual(json.loads(config.read_text())['workflow'], 'bot_development')

    def test_independent_recovery_rejects_legacy_retry_overrides(self):
        worker = self.worker('designer'); worker.runtime = {'fence': 'fixture'}
        with patch('gantry.bot_execution.recover_bot_task') as recover:
            for flags in ({'retry_inference': True}, {'collect_interrupted_verification': True}):
                self.fault('invalid_input', lambda: worker.recover('btask_fixture',
                    'Previous process stopped', **flags))
            recover.assert_not_called()

    def test_lost_finish_acknowledgement_is_not_reexecuted(self):
        task = self.task('designer'); calls = []; base_client = self.clients['designer']
        def infer(ctx, schema, directory):
            calls.append('model'); return self.infer(ctx, schema, directory)
        class LostAck:
            lost = False
            def call(_, name, args=None, key=None):
                result = base_client.call(name, args, key)
                if name == 'finish_bot_task' and not _.lost:
                    _.lost = True; raise OSError('fixture lost response after commit')
                return result
        with self.worker('designer', infer, LostAck()) as worker:
            self.assertEqual(worker.tick()[0]['status'], 'held')
        with self.worker('designer', infer) as worker:
            result = worker.recover(task['id'], 'Previous fixture stopped')
            self.assertEqual(result['task']['status'], 'completed')
        self.assertEqual(calls, ['model'])
        self.assertEqual(len(self.owner.call('get_bot_task', {'task_id': task['id']})['task']['reports']), 1)

    def test_lost_checkpoint_acknowledgement_does_not_duplicate_checkpoint(self):
        task = self.task('designer'); calls = []; base_client = self.clients['designer']
        def infer(ctx, schema, directory):
            calls.append('model'); return self.infer(ctx, schema, directory)
        class LostAck:
            lost = False
            def call(_, name, args=None, key=None):
                result = base_client.call(name, args, key)
                if name == 'checkpoint_bot_task' and not _.lost:
                    _.lost = True; raise OSError('fixture checkpoint reply lost')
                return result
        with self.worker('designer', infer, LostAck()) as worker: worker.tick()
        with self.worker('designer', infer) as worker:
            result = worker.recover(task['id'], 'Previous fixture stopped')
            self.assertEqual(result['task']['status'], 'completed')
        self.assertEqual(calls, ['model'])
        states = self.owner.call('list_development_states', {'session_id': self.sid})
        self.assertEqual(states['total'], 2)

    def test_lost_claim_acknowledgement_recovers_before_inference(self):
        task = self.task('designer'); base_client = self.clients['designer']
        class LostAck:
            lost = False
            def call(_, name, args=None, key=None):
                result = base_client.call(name, args, key)
                if name == 'claim_bot_task' and not _.lost:
                    _.lost = True; raise OSError('fixture claim reply lost')
                return result
        with self.worker('designer', client=LostAck()) as worker: worker.tick()
        with self.worker('designer') as worker:
            result = worker.recover(task['id'], 'Previous fixture stopped before execution')
            self.assertEqual(result['task']['status'], 'completed')

    def test_saved_mid_task_checkpoint_can_be_restored_by_another_context(self):
        task = self.task('designer'); client = self.clients['designer']
        with self.worker('designer') as worker:
            claim = client.call('claim_bot_task', {'task_id': task['id'], 'version': task['version'],
                'runtime_fence': worker.runtime['fence']})
            ref = {'task_id': task['id'], 'fence': claim['task']['fence']}
            checkpoint = client.call('checkpoint_bot_task', {**ref,
                'snapshot': self.artifact({'mechanical.txt': 'intermediate failed candidate', 'control.txt': '1'}),
                'summary': 'Intermediate failure', 'rationale': 'Keep the experiment', 'unfinished': ['Mismatch'],
                'capture': {'scope': 'Explicit adapter milestone', 'missing': ['unsaved operations']}})
            client.call('hold_bot_task', {**ref, 'reason': 'Customer context paused'})
        fresh = LocalClient(Service(self.root/'ledger'), self.tokens['lead'])
        from gantry.continuity_adapter import restore_development_state
        state = checkpoint['state']['id']
        receipt = restore_development_state(fresh, state, self.root/'handoff', 'fresh-state')
        self.assertEqual((Path(receipt['workspace'])/'mechanical.txt').read_text(), 'intermediate failed candidate')
        self.assertEqual(fresh.call('get_development_state', {'state_id': state})['status']['adoption'], 'unadopted')

    def test_additive_backup_restore_keeps_history_and_native_bytes(self):
        before = self.owner.call('export'); self.task('designer')
        with self.worker('designer') as worker: worker.tick()
        after = self.owner.call('export')
        self.assertEqual(after['events'][:len(before['events'])], before['events'])
        backup = self.root/'backup.json'; backup.write_text(json.dumps(after))
        restore_backup(self.root/'imported', after)
        imported = LocalClient(Service(self.root/'imported'), self.token)
        self.assertTrue(imported.call('verify')['valid'])
        self.assertTrue(imported.call('replay')['matched'])
        self.assertEqual(imported.call('list_bot_tasks', {'session_id': self.sid})['items'],
                         self.owner.call('list_bot_tasks', {'session_id': self.sid})['items'])

    def test_real_customer_process_uses_new_worker_route(self):
        task = self.task('designer'); script = self.root/'customer-bridge'
        script.write_text('#!' + sys.executable + '\nimport json,sys\nfrom pathlib import Path\n'
            'r=json.load(sys.stdin); p=Path(r["context"]["workspace"])/"mechanical.txt"; p.write_text("2")\n'
            'print(json.dumps(' + repr(self.answer(summary='Synthetic customer process result')) + '))\n')
        script.chmod(0o700)
        self.configs['designer'].update(command=[str(script)], executable_hash=__import__('hashlib').sha256(script.read_bytes()).hexdigest())
        self.owner.call('configure_bot_runtime', {'bot_id': 'designer', 'version': 1, 'principal_id': 'designer',
            'enabled': True, 'environment': environment_manifest(self.configs['designer'])})
        with BotWorker(self.clients['designer'], self.configs['designer'], self.root/'real-customer-worker') as worker:
            result = worker.tick()[0]
        self.assertEqual(result['task']['status'], 'completed', result)
        self.assertEqual(self.owner.call('review_automation_status', {'session_id': self.sid})['jobs'], [])

    def test_integration_respects_narrower_task_scope(self):
        self.task('control')
        with self.worker('control') as worker: result = worker.tick()[0]
        change_id = result['task']['change_id']
        change = next(c for c in self.owner.call('list_development_states', {'session_id': self.sid})['changes']
                      if c['id'] == change_id)
        self.task('lead', kind='integrate', write_scope=['mechanical.txt'])
        def integrate(ctx, schema, directory):
            return {'output': self.answer(integrate_changes=[{'id': change_id, 'version': change['version']}]),
                    'provider': {'kind': 'fixture'}}
        with self.worker('lead', integrate) as worker:
            self.assertEqual(worker.tick()[0]['reason'], 'scope_denied')

    def test_integration_cannot_silently_replace_own_saved_edit(self):
        self.task('control')
        with self.worker('control') as worker: result = worker.tick()[0]
        change = next(c for c in self.owner.call('list_development_states', {'session_id': self.sid})['changes']
                      if c['id'] == result['task']['change_id'])
        self.task('lead')
        def mixed(ctx, schema, directory):
            return {'output': self.answer(edits=[{'path': 'mechanical.txt', 'content': '3'}],
                integrate_changes=[{'id': change['id'], 'version': change['version']}]), 'provider': {'kind': 'fixture'}}
        with self.worker('lead', mixed) as worker:
            self.assertEqual(worker.tick()[0]['reason'], 'invalid_state')
        task = next(t for t in self.owner.call('list_bot_tasks', {'session_id': self.sid})['items'] if t['bot_id'] == 'lead')
        state = self.owner.call('get_development_state', {'state_id': task['output_state']})
        self.assertEqual(state['status']['verification'], 'unverified')
        self.assertEqual(state['state']['change_id'], task['change_id'])
        self.assertEqual(state['diffs'][0]['path'], 'mechanical.txt')

    def test_failed_child_report_wakes_manager_without_mentor(self):
        parent = self.task('mechanical')
        with self.worker('mechanical') as manager: manager.tick()
        def fail(ctx, schema, directory):
            return {'output': self.answer(status='failed', summary='Fixture interface did not match'), 'provider': {'kind': 'fixture'}}
        with self.worker('designer', fail) as worker: worker.tick()
        view = self.owner.call('get_bot_task', {'task_id': parent['id']})
        self.assertEqual(view['task']['status'], 'pending')
        self.assertEqual(view['children'][0]['status'], 'failed')
        seen = []
        def replan(ctx, schema, directory):
            seen.extend(ctx['children']); return {'output': self.answer(status='blocked',
                summary='Manager requires a revised interface before continuing'), 'provider': {'kind': 'fixture'}}
        with self.worker('mechanical', replan) as manager:
            self.assertEqual(manager.tick()[0]['task']['status'], 'blocked')
        self.assertEqual(seen[0]['reports'][-1]['report']['summary'], 'Fixture interface did not match')


    def test_large_restore_inventory_stays_available_without_filling_model_input(self):
        from gantry.bot_execution import _input
        task = self.task('designer', dependencies=['mechanical.txt'])
        context = self.clients['designer'].call('get_bot_task', {'task_id': task['id']})
        workspace = self.root/'bounded-input'/'workspace'; workspace.mkdir(parents=True)
        (workspace/'mechanical.txt').write_text('1'); (workspace/'control.txt').write_text('1')
        names = [f'geometry/part-{i:05d}.step' for i in range(10000)]
        context['development']['manifest'].update({name: {'hash': 'a'*64, 'size': 8000} for name in names})
        context['development']['restores'] = [{'hashes': {name: 'a'*64 for name in names}}]
        context['development']['state']['components']['assembly']['files'] = names
        result = _input(context, workspace)
        self.assertLess(len(json.dumps(result).encode()), 30000)
        self.assertEqual(next(iter(result['files'])), 'mechanical.txt')
        self.assertEqual(result['capture']['omitted_file_count'], 10000)
        self.assertTrue(result['capture']['omitted_list_truncated'])
        saved = json.loads(Path(result['full_context']['path']).read_text())
        self.assertEqual(saved, context)
        self.assertEqual(result['full_context']['sha256'], digest(saved))


    def test_large_experience_inventories_remain_retrievable_without_repeating_them(self):
        from gantry.bot_execution import _input
        task = self.task('designer', dependencies=['mechanical.txt'])
        context = self.clients['designer'].call('get_bot_task', {'task_id': task['id']})
        workspace = self.root/'experience-input'/'workspace'; workspace.mkdir(parents=True)
        (workspace/'mechanical.txt').write_text('1'); (workspace/'control.txt').write_text('1')
        names = [f'geometry/part-{i:05d}.step' for i in range(2000)]
        hashes = {name: 'a'*64 for name in names}; hashes['mechanical.txt'] = 'b'*64
        context['memory'] = {'items': [dict(id=f'memory-{i}', input_hashes=hashes,
            paths=names + ['mechanical.txt'], observation='Source-bound experience, not authority',
            limitations=['Physical compatibility remains unverified'], state_id='recorded-state') for i in range(30)]}
        result = _input(context, workspace)
        self.assertLess(len(json.dumps(result).encode()), 160000)
        saved = json.loads(Path(result['full_context']['path']).read_text())
        self.assertEqual(saved, context)
        self.assertEqual(result['full_context']['sha256'], digest(saved))
        for index, memory in enumerate(result['memory']['items']):
            self.assertEqual(memory['observation'], context['memory']['items'][index]['observation'])
            self.assertEqual(memory['limitations'], ['Physical compatibility remains unverified'])
            self.assertEqual(memory['input_hash_count'], 2001)
            self.assertEqual(memory['path_count'], 2001)
            self.assertTrue(memory['input_hashes_truncated'] and memory['paths_truncated'])
            self.assertEqual(next(iter(memory['input_hashes'])), 'mechanical.txt')
            self.assertEqual(memory['detail_reference']['json_pointer'], f'/memory/items/{index}')
            self.assertEqual(memory['detail_reference']['sha256'], digest(saved['memory']['items'][index]))


if __name__ == '__main__': unittest.main()
