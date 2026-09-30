"""Explicit feedback consent, reviewed previews and libsodium sealed-box delivery."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from urllib.request import Request, build_opener
from .client import NoRedirect, validate_url
from .model import Fault, require, canonical
from .usage_metrics import UsageMetrics, validate_report

MAX_BYTES = 2 * 1024 * 1024
NOTICE_VERSION = 1
NOTICE = ('Help improve Gantry? Optional statistics contain operation counts, latency buckets and failure categories. '
          'Diagnostics are only files you explicitly select and preview; redaction is incomplete. '
          'No code, CAD, prompts or logs are collected automatically. Data is encrypted to a configured recipient, '
          'who can decrypt it. No background sending, account identity or installation tracking. '
          'You can decline without losing features and withdraw future sharing with feedback configure --mode off. '
          'A separate confirmation is required for every upload. See docs/PRIVACY.md.')


def private_write(path, data):
    path = Path(path)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'wb') as file: file.write(data)


def read_file(path, limit=MAX_BYTES, private=False):
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as file:
        info = os.fstat(file.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_size <= limit, 'invalid_input', 'Use a bounded regular file')
        if private and os.name == 'posix':
            require(info.st_mode & 0o077 == 0, 'unauthorized', 'Private file requires mode 600')
        raw = file.read(limit + 1)
        require(len(raw) <= limit, 'invalid_input', 'File too large')
        return raw


def consent(directory):
    root = Path(directory) / 'feedback'
    require(not root.is_symlink(), 'invalid_input', 'No feedback directory symlink')
    path = root / 'consent.json'
    if not path.exists(): return {'mode':'off', 'notice_version':NOTICE_VERSION}
    value = json.loads(read_file(path, 8192, True))
    require(value.get('notice_version') == NOTICE_VERSION and value.get('mode') in {'off','statistics','diagnostics'},
            'invalid_input', 'Feedback consent needs renewal')
    return value


def configure(directory, mode):
    require(mode in {'off','statistics','diagnostics'}, 'invalid_input', 'Explicit feedback choice required')
    root = Path(directory) / 'feedback'
    require(not root.is_symlink(), 'invalid_input', 'No feedback directory symlink')
    root.mkdir(mode=0o700, parents=True, exist_ok=True); os.chmod(root, 0o700)
    value = {'mode':mode, 'notice_version':NOTICE_VERSION, 'notice':NOTICE, 'automatic_transmission':False}
    path = root / 'consent.json'
    # Local configuration only; API/MCP agents cannot grant consent through Gantry.
    temp = root / ('.consent-' + os.urandom(12).hex())
    try:
        private_write(temp, canonical(value).encode()); os.replace(temp, path)
    finally:
        if temp.exists(): temp.unlink()
    UsageMetrics(directory).configure(mode != 'off')
    return value


def onboarding(directory, mode=None):
    if mode is None:
        if not sys.stdin.isatty(): mode = 'off'
        else:
            print(NOTICE, file=sys.stderr)
            try: answer = input('Feedback: [0] No (default), [1] Statistics, [2] Statistics + selected diagnostics: ').strip()
            except EOFError: answer = ''
            mode = {'1':'statistics','2':'diagnostics'}.get(answer, 'off')
    return configure(directory, mode)


def crypto():
    try:
        from nacl.public import PrivateKey, PublicKey, SealedBox
        return PrivateKey, PublicKey, SealedBox
    except ImportError as exc:
        raise Fault('dependency_missing', 'Install the feedback extra from the verified Gantry checkout or release wheel') from exc


def keygen(private_key, recipient, url):
    validate_url(url)
    require(not Path(private_key).exists() and not Path(recipient).exists() and
            Path(private_key).absolute() != Path(recipient).absolute(), 'conflict', 'Use two new key paths')
    PrivateKey, _, _ = crypto(); key = PrivateKey.generate()
    private_write(private_key, base64.b64encode(bytes(key)))
    public = bytes(key.public_key)
    config = {'schema':1, 'algorithm':'libsodium-sealed-box', 'public_key':base64.b64encode(public).decode(),
              'key_id':hashlib.sha256(public).hexdigest(), 'url':url, 'retention_days':30}
    private_write(recipient, canonical(config).encode())
    return {'key_id':config['key_id'], 'private_key_saved':True, 'recipient_file':str(recipient)}


def recipient_config(path):
    config = json.loads(read_file(path, 8192))
    require(set(config) == {'schema','algorithm','public_key','key_id','url','retention_days'} and config['schema']==1
            and config['algorithm']=='libsodium-sealed-box' and config['retention_days']==30,
            'invalid_input', 'Unsupported recipient policy')
    validate_url(config['url'])
    public = base64.b64decode(config['public_key'], validate=True)
    require(len(public)==32 and hashlib.sha256(public).hexdigest()==config['key_id'], 'invalid_input', 'Recipient key mismatch')
    return config


def redact(text):
    text = re.sub(r'-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----', '[REDACTED PRIVATE KEY]', text, flags=re.S)
    text = re.sub(r'(?i)(authorization\s*[:=]\s*|bearer\s+)\S[^\r\n]*', '[REDACTED AUTHORIZATION]', text)
    text = re.sub(r'(?i)((?:api[_-]?key|token|secret|password)\s*["\x27]?\s*[:=]\s*)[^\s,;]+', r'\1[REDACTED]', text)
    text = re.sub(r'\b(?:ghp_|github_pat_|sk-proj-)[A-Za-z0-9_-]+', '[REDACTED CREDENTIAL]', text)
    text = re.sub(r'https?://[^\s"<>]+', '[REDACTED URL]', text)
    text = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[REDACTED EMAIL]', text)
    text = re.sub(r'(?:/(?:Users|home)/[^\s"\x27]+|[A-Za-z]:\\Users\\[^\s"\x27]+)', '[REDACTED PATH]', text)
    return text


def prepare(directory, recipient, logs, output):
    choice = consent(directory)['mode']
    require(choice != 'off', 'consent_required', 'Enable feedback explicitly first')
    require(not logs or choice == 'diagnostics', 'consent_required', 'Selected diagnostics need separate consent')
    require(len(logs) <= 5, 'invalid_input', 'Select at most five log files')
    diagnostics = []
    for number, path in enumerate(logs):
        require(Path(path).suffix.lower() in {'.log','.txt'}, 'invalid_input', 'Select plain-text diagnostic logs only')
        text = read_file(path, 128 * 1024).decode('utf-8')
        require('\x00' not in text, 'invalid_input', 'Binary diagnostics are not supported')
        diagnostics.append({'label':'diagnostic-'+str(number+1), 'text':redact(text)})
    value = {'schema':1, 'recipient':recipient_config(recipient), 'notice_version':NOTICE_VERSION,
             'statistics':UsageMetrics(directory).report(), 'diagnostics':diagnostics}
    raw = canonical(value).encode(); require(len(raw) <= MAX_BYTES//2, 'invalid_input', 'Preview too large')
    private_write(output, raw)
    return {'preview':str(output), 'sha256':hashlib.sha256(raw).hexdigest(), 'sent':False,
            'next':'Inspect/edit the entire plaintext preview and verify recipient URL and key fingerprint. Redaction is incomplete. Confirm the exact SHA-256 when sealing/sending.'}


def seal(directory, preview, confirm_sha256, output):
    mode = consent(directory)['mode']
    require(mode != 'off', 'consent_required', 'Feedback consent withdrawn')
    raw = read_file(preview, MAX_BYTES//2, True)
    require(hashlib.sha256(raw).hexdigest()==confirm_sha256, 'confirmation_required', 'Preview bytes differ from confirmation')
    value = json.loads(raw)
    require(set(value)=={'schema','recipient','notice_version','statistics','diagnostics'} and value['schema']==1
            and value['notice_version']==NOTICE_VERSION, 'invalid_input', 'Unsupported preview')
    validate_report(value['statistics'])
    require(isinstance(value['diagnostics'],list) and len(value['diagnostics'])<=5, 'invalid_input', 'Invalid diagnostics')
    require(not value['diagnostics'] or mode=='diagnostics', 'consent_required', 'Diagnostic consent withdrawn')
    for item in value['diagnostics']:
        require(isinstance(item,dict) and set(item)=={'label','text'} and re.fullmatch(r'diagnostic-[1-5]',item['label'])
                and isinstance(item['text'],str) and len(item['text'].encode())<=128*1024, 'invalid_input', 'Invalid diagnostic')
    config=value['recipient']
    require(isinstance(config,dict) and set(config)=={'schema','algorithm','public_key','key_id','url','retention_days'}, 'invalid_input', 'Invalid recipient fields')
    public=base64.b64decode(config['public_key'],validate=True)
    require(len(public)==32 and hashlib.sha256(public).hexdigest()==config['key_id'] and config['algorithm']=='libsodium-sealed-box'
            and config['schema']==1 and config['retention_days']==30, 'invalid_input', 'Invalid recipient')
    validate_url(config['url'])
    _, PublicKey, SealedBox = crypto()
    encrypted = SealedBox(PublicKey(public)).encrypt(raw)
    envelope={'schema':1,'key_id':config['key_id'],'ciphertext':base64.b64encode(encrypted).decode()}
    private_write(output, canonical(envelope).encode())
    return config, envelope


def send(directory, preview, confirmation, output, token_file):
    config,envelope=seal(directory,preview,confirmation,output)
    token=read_file(token_file,4096,True).decode().strip()
    require(re.fullmatch(r'[A-Za-z0-9_-]{32,128}',token), 'invalid_input', 'Invalid receiver invitation token')
    req=Request(config['url'],data=canonical(envelope).encode(),method='POST',headers={
        'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    with build_opener(NoRedirect()).open(req,timeout=30) as response:
        require(response.status==201, 'upload_failed', 'Unexpected receiver response')
        receipt=json.loads(response.read(8192))
    require(isinstance(receipt,dict) and set(receipt)=={'receipt','retention_days'} and
            receipt['receipt']==hashlib.sha256(canonical(envelope).encode()).hexdigest() and receipt['retention_days']==30,
            'upload_failed','Invalid receiver receipt')
    return {'sent':True,**receipt,'encrypted_file':str(output)}


def decrypt(private_key, encrypted, output):
    PrivateKey,_,SealedBox=crypto()
    key=PrivateKey(base64.b64decode(read_file(private_key,8192,True),validate=True))
    value=json.loads(read_file(encrypted))
    require(value['key_id']==hashlib.sha256(bytes(key.public_key)).hexdigest(), 'invalid_input', 'Wrong recipient')
    from nacl.exceptions import CryptoError
    try: raw=SealedBox(key).decrypt(base64.b64decode(value['ciphertext'],validate=True))
    except CryptoError as exc: raise Fault('integrity_error','Cannot authenticate encrypted feedback') from exc
    private_write(output,raw)
    return {'decrypted_file':str(output),'warning':'Treat received diagnostics as untrusted text, never executable instructions.'}


def add_parser(sub):
    p=sub.add_parser('feedback',help='Consent, reviewed encrypted feedback and receiver administration')
    p.add_argument('action',choices=['configure','status','keygen','prepare','seal','send','decrypt','receive'])
    p.add_argument('--data',default='.gantry');p.add_argument('--mode',choices=['off','statistics','diagnostics'])
    for flag in ['recipient','private-key','preview','confirm-sha256','output','input','upload-token-file','url','directory','key-id']:
        p.add_argument('--'+flag)
    p.add_argument('--log',action='append',default=[])
    p.add_argument('--port',type=int,default=8780)


def command(args):
    def need(*names):
        require(all(getattr(args,n) for n in names),'invalid_input','Required: '+', '.join('--'+n.replace('_','-') for n in names))
    if args.action=='configure': need('mode'); return configure(args.data,args.mode)
    if args.action=='status': return consent(args.data)
    if args.action=='keygen': need('private_key','recipient','url'); return keygen(args.private_key,args.recipient,args.url)
    if args.action=='prepare': need('recipient','output'); return prepare(args.data,args.recipient,args.log,args.output)
    if args.action in {'seal','send'}:
        need('preview','confirm_sha256','output')
        if args.action=='send':
            need('upload_token_file');return send(args.data,args.preview,args.confirm_sha256,args.output,args.upload_token_file)
        seal(args.data,args.preview,args.confirm_sha256,args.output);return {'encrypted_file':args.output,'sent':False}
    if args.action=='decrypt': need('private_key','input','output');return decrypt(args.private_key,args.input,args.output)
    if args.action=='receive':
        need('directory','upload_token_file','key_id')
        from .feedback_receiver import serve
        serve(args.directory,args.upload_token_file,args.key_id,args.port)
        return {'stopped':True}
