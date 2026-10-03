"""Persistent customer Bots. Real Core/workspaces; explicitly synthetic inference."""
import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

import test_bots as bot_fixture
from test_bots import profile
from test_development import LocalClient
from gantry.bot_worker import BotWorker, environment_manifest, infer_command
from gantry.mentor_daemon import process_job
from gantry.model import Fault, digest
from gantry.service import Service


class PersistentBotsTests(unittest.TestCase):
    setUp = bot_fixture.BotTests.setUp
    tearDown = bot_fixture.BotTests.tearDown
    call = bot_fixture.BotTests.call
    artifact = bot_fixture.BotTests.artifact
    policy = bot_fixture.BotTests.policy
    connect = bot_fixture.BotTests.connect
    detail = bot_fixture.BotTests.detail
    fault = bot_fixture.BotTests.fault
    initialize = bot_fixture.BotTests.initialize
    begin = bot_fixture.BotTests.begin
    checkpoint = bot_fixture.BotTests.checkpoint
    setup_review = bot_fixture.BotTests.setup_review
    submit = bot_fixture.BotTests.submit
    output = bot_fixture.BotTests.output
    setup_jobs = bot_fixture.BotTests.setup_jobs
    jobs = bot_fixture.BotTests.jobs
    inference = bot_fixture.BotTests.inference
    context = bot_fixture.BotTests.context
    memory = bot_fixture.BotTests.memory

    def setup_bots(self):
        r = self.setup_jobs()
        self.call('configure_organization', {'organization_id': 'studio', 'version': 0,
            'name': 'Robot studio', 'profile': profile('Preserve system acceptance'), 'enabled': True, 'share_reflections': True})
        self.configs = {}
        for role in ('integration', 'mechanical', 'developer'):
            bid = 'bot-' + role
            self.call('configure_bot', {'bot_id': bid, 'organization_id': 'studio', 'version': 0,
                'name': role, 'parent_bot_id': None if role == 'integration' else 'bot-integration',
                'profile': profile(role + ' persistent expertise'), 'enabled': True})
            self.bind(role)
            config = {'bot_id': bid, 'name': role + ' fixture runtime', 'backend': 'external_agent',
                'environment_definition': 'synthetic deterministic fixture', 'tools': []}
            self.configs[role] = config
            self.call('configure_bot_runtime', {'bot_id': bid, 'version': 0, 'enabled': True,
                'principal_id': 'admin' if role == 'developer' else 'mentor', 'environment': environment_manifest(config)})
        return r

    def bind(self, role):
        return self.call('bind_bot', {'bot_id': 'bot-' + role, 'session_id': self.session['id'],
                                    'role': role, 'version': 0, 'enabled': True})

    def worker(self, role, infer=None, client=None):
        return BotWorker(client or (self.client if role == 'developer' else self.mentor), self.configs[role],
                         self.root/'bots', infer or self.inference)

    def second_session(self):
        self.session = self.connect()
        d = self.detail()['session']
        self.call('configure_development', {'session_id': d['id'], 'version': d['version'], 'reason': 'Next authorized assignment',
            **{**self.policy(), 'actors': ['admin', 'mentor'], 'write_scope': ['input.txt']}})
        self.call('configure_review_team', {**self.team_args, 'session_id': d['id'], 'version': 0})
        self.call('configure_review_automation', {'session_id': d['id'], 'version': 0, 'enabled': True,
            'max_rounds': 1, 'max_jobs': 10, 'developer_principal': 'admin'})
        self.base = self.initialize(); self.cp = self.checkpoint(self.begin(self.base))
        for role in self.configs: self.bind(role)
        return self.submit(self.cp['change'])

    def test_offline_queue_automatic_loop_and_cross_session_fresh_worker(self):
        r = self.setup_bots()
        first_sid = r['session_id']
        self.assertEqual(self.mentor.call('get_persistent_bot', {'bot_id': 'bot-mechanical'})['runtime']['presence'], 'offline')
        self.assertEqual(len(self.mentor.call('bot_inbox', {'bot_id': 'bot-mechanical'})['jobs']), 1)
        with self.worker('mechanical') as mech, self.worker('integration') as lead, self.worker('developer') as dev:
            self.assertEqual(lead.tick()[0]['reason'], 'review_pending')
            mech.tick(); lead.tick(); result = dev.tick()
            self.assertEqual(result[0]['status'], 'completed')
            lead.tick(); mech.tick(); lead.tick()
        self.assertTrue(all(j['status'] == 'completed' for j in self.jobs()))
        memories = self.mentor.call('list_persistent_memories', {'bot_id': 'bot-integration'})['items']
        self.assertTrue(any(m['source'] == 'review_reflection' for m in memories))
        self.assertTrue(self.call('list_persistent_memories', {'bot_id': 'bot-developer'})['items'])
        self.assertEqual(self.detail()['session']['active_state'], self.base['id'])
        self.assertTrue(any(m['memory_scope'] == 'organization' for m in
            self.mentor.call('list_persistent_memories', {'bot_id': 'bot-mechanical'})['items']))
        r2 = self.second_session(); seen = []
        fresh = LocalClient(Service(self.service.store.directory, clock=self.service.clock), self.mentor_token)
        def infer(ctx, schema, directory):
            seen.append(ctx['review']['bot_context'])
            return self.inference(ctx, schema, directory)
        with self.worker('mechanical', infer, fresh) as worker: worker.tick()
        ctx = seen[0]
        self.assertEqual(ctx['bot_id'], 'bot-mechanical')
        self.assertEqual(ctx['profile']['mission'], 'mechanical persistent expertise')
        self.assertTrue(any(m['session_id'] == first_sid for m in ctx['persistent_memory']['items']))
        self.assertTrue(any(m['memory_scope'] == 'organization' for m in ctx['persistent_memory']['items']))
        self.assertNotEqual(first_sid, r2['session_id'])
        view = self.call('get_change_review', {'submission_id': r2['id']})
        self.assertEqual(view['development']['status']['adoption'], 'unadopted')
        self.assertTrue(self.call('replay')['matched'])

    def test_source_revocation_and_role_isolation(self):
        r = self.setup_bots(); memory = self.memory(r)
        self.call('share_organization_memory', {'organization_id': 'studio', 'memory_id': memory['id'], 'reason': 'Owner shares evidence'})
        self.fault('human_approval_required', lambda: self.mentor.call('share_organization_memory',
            {'organization_id': 'studio', 'memory_id': memory['id'], 'reason': 'Agent cannot expand sharing'}))
        self.second_session()
        self.assertTrue(self.mentor.call('list_persistent_memories', {'bot_id': 'bot-mechanical'})['items'])
        d = self.call('development_state', {'session_id': r['session_id']})['session']
        self.call('configure_development', {'session_id': d['id'], 'version': d['version'], 'reason': 'Remove source access',
            **{**self.policy(), 'actors': ['admin'], 'write_scope': ['input.txt']}})
        self.assertFalse(self.mentor.call('list_persistent_memories', {'bot_id': 'bot-mechanical'})['items'])
        self.fault('unauthorized', lambda: self.mentor.call('get_persistent_bot', {'bot_id': 'bot-developer'}))
        self.assertTrue(self.call('replay')['matched'])

    def test_concurrent_runtimes_and_stale_output_are_fenced(self):
        r = self.setup_bots()
        with self.worker('mechanical') as worker:
            rt = worker.runtime
            self.fault('conflict', lambda: self.mentor.call('start_bot_runtime', {'bot_id': rt['id'],
                'version': rt['version'], 'instance_id': 'other', 'environment_hash': rt['environment_hash']}))
            job = self.mentor.call('bot_inbox', {'bot_id': rt['id']})['jobs'][0]
            self.fault('stale_basis', lambda: self.mentor.call('claim_mentor_job', {'job_id': job['id'], 'lease_seconds': 60}))
            claim = self.mentor.call('claim_mentor_job', {'job_id': job['id'], 'lease_seconds': 60, 'runtime_fence': rt['fence']})
            status = self.mentor.call('review_automation_status', {'session_id': r['session_id']})
            self.assertNotIn(rt['fence'], json.dumps(status))
            self.call('configure_bot', {'bot_id': rt['id'], 'organization_id': 'studio', 'version': 1,
                'name': 'mechanical', 'parent_bot_id': 'bot-integration', 'profile': profile('Changed onboarding'), 'enabled': True})
            self.fault('stale_basis', lambda: self.mentor.call('finish_mentor_job', {'job_id': job['id'], 'fence': claim['fence'],
                'output': {'summary': 'Old inference', 'evidence': [r['state_id']], 'unresolved': []}, 'provider': {'kind': 'fixture'}}))
        self.assertTrue(self.call('replay')['matched'])

    def test_interrupt_after_saved_inference_recovers_without_repeating(self):
        self.setup_bots(); calls = []
        def broken(ctx, schema, directory):
            calls.append(ctx['task'])
            receipt = self.inference(ctx, schema, directory)
            from gantry.runner import persist
            persist(Path(directory)/'inference.json', {'phase': 'completed', 'context': ctx, 'schema': schema, 'receipt': receipt})
            raise Fault('temporarily_unavailable', 'Fixture interruption after saving output')
        with self.worker('mechanical', broken) as worker:
            held = worker.tick(); job_id = held[0]['job_id']
            self.assertEqual(held[0]['status'], 'held')
        def reuse(ctx, schema, directory):
            return json.loads((Path(directory)/'inference.json').read_text())['receipt']
        with self.worker('mechanical', reuse) as worker:
            self.assertEqual(worker.tick()[0]['reason'], 'explicit_recovery_required')
            result = worker.recover(job_id, 'Previous fixture worker exited')
            self.assertEqual(result['status'], 'completed')
        self.assertEqual(calls, ['specialist'])
        self.assertTrue(self.call('replay')['matched'])

    def test_agent_cannot_reconfigure_identity_runtime_or_hierarchy(self):
        self.setup_bots()
        self.fault('human_approval_required', lambda: self.mentor.call('configure_bot_runtime', {
            'bot_id': 'bot-mechanical', 'version': 1, 'principal_id': 'mentor', 'enabled': True,
            'environment': environment_manifest(self.configs['mechanical'])}))
        self.fault('invalid_input', lambda: self.call('configure_bot', {'bot_id': 'bot-integration',
            'organization_id': 'studio', 'version': 1, 'name': 'lead', 'parent_bot_id': 'bot-mechanical',
            'profile': profile(), 'enabled': True}))
        bad = {**self.configs['mechanical'], 'tools': ['unapproved tool']}
        self.fault('stale_basis', lambda: BotWorker(self.mentor, bad, self.root/'other', self.inference).__enter__())
        self.assertTrue(self.call('replay')['matched'])

    def test_customer_command_executes_and_reuses_receipt(self):
        bridge = self.root/'bridge'
        bridge.write_text('#!' + sys.executable + '\nimport json,sys\nr=json.load(sys.stdin)\nprint(json.dumps({"summary":"fixture bridge", "evidence":[], "unresolved":[]}))\n')
        bridge.chmod(0o700)
        config = {'command': [str(bridge)], 'executable_hash': hashlib.sha256(bridge.read_bytes()).hexdigest()}
        from gantry.mentor_jobs import SPECIALIST
        result = infer_command(config, {'fixture': True}, SPECIALIST, self.root/'model')
        self.assertEqual(result['provider']['kind'], 'customer_command')
        self.assertEqual(result, infer_command(config, {'fixture': True}, SPECIALIST, self.root/'model'))
        bridge.write_text('changed')
        self.fault('stale_basis', lambda: infer_command(config, {'fixture': True}, SPECIALIST, self.root/'model'))

    def test_cross_session_contradiction_retains_old_evidence(self):
        r = self.setup_bots(); memory = self.memory(r)
        r2 = self.second_session()
        newer = self.memory(r2, assessment='contradicted', contradicts=memory['id'])
        memories = self.mentor.call('list_persistent_memories', {'bot_id': 'bot-mechanical'})['items']
        self.assertEqual({m['id'] for m in memories}, {memory['id'], newer['id']})
        self.assertTrue(self.call('replay')['matched'])

    def test_revocation_during_inference_blocks_file_edit(self):
        self.setup_bots()
        with self.worker('mechanical') as mech: mech.tick()
        with self.worker('integration') as lead: lead.tick()
        def revoked(ctx, schema, directory):
            receipt = self.inference(ctx, schema, directory)
            self.call('configure_organization', {'organization_id': 'studio', 'version': 1,
                'name': 'Paused', 'profile': profile(), 'enabled': False})
            return receipt
        with self.worker('developer', revoked) as dev:
            result = dev.tick()[0]
            self.assertEqual(result['reason'], 'mode_disabled')
            workspace = dev.root/'jobs'/digest(result['job_id'])/'workspace'
            self.assertNotEqual((workspace/'input.txt').read_text(), 'corrected')
        self.assertTrue(self.call('replay')['matched'])

    def test_environment_and_expired_runtime_need_explicit_recovery(self):
        self.setup_bots()
        with self.worker('mechanical') as worker:
            rt = worker.runtime
            job = self.mentor.call('bot_inbox', {'bot_id': rt['id']})['jobs'][0]
            claimed = self.mentor.call('claim_mentor_job', {'job_id': job['id'], 'lease_seconds': 900, 'runtime_fence': rt['fence']})
            now = self.service.clock(); self.service.clock = lambda: now + 61000
            self.fault('stale_basis', lambda: self.mentor.call('check_mentor_job', {'job_id': job['id'], 'fence': claimed['fence']}))
            rt2 = self.mentor.call('start_bot_runtime', {'bot_id': rt['id'], 'version': rt['version'],
                'instance_id': 'replacement', 'environment_hash': rt['environment_hash']})
            self.fault('stale_basis', lambda: self.mentor.call('heartbeat_bot_runtime', {'bot_id': rt['id'], 'fence': rt['fence']}))
            self.assertNotEqual(rt['fence'], rt2['fence'])
            self.assertEqual(self.mentor.call('bot_inbox', {'bot_id': rt['id']})['jobs'][0]['status'], 'running')
        self.assertTrue(self.call('replay')['matched'])

    def test_opt_in_service_files_and_no_default_model(self):
        from gantry.bot_worker import service_manifest
        import plistlib
        cfg = self.root/'bot.json'; cfg.write_text('{}')
        launch = plistlib.loads(service_manifest(cfg, self.root/'journal', sys.executable, 'launchd').encode())
        self.assertTrue(launch['RunAtLoad'])
        self.assertIn('bot-worker', launch['ProgramArguments'])
        unit = service_manifest(cfg, self.root/'journal', sys.executable, 'systemd')
        self.assertIn('Restart=on-failure', unit)
        self.fault('invalid_input', lambda: BotWorker(self.client, {'bot_id': 'absent'}, self.root/'disabled'))

    def test_installed_customer_bridge_runs_queued_job_without_inference_override(self):
        self.setup_bots()
        bridge = self.root/'fixture-customer-agent'
        bridge.write_text('#!' + sys.executable + '\nimport json,sys\nr=json.load(sys.stdin)\n'
            'print(json.dumps({"summary":"Synthetic customer process report",'
            '"evidence":[r["context"]["review"]["state_id"]],"unresolved":[]}))\n')
        bridge.chmod(0o700)
        config = {**self.configs['mechanical'], 'command': [str(bridge)],
                  'executable_hash': hashlib.sha256(bridge.read_bytes()).hexdigest()}
        self.call('configure_bot_runtime', {'bot_id': 'bot-mechanical', 'version': 1, 'enabled': True,
            'principal_id': 'mentor', 'environment': environment_manifest(config)})
        with BotWorker(self.mentor, config, self.root/'customer-process') as worker:
            result = worker.tick()[0]
            self.assertEqual(result['status'], 'completed')
            receipt = json.loads((worker.root/'jobs'/digest(result['job_id'])/'job.json').read_text())
            self.assertEqual(receipt['receipt']['provider']['kind'], 'customer_command')
            self.assertIn('Synthetic', receipt['receipt']['output']['summary'])
        memory = self.mentor.call('list_persistent_memories', {'bot_id': 'bot-mechanical'})['items']
        self.assertEqual(memory[0]['source'], 'bot_job')
        self.assertTrue(self.call('replay')['matched'])

    def test_lost_recovery_ack_survives_another_runtime_restart(self):
        self.setup_bots(); inference_calls = []
        def broken(ctx, schema, directory):
            from gantry.runner import persist
            inference_calls.append(ctx['task'])
            persist(Path(directory)/'inference.json', {'phase': 'completed', 'context': ctx, 'schema': schema,
                'receipt': self.inference(ctx, schema, directory)})
            raise OSError('Fixture: worker interrupted after receipt')
        with self.worker('mechanical', broken) as worker:
            job_id = worker.tick()[0]['job_id']
        def reuse(ctx, schema, directory):
            return json.loads((Path(directory)/'inference.json').read_text())['receipt']
        delegate = self.mentor
        class LostAck:
            def call(self, command, args=None, key=None):
                result = delegate.call(command, args, key)
                if command == 'recover_mentor_job': raise OSError('Fixture: response lost after commit')
                return result
        with self.worker('mechanical', reuse, LostAck()) as worker:
            with self.assertRaises(OSError): worker.recover(job_id, 'Previous process stopped')
        with self.worker('mechanical', reuse) as worker:
            self.assertEqual(worker.recover(job_id, 'Both previous processes stopped')['status'], 'completed')
        self.assertEqual(inference_calls, ['specialist'])
        self.assertEqual(self.call('review_automation_status', {'session_id': self.session['id']})['policy']['used_jobs'], 1)
        self.assertTrue(self.call('replay')['matched'])

    def test_disabled_binding_cannot_write_persistent_experience(self):
        r = self.setup_bots()
        self.call('bind_bot', {'bot_id': 'bot-mechanical', 'session_id': self.session['id'],
            'role': 'mechanical', 'version': 1, 'enabled': False})
        self.fault('unauthorized', lambda: self.memory(r))
        self.assertTrue(self.call('replay')['matched'])
