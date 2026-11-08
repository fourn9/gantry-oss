"""Owner-configured evidence publication after real, anonymous tool execution."""
import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

from gantry.bot_worker import environment_manifest
from gantry.model import Fault
from gantry.project_sandbox import backend, runtime_roots
import test_bot_development as fixtures


class CrewToolEvidenceTests(unittest.TestCase):
    tearDown = fixtures.BotDevelopmentTests.tearDown
    scope = fixtures.BotDevelopmentTests.scope
    assignment = fixtures.BotDevelopmentTests.assignment
    task = fixtures.BotDevelopmentTests.task
    worker = fixtures.BotDevelopmentTests.worker
    answer = fixtures.BotDevelopmentTests.answer

    def setUp(self):
        self.check = {'id': 'load', 'scope': 'structural', 'components': ['part'], 'required': True,
            'inputs': ['mechanical.txt'], 'report': 'stress.json',
            'conditions': {'load_N': 100, 'fixture': 'fixed-base'},
            'evaluator': {'name': 'fixture-solver', 'version': '1'}, 'environment': {'mesh': 'm1'},
            'criteria': [{'metric': 'stress', 'unit': 'MPa', 'max': 50}]}
        self.plan = {'version': 1, 'components': [{'id': 'part', 'role': 'load_support',
            'assembly': 'frame', 'paths': ['mechanical.txt']}], 'checks': [self.check]}
        fixtures.BotDevelopmentTests.setUp(self)
        self.tool_scope = ['mechanical.txt', 'stress.json', 'tool-runs.txt']
        session = self.owner.call('development_state', {'session_id': self.sid})['session']
        self.owner.call('configure_development', {'session_id': self.sid, 'version': session['version'],
            'reason': 'Synthetic solver outputs are owner-authorized',
            **{**self.policy, 'write_scope': ['mechanical.txt', 'control.txt', 'stress.json', 'tool-runs.txt']}})
        self.owner.call('bind_development_bot', {'session_id': self.sid, 'bot_id': 'designer',
            'principal_id': 'designer', 'version': 1, 'write_scope': self.tool_scope,
            'can_assign': False, 'can_integrate': False, 'enabled': True})

    def artifact(self, files):
        return fixtures.BotDevelopmentTests.artifact(self, {**files, 'physical-plan.json': json.dumps(self.plan)})

    def configure_tool(self, report_mode='valid', plan_path='physical-plan.json', second_mode=None):
        if backend() == 'unavailable': self.skipTest('OS sandbox unavailable')
        script = f'''import hashlib, json
from pathlib import Path
counter = Path('tool-runs.txt')
runs = int(counter.read_text()) + 1 if counter.exists() else 1
counter.write_text(str(runs))
print('synthetic solver run ' + str(runs))
check = json.loads({json.dumps(self.check)!r})
report = {{'status': 'completed',
    'inputs': {{name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in check['inputs']}},
    'conditions': check['conditions'], 'evaluator': check['evaluator'], 'environment': check['environment'],
    'measurements': {{'stress': {{'value': 40, 'unit': 'MPa'}}}}, 'limitations': ['Synthetic static fixture only']}}
mode = {report_mode!r}
if mode == 'inputs': report['inputs']['mechanical.txt'] = 'f' * 64
if mode == 'evaluator': report['evaluator']['version'] = 'different-version'
if mode not in ('missing', 'unchanged'):
    Path('stress.json').write_text('{{broken' if mode == 'malformed' else json.dumps(report))
raise SystemExit(1 if mode == 'failed' else 0)
'''
        local_tools = {'stress': {'argv': [str(Path(sys.executable).resolve()), '-c', script], 'timeout_seconds': 10}}
        if second_mode is not None:
            second = script.replace(f'mode = {report_mode!r}', f'mode = {second_mode!r}')
            local_tools['repeat'] = {'argv': [str(Path(sys.executable).resolve()), '-c', second], 'timeout_seconds': 10}
        self.configs['designer'].update(agent_loop=True, local_tools=local_tools,
            tool_runtime=runtime_roots(), sandbox=backend(),
            tool_evidence={name: {'plan_path': plan_path} for name in local_tools})
        runtime = self.owner.call('get_persistent_bot', {'bot_id': 'designer'})['runtime']
        self.owner.call('configure_bot_runtime', {'bot_id': 'designer', 'version': runtime['version'],
            'principal_id': 'designer', 'enabled': True,
            'environment': environment_manifest(self.configs['designer'])})

    def action(self, name, arguments):
        return {'output': {'action': name, 'arguments_json': json.dumps(arguments),
            'rationale': 'Synthetic tool evidence fixture'}}

    def check_from_context(self, context):
        checks = context['development']['engineering']['checks']
        self.assertEqual([check['id'] for check in checks], ['load'],
            'Configured evidence must be published before the next model turn')
        return checks[0]

    def test_evidence_mapping_is_part_of_owner_approved_environment(self):
        config = {**self.configs['designer'], 'agent_loop': True,
            'tool_evidence': {'stress': {'plan_path': 'physical-plan.json'}}}
        changed = copy.deepcopy(config)
        changed['tool_evidence']['stress']['plan_path'] = 'different-plan.json'
        self.assertNotEqual(environment_manifest(config)['definition'], environment_manifest(changed)['definition'])

    def test_tool_publishes_pass_before_next_turn_and_later_edit_invalidates_it(self):
        self.configure_tool(); task = self.task('designer', write_scope=self.tool_scope); contexts = []
        def infer(context, schema, directory):
            contexts.append(context)
            if len(contexts) == 1: return self.action('tool', {'name': 'stress'})
            check = self.check_from_context(context)
            if len(contexts) == 2:
                self.assertEqual(context['last_result']['exit_code'], 0)
                self.assertEqual(check['effective_status'], 'pass')
                self.assertEqual(check['physical_result']['comparisons'][0]['observation']['value'], 40)
                return self.action('edit', {'path': 'mechanical.txt', 'content': '2',
                    'expected_hash': hashlib.sha256(b'1').hexdigest()})
            self.assertEqual(check['effective_status'], 'unknown')
            self.assertIn('mechanical.txt', check['stale_inputs'])
            return self.action('finish', self.answer())

        with self.worker('designer', infer) as worker: result = worker.tick()[0]

        self.assertEqual(result.get('task', {}).get('status'), 'completed', result)
        self.assertEqual(len(contexts), 3)
        view = self.owner.call('get_development_state', {'state_id': result['task']['output_state']})
        self.assertEqual(view['engineering']['checks'][0]['effective_status'], 'unknown')
        self.assertEqual(view['status']['adoption'], 'unadopted')
        self.assertEqual(view['status']['verification'], 'unverified')
        self.assertEqual(view['manifest']['tool-runs.txt']['hash'], hashlib.sha256(b'1').hexdigest())
        self.assertTrue(self.owner.call('replay')['matched'])

    def assert_unknown_report(self, report_mode, expected_reason):
        self.configure_tool(report_mode); self.task('designer', write_scope=self.tool_scope); contexts = []
        def infer(context, schema, directory):
            contexts.append(context)
            if len(contexts) == 1: return self.action('tool', {'name': 'stress'})
            check = self.check_from_context(context)
            self.assertEqual(context['last_result']['exit_code'], 0)
            self.assertEqual(check['effective_status'], 'unknown')
            self.assertIn(expected_reason, check['physical_result']['reasons'])
            return self.action('finish', self.answer())
        with self.worker('designer', infer) as worker: result = worker.tick()[0]
        self.assertEqual(result.get('task', {}).get('status'), 'completed', result)
        self.assertEqual(len(contexts), 2)

    def test_missing_report_is_published_as_unknown(self):
        self.assert_unknown_report('missing', 'report_missing_or_invalid')

    def test_malformed_report_is_published_as_unknown(self):
        self.assert_unknown_report('malformed', 'report_missing_or_invalid')

    def test_mismatched_evaluator_cannot_publish_pass(self):
        self.assert_unknown_report('evaluator', 'evaluator_mismatch')

    def test_mismatched_input_cannot_publish_pass(self):
        self.assert_unknown_report('inputs', 'inputs_mismatch')

    def test_unchanged_previous_pass_report_is_not_evidence_for_a_new_execution(self):
        self.configure_tool(second_mode='unchanged')
        self.task('designer', write_scope=self.tool_scope); contexts = []
        def infer(context, schema, directory):
            contexts.append(context)
            if len(contexts) == 1: return self.action('tool', {'name': 'stress'})
            check = self.check_from_context(context)
            self.assertEqual(context['last_result']['exit_code'], 0)
            if len(contexts) == 2:
                self.assertEqual(check['effective_status'], 'pass')
                return self.action('tool', {'name': 'repeat'})
            self.assertEqual(check['effective_status'], 'unknown',
                'A successful process that did not refresh the report cannot renew an earlier pass')
            self.assertEqual(context['files']['tool-runs.txt'], '2')
            return self.action('finish', self.answer())
        with self.worker('designer', infer) as worker: result = worker.tick()[0]
        self.assertEqual(result.get('task', {}).get('status'), 'completed', result)
        self.assertEqual(len(contexts), 3)

    def test_tool_failure_cannot_publish_pass_even_with_a_conforming_report(self):
        self.configure_tool('failed'); self.task('designer', write_scope=self.tool_scope); contexts = []
        def infer(context, schema, directory):
            contexts.append(context)
            if len(contexts) == 1: return self.action('tool', {'name': 'stress'})
            self.assertEqual(context['last_result']['exit_code'], 1)
            self.assertEqual(self.check_from_context(context)['effective_status'], 'unknown',
                'A conforming pass report does not erase the actual process failure')
            self.assertEqual(context['files']['tool-runs.txt'], '1')
            return self.action('finish', self.answer())
        with self.worker('designer', infer) as worker: result = worker.tick()[0]
        self.assertEqual(result.get('task', {}).get('status'), 'completed', result)
        self.assertEqual(len(contexts), 2)

    def test_identical_report_rewritten_by_new_execution_remains_valid(self):
        self.configure_tool(second_mode='valid')
        self.task('designer', write_scope=self.tool_scope); contexts = []
        def infer(context, schema, directory):
            contexts.append(context)
            if len(contexts) == 1: return self.action('tool', {'name': 'stress'})
            self.assertEqual(self.check_from_context(context)['effective_status'], 'pass')
            if len(contexts) == 2: return self.action('tool', {'name': 'repeat'})
            self.assertEqual(context['files']['stress.json'], contexts[1]['files']['stress.json'])
            self.assertEqual(context['files']['tool-runs.txt'], '2')
            return self.action('finish', self.answer())
        with self.worker('designer', infer) as worker: result = worker.tick()[0]
        self.assertEqual(result.get('task', {}).get('status'), 'completed', result)
        self.assertEqual(len(contexts), 3)

    def assert_publication_error_preserves_tool(self, client=None):
        self.task('designer', write_scope=self.tool_scope); contexts = []
        def infer(context, schema, directory):
            contexts.append(context)
            if len(contexts) == 1: return self.action('tool', {'name': 'stress'})
            self.assertEqual(len(contexts), 2, 'Publication failure must not rerun the actual tool')
            self.assertEqual(context['last_result'].get('error'), 'evidence_publication')
            actual = context['last_result']['tool_result']
            self.assertEqual(actual['exit_code'], 0)
            self.assertIn('synthetic solver run 1', actual['output'])
            self.assertTrue(actual['output_artifact'])
            self.assertEqual(context['files']['tool-runs.txt'], '1')
            self.assertFalse(context['development']['engineering']['checks'])
            return self.action('finish', self.answer())
        with self.worker('designer', infer, client) as worker: result = worker.tick()[0]
        self.assertEqual(result.get('task', {}).get('status'), 'completed', result)
        self.assertEqual(len(contexts), 2)
        view = self.owner.call('get_development_state', {'state_id': result['task']['output_state']})
        self.assertEqual(view['manifest']['tool-runs.txt']['hash'], hashlib.sha256(b'1').hexdigest())

    def test_missing_publication_plan_preserves_actual_tool_result_without_rerun(self):
        self.configure_tool(plan_path='absent-plan.json')
        self.assert_publication_error_preserves_tool()

    def test_publication_failure_preserves_actual_tool_result_without_rerun(self):
        self.configure_tool(); client = self.clients['designer']
        class FailedPublication:
            def call(_, operation, args=None, key=None):
                if operation == 'checkpoint_bot_task' and 'context' in args:
                    raise Fault('invalid_input', 'Synthetic evidence publication rejection')
                return client.call(operation, args, key)
        self.assert_publication_error_preserves_tool(FailedPublication())

    def test_lost_evidence_ack_recovers_without_rerunning_tool(self):
        self.configure_tool(); task = self.task('designer', write_scope=self.tool_scope)
        client = self.clients['designer']; lost = []; contexts = []
        class LostEvidenceAck:
            def call(_, operation, args=None, key=None):
                result = client.call(operation, args, key)
                if operation == 'checkpoint_bot_task' and 'context' in args and not lost:
                    lost.append(True)
                    raise OSError('Synthetic evidence acknowledgement lost after commit')
                return result
        def infer(context, schema, directory):
            contexts.append(context)
            if len(contexts) == 1: return self.action('tool', {'name': 'stress'})
            self.assertEqual(len(contexts), 2, 'Recovery must reuse the saved actual tool execution')
            self.assertEqual(self.check_from_context(context)['effective_status'], 'pass')
            self.assertEqual(context['files']['tool-runs.txt'], '1')
            return self.action('finish', self.answer())

        with self.worker('designer', infer, LostEvidenceAck()) as worker: result = worker.tick()[0]
        self.assertEqual(result.get('reason'), 'OSError', result)
        self.assertEqual(len(contexts), 1, 'Uncertain evidence publication must hold before another model turn')
        with self.worker('designer', infer) as worker:
            result = worker.recover(task['id'], 'Synthetic executor has stopped')

        self.assertEqual(result['task']['status'], 'completed')
        self.assertEqual(len(contexts), 2)
        view = self.owner.call('get_bot_task', {'task_id': task['id']})
        self.assertEqual(len(view['own_change']['checkpoints']), 2)
        self.assertEqual(view['development']['manifest']['tool-runs.txt']['hash'], hashlib.sha256(b'1').hexdigest())
        self.assertTrue(self.owner.call('replay')['matched'])

    def test_interrupted_evidence_completion_retains_publication_action(self):
        from unittest.mock import patch
        from gantry import crew_runtime
        self.configure_tool(); task = self.task('designer', write_scope=self.tool_scope)
        contexts = []; interrupted = []
        def infer(context, schema, directory):
            contexts.append(context)
            if len(contexts) == 1: return self.action('tool', {'name': 'stress'})
            self.assertEqual(context['files']['tool-runs.txt'], '1')
            self.assertEqual(self.check_from_context(context)['effective_status'], 'pass')
            return self.action('finish', self.answer())
        original = crew_runtime.persist
        def interrupt_after_completion(path, value):
            original(path, value)
            if path.name == 'action.json' and value.get('evidence_done') and not interrupted:
                interrupted.append(True)
                raise OSError('Synthetic interruption after publication completion was persisted')

        with self.worker('designer', infer) as worker:
            with patch('gantry.crew_runtime.persist', interrupt_after_completion):
                result = worker.tick()[0]
        self.assertEqual(result.get('reason'), 'OSError', result)
        with self.worker('designer', infer) as worker:
            result = worker.recover(task['id'], 'Synthetic executor has stopped')

        self.assertEqual(result['task']['status'], 'completed')
        self.assertEqual(len(contexts), 2)
        view = self.owner.call('get_bot_task', {'task_id': task['id']})
        publications = [item for item in view['actions'] if item['kind'] == 'tool_evidence']
        self.assertEqual(len(publications), 1, 'Recovery must retain the publication action exactly once')
        self.assertEqual(publications[0]['details']['result']['evidence_publication']['state_id'],
                         result['task']['output_state'])
