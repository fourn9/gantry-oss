import unittest
from unittest.mock import patch
import test_unlimited_connection as target

class SandboxGuardTests(unittest.TestCase):
    def test_unavailable_backend_skips_before_project_operations(self):
        case=target.UnlimitedConnectionTests('test_thirteen_real_sandboxed_tests_and_retry')
        with patch.object(target,'backend',return_value='unavailable'):
            with self.assertRaises(unittest.SkipTest):
                case.test_thirteen_real_sandboxed_tests_and_retry()


class BaselineVersionTests(unittest.TestCase):
    def test_two_component_stable_release_is_compared_numerically(self):
        from gantry.security_check import assess
        self.assertEqual(assess('3.12.15', {'pip':'26.3'})['findings'], [])
        self.assertTrue(assess('3.12.15', {'pip':'26.2'})['findings'])
        self.assertTrue(assess('3.12.15', {'pip':'26.3rc1'})['findings'])
