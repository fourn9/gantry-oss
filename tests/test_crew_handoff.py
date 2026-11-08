import unittest
import test_bot_bounded_context as fixtures
from gantry.bot_execution import _input
from gantry.model import canonical, digest


class HandoffTests(unittest.TestCase):
    def test_index_pins_changes_and_unknowns_without_inventing_acceptance(self):
        f=fixtures.BotBoundedContextTests(); f.setUp(); self.addCleanup(f.doCleanups)
        f.full['design_assessment']={'changes':[{'path':'mechanical.txt','before':'a'*64,'after':'b'*64,'kind':'modified'}],
            'open_checks':[{'id':'clearance','status':'unknown'}], 'gaps':['Physical evidence missing']}
        f.full['children']=[{'id':'child-1','status':'completed','output_state':'candidate-1',
            'reports':[{'report':{'status':'completed','summary':'Checked geometry','unverified':['Strength unknown']}}]}]
        result=_input(f.full,f.workspace)['handoff']
        self.assertEqual(result['baseline_state_id'],f.full['task']['state_id'])
        self.assertEqual(result['changes']['items'],f.full['design_assessment']['changes'])
        self.assertEqual(result['open_checks']['items'][0]['status'],'unknown')
        self.assertEqual(result['children']['items'][0]['report_sha256'],digest(f.full['children'][0]['reports'][-1]))
        self.assertEqual(result['gaps']['items'],['Physical evidence missing'])
        self.assertFalse(result['formal_adoption'])
        self.assertLess(len(canonical(result).encode()),12000)

    def test_large_index_declares_omissions_and_keeps_exact_source_references(self):
        f=fixtures.BotBoundedContextTests(); f.setUp(); self.addCleanup(f.doCleanups)
        rows=[{'path':f'part-{i}.txt','before':None,'after':'a'*64} for i in range(500)]
        f.full['design_assessment']={'changes':rows,'open_checks':[], 'gaps':['unknown '*10000]}
        result=_input(f.full,f.workspace)['handoff']
        self.assertLessEqual(len(canonical(result).encode()),12000)
        self.assertGreater(result['changes']['omitted'],0)
        self.assertEqual(result['changes']['sha256'],digest(rows))
        self.assertEqual(result['gaps']['omitted'],1)
