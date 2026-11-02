import unittest
from gantry.model import Fault
import test_hardware_publish as fixtures


class RecoveryTests(unittest.TestCase):
    setUp = fixtures.HardwarePublishTests.setUp
    tearDown = fixtures.HardwarePublishTests.tearDown
    call = fixtures.HardwarePublishTests.call
    artifact = fixtures.HardwarePublishTests.artifact
    connect = fixtures.HardwarePublishTests.connect
    initialize = fixtures.HardwarePublishTests.initialize
    begin = fixtures.HardwarePublishTests.begin
    detail = fixtures.HardwarePublishTests.detail
    policy = fixtures.HardwarePublishTests.policy
    prepare = fixtures.HardwarePublishTests.prepare

    def test_lost_ack_recovers_frozen_result_after_restart(self):
        from gantry.hardware import publish
        base, change, root = self.prepare()
        real = self.client
        class LostAck:
            def call(self, name, args, key=None):
                result = real.call(name, args, key)
                if name == 'checkpoint_change':
                    raise ConnectionError('lost acknowledgement')
                return result
        with self.assertRaises(ConnectionError):
            publish(LostAck(), base['id'], change['id'], change['version'], root, 'physical-plan.json', 'one')
        recovered = publish(real, base['id'], change['id'], change['version'], root, 'physical-plan.json', 'one')
        repeated = publish(real, base['id'], change['id'], change['version'], root, 'physical-plan.json', 'one')
        self.assertEqual(recovered['state']['id'], repeated['state']['id'])
        self.assertEqual(recovered['state']['context']['environment']['engineering']['checks'][0]['status'], 'pass')
        with self.assertRaises(Fault) as caught:
            publish(real, base['id'], change['id'], change['version'] + 1, root, 'physical-plan.json', 'one')
        self.assertEqual(caught.exception.code, 'idempotency_mismatch')
        self.assertTrue(self.call('replay')['matched'])
