"""Verification intent is recorded against frozen inputs, never a solver result."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from gantry.crew_runtime import _execute, action_schemas
from gantry.model import Fault, digest
from gantry.service import Service  # Register the complete Crew command contracts.


class VerificationPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.check = {'id': 'clearance', 'scope': 'placement', 'components': ['part'], 'required': True,
            'inputs': ['part.step'], 'report': 'report.json', 'conditions': {'unit': 'mm'},
            'evaluator': {'name': 'fixture', 'version': '1'}, 'environment': {'solver': 'fixture'},
            'requirement_refs': [], 'criteria': [{'metric': 'clearance', 'unit': 'mm', 'min': 1}]}
        self.plan = {'version': 1, 'components': [{'id': 'part', 'role': 'carrier',
            'assembly': 'test', 'paths': ['part.step']}], 'checks': [self.check]}
        (self.root/'part.step').write_text('anonymous fixture bytes, not native CAD')
        (self.root/'physical-plan.json').write_text(json.dumps(self.plan))
        manifest = {p.name: {'hash': hashlib.sha256(p.read_bytes()).hexdigest()} for p in self.root.iterdir()}
        self.full = {'task': {'id': 'task', 'state_id': 'base', 'write_scope': ['report.json']},
            'development': {'state': {'id': 'current'}, 'manifest': manifest, 'engineering': {'checks': []}}}
        self.baseline = {'manifest': copy.deepcopy(manifest)}
        outer = self
        class Client:
            def call(self, name, args):
                if name != 'get_development_state' or args != {'state_id': 'base'}: raise AssertionError((name, args))
                return outer.baseline
        self.client = Client()
        self.config = {'local_tools': {'verify': {'argv': ['/usr/bin/true'], 'timeout_seconds': 10}},
            'tool_evidence': {'verify': {'plan_path': 'physical-plan.json'}}}
        self.args = {'plan_path': 'physical-plan.json', 'check_ids': ['clearance'],
            'purpose': 'Check the changed carrier', 'question': 'Is nominal clearance sufficient?',
            'assumptions': ['Rigid nominal solids'], 'missing_inputs': [], 'tool_name': 'verify',
            'expected_outputs': ['report.json'], 'next_steps': {'pass': 'Review remaining coverage',
                'fail': 'Inspect contact and revise geometry', 'unknown': 'Obtain missing evidence'}}

    def run_plan(self, **changes):
        return _execute(self.client, self.full, {}, self.config, 'plan_verification',
            {**self.args, **changes}, self.root, self.root, 'plan-fixture')

    def test_plan_pins_inputs_and_criteria_without_running_a_tool(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        result = self.run_plan()
        self.assertIn('plan_verification', action_schemas())
        self.assertEqual(result['status'], 'planned')
        self.assertEqual(result['input_state'], 'current')
        self.assertEqual(result['plan']['sha256'], self.full['development']['manifest']['physical-plan.json']['hash'])
        self.assertEqual(result['checks'][0]['criteria'], self.check['criteria'])
        self.assertEqual(result['checks'][0]['input_hashes']['part.step'], self.full['development']['manifest']['part.step']['hash'])
        self.assertEqual(result['tool']['recipe_hash'], digest(self.config['local_tools']['verify']))
        self.assertFalse(result['execution']['performed'])
        self.assertFalse(result['formal_adoption'])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})

    def test_missing_tool_and_input_are_concrete_unexecutable_requests(self):
        (self.root/'part.step').unlink()
        result = self.run_plan(tool_name='uninstalled_solver')
        self.assertEqual(result['status'], 'unexecutable')
        self.assertIn({'code': 'tool_unavailable', 'tool': 'uninstalled_solver'}, result['missing'])
        self.assertIn({'code': 'input_missing', 'path': 'part.step'}, result['missing'])
        self.assertIsNone(result['checks'][0]['input_hashes']['part.step'])
        self.assertFalse(result['execution']['performed'])

    def test_changed_local_or_checkpointed_acceptance_is_rejected(self):
        changed = copy.deepcopy(self.plan); changed['checks'][0]['criteria'][0]['min'] = 0
        (self.root/'physical-plan.json').write_text(json.dumps(changed))
        for checkpointed in (False, True):
            with self.subTest(checkpointed=checkpointed):
                if checkpointed:
                    self.full['development']['manifest']['physical-plan.json']['hash'] = hashlib.sha256((self.root/'physical-plan.json').read_bytes()).hexdigest()
                with self.assertRaises(Fault) as error: self.run_plan()
                self.assertEqual(error.exception.code, 'stale_basis')

    def test_changed_input_is_unexecutable_without_claiming_current_binding(self):
        (self.root/'part.step').write_text('unsaved change')
        result = self.run_plan()
        self.assertEqual(result['status'], 'unexecutable')
        self.assertIn({'code': 'input_changed', 'path': 'part.step'}, result['missing'])

    def test_scope_and_tool_evidence_mapping_are_required(self):
        self.full['task']['write_scope'] = []
        self.config['tool_evidence'] = {}
        result = self.run_plan()
        self.assertEqual(result['status'], 'unexecutable')
        self.assertIn({'code': 'report_outside_scope', 'path': 'report.json'}, result['missing'])
        self.assertIn({'code': 'tool_evidence_mapping_missing', 'tool': 'verify', 'plan_path': 'physical-plan.json'}, result['missing'])

    def test_model_cannot_replace_criteria_or_select_unknown_duplicate_checks(self):
        for changes in ({'criteria': []}, {'check_ids': ['other']}, {'check_ids': ['clearance', 'clearance']},
                        {'expected_outputs': ['invented.json']}):
            with self.subTest(changes=changes), self.assertRaises(Fault): self.run_plan(**changes)

    def test_unsafe_input_symlink_is_rejected(self):
        (self.root/'part.step').unlink(); (self.root/'part.step').symlink_to(self.root/'physical-plan.json')
        with self.assertRaises(Fault) as error: self.run_plan()
        self.assertEqual(error.exception.code, 'scope_denied')

    def test_missing_assumptions_block_execution_and_preserve_next_branches(self):
        result = self.run_plan(missing_inputs=['Actual load is unknown'])
        self.assertEqual(result['status'], 'unexecutable')
        self.assertEqual(result['next_steps'], self.args['next_steps'])
        self.assertEqual(result['missing_inputs'], ['Actual load is unknown'])


class VerificationRecordTests(unittest.TestCase):
    def test_extract_evidence_uses_current_saved_state_and_exact_json_value(self):
        import test_crew_runtime as fixtures
        c = fixtures.CrewRuntimeTests(); c.setUp(); self.addCleanup(c.tearDown)
        c.enable_loop('designer'); task = c.task('designer'); calls = []
        def infer(ctx, schema, directory):
            calls.append(ctx)
            if ctx['round'] == 0:
                return c.action('edit', {'path': 'mechanical.txt', 'content': '2',
                    'expected_hash': hashlib.sha256(b'1').hexdigest()})
            if ctx['round'] == 1:
                return c.action('extract_evidence', {'subject_id': 'assembly', 'path': 'mechanical.txt',
                    'profile': 'fixture', 'fields': [{'name': 'travel', 'pointer': '', 'unit': 'mm'}]})
            return c.action('finish', c.answer())
        with c.worker('designer', infer) as worker: result = worker.tick()[0]
        self.assertEqual(result['task']['status'], 'completed')
        extracted = calls[2]['last_result']
        self.assertEqual(extracted['fields'][0]['value'], 2)
        self.assertEqual(extracted['state_id'], result['task']['output_state'])
        self.assertNotEqual(extracted['state_id'], c.base['id'])
        self.assertEqual(extracted['sources'][0]['sha256'], hashlib.sha256(b'2').hexdigest())
        self.assertNotIn('state_id', action_schemas()['extract_evidence']['properties'])
        from gantry.contracts import validate
        with self.assertRaises(Fault):
            validate({'subject_id': 'assembly', 'path': 'mechanical.txt', 'profile': 'fixture',
                'fields': [{'name': 'travel', 'pointer': ''}], 'state_id': c.base['id']},
                action_schemas()['extract_evidence'])
        self.assertTrue(c.owner.call('replay')['matched'])

    def test_lost_record_ack_recovery_preserves_one_plan_and_never_launches_tool(self):
        import test_crew_runtime as fixtures
        c = fixtures.CrewRuntimeTests(); c.setUp(); self.addCleanup(c.tearDown)
        c.enable_loop('designer'); task = c.task('designer'); calls = []; lost = []
        args = {'plan_path': 'physical-plan.json', 'check_ids': ['clearance'],
            'purpose': 'Request unavailable verification', 'question': 'Is clearance sufficient?',
            'assumptions': [], 'missing_inputs': [], 'tool_name': 'uninstalled_solver',
            'expected_outputs': ['report.json'], 'next_steps': {'pass': 'Review scope',
                'fail': 'Inspect geometry', 'unknown': 'Request missing plan and tool'}}
        client = c.clients['designer']
        class LostAck:
            def call(self, name, values=None, key=None):
                result = client.call(name, values, key)
                if name == 'record_bot_action' and values['kind'] == 'plan_verification' and not lost:
                    lost.append(result); raise OSError('Saved plan acknowledgement lost')
                return result
        def infer(ctx, schema, directory):
            calls.append(ctx)
            return c.action('plan_verification', args) if ctx['round'] == 0 else c.action('finish', c.answer())
        with c.worker('designer', infer, LostAck()) as worker:
            self.assertEqual(worker.tick()[0]['status'], 'held')
        with c.worker('designer', infer, LostAck()) as worker:
            result = worker.recover(task['id'], 'No process started; recover recorded plan')
        self.assertEqual(result['task']['status'], 'completed')
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1]['last_result']['status'], 'unexecutable')
        actions = c.owner.call('get_bot_task', {'task_id': task['id']})['actions']
        plans = [a for a in actions if a['kind'] == 'plan_verification']
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]['id'], lost[0]['id'])
        self.assertEqual(plans[0]['input_state'], c.base['id'])
        self.assertFalse(plans[0]['details']['result']['execution']['performed'])
        self.assertFalse(any(a['kind'] == 'tool' for a in actions))
        self.assertTrue(c.owner.call('replay')['matched'])
