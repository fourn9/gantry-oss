import json
import shutil
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch
import test_development as fixture
from gantry.adapters import restore_files
from gantry.runner import run_contract

class ReliabilityTests(unittest.TestCase):
    setUp=fixture.DevelopmentTests.setUp; tearDown=fixture.DevelopmentTests.tearDown
    call=fixture.DevelopmentTests.call; artifact=fixture.DevelopmentTests.artifact
    connect=fixture.DevelopmentTests.connect; policy=fixture.DevelopmentTests.policy
    detail=fixture.DevelopmentTests.detail; propose=fixture.DevelopmentTests.propose
    contract=fixture.DevelopmentTests.contract; fault=fixture.DevelopmentTests.fault

    def test_restore_cache_integrity_and_isolation(self):
        cold=restore_files(self.client,self.snapshot,self.root/'cold')
        self.assertEqual(cold['transfer']['downloaded_parts'],1)
        (self.root/'cold/input.txt').write_text('local change')
        warm=restore_files(self.client,self.snapshot,self.root/'warm')
        self.assertEqual(warm['transfer']['requests'],0)
        self.assertEqual((self.root/'warm/input.txt').read_text(),'initial')
        cache=list((self.root/'.gantry-cache').rglob('*'))
        next(p for p in cache if p.is_file()).write_text('corruption')
        again=restore_files(self.client,self.snapshot,self.root/'again')
        self.assertEqual(again['transfer']['downloaded_parts'],1)
        bad=fixture.LocalClient(self.service,'revoked')
        self.fault('unauthorized',lambda:restore_files(bad,self.snapshot,self.root/'denied'))
        self.assertFalse((self.root/'denied').exists())

    def slow_contract(self):
        self.recipe={'argv':[sys.executable,'-c',
            'import time,json;open("result.json","w").write("partial");time.sleep(1.5);open("result.json","w").write(json.dumps({"verdict":"pass"}))'],
            'timeout_seconds':10,'offline_grace_seconds':3}
        self.session=self.connect();return self.propose()

    def test_transient_outage_keeps_process_and_flushes_outbox(self):
        c=self.slow_contract(); original=self.client.call; failures=[]
        def flaky(name,args=None,key=None):
            if name=='record_execution_step' and not failures:
                failures.append(name);raise OSError('offline')
            return original(name,args,key)
        with patch.object(self.client,'call',side_effect=flaky):
            result=run_contract(self.client,c['id'],{'test':self.recipe},self.root/'runs',interval=.1)
        self.assertEqual(result['engineering_verdict'],'pass')
        self.assertEqual(len(failures),1)
        j=json.loads(next((self.root/'runs').rglob('journal.json')).read_text())
        self.assertTrue(j['outbox']);self.assertTrue(all(x['sent'] for x in j['outbox']))
        self.assertEqual(len(self.detail()['executions']),1)

    def test_single_changing_sample_recovers_without_invalidating_final_result(self):
        c=self.slow_contract(); original=shutil.copytree; mixed=[]
        def racing_copy(src,dst,*args,**kwargs):
            result=original(src,dst,*args,**kwargs)
            if not mixed and 'outbox' in Path(dst).parts:
                mixed.append(str(dst))
                (Path(dst)/'result.json').write_text('inconsistent intermediate copy')
            return result
        with patch('gantry.runner.shutil.copytree',side_effect=racing_copy):
            result=run_contract(self.client,c['id'],{'test':self.recipe},self.root/'runs',interval=.1)
        self.assertTrue(mixed)
        self.assertTrue(result['valid'],result)
        self.assertEqual(result['engineering_verdict'],'pass')
        self.assertEqual(len(self.detail()['executions']),1)
        journal=next((self.root/'runs').rglob('journal.json'))
        j=json.loads(journal.read_text())
        self.assertGreaterEqual(j['sampling_retries'],1)
        self.assertFalse(list((journal.parent/'outbox').iterdir()))

    def test_persistent_changing_samples_stay_incomplete_and_leave_no_partial_copies(self):
        c=self.slow_contract(); original=shutil.copytree
        def racing_copy(src,dst,*args,**kwargs):
            result=original(src,dst,*args,**kwargs)
            if 'outbox' in Path(dst).parts:
                (Path(dst)/'input.txt').write_text('inconsistent intermediate copy')
            return result
        with patch('gantry.runner.shutil.copytree',side_effect=racing_copy):
            result=run_contract(self.client,c['id'],{'test':self.recipe},self.root/'runs',interval=.1)
        self.assertFalse(result['valid'])
        self.assertIn('capture_incomplete',result['reasons'])
        journal=next((self.root/'runs').rglob('journal.json'))
        self.assertIn('unstable_local_sample',json.loads(journal.read_text())['missing'])
        self.assertFalse(list((journal.parent/'outbox').iterdir()))

    def test_resume_receipt_without_duplicate_launch(self):
        c=self.slow_contract()
        with patch('gantry.runner._follow_job',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt): run_contract(self.client,c['id'],{'test':self.recipe},self.root/'runs')
        result=run_contract(self.client,c['id'],{'test':self.recipe},self.root/'runs',interval=.1)
        self.assertEqual(result['engineering_verdict'],'pass')
        self.assertEqual(len(self.detail()['executions']),1)
        self.assertEqual(len(list((self.root/'runs').rglob('receipt.json'))),1)
        self.assertTrue(self.call('replay')['matched'])

    def test_offline_lease_stops_long_process(self):
        self.recipe={'argv':[sys.executable,'-c','import time;time.sleep(20)'],'timeout_seconds':25,'offline_grace_seconds':1}
        self.session=self.connect();c=self.propose();original=self.client.call
        def offline(name,args=None,key=None):
            if name=='development_state' and list((self.root/'runs').rglob('receipt.json')): raise OSError('offline')
            return original(name,args,key)
        started=time.monotonic()
        with patch.object(self.client,'call',side_effect=offline):
            result=run_contract(self.client,c['id'],{'test':self.recipe},self.root/'runs',interval=.1)
        self.assertLess(time.monotonic()-started,8)
        receipt=json.loads(next((self.root/'runs').rglob('receipt.json')).read_text())
        self.assertEqual(receipt['reason'],'connection_lease_expired')
        self.assertNotEqual(result['engineering_verdict'],'pass')

    def test_actual_http_disconnect_reconnect_keeps_one_execution(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        from gantry.server import Server
        from gantry.client import Client
        c=self.slow_contract()
        server=Server(('127.0.0.1',0),self.service);address=server.server_address
        threading.Thread(target=server.serve_forever,daemon=True).start()
        client=Client('http://127.0.0.1:'+str(address[1]),self.token)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(run_contract,client,c['id'],{'test':self.recipe},self.root/'runs',.1)
            deadline=time.monotonic()+5
            while not list((self.root/'runs').rglob('receipt.json')) and time.monotonic()<deadline:time.sleep(.02)
            server.shutdown();server.server_close();time.sleep(.3)
            server=Server(address,self.service);threading.Thread(target=server.serve_forever,daemon=True).start()
            try:
                try:result=future.result(timeout=10)
                except OSError:result=run_contract(client,c['id'],{'test':self.recipe},self.root/'runs',interval=.1)
                self.assertEqual(result['engineering_verdict'],'pass')
                self.assertEqual(len(self.detail()['executions']),1)
                logs=list((self.root/'runs').rglob('transport.jsonl'))
                self.assertTrue(logs)
            finally:server.shutdown();server.server_close()
