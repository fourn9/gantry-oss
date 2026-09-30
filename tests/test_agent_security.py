import contextlib
import io
import json
import os
import secrets
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from gantry.agent_connection import connection_config,PROFILES
from gantry.client import Client
from gantry.mcp import run,tool_list
from gantry.model import Fault
from gantry.service import Service,token_hash
from gantry.usage_metrics import UsageMetrics,summarize,validate_report
from test_interfaces import InterfaceTests


class SecurityTests(unittest.TestCase):
    def test_plaintext_remote_and_credentials_in_url_rejected(self):
        for url in ('http://example.com','https://user:secret@example.com','https://example.com/?token=x'):
            with self.subTest(url=url),self.assertRaises(Fault):Client(url,'secret')
        Client('https://example.com/w/a','secret')

    def test_configs_never_embed_token(self):
        with tempfile.TemporaryDirectory() as directory:
            token=Path(directory)/'agent.token';token.write_text('DO_NOT_PUBLISH');token.chmod(0o600)
            for client in ('claude','cursor','codex','generic'):
                config=connection_config(client,'http://127.0.0.1:8765',token,'developer',sys.executable)
                self.assertNotIn('DO_NOT_PUBLISH',config)
                self.assertIn('--require-agent',config)
                if client!='codex':self.assertEqual(json.loads(config)['mcpServers']['gantry']['type'],'stdio')
            if os.name=='posix':
                token.chmod(0o644)
                with self.assertRaises(Fault):connection_config('cursor','http://localhost:8765',token,'developer',sys.executable)

    def test_no_agent_profile_contains_adoption_or_admin_tools(self):
        for profile in PROFILES:
            exposed={t['name'] for t in tool_list(profile)}
            self.assertFalse(exposed & {'review_adoption','commit','configure_development','configure_review_team','export'})
        self.assertNotIn('checkpoint_change',{t['name'] for t in tool_list('read-only')})

    def test_dedicated_agent_check_rejects_admin(self):
        class Fake:
            def call(self,*args):return {'kind':'human','permissions':['admin']}
        with self.assertRaises(Fault):run(Fake(),require_agent=True)

    def test_telemetry_opt_in_aggregation_disable_and_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            service=Service(directory);token=service.bootstrap()['token'];m=UsageMetrics(directory)
            service.call(token,'identity');self.assertFalse(m.root.exists())
            m.configure(True)
            service.call(token,'identity')
            with self.assertRaises(Fault):service.call('private-secret-invalid','identity')
            report=m.report();raw=json.dumps(report)
            for forbidden in (token,directory,'private-secret-invalid','token_hash','actor_id'):
                self.assertNotIn(forbidden,raw)
            self.assertEqual(sum(x['count'] for x in report['metrics']),2)
            self.assertEqual(summarize([report])['reports'],1)
            report['code']='private code'
            with self.assertRaises(Fault):validate_report(report)
            m.configure(False);self.assertEqual(m.report()['metrics'],[])


class HttpSecurityTests(InterfaceTests):
    def test_loopback_dns_rebinding_host_denied(self):
        with self.assertRaises(HTTPError) as caught:
            urlopen(Request(self.url+'/health',headers={'Host':'attacker.example'}))
        self.assertEqual(caught.exception.code,403)

    def test_redirect_never_forwards_authorization(self):
        from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
        import threading
        received=[]
        class Redirect(BaseHTTPRequestHandler):
            def do_POST(self):
                self.send_response(307);self.send_header('Location',self.server.destination);self.end_headers()
            def do_GET(self):received.append(self.headers.get('Authorization'));self.send_response(200);self.end_headers()
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Redirect)
        server.destination='http://127.0.0.1:'+str(server.server_port)+'/leak'
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with self.assertRaises(Fault):Client(server.destination,'secret').call('identity')
            self.assertEqual(received,[])
        finally:server.shutdown();server.server_close();thread.join()

    def test_command_allowlist_expiration_and_mcp_agent_identity(self):
        token=secrets.token_urlsafe(32)
        proposal=self.client.call('propose',{'title':'Delegate fixture agent','changes':[{'id':'test-agent','type':'principal','data':{
            'kind':'agent','permissions':['read','record'],'token_hash':token_hash(token),
            'allowed_commands':['identity'],'expires_at':self.service.clock()+60000}}]})
        args={'proposal_id':proposal['id'],'version':1}
        self.client.call('submit',args);self.client.call('endorse',{**args,'reason':'fixture'})
        self.client.call('review_adoption',{**args,'reason':'fixture','verdict':'approve'});self.client.call('commit',args)
        client=Client(self.url,token)
        self.assertEqual(client.call('identity')['kind'],'agent')
        with self.assertRaises(Fault):client.call('state')
        messages=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25'}},
                  {'jsonrpc':'2.0','method':'notifications/initialized'},
                  {'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'identity','arguments':{'arguments':{}}}}]
        output=io.StringIO()
        from unittest.mock import patch
        with patch('sys.stdin',io.StringIO('\n'.join(map(json.dumps,messages))+'\n')),contextlib.redirect_stdout(output):
            run(client,'read-only',True)
        self.assertFalse(json.loads(output.getvalue().splitlines()[-1])['result']['isError'])
        clock=self.service.clock;self.service.clock=lambda:clock()+120000
        with self.assertRaises(Fault):client.call('identity')
