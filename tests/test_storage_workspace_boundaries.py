import os
import secrets
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gantry.model import Fault
from gantry.service import Service, token_hash
from gantry.server import CloudServer


class StorageBoundaryTests(unittest.TestCase):
    def test_reader_metadata_survives_restart_export_and_replay(self):
        with tempfile.TemporaryDirectory() as root:
            svc = Service(root); admin = svc.bootstrap()['token']
            def call(cmd, args): return svc.call(admin, cmd, args, secrets.token_hex(12))
            reader = secrets.token_urlsafe(32)
            p = call('propose', {'title':'Reader', 'changes':[{'id':'reader','type':'principal',
                'data':{'kind':'agent','permissions':['read'],'token_hash':token_hash(reader)}}]})
            a = {'proposal_id':p['id'],'version':p['version']}
            call('submit', a); call('endorse', {**a,'reason':'test'})
            call('review_adoption', {**a,'reason':'test','verdict':'approve'}); call('commit', a)
            for files in ({'a':None}, {'_manifest_root':None}, {'x':{'nested':None}}):
                basis = {'type':'artifact_snapshot','data':{'files':files}}
                svc.call(reader, 'subscribe', {'types':['decision'],'basis':basis}, secrets.token_hex(12))
                self.assertTrue(svc.call(admin,'verify')['valid'])
                self.assertEqual(svc.call(admin,'export')['events'][-1]['basis'], basis)
            svc = Service(root)
            self.assertTrue(svc.call(admin,'verify')['valid'])
            self.assertTrue(call('replay', {})['matched'])


class WorkspaceBoundaryTests(unittest.TestCase):
    def test_nested_workspace_cannot_reference_sibling_credentials(self):
        with tempfile.TemporaryDirectory() as root:
            tokens = {name:Service(Path(root)/name).bootstrap()['token'] for name in ('team','team-a')}
            server = CloudServer(('127.0.0.1',0), root)
            try:
                a,_=server.resolve('/w/team/'); b,_=server.resolve('/w/team-a/')
                token=tokens['team']
                def call(cmd,args): return a.call(token,cmd,args,secrets.token_hex(12))
                project=call('save_project',{'name':'Fixture','description':'Isolation'})
                args={'project_id':project['id'],'provider':'github','name':'Fixture',
                      'repository':'example/fixture','enabled':True}
                victim=b.credential_prefix+'GITHUB'
                with patch.dict(os.environ,{victim:'fixture-only'}):
                    with self.assertRaises(Fault):call('configure_integration',{**args,'credential_ref':victim})
                    own=a.credential_prefix+'GITHUB'
                    with patch.dict(os.environ,{own:'own-fixture'}):
                        item=call('configure_integration',{**args,'credential_ref':own})
                        self.assertTrue(item['credential_configured'])
                    # Stored legacy references must be denied again at use time.
                    a.credential_prefix=b.credential_prefix
                    with patch('gantry.github_connector.fetch_repository') as fetch:
                        with self.assertRaises(Fault):call('sync_integration',{'integration_id':item['id']})
                        fetch.assert_not_called()
                    self.assertFalse(a._integration_view(item)['credential_configured'])
            finally:server.server_close()


class CodecTests(unittest.TestCase):
    def test_legacy_manifest_and_new_literal_metadata_roundtrip(self):
        from gantry import manifest_store
        import sqlite3
        with sqlite3.connect(':memory:') as con:
            manifest_store.schema(con)
            files={'file':{'hash':'fixture','size':1}}
            root=manifest_store.Tree(con).manifest(files)
            legacy={'_gantry_storage':1,'value':{'type':'artifact_snapshot',
                'data':{'files':{'_manifest_root':root}}}}
            expected={'type':'artifact_snapshot','data':{'files':files}}
            self.assertEqual(manifest_store.unpack(con,legacy),expected)
            value={'type':'artifact_snapshot','data':{'files':files,
                'source':{'type':'artifact_snapshot','data':{'files':{'a':None}}}}}
            packed=manifest_store.pack(con,value,[()])
            self.assertEqual(manifest_store.unpack(con,packed),value)
            literal={'_gantry_storage':1,'value':legacy}
            self.assertEqual(manifest_store.unpack(con,manifest_store.pack(con,literal)),literal)

    def test_lossy_codec_aborts_before_event_insert(self):
        from gantry import manifest_store
        with tempfile.TemporaryDirectory() as root:
            svc=Service(root); token=svc.bootstrap()['token']
            before=svc.call(token,'verify')
            original=manifest_store.pack
            def lossy(con,value,*args):
                packed=original(con,value,*args)
                if 'event_id' in value: packed['value']['basis']={'unexpected':'change'}
                return packed
            with patch('gantry.manifest_store.pack',side_effect=lossy):
                with self.assertRaises(Fault):
                    svc.call(token,'subscribe',{'types':['decision']},'lossy')
            self.assertEqual(svc.call(token,'verify'),before)
            self.assertTrue(svc.call(token,'replay',{},'replay')['matched'])

    def test_resolver_denies_out_of_scope_before_environment_lookup(self):
        from gantry.github_connector import credential
        with patch('gantry.github_connector.os.environ.get') as read:
            with self.assertRaises(Fault):
                credential('GANTRY_CONNECTOR_WS_61__GITHUB','GANTRY_CONNECTOR_WS_62__')
            read.assert_not_called()
