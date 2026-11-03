import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from gantry.model import Fault, digest


class PhysicalExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve(); self.source=self.root/'source'; self.source.mkdir()
        (self.source/'input.txt').write_text('candidate')
        self.script='''import json,hashlib,pathlib
p=json.loads(pathlib.Path('physical-plan.json').read_text())['checks'][0]
r={k:p[k] for k in ['conditions','evaluator','environment']}
r.update(status='completed',inputs={n:hashlib.sha256(pathlib.Path(n).read_bytes()).hexdigest() for n in p['inputs']},
 limitations=['Synthetic evaluator; no physics'],measurements={'error':{'value':0,'unit':'mm'}})
pathlib.Path('report.json').write_text(json.dumps(r))
'''
        (self.source/'evaluate.py').write_text(self.script)
        self.check={'id':'motion','scope':'motion','components':['part'],'required':True,
            'inputs':['input.txt','evaluate.py'],'report':'report.json','conditions':{'speed':1},
            'evaluator':{'name':'fixture','version':'1'},'environment':{'python':sys.version.split()[0]},
            'criteria':[{'metric':'error','unit':'mm','max':1}]}
        self.plan={'version':1,'components':[{'id':'part','role':'moving','assembly':'robot','paths':['input.txt']}], 'checks':[self.check]}
        (self.source/'physical-plan.json').write_text(json.dumps(self.plan))
        self.recipe={'argv':[sys.executable,'-I','evaluate.py'],'timeout_seconds':5}

    def run_job(self, **kwargs):
        from gantry.physical_execution import run
        return run(self.source,'physical-plan.json','motion',self.recipe,digest(self.recipe),self.root/'job',**kwargs)

    def test_frozen_run_retains_evidence_and_does_not_repeat(self):
        r=self.run_job(); self.assertEqual(r['evaluation']['status'],'pass')
        self.assertEqual(r['outcome'],'completed')
        self.assertEqual(self.run_job(), r)
        self.assertEqual((self.root/'job/workspace/input.txt').read_text(),'candidate')
        self.assertEqual((self.source/'input.txt').read_text(),'candidate')

    def test_mutated_input_cannot_produce_pass(self):
        (self.source/'evaluate.py').write_text("from pathlib import Path\nPath('input.txt').write_text('tampered')\n"+self.script)
        r=self.run_job()
        self.assertEqual(r['evaluation']['status'],'unknown')
        self.assertIn('input_changed_during_execution',r['problems'])

    def test_failed_process_and_missing_report_are_recorded(self):
        (self.source/'evaluate.py').write_text('raise SystemExit(3)')
        r=self.run_job(); self.assertEqual(r['exit_code'],3)
        self.assertEqual(r['evaluation']['status'],'unknown')
        self.assertTrue((self.root/'job/stderr.log').exists())

    def test_unapproved_recipe_and_ambiguous_launch_are_held(self):
        from gantry.physical_execution import run
        with self.assertRaises(Fault):
            run(self.source,'physical-plan.json','motion',self.recipe,'0'*64,self.root/'bad')
        from unittest.mock import patch
        with patch('gantry.physical_execution.subprocess.Popen', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt): self.run_job()
        with self.assertRaises(Fault) as caught: self.run_job()
        self.assertEqual(caught.exception.code,'execution_uncertain')

    def test_collect_checks_current_inputs_and_retains_failed_raw_report(self):
        from gantry.physical_execution import collect
        (self.source/'evaluate.py').write_text(self.script+'raise SystemExit(2)\n')
        self.run_job()
        result=collect(self.root/'job',self.source)
        self.assertEqual(json.loads((self.source/'report.json').read_text())['status'],'error')
        self.assertEqual(json.loads((self.source/result['evidence_path']/'receipt.json').read_text())['report']['status'],'completed')
        self.assertEqual(collect(self.root/'job',self.source),result)
        (self.source/'input.txt').write_text('new candidate')
        with self.assertRaises(Fault) as caught: collect(self.root/'job',self.source)
        self.assertEqual(caught.exception.code,'stale_basis')

    def test_reconcile_interruption_is_unknown_and_never_relaunched(self):
        from gantry.physical_execution import reconcile
        from unittest.mock import patch
        with patch('gantry.physical_execution.subprocess.Popen',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt): self.run_job()
        with self.assertRaises(Fault): reconcile(self.root/'job',False)
        result=reconcile(self.root/'job',True)
        self.assertEqual(result['evaluation']['status'],'unknown')
        self.assertEqual(self.run_job(),result)

    def test_changed_log_cannot_be_published_as_execution_evidence(self):
        from gantry.physical_execution import collect
        self.run_job()
        (self.root/'job/stdout.log').write_text('forged output')
        with self.assertRaises(Fault) as caught: collect(self.root/'job',self.source)
        self.assertEqual(caught.exception.code,'integrity_error')

    @unittest.skipUnless(sys.platform != 'win32','POSIX process groups')
    def test_background_child_prevents_pass(self):
        (self.source/'evaluate.py').write_text(self.script+'''import subprocess,sys
subprocess.Popen([sys.executable,'-c','import time;time.sleep(5)'])
''')
        result=self.run_job()
        self.assertEqual(result['evaluation']['status'],'unknown')
        self.assertIn('descendants_after_parent_exit',result['problems'])

    def test_missing_report_path_is_rejected_before_launch(self):
        del self.plan['checks'][0]['report']
        (self.source/'physical-plan.json').write_text(json.dumps(self.plan))
        with self.assertRaises(Fault) as caught: self.run_job()
        self.assertEqual(caught.exception.code,'invalid_input')
        self.assertFalse((self.root/'job').exists())
