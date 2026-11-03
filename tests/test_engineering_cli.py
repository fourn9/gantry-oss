import argparse
import json
import subprocess
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
import test_continuity as fixtures
from gantry.model import Fault


class CLITests(unittest.TestCase):
    for name in ('setUp','tearDown','call','artifact','policy','connect','detail','fault','initialize','begin','checkpoint'):
        locals()[name]=getattr(fixtures.ContinuityTests,name)

    def test_real_cli_http_checkpoint_and_invalid_token_retry(self):
        from gantry.server import Server
        server=Server(('127.0.0.1',0),self.service)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        token=self.root/'operator.token';token.write_text(self.token);token.chmod(0o600)
        url='http://127.0.0.1:'+str(server.server_port)
        def cli(*args):
            return subprocess.run([sys.executable,'-m','gantry.engineering_cli','--url',url,
                '--token-file',str(token),*args],capture_output=True,text=True,timeout=30)
        base=self.initialize()
        result=cli('checkout','--state-id',base['id'],'--destination',str(self.root/'checkout'),
            '--title','CLI test','--purpose','HTTP roundtrip','--scope','input.txt','--assignee','admin','--key','start')
        self.assertEqual(result.returncode,0,result.stderr)
        root=Path(json.loads(result.stdout)['workspace']);(root/'input.txt').write_text('updated')
        args=('checkpoint','--root',str(root),'--summary','CLI candidate','--reason','Unverified','--key','save')
        first=cli(*args);self.assertEqual(first.returncode,0,first.stderr)
        token.write_text('invalid')
        refused=cli(*args);self.assertNotEqual(refused.returncode,0)
        self.assertEqual(json.loads(refused.stderr)['error']['code'],'unauthorized')
        token.write_text(self.token)
        self.assertEqual(json.loads(cli(*args).stdout)['state']['id'],json.loads(first.stdout)['state']['id'])

    def test_evaluate_holds_changed_requirement_before_launch(self):
        from gantry.engineering_cli import execute
        token=self.root/'operator.token';token.write_text('test-only')
        args=argparse.Namespace(command='evaluate',url='http://localhost:1',token_file=str(token),root=str(self.root))
        class Client:
            def call(self,*args): return {'requirement_coverage':{'items':[{'status':'needs_review'}]}}
        with patch('gantry.client.Client',return_value=Client()),patch('gantry.engineering_workflow.link',return_value={'state_id':'s'}):
            with self.assertRaises(Fault) as caught: execute(args)
        self.assertEqual(caught.exception.code,'stale_basis')
