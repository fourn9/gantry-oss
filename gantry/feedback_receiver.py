"""Single-threaded, bounded opaque feedback inbox. No decryption or public download."""
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import threading
import time
from .feedback import MAX_BYTES, read_file, private_write
from .model import canonical, require

RETENTION = 30 * 86400
CAPACITY = 100 * 1024 * 1024


class Receiver(HTTPServer):
    def __init__(self, address, directory, token_file, key_id):
        root=Path(directory)
        require(not root.is_symlink(),'invalid_input','Inbox must not be a symlink')
        root.mkdir(parents=True,exist_ok=True,mode=0o700);os.chmod(root,0o700)
        self.root=root;self.token=read_file(token_file,4096,True).decode().strip()
        require(re.fullmatch(r'[A-Za-z0-9_-]{32,128}',self.token),'invalid_input','Use a strong invitation token')
        require(re.fullmatch(r'[a-f0-9]{64}',key_id),'invalid_input','Pinned recipient fingerprint required')
        self.key_id=key_id;self.request_count=0;self.window=time.monotonic()
        self.storage_lock=threading.Lock();self.stop_cleanup=threading.Event()
        self.prune()
        super().__init__(address, Handler)
        self.cleaner=threading.Thread(target=self.cleanup_loop,daemon=True);self.cleaner.start()

    def prune(self):
        with self.storage_lock:
            now=time.time()
            for path in self.root.glob('*.json'):
                if path.is_symlink(): continue
                if now-path.stat().st_mtime >= RETENTION: path.unlink()

    def cleanup_loop(self):
        while not self.stop_cleanup.wait(60): self.prune()

    def server_close(self):
        self.stop_cleanup.set()
        super().server_close()
        self.cleaner.join(timeout=2)

    def handle_error(self, request, client_address):
        # Base HTTPServer would print peer addresses and tracebacks.
        pass

    def get_request(self):
        sock,address=super().get_request();sock.settimeout(5);return sock,address


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass  # No address, headers, query strings or payload logging.
    def reply(self,code,value):
        raw=canonical(value).encode();self.send_response(code)
        self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        self.reply(200 if self.path=='/health' else 404,{'service':'feedback-receiver'} if self.path=='/health' else {'error':'not_found'})
    def do_POST(self):
        try:
            if self.path!='/v1/feedback': self.reply(404,{'error':'not_found'});return
            now=time.monotonic()
            if now-self.server.window>=60:self.server.window=now;self.server.request_count=0
            self.server.request_count+=1
            if self.server.request_count>30:self.reply(429,{'error':'rate_limited'});return
            headers=self.headers
            if len(headers.get_all('Authorization',[]))!=1 or not secrets.compare_digest(headers.get('Authorization',''),'Bearer '+self.server.token):
                self.reply(401,{'error':'unauthorized'});return
            if headers.get('Origin') or headers.get('Transfer-Encoding') or len(headers.get_all('Content-Length',[]))!=1:
                self.reply(400,{'error':'invalid_request'});return
            length=int(headers['Content-Length'])
            if not 1<=length<=MAX_BYTES or headers.get('Content-Type')!='application/json':
                self.reply(413,{'error':'invalid_size_or_type'});return
            raw=self.rfile.read(length)
            if len(raw)!=length: self.reply(400,{'error':'incomplete_body'});return
            data=json.loads(raw)
            require(isinstance(data,dict) and set(data)=={'schema','key_id','ciphertext'} and data['schema']==1
                    and data['key_id']==self.server.key_id,'invalid_input','Invalid envelope')
            cipher=base64.b64decode(data['ciphertext'],validate=True)
            require(48<=len(cipher)<=MAX_BYTES,'invalid_input','Invalid ciphertext')
            # Deliberately opaque: encryption authenticity is verified offline by the key holder.
            raw=canonical(data).encode();receipt=hashlib.sha256(raw).hexdigest();self.server.prune()
            with self.server.storage_lock:
                path=self.server.root/(receipt+'.json')
                if path.exists():
                    require(not path.is_symlink(),'invalid_input','Invalid inbox entry')
                else:
                    used=sum(p.stat().st_size for p in self.server.root.glob('*.json') if not p.is_symlink())
                    if used+len(raw)>CAPACITY:self.reply(507,{'error':'inbox_full'});return
                    private_write(path,raw)
            self.reply(201,{'receipt':receipt,'retention_days':30})
        except Exception:
            self.reply(400,{'error':'invalid_request'})


def serve(directory,token_file,key_id,port):
    server=Receiver(('127.0.0.1',port),directory,token_file,key_id)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
