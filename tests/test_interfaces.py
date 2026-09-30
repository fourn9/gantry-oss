import base64
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import threading
import unittest

from gantry.backup import restore_backup
from gantry.client import Client
from gantry.model import Fault, digest
from gantry.server import Server
from gantry.service import Service
from gantry.mcp import tool_list


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = Service(self.temp.name)
        self.token = self.service.bootstrap()["token"]
        self.server = Server(("127.0.0.1", 0), self.service)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = "http://127.0.0.1:" + str(self.server.server_port)
        self.client = Client(self.url, self.token)

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.temp.cleanup()

    def test_http_cli_and_mcp_share_one_ledger(self):
        p = self.client.call("propose", {"title": "HTTP proposal", "changes": [{"id": "goal", "type": "goal", "data": {"text": "grip"}}]})
        args = {"proposal_id": p["id"], "version": 1, "reason": "reviewed"}
        self.client.call("submit", {"proposal_id": p["id"], "version": 1})
        env = {**os.environ, "GANTRY_TOKEN": self.token, "GANTRY_URL": self.url}
        proc = subprocess.run(["python3", "-m", "gantry", "call", "endorse"], input=json.dumps(args), env=env,
                              text=True, capture_output=True, timeout=10)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "review_adoption", "arguments": {
                "arguments": {**args, "verdict": "approve"}, "idempotency_key": "mcp-approve"}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "commit", "arguments": {
                "arguments": {"proposal_id": p["id"], "version": 1}, "idempotency_key": "mcp-commit"}}}]
        proc = subprocess.run(["python3", "-m", "gantry", "mcp"], input="\n".join(json.dumps(x) for x in messages) + "\n",
                              env=env, text=True, capture_output=True, timeout=10)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        outputs = [json.loads(line) for line in proc.stdout.splitlines()]
        self.assertEqual(outputs[-1]["error"]["code"], -32602, outputs)
        # Agents no longer receive human adoption tools, even with a human token.
        self.client.call("review_adoption", {**args, "verdict":"approve"})
        self.client.call("commit", {"proposal_id":p["id"], "version":1})
        self.assertIn("goal", self.client.call("design")["contents"])
        self.assertTrue(self.client.call("verify")["valid"])

    def test_backup_restores_credentials_events_and_blobs(self):
        a = self.client.call("capture_artifact", {"files": {"model.step": base64.b64encode(b"STEP fixture").decode()}})
        bundle = self.client.call("export")
        destination = Path(self.temp.name) / "restored"
        restore_backup(destination, bundle)
        restored = Service(destination)
        result = restored.call(self.token, "restore_artifact", {"revision_id": a["revision_id"]})
        self.assertEqual(base64.b64decode(result["files"]["model.step"]), b"STEP fixture")
        self.assertEqual(restored.call(self.token, "state"), self.client.call("state"))

    def test_http_rejects_missing_auth_and_record_bypass(self):
        with self.assertRaises(Fault) as caught: Client(self.url, "").call("state")
        self.assertEqual(caught.exception.code, "unauthorized")
        with self.assertRaises(Fault) as caught: self.client.call("record", {"type": "policy", "data": {}})
        self.assertEqual(caught.exception.code, "invalid_input")

    def test_typed_mcp_contracts_and_invalid_http_input(self):
        contracts = {tool["name"]: tool for tool in tool_list()}
        self.assertIn("changes", contracts["propose"]["inputSchema"]["properties"]["arguments"]["required"])
        self.assertIn("idempotency_key", contracts["commit"]["inputSchema"]["required"])
        for args in ({"dependencies": [1], "title": "x", "completion_condition": "y"},
                     {"title": "x", "completion_condition": "y", "unexpected": True}):
            with self.assertRaises(Fault) as caught: self.client.call("create_work", args)
            self.assertEqual(caught.exception.code, "invalid_input")
        self.assertIsNone(self.client.call("state")["head"])

    def test_focused_context_http_cli_mcp_equivalence(self):
        p = self.client.call('propose', {'title': 'Focus fixture', 'changes': [
            {'id': 'grip', 'type': 'subsystem', 'data': {'name': 'Grip'}}]})
        work = self.client.call('create_work', {'title': 'Inspect grip', 'completion_condition': 'Evidence',
                               'proposal_id': p['id'], 'design_id': p['candidate_id']})
        args = {'work_id': work['id'], 'view': 'focused', 'entry_ids': ['grip']}
        expected = self.client.call('context', args)
        env = {**os.environ, 'GANTRY_TOKEN': self.token, 'GANTRY_URL': self.url}
        cli = subprocess.run(['python3', '-m', 'gantry', 'call', 'context'],
                             input=json.dumps(args), env=env, text=True, capture_output=True, timeout=10)
        self.assertEqual(cli.returncode, 0, cli.stderr)
        self.assertEqual(json.loads(cli.stdout), expected)
        messages = [
            {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-11-25'}},
            {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
             'params': {'name': 'context', 'arguments': {'arguments': args}}},
        ]
        mcp = subprocess.run(['python3', '-m', 'gantry', 'mcp'],
                             input='\n'.join(json.dumps(item) for item in messages) + '\n',
                             env=env, text=True, capture_output=True, timeout=10)
        self.assertEqual(mcp.returncode, 0, mcp.stderr)
        result = json.loads(mcp.stdout.splitlines()[-1])['result']
        self.assertFalse(result['isError'])
        self.assertEqual(json.loads(result['content'][0]['text']), expected)


    def test_v011_state_is_equivalent_over_http_cli_mcp(self):
        artifact = self.client.call('capture_artifact', {'files': {'model.txt': 'aW5pdGlhbA=='}})
        session = self.client.call('connect_development', {'title':'late connection','snapshot':artifact['revision_id'],
            'capture':{'scope':'files','missing':['earlier operations']},'unverified':['physics'],
            'mode':'record','actors':['admin'],'write_scope':[],'recipes':{},'max_executions':0,
            'timeout_seconds':10,'max_parallel':1})
        args={'session_id':session['id']}; expected=self.client.call('development_state',args)
        env={**os.environ,'GANTRY_TOKEN':self.token,'GANTRY_URL':self.url}
        cli=subprocess.run(['python3','-m','gantry','call','development_state'],input=json.dumps(args),env=env,text=True,capture_output=True,timeout=10)
        self.assertEqual(cli.returncode,0,cli.stderr);self.assertEqual(json.loads(cli.stdout),expected)
        messages=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25'}},
            {'jsonrpc':'2.0','method':'notifications/initialized'},
            {'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'development_state','arguments':{'arguments':args}}}]
        mcp=subprocess.run(['python3','-m','gantry','mcp'],input='\n'.join(json.dumps(m) for m in messages)+'\n',env=env,text=True,capture_output=True,timeout=10)
        result=json.loads(mcp.stdout.splitlines()[-1])['result'];self.assertFalse(result['isError'])
        self.assertEqual(json.loads(result['content'][0]['text']),expected)
        tools={t['name']:t for t in tool_list()}
        for command in ('mentor_propose','start_execution','finish_execution','invalidate_submission'):
            self.assertIn('idempotency_key',tools[command]['inputSchema']['required'])

if __name__ == "__main__": unittest.main()
