"""Actual anonymous sandbox executions keep receipts when output import fails."""
import json
import unittest

from gantry.bot_worker import environment_manifest
from gantry.model import Fault
import test_crew_tool_evidence as fixtures


class CrewToolCaptureTests(unittest.TestCase):
    def setUp(self):
        self.c = fixtures.CrewToolEvidenceTests()
        self.c.setUp()
        self.addCleanup(self.c.tearDown)

    def configure_capture_failure(self, effect, exit_code=0):
        c = self.c
        c.configure_tool('failed' if exit_code else 'valid')
        config = c.configs['designer']
        argv = config['local_tools']['stress']['argv']
        # The actual installed program emits a conforming pass report and stdout;
        # its additional file effect must reject the whole import, including that report.
        argv[-1] = argv[-1].replace('raise SystemExit(', effect + '\nraise SystemExit(')
        runtime = c.owner.call('get_persistent_bot', {'bot_id': 'designer'})['runtime']
        c.owner.call('configure_bot_runtime', {'bot_id': 'designer', 'version': runtime['version'],
            'principal_id': 'designer', 'enabled': True, 'environment': environment_manifest(config)})
        return c.task('designer', write_scope=c.tool_scope)

    def run_capture_failure(self, effect, cause, exit_code=0):
        c = self.c
        task = self.configure_capture_failure(effect, exit_code)
        contexts = []

        def infer(context, schema, directory):
            contexts.append(context)
            if len(contexts) == 1:
                return c.action('tool', {'name': 'stress'})
            self.assertEqual(len(contexts), 2, 'Capture rejection must not rerun the tool')
            result = context['last_result']
            self.assertEqual(result.get('error'), 'tool_capture')
            self.assertEqual(result['cause'], cause)
            actual = result['tool_result']
            self.assertEqual(actual['exit_code'], exit_code)
            self.assertIsNone(actual['reason'])
            self.assertGreaterEqual(actual['seconds'], 0)
            self.assertIn('synthetic solver run 1', actual['output'])
            self.assertTrue(actual['output_artifact'])
            self.assertFalse(actual['workspace_changes_applied'])
            self.assertEqual(context['files']['mechanical.txt'], '1')
            self.assertEqual(context['files']['control.txt'], '1')
            self.assertNotIn('stress.json', context['files'])
            self.assertNotIn('tool-runs.txt', context['files'])
            self.assertFalse(context['development']['engineering']['checks'])
            self.assertNotIn('evidence_publication', result)
            return c.action('finish', c.answer(summary='Output capture rejected; verification unavailable'))

        with c.worker('designer', infer) as worker:
            completed = worker.tick()[0]
        self.assertEqual(completed.get('task', {}).get('status'), 'completed', completed)
        self.assertEqual(len(contexts), 2)
        view = c.owner.call('get_bot_task', {'task_id': task['id']})
        self.assertNotIn('output_state', view['task'])
        receipts = [a for a in view['actions'] if a['kind'] == 'tool']
        self.assertEqual(len(receipts), 1)
        result = receipts[0]['details']['result']
        self.assertEqual(result, contexts[1]['last_result'])
        self.assertEqual(receipts[0]['details']['workspace_before'], receipts[0]['details']['workspace_after'])
        self.assertFalse([a for a in view['actions'] if a['kind'] == 'tool_evidence'])
        self.assertNotIn('outside-secret-target', json.dumps(result))
        self.assertTrue(c.owner.call('replay')['matched'])

    def test_oversize_output_retains_execution_receipt_without_partial_import(self):
        self.run_capture_failure("Path('mechanical.txt').write_text('2')\n"
            "Path('tool-runs.txt').write_bytes(b'x' * (16 * 1024 * 1024 + 1))", 'capture_incomplete')

    def test_nonzero_exit_is_preserved_independently_of_capture_failure(self):
        self.run_capture_failure("Path('tool-runs.txt').write_bytes(b'x' * (16 * 1024 * 1024 + 1))",
            'capture_incomplete', exit_code=1)

    def test_out_of_scope_output_retains_receipt_but_never_imports(self):
        self.run_capture_failure("Path('control.txt').write_text('outside task authority')", 'scope_denied')

    def test_symlink_output_retains_receipt_without_exposing_target(self):
        self.run_capture_failure("Path('tool-runs.txt').unlink()\n"
            "Path('tool-runs.txt').symlink_to('/outside-secret-target')", 'scope_denied')

    def test_stale_authority_after_execution_holds_before_capture_feedback(self):
        c = self.c
        task = self.configure_capture_failure(
            "Path('tool-runs.txt').write_bytes(b'x' * (16 * 1024 * 1024 + 1))")
        client = c.clients['designer']; output_saved = []; contexts = []

        class ExpiredAfterExecution:
            def call(_, operation, args=None, key=None):
                if operation == 'check_bot_task' and output_saved:
                    raise Fault('stale_basis', 'Synthetic authority changed after execution')
                result = client.call(operation, args, key)
                if operation == 'capture_artifact' and set(args['files']) == {'tool-output.txt'}:
                    output_saved.append(True)
                return result

        def infer(context, schema, directory):
            contexts.append(context)
            return c.action('tool', {'name': 'stress'})

        with c.worker('designer', infer, ExpiredAfterExecution()) as worker:
            result = worker.tick()[0]
        self.assertEqual(result['status'], 'held')
        self.assertEqual(result['reason'], 'stale_basis')
        self.assertEqual(len(contexts), 1, 'Changed authority must not become a new model action')
        saved = list((c.root/'workers').rglob('tool-execution.json'))
        self.assertEqual(len(saved), 1)
        receipt = json.loads(saved[0].read_text())
        self.assertEqual(receipt['exit_code'], 0)
        self.assertIn('synthetic solver run 1', receipt['output'])
        self.assertFalse(receipt['workspace_changes_applied'])
        view = c.owner.call('get_bot_task', {'task_id': task['id']})
        self.assertNotIn('output_state', view['task'])
        self.assertFalse(view['development']['engineering']['checks'])
