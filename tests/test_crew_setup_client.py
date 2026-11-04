"""Anonymous customer setup fixtures; no model or external tool is executed."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from gantry.model import Fault, digest
from gantry.project_connect import load, save


PROFILE = {'mission': 'Inspect saved work', 'responsibilities': ['Report evidence'],
           'focus_paths': ['src/'], 'workflow': ['Review then delegate'],
           'report_when': ['Blocked'], 'style': 'Concise', 'onboarding': ['Read source']}
PROPOSAL = {'organization_profile': PROFILE, 'goal': 'Review saved controller',
            'acceptance': ['Explain next test'], 'lead_role_id': 'lead',
            'roles': [{'role_id': 'lead', 'name': 'Project lead', 'parent_role_id': None,
                       'existing_bot_id': None, 'profile': PROFILE, 'write_scope': ['src/'],
                       'can_assign': True, 'can_integrate': True,
                       'rationale': 'Source defines controller review', 'evidence_ids': ['evidence-1']}],
            'unknowns': ['Native tooling unverified'],
            'first_task': {'title': 'Plan controller review', 'completion': ['List evidence and next test']}}


class SetupClient:
    """Models committed responses, including a deliberately lost acknowledgement."""
    url = 'http://127.0.0.1:8765'

    def __init__(self):
        self.actor = 'owner'; self.calls = []; self.responses = {}; self.lose = None
        self.runtime = None
        self.setup = {'id': 'setup-1', 'version': 1, 'status': 'draft',
            'session_id': 'session-1', 'state_id': 'state-1', 'snapshot': 'snapshot-1',
            'organization_id': 'organization-1', 'organization_name': 'Controller team',
            'notes': 'Review only', 'manifest': {}, 'basis': 'basis-1',
            'evidence_records': [{'id': 'evidence-1', 'text': 'Review controller'}],
            'source_limitations': ['Only selected saved exports'],
            'context': {'state': {'id': 'state-1'}, 'organization': None,
                        'existing_bots': [], 'scope': ['src/']}, 'proposal': None,
            'result': None, 'readiness': [], 'execution_enabled': False}

    def call(self, command, args=None, key=None):
        args = args or {}; self.calls.append((command, copy.deepcopy(args), key))
        if key in self.responses:
            previous, result = self.responses[key]
            assert previous == (command, args), 'Idempotency body changed'
            return copy.deepcopy(result)
        if command == 'identity':
            return {'id': self.actor, 'kind': 'human', 'permissions': ['read', 'work', 'admin']}
        if command == 'workspace_members':
            return {'ledger_id': 'ledger-1', 'members': [],
                    'sessions': [{'id': 'session-1', 'zone': 'root'}]}
        if command == 'get_crew_setup': return copy.deepcopy(self.setup)
        if command == 'get_persistent_bot': return {'runtime': copy.deepcopy(self.runtime)}
        if command == 'propose_crew_setup':
            self.setup['version'] += 1
            self.setup['status'] = 'proposed'
            self.setup['proposal'] = {'content': args['proposal'], 'hash': digest(args['proposal']), 'author': self.actor}
        elif command == 'activate_crew_setup':
            self.setup['version'] += 1; self.setup['status'] = 'activated'
            self.setup['result'] = {'organization_id': 'organization-1', 'lead_bot_id': 'bot-created',
                'roles': [{'role_id': 'lead', 'bot_id': 'bot-created',
                           'principal_id': args['bindings'][0]['principal_id']}]}
        elif command == 'configure_bot_runtime':
            self.runtime = {**args, 'version': 1, 'environment_hash': digest(args['environment'])}
        else: raise AssertionError(command)
        result = copy.deepcopy(self.runtime if command == 'configure_bot_runtime' else self.setup)
        if key: self.responses[key] = ((command, copy.deepcopy(args)), result)
        if command == self.lose:
            self.lose = None
            raise OSError('Committed response lost')
        return result


class CrewSetupClientTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.client = SetupClient()

    def tearDown(self): self.temp.cleanup()

    def proposal(self):
        self.client.setup['status'] = 'proposed'
        self.client.setup['proposal'] = {'content': copy.deepcopy(PROPOSAL), 'hash': digest(PROPOSAL), 'author': 'owner'}

    def test_analysis_retries_commit_without_repeating_inference_or_granting_authority(self):
        from gantry.crew_setup_client import analyze
        calls = []
        def infer(context, schema, directory):
            calls.append(context)
            self.assertEqual(context['evidence_records'][0]['id'], 'evidence-1')
            return {'output': copy.deepcopy(PROPOSAL), 'provider': {'kind': 'fixture'}}
        self.client.lose = 'propose_crew_setup'
        with self.assertRaises(OSError): analyze(self.client, 'setup-1', self.root/'analysis', infer, {'backend': 'fixture'})
        result = analyze(self.client, 'setup-1', self.root/'analysis', infer, {'backend': 'fixture'})
        self.assertEqual(len(calls), 1); self.assertFalse(result['project_executed'])
        self.assertNotIn('activate_crew_setup', [x[0] for x in self.client.calls])
        self.assertEqual((self.root/'analysis/submission.json').stat().st_mode & 0o777, 0o600)
        self.client.actor = 'another-owner'
        with self.assertRaises(Fault): analyze(self.client, 'setup-1', self.root/'analysis', infer, {'backend': 'fixture'})

    def test_prepare_activate_configure_keep_tokens_private_and_retry_exact_requests(self):
        from gantry.crew_setup_client import prepare, activate, configure
        self.proposal(); root = self.root/'runtimes'
        template = {'name': 'Customer tools', 'local_tools': {}, 'tool_runtime': ['/customer/runtime'],
                    'sandbox': 'seatbelt', 'tools': ['read_file']}
        prepared = prepare(self.client, 'setup-1', root, 'codex-subscription', template)
        self.assertEqual([x[0] for x in self.client.calls].count('activate_crew_setup'), 0)
        self.assertEqual(prepare(self.client, 'setup-1', root, 'codex-subscription', template), prepared)
        self.client.lose = 'activate_crew_setup'
        with self.assertRaises(OSError): activate(self.client, 'setup-1', root, prepared['proposal_hash'])
        activated = activate(self.client, 'setup-1', root, prepared['proposal_hash'])
        self.assertEqual(activated['status'], 'activated')
        cfg = load(Path(prepared['runtimes'][0]['config_file']))
        self.assertEqual(cfg['bot_id'], 'bot-created'); self.assertTrue(cfg['agent_loop'])
        self.assertEqual(cfg['local_tools'], template['local_tools'])
        self.assertEqual(cfg['learning_mode'], 'selective'); self.assertTrue(cfg['personal_continuity'])
        token = Path(cfg['token_file']).read_text().strip()
        self.assertNotIn(token, json.dumps(self.client.calls)); self.assertNotIn(token, json.dumps(prepared))
        self.client.lose = 'configure_bot_runtime'
        with self.assertRaises(OSError): configure(self.client, 'setup-1', root, prepared['runtime_plan_hash'])
        result = configure(self.client, 'setup-1', root, prepared['runtime_plan_hash'])
        self.assertIn('bot-worker', result['worker_commands'][0]); self.assertFalse(result['workers_started'])
        self.assertEqual(self.client.runtime['version'], 1)
        self.assertTrue(all(p.stat().st_mode & 0o077 == 0 for p in root.rglob('*')))

    def test_modified_prepared_configuration_cannot_be_approved(self):
        from gantry.crew_setup_client import prepare, activate, configure
        self.proposal(); root = self.root/'runtimes'
        prepared = prepare(self.client, 'setup-1', root, 'codex-subscription', {'name': 'Tools'})
        activate(self.client, 'setup-1', root, prepared['proposal_hash'])
        cfg_path = Path(prepared['runtimes'][0]['config_file']); cfg = load(cfg_path)
        cfg['local_tools'] = {'unexpected': {'command': ['/unreviewed']}}; save(cfg_path, cfg)
        with self.assertRaises(Fault): configure(self.client, 'setup-1', root, prepared['runtime_plan_hash'])
        self.assertIsNone(self.client.runtime)

    def test_analysis_rejects_backend_rebinding_without_inference(self):
        from gantry.crew_setup_client import analyze
        def infer(*_): return {'output': copy.deepcopy(PROPOSAL)}
        analyze(self.client, 'setup-1', self.root/'analysis', infer, {'backend': 'first'})
        with self.assertRaises(Fault): analyze(self.client, 'setup-1', self.root/'analysis', infer, {'backend': 'second'})

    def test_changed_token_is_rejected_before_activation(self):
        from gantry.crew_setup_client import prepare, activate
        self.proposal(); root = self.root/'runtimes'
        prepared = prepare(self.client, 'setup-1', root, 'codex-subscription', {'name': 'Tools'})
        Path(prepared['runtimes'][0]['token_file']).write_text('different-token\n')
        with self.assertRaises(Fault): activate(self.client, 'setup-1', root, prepared['proposal_hash'])
        self.assertFalse(self.client.setup['result'])

    def test_uncertain_customer_command_is_not_silently_invoked_again(self):
        import hashlib
        import sys
        from gantry.bot_worker import infer_command
        from gantry.crew_setup_client import analyze
        executable = Path(sys.executable).resolve()
        count = self.root/'calls.txt'
        command = [str(executable), '-c',
            'from pathlib import Path; import sys; Path(sys.argv[1]).open("a").write("called\\n"); sys.exit(1)', str(count)]
        config = {'command': command, 'executable_hash': hashlib.sha256(executable.read_bytes()).hexdigest()}
        infer = lambda context, schema, directory: infer_command(config, context, schema, directory)
        descriptor = {'backend': 'customer-command', 'config': config}
        with self.assertRaises(Fault) as caught: analyze(self.client, 'setup-1', self.root/'analysis', infer, descriptor)
        self.assertEqual(caught.exception.code, 'provider_failed')
        with self.assertRaises(Fault) as caught: analyze(self.client, 'setup-1', self.root/'analysis', infer, descriptor)
        self.assertEqual(caught.exception.code, 'outcome_unknown')
        self.assertEqual(count.read_text(), 'called\n')
        self.assertTrue(all(p.stat().st_mode & 0o077 == 0 for p in (self.root/'analysis').rglob('*')))

    def test_worker_mapping_rejects_owner_token_and_invalid_environment(self):
        from gantry.crew_setup_client import prepare
        self.proposal(); token_file = self.root/'owner.token'
        token_file.write_text('fixture-owner-token'); token_file.chmod(0o600)
        with patch('gantry.crew_setup_client.Client', return_value=self.client):
            with self.assertRaises(Fault) as caught:
                prepare(self.client, 'setup-1', self.root/'runtimes', 'codex-subscription', {'name': 'Tools'},
                        [{'role_id': 'lead', 'principal_id': 'owner', 'token_file': str(token_file)}])
        self.assertEqual(caught.exception.code, 'scope_denied')
        with self.assertRaises(Fault):
            prepare(self.client, 'setup-1', self.root/'bad', 'codex-subscription', {'name': 'Tools', 'tools': 'invalid'})
        self.assertFalse((self.root/'bad').exists())


import test_crew_setup as fixtures


class CrewSetupIntegrationTests(unittest.TestCase):
    setUp = fixtures.CrewSetupTests.setUp
    tearDown = fixtures.CrewSetupTests.tearDown
    call = fixtures.CrewSetupTests.call
    artifact = fixtures.CrewSetupTests.artifact
    connect = fixtures.CrewSetupTests.connect
    policy = fixtures.CrewSetupTests.policy
    imported = fixtures.CrewSetupTests.imported
    setup = fixtures.CrewSetupTests.setup
    proposal = fixtures.CrewSetupTests.proposal

    def test_real_setup_generates_dedicated_workers_and_requires_online_runtime(self):
        from gantry.bot_worker import BotWorker
        from gantry.crew_setup_client import analyze, prepare, activate, configure, start_work
        from test_development import LocalClient
        self.client.url = 'http://127.0.0.1:8765'
        d = self.setup(); proposal = self.proposal(d)
        analyzed = analyze(self.client, d['id'], self.root/'analysis',
            lambda *_: {'output': proposal, 'provider': {'kind': 'fixture'}}, {'backend': 'fixture'})
        private = self.root/'customer'
        prepared = prepare(self.client, d['id'], private, 'codex-subscription', {'name': 'Customer tools'})
        self.assertEqual(analyzed['proposal_hash'], prepared['proposal_hash'])
        activated = activate(self.client, d['id'], private, prepared['proposal_hash'])
        configured = configure(self.client, d['id'], private, prepared['runtime_plan_hash'])
        self.assertTrue(all(r['runtime'] == 'offline' for r in configured['readiness']))
        self.assertEqual(self.call('list_bot_tasks', {'session_id': self.sid})['items'], [])
        self.assertFalse(self.call('get_crew_setup', {'setup_id': d['id']})['execution_enabled'])
        with self.assertRaises(Fault) as caught: start_work(self.client, d['id'], private)
        self.assertEqual(caught.exception.code, 'mode_disabled')
        session = self.call('development_state', {'session_id': self.sid})['session']
        self.call('studio_execution_policy', {'session_id': self.sid, 'version': session['version'],
                    'enabled': True, 'max_parallel': 2, 'max_executions': None})
        with self.assertRaises(Fault) as caught: start_work(self.client, d['id'], private)
        self.assertEqual(caught.exception.code, 'runtime_unavailable')
        lead = activated['result']['lead_bot_id']
        config = next(load(Path(r['config_file'])) for r in prepared['runtimes']
                      if load(Path(r['config_file']))['bot_id'] == lead)
        worker_client = LocalClient(self.service, Path(config['token_file']).read_text().strip())
        identity = worker_client.call('identity')
        self.assertEqual(identity['kind'], 'agent'); self.assertNotIn('admin', identity['permissions'])
        with BotWorker(worker_client, config, self.root/'workers', infer_fn=lambda *_: self.fail('No inference expected')):
            started = start_work(self.client, d['id'], private)
            self.assertEqual(started['result']['first_task_id'], start_work(self.client, d['id'], private)['result']['first_task_id'])
            tasks = self.call('list_bot_tasks', {'session_id': self.sid})['items']
            self.assertEqual(len(tasks), 1); self.assertEqual(tasks[0]['kind'], 'plan')
        self.assertTrue(self.call('replay')['matched'])

    def test_preview_stays_local_and_upload_retries_saved_bytes(self):
        import argparse
        from gantry.crew_setup_cli import add_parser, run
        parser = argparse.ArgumentParser(); add_parser(parser.add_subparsers(dest='command'))
        project = self.imported(); source = self.root/'exports'; source.mkdir()
        (source/'roles.csv').write_text('role,responsibility\nLead,Review controller\n')
        argv = ['crew-setup', 'start', '--session-id', project['state']['session_id'],
                '--state-id', project['state']['id'], '--name', 'Controller team', '--root', str(source),
                '--source', 'spreadsheet=roles.csv']
        class NoNetwork:
            def call(self, *_): raise AssertionError('Preview contacted Core')
        preview = run(NoNetwork(), parser.parse_args(argv))
        self.assertFalse(preview['sent']); self.assertFalse((source/'.gantry').exists())
        client = self.client
        class LostUpload:
            lost = False
            def call(inner, name, args=None, key=None):
                result = client.call(name, args, key)
                if name == 'start_crew_setup' and not inner.lost:
                    inner.lost = True; raise OSError('Lost committed acknowledgement')
                return result
        args = parser.parse_args(argv+['--apply', '--journal', str(self.root/'upload')])
        lost = LostUpload()
        with self.assertRaises(OSError): run(lost, args)
        result = run(lost, args)
        self.assertTrue(result['sent'])
        self.assertEqual(len(self.call('list_crew_setups', {'session_id': project['state']['session_id']})['items']), 1)
        (source/'roles.csv').write_text('role,responsibility\nLead,Different evidence\n')
        with self.assertRaises(Fault): run(lost, args)

    def test_existing_bot_configs_credentials_and_runtime_versions_are_preserved(self):
        from gantry.crew_setup_client import analyze, prepare, activate, configure
        from test_development import LocalClient
        self.client.url = 'http://127.0.0.1:8765'; d = self.setup(); proposal = self.proposal(d)
        analyze(self.client, d['id'], self.root/'analysis', lambda *_: {'output': proposal}, {'backend': 'fixture'})
        root = self.root/'first'; first = prepare(self.client, d['id'], root, 'codex-subscription', {'name': 'Customer tools'})
        activated = activate(self.client, d['id'], root, first['proposal_hash'])
        configure(self.client, d['id'], root, first['runtime_plan_hash'])
        roles = activated['result']['roles']; mappings = []
        for role, runtime in zip(roles, first['runtimes']):
            mappings.append({**{k: role[k] for k in ('role_id', 'principal_id')},
                             'token_file': runtime['token_file'], 'config_file': runtime['config_file']})
        old_bytes = {p: Path(p).read_bytes() for m in mappings for p in (m['config_file'], m['token_file'])}
        old_runtimes = {r['bot_id']: self.call('get_persistent_bot', {'bot_id': r['bot_id']})['runtime'] for r in roles}
        second = self.call('start_crew_setup', {'session_id': self.sid, 'state_id': self.project['state']['id'],
            'organization_id': activated['result']['organization_id'], 'organization_name': 'Assembly team',
            'notes': 'Reuse existing team', 'files': {}, 'sources': []})
        proposal = self.proposal(second)
        for role, saved_role in zip(proposal['roles'], roles): role['existing_bot_id'] = saved_role['bot_id']
        analyze(self.client, second['id'], self.root/'analysis-2', lambda *_: {'output': proposal}, {'backend': 'fixture'})
        second_root = self.root/'second'
        with patch('gantry.crew_setup_client.Client', side_effect=lambda url, token: LocalClient(self.service, token)):
            prepared = prepare(self.client, second['id'], second_root, 'codex-subscription', {'name': 'Customer tools'}, mappings)
        activate(self.client, second['id'], second_root, prepared['proposal_hash'])
        configure(self.client, second['id'], second_root, prepared['runtime_plan_hash'])
        self.assertEqual(old_bytes, {p: Path(p).read_bytes() for p in old_bytes})
        for bid, old in old_runtimes.items(): self.assertEqual(old, self.call('get_persistent_bot', {'bot_id': bid})['runtime'])
        self.assertTrue(all(r['reused'] for r in prepared['runtimes']))


if __name__ == '__main__': unittest.main()
