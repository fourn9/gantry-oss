import base64
import copy
import json
import os
import secrets
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from gantry.model import Fault
from gantry.service import Service
from gantry.client import Client
from gantry.server import CloudServer
from gantry.backup import restore_backup


class ProductTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.service = Service(self.root/'ledger'); self.token = self.service.bootstrap()['token']
        self.project = self.call('save_project', {'name': 'Robot fleet', 'description': 'Post-release maintenance'})
    def tearDown(self): self.temp.cleanup()
    def call(self, command, args=None, key=None):
        return self.service.call(self.token, command, args, key or secrets.token_hex(12))
    def integration(self, provider='monitoring'):
        return self.call('configure_integration', {'project_id': self.project['id'], 'name': 'Issues', 'provider': provider,
            'enabled': True, **({'repository': 'octocat/Hello-World'} if provider == 'github' else {})})
    def upload(self, files=None):
        return self.call('upload_project_files', {'project_id': self.project['id'], 'summary': 'Existing robot', 'category': 'simulation',
            'files': {k: base64.b64encode(v).decode() for k,v in (files or {'model.xml': b'<mujoco/>', 'control.py': b'gain = 1'}).items()}})
    def session(self, signal=None):
        upload = self.upload()
        return self.call('create_product_session', {'project_id': self.project['id'], 'title': 'Investigate head stalls',
            'goal': 'Reproduce and explain before changing the design', 'snapshot': upload['snapshot'],
            **({'signal_id': signal['id']} if signal else {})})

    def test_ingestion_updates_provenance_without_duplicate_session_or_adoption(self):
        i = self.integration(); a = {'integration_id':i['id'], 'source_event_id':'evt-1', 'title':'Stall', 'body':'A log',
            'occurred_at':'2026-09-22T00:00:00Z', 'observed_configuration': {'hardware':'H1','software':'S2','electrical':'E3'}}
        signal = self.call('ingest_signal', a); repeat = self.call('ingest_signal', a)
        self.assertEqual(signal['revision_id'], repeat['revision_id'])
        session = self.session(signal); sid = session['session']['id']
        changed = self.call('ingest_signal', {**a,'body':'Additional evidence'})
        self.assertNotEqual(changed['revision_id'], signal['revision_id'])
        detail = self.call('session_details', {'session_id':sid})
        self.assertEqual(detail['link']['source_revision'], signal['revision_id'])
        self.assertEqual(detail['source']['revision_id'], changed['revision_id'])
        self.assertTrue(any(changed['revision_id'] in m['references'] for m in detail['milestones']))
        self.assertEqual(detail['state']['status']['adoption'], 'unadopted')
        self.assertEqual(detail['summary']['status'], 'queued')
        ctx = self.call('mentor_context', {'session_id':sid})
        self.assertEqual(ctx['incoming_source']['observed_configuration']['electrical'], 'E3')
        self.assertTrue(self.call('replay')['matched'])

    def test_upload_secret_path_limits_and_restore(self):
        for files in ({'../escape':b'data'}, {'.env':b'PASSWORD=secret'}, {'private.pem':b'data'},
                      {'notes.txt':b'-----BEGIN PRIVATE KEY-----'}, {'auth.json':b'{}'}):
            with self.assertRaises(Fault): self.upload(files)
        upload = self.upload({'model.step': b'ISO-10303-21; fixture', 'code/control.py': b'gain=2'})
        result = self.call('restore_artifact', {'revision_id':upload['snapshot']})
        self.assertEqual(base64.b64decode(result['files']['code/control.py']), b'gain=2')
        self.assertIsNone(self.call('state')['head'])
        with self.assertRaises(Fault): self.session({'id':'missing'})

    def test_github_real_adapter_boundary_idempotency_and_disconnect(self):
        i = self.integration('github')
        response = {'signals':[{'source_event_id':'42','kind':'issue','title':'Bug','body':'<script>test</script>',
            'occurred_at':'2026-09-22', 'source_status':'open'}], 'repository_id':123,
            'coverage':'fixture', 'partial':True,'requests':2}
        with patch('gantry.github_connector.fetch_repository', return_value=response) as fetch:
            r = self.call('sync_integration', {'integration_id':i['id']}, 'sync1')
            self.assertTrue(r['synced']); self.assertTrue(r['integration']['partial'])
            self.assertEqual(self.call('sync_integration', {'integration_id':i['id']}, 'sync1'), r)
            self.assertEqual(fetch.call_count,1)
        i = self.call('configure_integration', {'integration_id':i['id'],'version':1, 'project_id':self.project['id'],
            'provider':'github','name':'GitHub','repository':'octocat/Hello-World','enabled':False})
        with self.assertRaises(Fault): self.call('sync_integration', {'integration_id':i['id']})
        self.assertEqual(len(self.call('product_overview')['signals']),1)
        self.assertEqual(i['status'],'disconnected')

    def test_sync_rechecks_config_after_network_and_records_error(self):
        i = self.integration('github')
        def fetch(config):
            self.call('configure_integration', {'integration_id':i['id'],'version':1,'project_id':self.project['id'],
                'provider':'github','name':'GitHub','repository':'octocat/Hello-World','enabled':False})
            return {'signals':[], 'repository_id':1,'coverage':'fixture','partial':False,'requests':1}
        with patch('gantry.github_connector.fetch_repository', side_effect=fetch):
            with self.assertRaises(Fault) as exc: self.call('sync_integration', {'integration_id':i['id']})
            self.assertEqual(exc.exception.code,'stale_basis')
        other = self.integration('github')
        with patch('gantry.github_connector.fetch_repository', side_effect=Fault('github_http_401','Access denied')):
            r = self.call('sync_integration', {'integration_id':other['id']})
        self.assertFalse(r['synced']); self.assertEqual(r['integration']['status'],'error')

    def test_late_sync_cannot_overwrite_another_completed_acquisition(self):
        i = self.integration('github'); calls = []
        def fetch(config):
            calls.append(1)
            if len(calls) == 1:
                self.call('sync_integration', {'integration_id':i['id']}, 'newer-sync')
                title = 'Old response'
            else:
                title = 'New response'
            return {'signals':[{'source_event_id':'1','kind':'issue','title':title,'body':'',
                'occurred_at':'2026-09-22','source_status':'open'}], 'repository_id':1,
                'coverage':'fixture','partial':False,'requests':2}
        with patch('gantry.github_connector.fetch_repository', side_effect=fetch):
            with self.assertRaises(Fault) as exc:
                self.call('sync_integration', {'integration_id':i['id']}, 'older-sync')
        self.assertEqual(exc.exception.code, 'stale_basis')
        self.assertEqual(self.call('product_overview')['signals'][0]['title'], 'New response')

    def test_credentials_not_saved_and_workspace_reference_is_scoped(self):
        self.service.credential_prefix='GANTRY_CONNECTOR_TEAM_A_'
        with self.assertRaises(Fault):
            self.call('configure_integration', {'project_id':self.project['id'],'provider':'github','name':'x',
                'repository':'a/b','enabled':True,'credential_ref':'GANTRY_CONNECTOR_TEAM_B_GITHUB'})
        with patch.dict(os.environ, {'GANTRY_CONNECTOR_TEAM_A_GITHUB':'sensitive-credential'}):
            r = self.call('configure_integration', {'project_id':self.project['id'],'provider':'github','name':'x',
                'repository':'a/b','enabled':True,'credential_ref':'GANTRY_CONNECTOR_TEAM_A_GITHUB'})
            self.assertTrue(r['credential_configured'])
            self.assertNotIn('sensitive-credential',json.dumps(self.call('export')))

    def test_worker_expiry_closure_and_backup(self):
        item = self.session(); sid = item['session']['id']
        self.call('worker_heartbeat', {'worker_id':'mentor1','kind':'mentor','session_ids':[sid], 'status':'working','summary':'Drafting'})
        self.assertEqual(self.call('product_overview')['sessions'][0]['status'],'running')
        self.service.clock=lambda:10**15
        self.assertFalse(self.call('product_overview')['workers'][0]['online'])
        self.call('set_session_outcome', {'session_id':sid,'version':1,'outcome':'closed','reason':'Reviewed'})
        view = self.call('session_details', {'session_id':sid})
        self.assertEqual(view['summary']['status'],'done'); self.assertEqual(view['state']['status']['adoption'],'unadopted')
        with self.assertRaises(Fault): self.call('request_mentor', {'session_id':sid,'summary':'Ignore closed session'})
        bundle=self.call('export'); restore_backup(self.root/'restored',bundle)
        restored=Service(self.root/'restored'); restored.clock=self.service.clock
        self.assertEqual(restored.call(self.token,'session_details',{'session_id':sid}),view)

    def test_continuation_has_real_parent_and_paused_work_cannot_start(self):
        from gantry.model import digest
        first=self.session(); parent=first['state']['id']
        fork=self.call('create_product_session', {'project_id':self.project['id'],'title':'Continue',
            'goal':'Use exact prior state','state_id':parent})
        view=self.call('get_development_state',{'state_id':fork['state']['id']})
        self.assertEqual(view['diffs'],[]); self.assertEqual(view['state']['parents'],[parent])
        d=fork['session']; recipe={'argv':['python3','check.py']}
        self.call('configure_development', {'session_id':d['id'],'version':d['version'],'reason':'Test',
            'mode':'execute','actors':['admin'],'write_scope':['result.json'],'recipes':{'test':digest(recipe)},
            'max_executions':1,'timeout_seconds':30,'max_parallel':1})
        ctx=self.call('mentor_context',{'session_id':d['id']}); m=ctx['milestones'][0]
        contract=self.call('mentor_propose', {'session_id':d['id'],'milestone_id':m['id'],
            'input_state':fork['state']['id'],'evidence':[fork['state']['id']],
            'contract':{'title':'Check','input_snapshot':d['snapshot'],'write_scope':['result.json'],
                'recipe':'test','recipe_hash':digest(recipe),'expected_outputs':['result.json'],
                'completion':{'description':'Check','required_files':['result.json'],'require_exit_zero':True},
                'dependencies':[],'hypothesis':'Test','rationale':'Test'}})
        self.assertTrue(self.call('check_execution',{'contract_id':contract['id']})['allowed'])
        self.call('set_session_outcome',{'session_id':d['id'],'version':1,'outcome':'paused','reason':'Stop'})
        result=self.call('start_execution',{'contract_id':contract['id'],'version':1})
        self.assertFalse(result['allowed']);self.assertIn('session_not_open',result['reasons'])
        self.assertEqual(self.call('development_state',{'session_id':d['id']})['session']['used_executions'],0)

    def test_new_surfaces_keep_mcp_contracts_and_do_not_accept_acquired_data(self):
        from gantry.mcp import tool_list
        tools={t['name']:t for t in tool_list()}
        for name in ('save_project','upload_project_files','sync_integration','request_mentor','create_product_session'):
            self.assertIn('idempotency_key',tools[name]['inputSchema']['required'])
        self.assertNotIn('idempotency_key',tools['session_details']['inputSchema'].get('required',[]))
        with self.assertRaises(Fault):
            self.call('sync_integration',{'integration_id':'fake','_acquired':{'synced':True}})

    def test_github_host_path_and_redirect_restrictions(self):
        from gantry.github_connector import validate_repository, NoRedirect
        for name in ('http://localhost/secret','a/../b','a/b?token=secret','a/b#x','../b'):
            with self.assertRaises(Fault):validate_repository(name)
        self.assertIsNone(NoRedirect().redirect_request(None,None,302,'',{},'http://localhost'))

    def test_pr_version_rechecked_even_without_checks_permission(self):
        from gantry.github_connector import fetch_repository
        from urllib.error import HTTPError
        from unittest.mock import MagicMock
        def response(body):
            item=MagicMock();item.__enter__.return_value=item
            item.read.return_value=json.dumps(body).encode();item.headers={}
            return item
        opener=MagicMock()
        opener.open.side_effect=[response({'id':1}), response([{'number':1,'title':'PR','pull_request':{},'updated_at':'now'}]),
            response({'head':{'sha':'a'*40},'base':{'sha':'b'*40}}),
            response([{'filename':'control.py','patch':'+gain=2'}]),
            HTTPError('https://api.github.com',403,'Forbidden',{},None),
            response({'head':{'sha':'c'*40},'base':{'sha':'b'*40}})]
        with patch('gantry.github_connector.build_opener',return_value=opener):
            item=fetch_repository({'repository':'example/robot'})['signals'][0]
        self.assertNotIn('files',item)
        self.assertTrue(any('PR moved' in s for s in item['capture_missing']))
        self.assertNotIn('checks',item)


    def test_expired_or_disallowed_identity_cannot_fetch_or_reuse_cached_sync(self):
        from contextlib import closing
        from gantry import indexed
        from gantry.model import canonical
        integration=self.integration('github')
        fake={'signals':[],'repository_id':1,'partial':False,'coverage':'fixture','requests':1}
        with patch('gantry.github_connector.fetch_repository',return_value=fake):
            self.call('sync_integration',{'integration_id':integration['id']},key='cached-sync')
        with closing(self.service.store.connect()) as con:
            s=self.service.store.state(con);principal=dict(s['principals']['admin'])
            principal['expires_at']=self.service.clock()-1
            indexed.put(con,'principals','admin',principal,canonical);con.commit()
        with patch('gantry.github_connector.fetch_repository') as acquire:
            for key in ('cached-sync','new-sync'):
                with self.assertRaises(Fault) as error:self.call('sync_integration',{'integration_id':integration['id']},key=key)
                self.assertEqual(error.exception.code,'unauthorized')
            acquire.assert_not_called()
        with closing(self.service.store.connect()) as con:
            principal.pop('expires_at');principal['allowed_commands']=['identity']
            indexed.put(con,'principals','admin',principal,canonical);con.commit()
        with patch('gantry.github_connector.fetch_repository') as acquire:
            with self.assertRaises(Fault):self.call('sync_integration',{'integration_id':integration['id']},key='cached-sync')
            acquire.assert_not_called()


class CloudTests(unittest.TestCase):
    def test_workspace_isolation_and_static_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); a=Service(root/'alpha'); ta=a.bootstrap()['token']; b=Service(root/'beta'); tb=b.bootstrap()['token']
            server=CloudServer(('127.0.0.1',0),root); thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
            try:
                url='http://127.0.0.1:'+str(server.server_port)
                alpha=Client(url+'/w/alpha',ta); beta=Client(url+'/w/beta',tb)
                alpha.call('save_project',{'name':'Private Alpha','description':'Private'})
                self.assertEqual(beta.call('product_overview')['projects'],[])
                for path in ('beta','missing','../alpha'):
                    with self.assertRaises(Fault):Client(url+'/w/'+path,ta).call('product_overview')
                from urllib.request import urlopen
                for path in ('/','/w/alpha/','/w/alpha/app.js','/w/alpha/ui.js','/w/alpha/views.js'):
                    with urlopen(url+path) as r:self.assertEqual(r.status,200)
                self.assertFalse((root/'missing').exists())
            finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
