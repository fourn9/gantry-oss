import unittest
from gantry.model import canonical, digest, Fault
import test_bot_bounded_context as fixtures


class ActionInputBudgetTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.BotBoundedContextTests(); self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_final_prompt_includes_overhead_and_retains_contract(self):
        from gantry.crew_runtime import action_input
        f = self.fixture
        f.full['task']['completion'] = ['Required: ' + 'x' * 370000]
        last = {str(i): 'e' * 7000 for i in range(13)}
        result = action_input(f.full, f.workspace, {}, last, 2)
        self.assertLessEqual(len(canonical(result).encode()), 480000)
        self.assertEqual(result['task']['completion'], f.full['task']['completion'])
        self.assertEqual(result['last_result']['sha256'], digest(last))
        self.assertTrue(result['last_result']['truncated'])
        self.assertIn('get_bot_records', str(result['last_result']))

    def test_essential_config_is_not_silently_discarded(self):
        from gantry.crew_runtime import action_input
        f = self.fixture
        with self.assertRaises(Fault) as caught:
            action_input(f.full, f.workspace, {'local_tools': {'oversize': 'x'*490000}}, None, 0)
        self.assertEqual(caught.exception.code, 'context_limit')
