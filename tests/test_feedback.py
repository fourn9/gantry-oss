import base64
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from gantry import feedback as f
from gantry.feedback_receiver import Receiver, RETENTION
from gantry.model import Fault, canonical

@unittest.skipUnless(__import__('importlib.util',fromlist=['find_spec']).find_spec('nacl'), 'Install the feedback extra')
class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.data=self.root/'data'
    def tearDown(self):self.temp.cleanup()
    def configure(self):f.configure(self.data,'diagnostics')
    def keys(self,url='http://127.0.0.1:8780/v1/feedback'):
        f.keygen(self.root/'private.key',self.root/'recipient.json',url)
    def preview(self):
        log=self.root/'test.log'
        log.write_text('Authorization: Bearer super-secret-value\napi_key=super-secret-value\nerror at /home/alice/project/file.py\ncontact alice@example.com\nfailed operation\n')
        return f.prepare(self.data,self.root/'recipient.json',[log],self.root/'preview.json')
    def test_default_noninteractive_and_explicit_prompt(self):
        with patch('sys.stdin',io.StringIO('')):
            self.assertEqual(f.onboarding(self.data)['mode'],'off')
        with patch('sys.stdin.isatty',return_value=True),patch('builtins.input',return_value='2'):
            self.assertEqual(f.onboarding(self.data)['mode'],'diagnostics')
        f.configure(self.data,'off')
        with self.assertRaises(Fault):f.prepare(self.data,'missing',[],self.root/'out')
    def test_permission_and_selected_logs_only(self):
        self.configure();self.keys();preview=self.preview()
        raw=(self.root/'preview.json').read_text()
        for hidden in ['super-secret-value','alice@example.com','/home/alice','test.log']:
            self.assertNotIn(hidden,raw)
        self.assertIn('failed operation',raw)
        self.assertEqual((self.root/'preview.json').stat().st_mode & 0o777,0o600)
        f.configure(self.data,'statistics')
        with self.assertRaises(Fault):f.seal(self.data,self.root/'preview.json',preview['sha256'],self.root/'sealed')
    def test_exact_confirmation_tamper_revoke_and_wrong_key(self):
        self.configure();self.keys();preview=self.preview()
        with self.assertRaises(Fault):f.seal(self.data,self.root/'preview.json','0'*64,self.root/'no')
        f.seal(self.data,self.root/'preview.json',preview['sha256'],self.root/'sealed')
        self.assertNotIn('failed operation',(self.root/'sealed').read_text())
        f.decrypt(self.root/'private.key',self.root/'sealed',self.root/'opened')
        self.assertEqual((self.root/'opened').read_bytes(),(self.root/'preview.json').read_bytes())
        value=json.loads((self.root/'sealed').read_text());cipher=bytearray(base64.b64decode(value['ciphertext']));cipher[-1]^=1
        value['ciphertext']=base64.b64encode(cipher).decode();(self.root/'tampered').write_text(json.dumps(value))
        with self.assertRaises(Fault):f.decrypt(self.root/'private.key',self.root/'tampered',self.root/'bad')
        f.keygen(self.root/'wrong.key',self.root/'wrong.json','http://localhost:1/v1/feedback')
        with self.assertRaises(Fault):f.decrypt(self.root/'wrong.key',self.root/'sealed',self.root/'bad2')
        f.configure(self.data,'off')
        with self.assertRaises(Fault):f.seal(self.data,self.root/'preview.json',preview['sha256'],self.root/'revoked')
    def test_symlink_and_oversized_log_refused(self):
        self.configure();self.keys();(self.root/'source.log').write_text('x');(self.root/'linked.log').symlink_to(self.root/'source.log')
        with self.assertRaises(OSError):f.prepare(self.data,self.root/'recipient.json',[self.root/'linked.log'],self.root/'out')
        (self.root/'large.log').write_bytes(b'x'*(128*1024+1))
        with self.assertRaises(Fault):f.prepare(self.data,self.root/'recipient.json',[self.root/'large.log'],self.root/'out')
    def test_upload_does_not_report_success_for_an_unrelated_receipt(self):
        self.configure();self.keys();preview=self.preview()
        f.private_write(self.root/'invite.token',secrets.token_urlsafe(32).encode())
        response=io.BytesIO(json.dumps({'receipt':'0'*64,'retention_days':30}).encode())
        response.status=201
        with patch('gantry.feedback.build_opener') as opener:
            opener.return_value.open.return_value=response
            with self.assertRaises(Fault) as error:
                f.send(self.data,self.root/'preview.json',preview['sha256'],self.root/'sealed',self.root/'invite.token')
            self.assertEqual(error.exception.code,'upload_failed')
            opener.return_value.open.assert_called_once()
        self.assertTrue((self.root/'sealed').is_file())
    def test_real_encrypted_upload_retention_no_download_and_no_key_online(self):
        self.configure();self.keys();token=secrets.token_urlsafe(32);f.private_write(self.root/'invite.token',token.encode())
        key=json.loads((self.root/'recipient.json').read_text())
        server=Receiver(('127.0.0.1',0),self.root/'inbox',self.root/'invite.token',key['key_id'])
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        url='http://127.0.0.1:'+str(server.server_port)
        key['url']=url+'/v1/feedback';(self.root/'recipient.json').write_text(json.dumps(key))
        try:
            preview=self.preview()
            with self.assertRaises(HTTPError) as error:urlopen(Request(url+'/v1/feedback',data=b'{}',headers={'Content-Type':'application/json'}))
            self.assertEqual(error.exception.code,401)
            sent=f.send(self.data,self.root/'preview.json',preview['sha256'],self.root/'sealed',self.root/'invite.token')
            self.assertTrue(sent['sent']);saved=self.root/'inbox'/(sent['receipt']+'.json')
            self.assertEqual(saved.read_bytes(),(self.root/'sealed').read_bytes())
            self.assertEqual(len(list((self.root/'inbox').iterdir())),1)
            with self.assertRaises(HTTPError):urlopen(url+'/'+saved.name)
            body=(self.root/'sealed').read_bytes()
            request=Request(url+'/v1/feedback',data=body,headers={'Content-Type':'application/json','Authorization':'Bearer '+token})
            with urlopen(request) as response:self.assertEqual(json.load(response)['receipt'],sent['receipt'])
            self.assertEqual(len(list((self.root/'inbox').iterdir())),1)
            wrong=dict(json.loads(body));wrong['key_id']='0'*64
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(url+'/v1/feedback',data=canonical(wrong).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+token}))
            self.assertEqual(error.exception.code,400)
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(url+'/v1/feedback',data=b'x',headers={'Content-Type':'application/json','Authorization':'Bearer '+token,'Content-Length':str(f.MAX_BYTES+1)}))
            self.assertEqual(error.exception.code,413)
            os.utime(saved,(time.time()-RETENTION-1,)*2);server.prune();self.assertFalse(saved.exists())
            with patch('gantry.feedback_receiver.CAPACITY',1),self.assertRaises(HTTPError) as error:urlopen(request)
            self.assertEqual(error.exception.code,507)
            server.request_count=30
            with self.assertRaises(HTTPError) as error:urlopen(request)
            self.assertEqual(error.exception.code,429)
        finally:server.shutdown();server.server_close();thread.join()
