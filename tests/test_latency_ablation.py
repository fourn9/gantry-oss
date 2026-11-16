import importlib.util
import tempfile
import unittest
from collections import Counter
from pathlib import Path

spec=importlib.util.spec_from_file_location('latency_ablation',Path(__file__).parents[1]/'examples/engineering-crew/ablation.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)

class AblationTests(unittest.TestCase):
    def test_schedule_balances_positions_and_never_reuses_old_case(self):
        rows=a.schedule();self.assertEqual(len(rows),16)
        for case in range(4):self.assertEqual({r['condition'] for r in rows if r['case']==case},set(a.CONDITIONS))
        for position in range(4):self.assertEqual({r['condition'] for r in rows if r['position']==position},set(a.CONDITIONS))
        self.assertEqual(len(set(a.CASES)),4);self.assertNotIn((-4,0,-3),a.CASES)

    def test_private_output_cannot_overwrite_or_enter_repository(self):
        from gantry.model import Fault
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(Fault):a.new_root(folder)
        with self.assertRaises(Fault):a.new_root(Path(__file__).parents[1]/'ablation-private-test-output')

    def test_native_preparation_is_shared_and_tampering_rejected(self):
        try:from gantry import cad_kernel
        except ImportError:self.skipTest('Optional native CAD runtime not installed')
        from gantry.model import Fault
        import json
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);prepared=root/'prepared';prepared.mkdir()
            protocol=a.prepare(prepared,'not-invoked')
            copies=[]
            for label in ['a','b']:
                target=root/label;target.mkdir()
                frozen,_=a.copy_fixture(prepared,protocol['schedule'][0],target,protocol);copies.append(frozen['manifest'])
            self.assertEqual(copies[0],copies[1])
            p=prepared/'case-0'/'frozen.json';f=json.loads(p.read_text());f['goal']='modified';p.write_text(json.dumps(f))
            target=root/'tampered';target.mkdir()
            with self.assertRaises(Fault):a.copy_fixture(prepared,protocol['schedule'][0],target,protocol)

    def test_held_provider_failure_stops_subsequent_samples(self):
        import json
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            # This is the held result returned by BotWorker.tick after catching
            # a provider Fault: the comparison can finish without raising it.
            (root/'worker-results.json').write_text(json.dumps([
                {'job_id':'job','status':'held','reason':'provider_usage_limited'}]))
            error=a.recorded_failure(root,[])
            self.assertEqual(error['code'],'provider_usage_limited')
            self.assertIn(error['code'],a.STOP_ERRORS)
            calls=[{'status':'failed','error':'provider_rate_limited'}]
            self.assertEqual(a.recorded_failure(root,calls)['code'],'provider_rate_limited')
            (root/'worker-results.json').write_text('[]')
            self.assertIsNone(a.recorded_failure(root,[]))
