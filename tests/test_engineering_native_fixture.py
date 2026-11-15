"""Objective checks kept in tests, never supplied as a Bot answer."""
import importlib.util,json,tempfile,unittest,shutil
from pathlib import Path
from gantry.service import Service
from gantry.learning_evaluation_setup import LocalClient
from gantry.project_sandbox import execute,runtime_roots,backend

class NativeFixtureTests(unittest.TestCase):
    def test_actual_step_and_controller_fix_then_calibration_break(self):
        try:from gantry import cad_kernel
        except ImportError:self.skipTest('Optional native CAD runtime not installed')
        s=importlib.util.spec_from_file_location('native_fixture',Path(__file__).parents[1]/'examples/engineering-crew/run.py')
        m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);service=Service(root/'ledger');owner=LocalClient(service,service.bootstrap()['token'])
            _,state,_,_,tools=m.fixture(owner,root)
            self.assertEqual(state['context']['environment']['engineering']['checks'][0]['status'],'fail')
            work=root/'initial'
            def run(name):
                with tempfile.TemporaryDirectory(dir=root) as temp:
                    scratch=Path(temp)
                    for source in work.iterdir():
                        if source.is_file():shutil.copy2(source,scratch/source.name)
                    result=execute(tools[name],scratch,runtime_roots(),backend(),lambda:None)
                    self.assertEqual(result['exit_code'],0,result)
                    for p in scratch.iterdir():
                        if p.is_file() and not p.name.startswith('.'):shutil.copy2(p,work/p.name)
            (work/'design.json').write_text('{"carrier_x_mm":12}')
            (work/'control.json').write_text('{"target_mm":10}')
            run('build');step=(work/'carrier.step').read_bytes();run('verify')
            self.assertEqual(step,(work/'carrier.step').read_bytes(),'Verifier must not change evaluated geometry')
            from gantry.physical_evidence import evaluate
            import hashlib
            check=json.loads((work/'physical-plan.json').read_text())['checks'][0]
            def result():return evaluate(check,json.loads((work/'report.json').read_text()),
                {p:hashlib.sha256((work/p).read_bytes()).hexdigest() for p in check['inputs']})
            self.assertEqual(result()['status'],'pass')
            (work/'calibration.json').write_text('{"offset_mm":3}')
            self.assertEqual(result()['status'],'unknown','Old result cannot pass changed input')
            run('verify');self.assertEqual(result()['status'],'fail')
