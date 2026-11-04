"""Customer setup host boundaries and integration; inference is explicitly synthetic."""
import json
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch

from gantry.model import Fault
from gantry.project_connect import load, save
import test_crew_setup as fixtures


class HostBoundaryTests(unittest.TestCase):
    def test_uncertain_inference_is_not_repeated_and_completed_receipt_replays(self):
        import tempfile
        from gantry.crew_setup_host import guarded_inference
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); calls = []
            def fail(*args):
                calls.append(1)
                raise OSError('private credential must never be public')
            infer = guarded_inference(fail)
            with self.assertRaises(OSError): infer({'input': 'fixture'}, {}, root/'uncertain')
            with self.assertRaises(Fault) as caught: infer({'input': 'fixture'}, {}, root/'uncertain')
            self.assertEqual(caught.exception.code, 'outcome_unknown')
            self.assertEqual(len(calls), 1)
            success = guarded_inference(lambda *_: {'output': {'ok': True}, 'provider': {'private': 'secret'}})
            first = success({}, {}, root/'complete')
            second = guarded_inference(fail)({}, {}, root/'complete')
            self.assertEqual(first, second)
            self.assertEqual(len(calls), 1)
            from gantry.model import digest
            save(root/'recover'/'host-inference.json', {'intent': digest({'context': {}, 'schema': {}})})
            save(root/'recover'/'inference.json', {'phase': 'completed', 'context': {}, 'schema': {}, 'receipt': first})
            self.assertEqual(guarded_inference(fail)({}, {}, root/'recover'), first)
            self.assertEqual(len(calls), 1)

    def test_local_configuration_requires_explicit_backend_and_rejects_browser_fields(self):
        from gantry.crew_setup_host import host_configuration
        with self.assertRaises(Fault): host_configuration('paid-api', {'name': 'Tools'})
        with self.assertRaises(Fault):
            host_configuration('codex-subscription', {'name': 'Tools', 'token_file': '/private'})
        with self.assertRaises(Fault):
            host_configuration('codex-subscription', {'name': 'Tools'}, {'command': ['/bad']})
        result = host_configuration('codex-subscription', {'name': 'Tools', 'tools': []})
        self.assertEqual(result['backend'], 'codex-subscription')
        self.assertEqual(result['runtime_template']['workflow'], 'bot_development')

    def test_cli_connection_is_private_and_preserves_exact_configuration(self):
        import argparse
        import tempfile
        from gantry.crew_setup_host_cli import add_parser, connection
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); token = root/'owner.token'; token.write_text('fixture-owner-token'); token.chmod(0o600)
            template = root/'runtime.json'; save(template, {'name': 'Customer tools'})
            parser = argparse.ArgumentParser(); parser.add_argument('--url', default='http://127.0.0.1:8765')
            parser.add_argument('--token-file', default=str(token)); add_parser(parser.add_subparsers(dest='command'))
            argv = ['crew-setup-host', 'connect', '--journal', str(root/'host'), '--backend', 'codex-subscription',
                    '--runtime-template', str(template)]
            first = connection(parser.parse_args(argv))
            self.assertEqual(first, connection(parser.parse_args(argv)))
            self.assertNotIn('fixture-owner-token', (root/'host'/'connection.json').read_text())
            self.assertEqual(first, connection(parser.parse_args(['crew-setup-host', 'run', '--journal', str(root/'host')])))
            save(template, {'name': 'Changed tools'})
            with self.assertRaises(Fault): connection(parser.parse_args(argv))


class HostIntegrationTests(unittest.TestCase):
    setUp = fixtures.CrewSetupTests.setUp
    tearDown = fixtures.CrewSetupTests.tearDown
    call = fixtures.CrewSetupTests.call
    artifact = fixtures.CrewSetupTests.artifact
    connect = fixtures.CrewSetupTests.connect
    policy = fixtures.CrewSetupTests.policy
    imported = fixtures.CrewSetupTests.imported
    setup = fixtures.CrewSetupTests.setup
    proposal = fixtures.CrewSetupTests.proposal

    def host(self, infer=None, **kwargs):
        from gantry.crew_setup_host import CrewSetupHost, host_configuration
        self.client.url = 'http://127.0.0.1:8765'
        config = host_configuration('codex-subscription', {'name': 'Customer tools'})
        return CrewSetupHost(self.client, 'test-host', 'Fixture host', self.root/'host', config,
                             infer_fn=infer, **kwargs)

    def request(self, host, setup_id, action, **extra):
        d = self.call('get_crew_setup', {'setup_id': setup_id})
        if action == 'start':
            extra.setdefault('session_version', self.call('development_state', {'session_id': d['session_id']})['session']['version'])
        return self.call('request_crew_setup_job', {'setup_id': setup_id, 'version': d['version'],
            'host_id': host.host_id, 'config_hash': host.config_hash, 'action': action, **extra})

    def test_analyze_prepares_only_public_allowlisted_review_and_does_not_activate(self):
        d = self.setup(); calls = []
        def infer(*_):
            calls.append(1)
            return {'output': self.proposal(d), 'provider': {'secret': 'private-provider-value'}}
        with self.host(infer) as host:
            requested = self.request(host, d['id'], 'analyze')
            result = host.tick()
            self.assertEqual(result['id'], requested['id'])
            self.assertEqual(result['status'], 'succeeded')
            control = self.call('get_crew_setup_control', {'setup_id': d['id']})
            self.assertTrue(control['hosts'][0]['online'])
            prepared = control['prepared']; self.assertEqual(len(prepared['roles']), 2)
            self.assertEqual(set(prepared['roles'][0]), {'role_id', 'principal_id', 'reused', 'name', 'tools'})
            public = str(control)
            for secret in ('token_file', 'config_file', 'worker_commands', 'private-provider-value', str(self.root)):
                self.assertNotIn(secret, public)
            self.assertFalse(self.call('state').get('persistent_bots'))
            self.assertEqual(len(calls), 1)
        self.assertFalse(self.call('get_crew_setup_control', {'setup_id': d['id']})['hosts'][0]['online'])

    def test_failed_inference_is_held_and_explicit_resume_never_reinvokes_unknown_call(self):
        d = self.setup(); calls = []
        def infer(*_):
            calls.append(1)
            raise OSError('private-command and private-token')
        with self.host(infer) as host:
            job = self.request(host, d['id'], 'analyze')
            held = host.tick(); self.assertEqual(held['status'], 'held')
            self.assertNotIn('private-', held['summary'])
            self.call('resume_crew_setup_job', {'job_id': job['id']})
            self.assertEqual(host.tick()['status'], 'held')
            self.assertEqual(len(calls), 1)

    def test_heartbeat_keeps_host_online_during_long_inference_and_lock_prevents_duplicate_host(self):
        d = self.setup(); entered = threading.Event(); release = threading.Event(); outcomes = []
        def infer(*_):
            entered.set(); release.wait(5)
            return {'output': self.proposal(d)}
        heartbeat = threading.Event(); original_call = self.client.call
        def call(name, args=None, key=None):
            result = original_call(name, args, key)
            if name == 'heartbeat_crew_setup_host' and entered.is_set(): heartbeat.set()
            return result
        self.client.call = call
        with self.host(infer, heartbeat_interval=.01) as host:
            self.request(host, d['id'], 'analyze')
            thread = threading.Thread(target=lambda: outcomes.append(host.tick())); thread.start()
            try:
                self.assertTrue(entered.wait(2))
                with self.assertRaises(Fault):
                    with self.host(infer): pass
                self.assertTrue(heartbeat.wait(2))
                control = self.call('get_crew_setup_control', {'setup_id': d['id']})
                self.assertTrue(control['hosts'][0]['online'])
            finally: release.set(); thread.join(5)
            self.assertEqual(outcomes[0]['status'], 'succeeded')

    def test_lost_finish_acknowledgement_replays_exact_job_without_new_inference(self):
        d = self.setup(); calls = []; original = self.client.call; lost = []
        def infer(*_): calls.append(1); return {'output': self.proposal(d)}
        def call(name, args=None, key=None):
            result = original(name, args, key)
            if name == 'finish_crew_setup_job' and not lost:
                lost.append(1); raise OSError('lost receipt')
            return result
        self.client.call = call
        with self.host(infer) as host:
            job = self.request(host, d['id'], 'analyze')
            with self.assertRaises(OSError): host.tick()
            result = host.tick()
            self.assertEqual(result['id'], job['id']); self.assertEqual(result['status'], 'succeeded')
            self.assertEqual(len(calls), 1)

    def test_actual_workers_start_first_task_and_stop_after_explicit_policy(self):
        from gantry.crew_setup_host_workers import HostWorkers
        from test_development import LocalClient
        d = self.setup(); seen = threading.Event()
        def worker_infer(context, schema, directory):
            if context.get('operation') == 'reflect_on_experience':
                return {'output': {'summary': 'No new lesson', 'lessons': [], 'feedback': []}}
            seen.set()
            answer = {'summary': 'Saved-source synthetic report', 'rationale': 'Checked the onboarding context',
                'status': 'completed', 'unverified': ['Physical clearance'], 'edits': [], 'assignments': [], 'integrate_changes': []}
            return {'output': {'action': 'finish', 'arguments_json': json.dumps(answer), 'rationale': 'Report fixture outcome'}}
        workers = HostWorkers(self.root/'host'/'workers', client_factory=lambda config:
            LocalClient(self.service, Path(config['token_file']).read_text().strip()), infer_fn=worker_infer, interval=.02)
        with self.host(lambda *_: {'output': self.proposal(d)}, workers=workers) as host:
            self.request(host, d['id'], 'analyze'); self.assertEqual(host.tick()['status'], 'succeeded')
            prepared = self.call('get_crew_setup_control', {'setup_id': d['id']})['prepared']
            hashes = {k: prepared[k] for k in ('proposal_hash', 'runtime_plan_hash')}
            self.request(host, d['id'], 'activate', **hashes)
            self.assertEqual(host.tick()['status'], 'succeeded')
            self.assertFalse(workers.workers)
            self.assertFalse(self.call('list_bot_tasks', {'session_id': self.sid})['items'])
            with self.assertRaises(Fault): self.request(host, d['id'], 'start', **hashes)
            session = self.call('development_state', {'session_id': self.sid})['session']
            self.call('studio_execution_policy', {'session_id': self.sid, 'version': session['version'],
                'enabled': True, 'max_parallel': 2, 'max_executions': None})
            self.request(host, d['id'], 'start', **hashes)
            result = host.tick(); self.assertEqual(result['status'], 'succeeded')
            self.assertTrue(seen.wait(3))
            deadline = time.monotonic()+3
            while time.monotonic() < deadline:
                tasks = self.call('list_bot_tasks', {'session_id': self.sid})['items']
                if tasks and tasks[0]['status'] == 'completed': break
                time.sleep(.02)
            self.assertEqual(len(tasks), 1); self.assertEqual(tasks[0]['status'], 'completed')
            self.request(host, d['id'], 'stop')
            self.assertEqual(host.tick()['status'], 'succeeded')
            current = self.call('get_crew_setup', {'setup_id': d['id']})
            self.assertTrue(all(r['runtime'] == 'offline' for r in current['readiness']))
            self.assertFalse(workers.workers)
        self.assertTrue(self.call('replay')['matched'])

    def activate_for_workers(self, host, d):
        self.request(host, d['id'], 'analyze'); self.assertEqual(host.tick()['status'], 'succeeded')
        prepared = self.call('get_crew_setup_control', {'setup_id': d['id']})['prepared']
        hashes = {k: prepared[k] for k in ('proposal_hash', 'runtime_plan_hash')}
        self.request(host, d['id'], 'activate', **hashes); self.assertEqual(host.tick()['status'], 'succeeded')
        session = self.call('development_state', {'session_id': self.sid})['session']
        self.call('studio_execution_policy', {'session_id': self.sid, 'version': session['version'],
            'enabled': True, 'max_parallel': 2, 'max_executions': None})
        return hashes

    def test_resumed_start_restarts_workers_without_duplicating_the_saved_first_task(self):
        from gantry.crew_setup_host_workers import HostWorkers
        from test_development import LocalClient
        class QuietWorkers(HostWorkers):
            # Real runtime registration/heartbeat, no model work needed for this recovery scenario.
            def run_setup(self, setup_id): pass
        def workers():
            return QuietWorkers(self.root/'host'/'workers', client_factory=lambda config:
                LocalClient(self.service, Path(config['token_file']).read_text().strip()))
        d = self.setup(); original = self.client.call; interrupted = []
        def call(name, args=None, key=None):
            if name == 'finish_crew_setup_job' and args['summary'].startswith('Customer workers') and not interrupted:
                interrupted.append(1); raise OSError('interrupted before finish')
            return original(name, args, key)
        self.client.call = call
        with self.host(lambda *_: {'output': self.proposal(d)}, workers=workers()) as host:
            hashes = self.activate_for_workers(host, d)
            job = self.request(host, d['id'], 'start', **hashes)
            with self.assertRaises(OSError): host.tick()
            task_id = self.call('get_crew_setup', {'setup_id': d['id']})['result']['first_task_id']
        with self.host(lambda *_: self.fail('Never reinfer a saved proposal'), workers=workers()) as host:
            self.call('resume_crew_setup_job', {'job_id': job['id']})
            result = host.tick(); self.assertEqual(result['status'], 'succeeded')
            current = self.call('get_crew_setup', {'setup_id': d['id']})
            self.assertEqual(current['result']['first_task_id'], task_id)
            self.assertTrue(all(r['runtime'] == 'online' for r in current['readiness']))
            self.assertEqual(len(self.call('list_bot_tasks', {'session_id': self.sid})['items']), 1)

    def test_committed_start_with_lost_ack_reconciles_without_reexecuting_after_policy_changes(self):
        from gantry.crew_setup_host_workers import HostWorkers
        from test_development import LocalClient
        class QuietWorkers(HostWorkers):
            def run_setup(self, setup_id): pass
        workers = QuietWorkers(self.root/'host'/'workers', client_factory=lambda config:
            LocalClient(self.service, Path(config['token_file']).read_text().strip()))
        d = self.setup(); original = self.client.call; lost = []
        def call(name, args=None, key=None):
            result = original(name, args, key)
            if name == 'finish_crew_setup_job' and args['summary'].startswith('Customer workers') and not lost:
                lost.append(1); raise OSError('Lost committed finish')
            return result
        self.client.call = call
        with self.host(lambda *_: {'output': self.proposal(d)}, workers=workers) as host:
            hashes = self.activate_for_workers(host, d)
            job = self.request(host, d['id'], 'start', **hashes)
            with self.assertRaises(OSError): host.tick()
            session = self.call('development_state', {'session_id': self.sid})['session']
            self.call('studio_execution_policy', {'session_id': self.sid, 'version': session['version'],
                'enabled': False, 'max_parallel': 2, 'max_executions': None})
            result = host.tick()
            self.assertEqual(result['id'], job['id']); self.assertEqual(result['status'], 'succeeded')
            self.assertIsNone(host.tick())

    def test_stale_policy_finish_holds_then_retry_only_stops_and_allows_fresh_start(self):
        from gantry.crew_setup_host_workers import HostWorkers
        from gantry.model import digest
        from test_development import LocalClient
        class QuietWorkers(HostWorkers):
            starts = 0
            def start_setup(self, setup_id, prepared):
                self.starts += 1
                return super().start_setup(setup_id, prepared)
            def run_setup(self, setup_id): pass
        workers = QuietWorkers(self.root/'host'/'workers', client_factory=lambda config:
            LocalClient(self.service, Path(config['token_file']).read_text().strip()))
        d = self.setup(); original = self.client.call; changed = []
        def call(name, args=None, key=None):
            if name == 'finish_crew_setup_job' and args['summary'].startswith('Customer workers') and not changed:
                changed.append(1)
                session = original('development_state', {'session_id': self.sid})['session']
                original('studio_execution_policy', {'session_id': self.sid, 'version': session['version'],
                    'enabled': True, 'max_parallel': 1, 'max_executions': None})
            return original(name, args, key)
        self.client.call = call
        with self.host(lambda *_: {'output': self.proposal(d)}, workers=workers) as host:
            hashes = self.activate_for_workers(host, d)
            job = self.request(host, d['id'], 'start', **hashes)
            held = host.tick(); self.assertEqual(held['status'], 'held')
            path = host.root/'jobs'/digest(job['id'])/'job.json'
            completed = load(path)['completed']
            task_id = self.call('get_crew_setup', {'setup_id': d['id']})['result']['first_task_id']
            resumed = self.call('resume_crew_setup_job', {'job_id': job['id']})
            self.assertTrue(resumed['recovery_only'])
            original_journal = load(path); path.unlink()
            self.assertEqual(host.tick()['status'], 'held')
            self.assertEqual(workers.starts, 1)
            self.assertFalse(path.exists())
            save(path, original_journal)
            self.call('resume_crew_setup_job', {'job_id': job['id']})
            self.assertEqual(host.tick()['status'], 'cancelled')
            self.assertEqual(workers.starts, 1)
            self.assertEqual(load(path)['completed'], completed)
            current = self.call('get_crew_setup', {'setup_id': d['id']})
            self.assertEqual(current['result']['first_task_id'], task_id)
            self.assertTrue(all(r['runtime'] == 'offline' for r in current['readiness']))
            fresh = self.request(host, d['id'], 'start', **hashes)
            self.assertNotEqual(fresh['id'], job['id'])
            self.assertEqual(host.tick()['status'], 'succeeded')
            self.assertEqual(workers.starts, 2)
            self.assertEqual(self.call('get_crew_setup', {'setup_id': d['id']})['result']['first_task_id'], task_id)

    def test_stop_during_inference_reaps_finished_handles_before_next_start(self):
        from gantry.crew_setup_host_workers import HostWorkers
        from test_development import LocalClient
        entered = threading.Event(); release = threading.Event(); calls = []
        def infer(*_):
            calls.append(1); entered.set(); release.wait(6)
            raise OSError('Synthetic interrupted provider')
        workers = HostWorkers(self.root/'host'/'workers', client_factory=lambda config:
            LocalClient(self.service, Path(config['token_file']).read_text().strip()), infer_fn=infer, interval=.01)
        d = self.setup()
        with self.host(lambda *_: {'output': self.proposal(d)}, workers=workers) as host:
            hashes = self.activate_for_workers(host, d)
            self.request(host, d['id'], 'start', **hashes); self.assertEqual(host.tick()['status'], 'succeeded')
            try:
                self.assertTrue(entered.wait(2))
                self.request(host, d['id'], 'stop'); self.assertEqual(host.tick()['status'], 'succeeded')
                self.assertTrue(any(h['thread'].is_alive() for h in workers.workers.values()))
            finally: release.set()
            for handle in list(workers.workers.values()): handle['thread'].join(3)
            self.request(host, d['id'], 'start', **hashes)
            self.assertEqual(host.tick()['status'], 'succeeded')
            self.assertEqual(len(calls), 1)
            current = self.call('get_crew_setup', {'setup_id': d['id']})
            self.assertTrue(all(r['runtime'] == 'online' for r in current['readiness']))

    def test_missing_original_journal_on_resume_holds_without_inference(self):
        d = self.setup()
        with self.host(lambda *_: self.fail('No inference expected')) as host:
            job = self.request(host, d['id'], 'analyze')
            self.call('claim_crew_setup_job', {'host_id': host.host_id, 'instance_id': host.instance_id})
        with self.host(lambda *_: self.fail('Missing journal must never reinfer')) as host:
            self.call('resume_crew_setup_job', {'job_id': job['id']})
            result = host.tick()
            self.assertEqual(result['status'], 'held')

    def test_failed_start_rolls_back_new_workers_before_any_model_work(self):
        from gantry.crew_setup_host_workers import HostWorkers
        from test_development import LocalClient
        workers = HostWorkers(self.root/'host'/'workers', client_factory=lambda config:
            LocalClient(self.service, Path(config['token_file']).read_text().strip()),
            infer_fn=lambda *_: self.fail('Failed start must never dispatch provider work'))
        d = self.setup(); original = self.client.call
        with self.host(lambda *_: {'output': self.proposal(d)}, workers=workers) as host:
            hashes = self.activate_for_workers(host, d)
            def call(name, args=None, key=None):
                if name == 'start_crew_setup_work': raise OSError('Synthetic unavailable Core')
                return original(name, args, key)
            self.client.call = call
            self.request(host, d['id'], 'start', **hashes)
            self.assertEqual(host.tick()['status'], 'held')
            self.assertFalse(workers.workers)
            current = self.call('get_crew_setup', {'setup_id': d['id']})
            self.assertTrue(all(r['runtime'] == 'offline' for r in current['readiness']))

    def test_lost_stop_ack_is_held_then_resume_reconciles_every_owned_worker(self):
        from gantry.crew_setup_host_workers import HostWorkers
        from test_development import LocalClient
        class QuietWorkers(HostWorkers):
            def run_setup(self, setup_id): pass
        workers = QuietWorkers(self.root/'host'/'workers', client_factory=lambda config:
            LocalClient(self.service, Path(config['token_file']).read_text().strip()))
        d = self.setup()
        with self.host(lambda *_: {'output': self.proposal(d)}, workers=workers) as host:
            hashes = self.activate_for_workers(host, d)
            self.request(host, d['id'], 'start', **hashes); self.assertEqual(host.tick()['status'], 'succeeded')
            handle = next(iter(workers.workers.values())); original = handle['worker'].client.call; lost = []
            def call(name, args=None, key=None):
                result = original(name, args, key)
                if name == 'stop_bot_runtime' and not lost:
                    lost.append(1); raise OSError('Lost committed stop acknowledgement')
                return result
            handle['worker'].client.call = call
            job = self.request(host, d['id'], 'stop')
            self.assertEqual(host.tick()['status'], 'held')
            self.assertIn(d['id'], handle['setups'])
            current = self.call('get_crew_setup', {'setup_id': d['id']})
            self.assertTrue(all(r['runtime'] == 'offline' for r in current['readiness']))
            self.call('resume_crew_setup_job', {'job_id': job['id']})
            self.assertEqual(host.tick()['status'], 'succeeded')
            self.assertFalse(workers.workers)

    def test_explicit_stop_fences_shared_owned_runtimes_but_rollback_preserves_existing_references(self):
        from gantry.crew_setup_host_workers import HostWorkers
        from test_development import LocalClient
        class QuietWorkers(HostWorkers):
            def run_setup(self, setup_id): pass
        workers = QuietWorkers(self.root/'host'/'workers', client_factory=lambda config:
            LocalClient(self.service, Path(config['token_file']).read_text().strip()))
        d = self.setup()
        with self.host(lambda *_: {'output': self.proposal(d)}, workers=workers) as host:
            hashes = self.activate_for_workers(host, d)
            self.request(host, d['id'], 'start', **hashes); self.assertEqual(host.tick()['status'], 'succeeded')
            prepared = load(host._preparation(d['id'])/'preparation.json')
            added = workers.start_setup('shared-setup', prepared)
            self.assertEqual(len(added), 2)
            workers.stop_setup('shared-setup', only=added)
            self.assertTrue(all(h['setups'] == {d['id']} for h in workers.workers.values()))
            current = self.call('get_crew_setup', {'setup_id': d['id']})
            self.assertTrue(all(r['runtime'] == 'online' for r in current['readiness']))
            workers.start_setup('shared-setup', prepared)
            self.request(host, d['id'], 'stop'); self.assertEqual(host.tick()['status'], 'succeeded')
            current = self.call('get_crew_setup', {'setup_id': d['id']})
            self.assertTrue(all(r['runtime'] == 'offline' for r in current['readiness']))
            self.assertFalse(workers.workers)

    def test_new_setup_reuses_host_owned_private_bot_mappings_without_rewriting_files(self):
        from test_development import LocalClient
        d = self.setup(); proposals = {d['id']: self.proposal(d)}
        with self.host(lambda context, *_: {'output': proposals[context['setup_id']]}) as host:
            self.request(host, d['id'], 'analyze'); host.tick()
            prepared = self.call('get_crew_setup_control', {'setup_id': d['id']})['prepared']
            hashes = {k: prepared[k] for k in ('proposal_hash', 'runtime_plan_hash')}
            self.request(host, d['id'], 'activate', **hashes); self.assertEqual(host.tick()['status'], 'succeeded')
            original = self.call('get_crew_setup', {'setup_id': d['id']})
            saved = load(host._preparation(d['id'])/'preparation.json')
            old_files = {p: Path(p).read_bytes() for r in saved['runtimes']
                         for p in (r['config_file'], r['config']['token_file'])}
            old_runtimes = {r['bot_id']: self.call('get_persistent_bot', {'bot_id': r['bot_id']})['runtime']
                            for r in original['result']['roles']}
            second = self.call('start_crew_setup', {'session_id': self.sid, 'state_id': d['state_id'],
                'organization_id': original['result']['organization_id'], 'organization_name': 'Assembly team',
                'notes': 'Reuse the same customer workers', 'files': {}, 'sources': []})
            proposal = self.proposal(second)
            for role, previous in zip(proposal['roles'], original['result']['roles']):
                role['existing_bot_id'] = previous['bot_id']
            proposals[second['id']] = proposal
            with patch('gantry.crew_setup_client.Client', side_effect=lambda url, token: LocalClient(self.service, token)):
                self.request(host, second['id'], 'analyze')
                self.assertEqual(host.tick()['status'], 'succeeded')
            prepared = self.call('get_crew_setup_control', {'setup_id': second['id']})['prepared']
            self.assertTrue(all(r['reused'] for r in prepared['roles']))
            hashes = {k: prepared[k] for k in ('proposal_hash', 'runtime_plan_hash')}
            self.request(host, second['id'], 'activate', **hashes); self.assertEqual(host.tick()['status'], 'succeeded')
            self.assertEqual(old_files, {p: Path(p).read_bytes() for p in old_files})
            for bot_id, runtime in old_runtimes.items():
                self.assertEqual(runtime, self.call('get_persistent_bot', {'bot_id': bot_id})['runtime'])


if __name__ == '__main__': unittest.main()
