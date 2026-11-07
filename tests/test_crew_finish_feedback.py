"""Anonymous real-ledger regressions for the Crew finish validation boundary."""
import json
import unittest

from gantry.bot_worker import environment_manifest
from gantry.model import Fault
import test_bot_development as fixtures


class CrewFinishFeedbackTests(unittest.TestCase):
    # Reuse the anonymous integration fixture without collecting its test cases.
    setUp = fixtures.BotDevelopmentTests.setUp
    tearDown = fixtures.BotDevelopmentTests.tearDown
    scope = fixtures.BotDevelopmentTests.scope
    artifact = fixtures.BotDevelopmentTests.artifact
    assignment = fixtures.BotDevelopmentTests.assignment
    task = fixtures.BotDevelopmentTests.task
    worker = fixtures.BotDevelopmentTests.worker
    answer = fixtures.BotDevelopmentTests.answer

    def enable_loop(self):
        self.configs['designer']['agent_loop'] = True
        self.owner.call('configure_bot_runtime', {'bot_id': 'designer', 'version': 1,
            'principal_id': 'designer', 'enabled': True,
            'environment': environment_manifest(self.configs['designer'])})

    def finish(self, **report):
        return {'output': {'action': 'finish', 'arguments_json': json.dumps(self.answer(**report)),
            'rationale': 'Synthetic finish-boundary fixture'}}

    def test_core_report_rejection_returns_to_model_in_same_attempt(self):
        self.enable_loop(); task = self.task('designer'); contexts = []
        def infer(context, schema, directory):
            contexts.append(context)
            if len(contexts) == 1:
                return self.finish(status='waiting', summary='No delegated work exists')
            self.assertEqual(context['last_result']['error'], 'invalid_input')
            self.assertIn('Waiting requires child work or a consultation', context['last_result']['message'])
            return self.finish(summary='Corrected report after Core validation')

        with self.worker('designer', infer) as worker:
            result = worker.tick()[0]

        self.assertEqual(result.get('task', {}).get('status'), 'completed', result)
        self.assertEqual(len(contexts), 2)
        view = self.owner.call('get_bot_task', {'task_id': task['id']})
        self.assertEqual(view['task']['attempt'], 1)
        self.assertEqual(len(view['task']['reports']), 1)
        self.assertEqual(view['task']['reports'][0]['report']['summary'], 'Corrected report after Core validation')
        self.assertTrue(any(action['kind'] == 'finish' and
            action['details']['result'].get('error') == 'invalid_input' for action in view['actions']))
        self.assertTrue(self.owner.call('replay')['matched'])

    def test_lost_ack_after_corrected_report_recovers_without_new_model_turn(self):
        self.enable_loop(); task = self.task('designer'); contexts = []
        client = self.clients['designer']; lost = []
        class LostAck:
            def call(_, operation, args=None, key=None):
                result = client.call(operation, args, key)
                if operation == 'finish_bot_task' and not lost:
                    lost.append(True)
                    raise OSError('Synthetic response loss after successful commit')
                return result
        def infer(context, schema, directory):
            contexts.append(context)
            if len(contexts) == 1: return self.finish(status='waiting')
            self.assertEqual(len(contexts), 2, 'Recovery must not request another model decision')
            self.assertEqual(context['last_result']['error'], 'invalid_input')
            return self.finish(summary='Corrected report committed exactly once')

        with self.worker('designer', infer, LostAck()) as worker:
            result = worker.tick()[0]
        self.assertEqual(result.get('reason'), 'OSError', result)
        with self.worker('designer', infer) as worker:
            result = worker.recover(task['id'], 'Synthetic executor has stopped')

        self.assertEqual(result['task']['status'], 'completed')
        self.assertEqual(result['task']['attempt'], 1)
        self.assertEqual(len(contexts), 2)
        self.assertEqual(len(self.owner.call('get_bot_task', {'task_id': task['id']})['task']['reports']), 1)
        memories = self.clients['designer'].call('list_persistent_memories', {'bot_id': 'designer'})['items']
        self.assertEqual(len({m['id'] for m in memories
            if m['observation'] == 'Corrected report committed exactly once'}), 1)
        self.assertTrue(self.owner.call('replay')['matched'])

    def test_uncertain_finish_reconciles_once_before_any_new_model_turn(self):
        self.enable_loop()
        for committed in (False, True):
            with self.subTest(committed=committed):
                task = self.task('designer'); contexts = []; lost = []
                client = self.clients['designer']
                class UncertainFinish:
                    def call(_, operation, args=None, key=None):
                        if operation == 'finish_bot_task' and not lost:
                            lost.append(True)
                            if committed: client.call(operation, args, key)
                            raise Fault('temporarily_unavailable', 'Synthetic uncertain finish response')
                        return client.call(operation, args, key)
                def infer(context, schema, directory):
                    contexts.append(context)
                    self.assertEqual(len(contexts), 1, 'An uncertain finish is not validation feedback')
                    return self.finish()

                with self.worker('designer', infer, UncertainFinish()) as worker:
                    result = worker.tick()[0]
                self.assertEqual(result.get('reason'), 'temporarily_unavailable', result)
                with self.worker('designer', infer) as worker:
                    result = worker.recover(task['id'], 'Synthetic executor has stopped')

                self.assertEqual(result['task']['status'], 'completed')
                self.assertEqual(result['task']['attempt'], 1)
                self.assertEqual(len(contexts), 1)
                view = self.owner.call('get_bot_task', {'task_id': task['id']})
                self.assertEqual(len(view['task']['reports']), 1)
        self.assertTrue(self.owner.call('replay')['matched'])

    def test_authority_revoked_at_finish_stays_held_without_model_retry(self):
        self.enable_loop(); task = self.task('designer'); contexts = []; revoked = []
        client = self.clients['designer']
        class RevokedAtFinish:
            def call(_, operation, args=None, key=None):
                if operation == 'finish_bot_task' and not revoked:
                    revoked.append(True)
                    self.owner.call('configure_organization', {'organization_id': 'team', 'version': 1,
                        'name': 'Synthetic stopped organization', 'profile': fixtures.profile(), 'enabled': False})
                return client.call(operation, args, key)
        def infer(context, schema, directory):
            contexts.append(context)
            self.assertEqual(len(contexts), 1, 'Revoked authority must not become another reasoning turn')
            return self.finish()

        with self.worker('designer', infer, RevokedAtFinish()) as worker:
            result = worker.tick()[0]

        self.assertEqual(result.get('status'), 'held', result)
        self.assertEqual(result.get('reason'), 'mode_disabled', result)
        self.assertEqual(len(contexts), 1)
        self.assertEqual(self.owner.call('get_bot_task', {'task_id': task['id']})['task']['reports'], [])

    def test_changed_basis_at_finish_stays_held_without_model_retry(self):
        self.enable_loop(); task = self.task('designer'); contexts = []; advanced = []
        client = self.clients['designer']
        class ChangedAtFinish:
            def call(_, operation, args=None, key=None):
                if operation == 'finish_bot_task' and not advanced:
                    advanced.append(True)
                    session = self.owner.call('development_state', {'session_id': self.sid})['session']
                    self.owner.call('advance_development', {'session_id': self.sid, 'version': session['version'],
                        'snapshot': session['snapshot'], 'reason': 'Synthetic input premise changed',
                        'capture': session['capture'], 'unverified': session['unverified']})
                return client.call(operation, args, key)
        def infer(context, schema, directory):
            contexts.append(context)
            self.assertEqual(len(contexts), 1, 'A changed assignment basis must not be bypassed by another turn')
            return self.finish()

        with self.worker('designer', infer, ChangedAtFinish()) as worker:
            result = worker.tick()[0]

        self.assertEqual(result.get('status'), 'held', result)
        self.assertEqual(result.get('reason'), 'stale_basis', result)
        self.assertEqual(len(contexts), 1)
        self.assertEqual(self.owner.call('get_bot_task', {'task_id': task['id']})['task']['reports'], [])
