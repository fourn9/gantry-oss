import tempfile,json,unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from gantry.monthly_codex import infer_monthly
from gantry.model import Fault

class MonthlyTests(unittest.TestCase):
    def test_api_login_is_refused(self):
        with tempfile.TemporaryDirectory() as root, patch('gantry.monthly_codex.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='Logged in using API key',stderr='')):
            with self.assertRaises(Fault) as error:infer_monthly({}, {}, root)
            self.assertEqual(error.exception.code,'subscription_login_required')
    def test_official_cli_tools_disabled_and_receipt_reused(self):
        commands=[]
        class Process:
            returncode=0
            pid=99999999
            def __init__(self,argv,**kw):
                commands.append((argv,kw));self.output=Path(argv[argv.index('-o')+1])
            def communicate(self,prompt,timeout):self.output.write_text('{"status":"ready"}')
        schema={'type':'object','properties':{'status':{'type':'string'}},'required':['status'],'additionalProperties':False}
        with tempfile.TemporaryDirectory() as root, patch('gantry.monthly_codex.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='',stderr='Logged in using ChatGPT')),patch('gantry.monthly_codex.subprocess.Popen',Process),patch.dict('os.environ',{'OPENAI_API_KEY':'must-not-use','CODEX_API_KEY':'must-not-use'}):
            out=infer_monthly({'task':'ready'},schema,root)
            self.assertEqual(out['output'],{'status':'ready'})
            self.assertEqual(infer_monthly({'task':'ready'},schema,root),out)
            self.assertEqual(len(commands),1)
            argv,kw=commands[0]
            self.assertIn('shell_tool',argv);self.assertIn('view_image',argv);self.assertIn('apps',argv)
            self.assertNotIn('OPENAI_API_KEY',kw['env']);self.assertNotIn('CODEX_API_KEY',kw['env'])
    def test_uncertain_invocation_not_repeated(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root,'inference.json').write_text(json.dumps({'phase':'started','context':{},'schema':{}}))
            with self.assertRaises(Fault) as error:infer_monthly({}, {}, root)
            self.assertEqual(error.exception.code,'outcome_unknown')
    def test_explicit_model_and_effort_are_pinned_to_receipt(self):
        commands=[]
        class Process:
            returncode=0
            pid=99999999
            def __init__(self,argv,**kw):
                commands.append(argv); self.output=Path(argv[argv.index('-o')+1])
            def communicate(self,prompt,timeout): self.output.write_text('{}')
        with tempfile.TemporaryDirectory() as root, patch('gantry.monthly_codex.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='ChatGPT',stderr='')), patch('gantry.monthly_codex.subprocess.Popen',Process):
            out=infer_monthly({}, {}, root, model='explicit-model', reasoning_effort='low')
            self.assertEqual(commands[0][commands[0].index('--model')+1],'explicit-model')
            self.assertIn('model_reasoning_effort="low"',commands[0])
            self.assertEqual(out['provider']['model'],'explicit-model')
            with self.assertRaises(Fault): infer_monthly({}, {}, root, model='different', reasoning_effort='low')
