import http.client
import json
import secrets
import tempfile
import threading
import unittest
from pathlib import Path
from gantry.server import Server
from gantry.service import Service
from gantry.feedback_receiver import Receiver


class HttpMaintenanceTests(unittest.TestCase):
    def test_api_rejects_encodings_before_dispatch_and_hides_parse_details(self):
        with tempfile.TemporaryDirectory() as root:
            service = Service(root)
            token = service.bootstrap()['token']
            server = Server(('127.0.0.1', 0), service)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                for encoding in ['br', 'gzip', 'identity, br']:
                    status, body = self.post(server, '/v1/commands/identity', token, b'{}', encoding)
                    self.assertEqual(status, 400, body)
                self.assertEqual(self.post(server, '/v1/commands/identity', token, b'{}')[0], 200)
                status, body = self.post(server, '/v1/commands/identity', token, b'{')
                self.assertEqual(status, 400)
                self.assertEqual(body['error']['message'], 'Invalid request')
            finally:
                server.shutdown(); server.server_close(); thread.join()

    def test_feedback_rejects_encoded_envelope_without_storing_it(self):
        with tempfile.TemporaryDirectory() as root:
            token = secrets.token_urlsafe(32)
            token_file = Path(root) / 'invite'
            token_file.write_text(token); token_file.chmod(0o600)
            inbox = Path(root) / 'inbox'
            server = Receiver(('127.0.0.1', 0), inbox, token_file, 'a' * 64)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            try:
                envelope = json.dumps({'schema': 1, 'key_id': 'a' * 64,
                                       'ciphertext': 'A' * 64}).encode()
                status, _ = self.post(server, '/v1/feedback', token, envelope, 'br')
                self.assertEqual(status, 400)
                self.assertEqual(list(inbox.glob('*.json')), [])
                self.assertEqual(self.post(server, '/v1/feedback', token, envelope)[0], 201)
            finally:
                server.shutdown(); server.server_close(); thread.join()

    def post(self, server, path, token, body, encoding=None):
        conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
        headers = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}
        if encoding is not None: headers['Content-Encoding'] = encoding
        try:
            conn.request('POST', path, body=body, headers=headers)
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()
