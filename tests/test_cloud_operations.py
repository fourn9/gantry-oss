import json
from pathlib import Path
import tempfile
import unittest

from gantry.model import Fault,digest
from gantry.service import Service

class CloudOperationsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_provision_isolated_workspace_and_verified_backup_restore(self):
        from gantry.cloud import provision,backup,restore,make_request
        p=provision(self.root/'cloud','team-one','owner')
        token=Path(p['token_file']).read_text().strip();s=Service(p['directory'])
        r=s.call(token,'capture_artifact',{'files':{'hello.txt':'aGVsbG8='}},'one')
        copied=backup(p['directory'],self.root/'backup')
        self.assertNotIn('admin.token',[x.name for x in (self.root/'backup').rglob('*')])
        restored=restore(self.root/'backup',self.root/'new-cloud','team-one')
        other=Service(restored['directory'])
        self.assertEqual(other.call(token,'restore_artifact',{'revision_id':r['revision_id']})['files']['hello.txt'],'aGVsbG8=')
        self.assertEqual(copied['checkpoint']['ledger_id'],p['ledger_id'])
        with self.assertRaises(Fault):provision(self.root/'cloud','team-one','owner')
        with self.assertRaises(Fault):restore(self.root/'backup',self.root/'new-cloud','team-one')
        generated=make_request('teammate',p['ledger_id'],'contributor',['root'],self.root/'member.token',self.root/'request.json')
        request=json.loads((self.root/'request.json').read_text())
        self.assertEqual(generated['fingerprint'],digest(request))
        self.assertNotIn((self.root/'member.token').read_text().strip(),(self.root/'request.json').read_text())
        self.assertEqual((self.root/'member.token').stat().st_mode&0o077,0)
    def test_invalid_paths_corrupt_backup_and_existing_token_refused(self):
        from gantry.cloud import provision,backup,restore,make_request
        with self.assertRaises(Fault):provision(self.root/'cloud','../escape','owner')
        p=provision(self.root/'cloud','team','owner');backup(p['directory'],self.root/'backup')
        (self.root/'backup'/'backup.json').write_text('{}')
        with self.assertRaises((Fault,KeyError)):restore(self.root/'backup',self.root/'copy','team')
        self.assertFalse((self.root/'copy'/'team').exists())
        (self.root/'token').write_text('keep')
        with self.assertRaises(Fault):make_request('person',p['ledger_id'],'reader',['root'],self.root/'token',self.root/'request.json')
        self.assertEqual((self.root/'token').read_text(),'keep')

    def test_request_concurrency_has_a_hard_bound(self):
        import socket
        import threading
        from gantry.server import CloudServer
        server=CloudServer(('127.0.0.1',0),self.root)
        for _ in range(16):self.assertTrue(server.connections.acquire(False))
        t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
        try:
            with socket.create_connection(server.server_address,timeout=2) as s:
                s.sendall(b'GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n')
                self.assertIn(b'503 Service Unavailable',s.recv(4096))
        finally:
            for _ in range(16):server.connections.release()
            server.shutdown();server.server_close();t.join()

    def test_access_request_files_are_private_at_creation_under_open_umask(self):
        import os
        from unittest.mock import patch
        from gantry.cloud import make_request
        original=os.open;created=[]
        def checked(path,flags,mode=0o777,**kw):
            fd=original(path,flags,mode,**kw)
            if flags & os.O_CREAT:
                created.append(Path(path).name)
                self.assertTrue(flags & os.O_EXCL)
                self.assertEqual(os.fstat(fd).st_mode&0o777,0o600)
            return fd
        previous=os.umask(0)
        try:
            with patch('gantry.cloud.os.open',side_effect=checked):
                make_request('member','ledger_fixture','reader',['root'],self.root/'member.token',self.root/'request.json')
        finally:os.umask(previous)
        self.assertEqual(set(created),{'member.token','request.json'})
