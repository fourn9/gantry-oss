"""Local owner onboarding and scoped project operations; no provider calls."""
import base64
import contextlib
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import time
import tomllib

from .model import Fault, canonical, digest, require
from .service import Service, token_hash
from .connection_policy import clean_bytes, covered, safe_path
from .project_files import inventory, read_file, write_file
from .project_sandbox import backend, runtime_roots, execute


def private_dir(path):
    path = Path(path)
    require(not path.is_symlink(), 'scope_denied', 'Private directory must not be a symlink')
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    require(path.is_dir() and path.stat().st_uid == os.getuid(), 'scope_denied', 'Private directory must be owned by this user')
    os.chmod(path, 0o700)
    return path


def save(path, value):
    path = Path(path); private_dir(path.parent)
    fd, tmp = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f: f.write(canonical(value)); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def load(path):
    path = Path(path)
    require(not path.is_symlink() and path.stat().st_uid == os.getuid() and path.stat().st_mode & 0o077 == 0,
            'unauthorized', 'Private control file must be owner-only')
    return json.loads(path.read_text())


@contextmanager
def locked(path):
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    except BlockingIOError as exc:
        raise Fault('conflict', 'Another connection operation is active') from exc
    finally: os.close(fd)


class LocalClient:
    def __init__(self, service, token): self.service, self.token = service, token
    def call(self, name, args=None, key=None):
        return self.service.call(self.token, name, args or {}, key or secrets.token_hex(16))


def owner_client(meta):
    token_file = meta/'admin.token'
    service = Service(meta)
    with contextlib.closing(service.store.connect()) as con:
        initialized = con.execute('SELECT COUNT(*) FROM events').fetchone()[0] > 0
    if not token_file.exists():
        require(not initialized, 'unauthorized', 'Initialized ledger has no owner credential; restore it from your private backup')
        with token_file.open('x') as f:
            os.chmod(token_file, 0o600); f.write(secrets.token_urlsafe(32)+'\n'); f.flush(); os.fsync(f.fileno())
    require(not token_file.is_symlink() and token_file.stat().st_mode & 0o077 == 0,
            'unauthorized', 'Owner token file must be private')
    token = token_file.read_text().strip()
    if not initialized:
        service.bootstrap(_token=token)
        from .feedback import onboarding
        onboarding(meta, 'off')
    return LocalClient(service, token)


def discover(root, mode='work-capable', paths=None, commands=None, client='generic', ttl=3600, delegation=None, write_paths=None):
    root = Path(root).resolve()
    require(root.is_dir(), 'invalid_input', 'Project directory required')
    require(type(ttl) is int and 60 <= ttl <= 8*3600, 'invalid_input', 'Expiry must be 60–28800 seconds')
    if paths:
        for path in paths: safe_path(path, True)
    payload, hashes, omitted = inventory(root, paths)
    detected = {'git': (root/'.git').exists(), 'cad_files': sum(Path(p).suffix.lower() in
        {'.step', '.stp', '.fcstd', '.sldprt', '.sldasm', '.f3d', '.stl'} for p in hashes),
        'python': any(p.endswith('.py') for p in hashes),
        'mujoco_models': any(p.endswith('.xml') for p in hashes),
        'test_directory': any(p.startswith('tests/') for p in hashes)}
    chosen = {}
    if mode == 'work-capable':
        if commands is not None: chosen = commands
        elif detected['test_directory'] and detected['python']:
            chosen = {'test': {'argv': [str(Path(sys.executable).resolve()), '-B', '-m', 'unittest', 'discover', '-s', 'tests'], 'timeout_seconds': 60}}
    delegation = delegation or {'goal': 'Continue the existing project within the saved scope',
        'done': ['Save an unadopted candidate with evidence and remaining questions for review'],
        'constraints': ['Do not change existing requirements or operate hardware'],
        'hold': ['Stop for owner-only decisions or when completion cannot be assessed'],
        'max_reviews': 3, 'max_tests': 10, 'max_branches': 3, 'mentor': 'client'}
    plan = {'project': root.name, 'root': str(root), 'mode': mode, 'paths': sorted(paths or hashes),
        'write_paths': sorted(write_paths if write_paths is not None else (paths or hashes)) if mode == 'work-capable' else [],
        'commands': chosen, 'expires_at': int(time.time()*1000)+ttl*1000, 'files': hashes,
        'missing': [x['reason']+':'+x['path'] for x in omitted] + ['unsaved edits', 'history before connection'],
        'detected': detected, 'client': client, 'sandbox': backend(), 'runtime_roots': runtime_roots(), 'delegation': delegation}
    from .connection_policy import validate_plan
    validate_plan(plan)
    return plan, payload


def preview(plan):
    return {'project': plan['root'], 'agent': 'New dedicated, revocable project identity',
        'mode': plan['mode'], 'read_paths': plan['paths'], 'write_paths': plan['write_paths'], 'commands': plan['commands'],
        'delegation': plan['delegation'],
        'expires_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(plan['expires_at']/1000)),
        'denied': ['test-command network', 'workspace deletion', 'hardware', 'secrets', 'scope changes', 'formal integration/adoption'],
        'inference': ('Submitted review context is sent to the official Codex CLI under your ChatGPT login; provider limits apply'
                      if plan['delegation']['mentor'] == 'codex-subscription' else
                      'No automatic model call; your connected agent may read approved data under its own provider settings'),
        'capture': {'files': len(plan['files']), 'omissions': plan['missing']},
        'sandbox': plan['sandbox'], 'trusted_read_only_runtime': plan['runtime_roots'],
        'client': plan['client'], 'client_changes': 'Add only Gantry MCP entry; leave agent permissions unchanged',
        'feedback': 'Off. No project data or usage statistics sent to Gantry maintainers.',
        'approval_hash': digest(plan)}


def install_config(root, meta, client):
    # Do not import a repository-controlled gantry/ package or PYTHONPATH entry.
    args = ['-I', '-m', 'gantry', 'project-mcp', '--root', str(root)]
    entry = {'command': sys.executable, 'args': args}
    if client == 'generic':
        out = meta/'mcp.json'; save(out, {'mcpServers': {'gantry_project': entry}}); return str(out)
    if client == 'codex':
        directory = root/'.codex'
        require(not directory.is_symlink(), 'scope_denied', 'Client config directory cannot be a symlink')
        directory.mkdir(exist_ok=True)
        target = directory/'config.toml'
        require(not target.is_symlink() and (not target.exists() or target.stat().st_nlink == 1), 'scope_denied', 'Client config cannot be linked')
        raw = target.read_text() if target.exists() else ''
        parsed = tomllib.loads(raw)
        old = parsed.get('mcp_servers', {}).get('gantry_project')
        require(old is None or old == entry, 'conflict', 'Existing gantry_project entry differs; no client settings overwritten')
        if old is None:
            raw += '\n[mcp_servers.gantry_project]\ncommand = '+json.dumps(entry['command'])+'\nargs = '+json.dumps(args)+'\n'
            with target.open('w') as f: os.chmod(target, 0o600); f.write(raw)
        return str(target)
    target = root/('.mcp.json' if client == 'claude' else '.cursor/mcp.json')
    require(not target.parent.is_symlink() and not target.is_symlink() and (not target.exists() or target.stat().st_nlink == 1),
            'scope_denied', 'Client config cannot be linked')
    target.parent.mkdir(exist_ok=True)
    config = json.loads(target.read_text()) if target.exists() else {}
    require(isinstance(config, dict) and isinstance(config.get('mcpServers', {}), dict), 'invalid_input', 'Invalid existing client config')
    old = config.setdefault('mcpServers', {}).get('gantry_project')
    require(old is None or old == entry, 'conflict', 'Existing gantry_project differs; no client settings overwritten')
    config['mcpServers']['gantry_project'] = entry
    # Client settings can contain other credentials; do not copy them into journals or output.
    with target.open('w') as f: os.chmod(target, 0o600); json.dump(config, f, indent=2)
    return str(target)


def connect(root, *, mode='work-capable', paths=None, commands=None, client='generic', ttl=3600,
            prepare=False, approval=None, confirm=None, delegation=None, write_paths=None):
    root = Path(root).resolve(); meta = private_dir(root/'.gantry')
    with locked(meta/'connect.lock'):
        # Also protect projects initialized as Git repositories after connection.
        # A parent repository's info/exclude alone would not cover that case.
        try: ignored = read_file(meta, '.gitignore')
        except FileNotFoundError: ignored = None
        if ignored != b'*\n':
            write_file(meta, '.gitignore', b'*\n',
                       hashlib.sha256(ignored).hexdigest() if ignored is not None else 'absent')
        receipt_path = meta/'connection.json'; pending_path = meta/'connect-pending.json'
        if receipt_path.exists():
            project = Project(root); context = project.context()
            require(context['connection']['plan']['mode'] == mode and context['connection']['plan']['client'] == client
                and (not paths or sorted(paths) == context['connection']['plan']['paths'])
                and (commands is None or commands == context['connection']['plan']['commands']),
                'reauthorization_required', 'Disconnect and approve a new plan to change scope')
            require(delegation is None or delegation == context['connection']['plan']['delegation'],
                    'reauthorization_required', 'Delegation changed; reconnect with new approval')
            require(write_paths is None or sorted(write_paths) == context['connection']['plan']['write_paths'],
                    'reauthorization_required', 'Write paths changed; reconnect with new approval')
            config = install_config(root, meta, client)
            return {'status': 'connected', 'resumed': True, 'session_id': context['connection']['session_id'], 'config': config}
        if pending_path.exists():
            pending = load(pending_path); plan = pending['plan']
            require(plan['root'] == str(root) and plan['mode'] == mode and plan['client'] == client,
                    'conflict', 'A different plan is pending; inspect or cancel it first')
            require(not paths or sorted(paths) == plan['paths'], 'conflict', 'Pending paths differ')
            require(commands is None or commands == plan['commands'], 'conflict', 'Pending commands differ')
            require(delegation is None or delegation == plan['delegation'], 'conflict', 'Pending delegation differs')
            require(write_paths is None or sorted(write_paths) == plan['write_paths'], 'conflict', 'Pending write paths differ')
            payload, hashes, _ = inventory(root, plan['paths'])
            require(hashes == plan['files'], 'stale_basis', 'Workspace changed; cancel the pending connection and prepare again')
        else:
            plan, payload = discover(root, mode, paths, commands, client, ttl, delegation, write_paths)
            pending = {'plan': plan, 'request_key': secrets.token_hex(16)}
            save(pending_path, pending)
        shown = preview(plan)
        if prepare: return {'status': 'awaiting_owner', 'preview': shown, 'plan_file': str(pending_path), 'token_issued': False}
        require(plan['expires_at'] > int(time.time()*1000), 'unauthorized', 'Preview expired; cancel and prepare again')
        accepted = approval == digest(plan) if approval is not None else bool(confirm and confirm(shown))
        require(accepted, 'approval_required', 'Owner must confirm this exact plan; no capability activated')
        # Do not run repository code to discover or activate a connection.
        exclude = root/'.git/info/exclude'
        if (root/'.git').is_dir() and not (root/'.git').is_symlink():
            require(not exclude.is_symlink() and not exclude.parent.is_symlink(), 'scope_denied', 'Unsafe Git exclude path')
            exclude.parent.mkdir(exist_ok=True)
            old = exclude.read_text() if exclude.exists() else ''
            if '/.gantry/' not in old.splitlines():
                with exclude.open('a') as f: f.write('\n/.gantry/\n')
        owner = owner_client(meta)
        token_path = meta/'project-agent.token'
        if not token_path.exists():
            with token_path.open('x') as f: os.chmod(token_path, 0o600); f.write(secrets.token_urlsafe(32)+'\n')
        require(not token_path.is_symlink() and token_path.stat().st_mode & 0o077 == 0, 'unauthorized', 'Agent credential must be private')
        token = token_path.read_text().strip()
        mentor_path = meta/'project-mentor.token'
        if not mentor_path.exists():
            with mentor_path.open('x') as f: os.chmod(mentor_path, 0o600); f.write(secrets.token_urlsafe(32)+'\n')
        require(not mentor_path.is_symlink() and mentor_path.stat().st_mode & 0o077 == 0, 'unauthorized', 'Reviewer credential must be private')
        request = owner.call('request_connection', {'plan': plan, 'token_hash': token_hash(token),
            'mentor_token_hash': token_hash(mentor_path.read_text().strip())}, pending['request_key']+':request')
        pending['connection_id'] = request['id']; save(pending_path, pending)
        # All approval events, participant registration and the initial snapshot commit together.
        result = owner.call('approve_connection', {'connection_id': request['id'], 'plan_hash': digest(plan), 'files': payload},
                            pending['request_key']+':approve')
        save(receipt_path, {'connection_id': result['id'], 'root': str(root), 'plan_hash': digest(plan)})
        try: config = install_config(root, meta, client)
        except (Fault, OSError, ValueError):
            return {'status': 'connected_client_setup_pending', 'connection_id': result['id'],
                    'recovery': 'Fix the client config conflict and rerun the same connect command; no new approval is needed'}
        return {'status': 'connected', 'connection_id': result['id'], 'session_id': result['session_id'],
                'state_id': result['state_id'], 'mode': mode, 'config': config,
                'agent_token_embedded': False, 'client_permission_settings_changed': False,
                'next': 'Enable/reload Gantry once in the client, or use gantry project immediately'}


class Project:
    def __init__(self, root):
        self.root = Path(root).resolve(); self.meta = private_dir(self.root/'.gantry')
        self.receipt = load(self.meta/'connection.json')
        require(self.receipt['root'] == str(self.root), 'scope_denied', 'Project moved; approve a new connection')
        token_file = self.meta/'project-agent.token'
        require(not token_file.is_symlink() and token_file.stat().st_mode & 0o077 == 0,
                'unauthorized', 'Use the private agent credential')
        self.client = LocalClient(Service(self.meta), token_file.read_text().strip())

    def context(self):
        result = self.client.call('connection_context'); obj = result['connection']
        require(obj['id'] == self.receipt['connection_id'] and obj['plan_hash'] == self.receipt['plan_hash']
                and obj['plan']['root'] == str(self.root), 'scope_denied', 'Connection binding changed')
        return result

    def operate(self, action, arguments=None, key=None):
        a = arguments or {}; key = key or secrets.token_hex(16)
        if action == 'status': return self.context()
        clean_bytes(canonical(a).encode())
        branch_lock = hashlib.sha256(str(a.get('branch', 'main')).encode()).hexdigest()
        with locked(self.meta/('project-'+branch_lock+'.lock')):
            context = self.context(); plan = context['connection']['plan']
            if action in {'submit', 'review', 'respond', 'assumption'}:
                result = self.client.call('connection_'+action, a, key)
                if action == 'submit' and plan['delegation']['mentor'] == 'codex-subscription':
                    from .project_mentor import review
                    return {'submission': result, 'review': review(self, result['id'])}
                return result
            if action == 'branch':
                result = self.client.call('connection_branch', a, key)
                directory = private_dir(self.meta/'branches')/a['name']
                private_dir(directory); target = directory/'workspace'
                if target.exists():
                    _, hashes, _ = inventory(target, plan['paths'])
                    require(hashes == {p: v['hash'] for p, v in result['artifact']['manifest']['files'].items()},
                            'conflict', 'Branch restore differs; existing edits preserved')
                else:
                    with tempfile.TemporaryDirectory(prefix='.restore-', dir=directory) as staging:
                        bundle = Path(staging)/'workspace'; bundle.mkdir()
                        for name, content in result['artifact']['files'].items():
                            require(covered(name, plan['paths']), 'scope_denied', 'Branch file outside scope')
                            dest = bundle/name; dest.parent.mkdir(parents=True, exist_ok=True)
                            dest.write_bytes(clean_bytes(base64.b64decode(content)))
                        bundle.rename(target)
                return {'branch': result['branch'], 'name': a['name'], 'workspace': str(target),
                        'formal_adoption': False}
            branch = a.get('branch', 'main')
            workroot = self.root
            if branch != 'main':
                require(branch in context['connection']['branches'], 'not_found', 'Unknown candidate branch')
                workroot = self.meta/'branches'/branch/'workspace'
                require(workroot.is_dir() and not workroot.is_symlink() and not workroot.parent.is_symlink()
                        and not workroot.parent.parent.is_symlink(), 'scope_denied', 'Unsafe branch workspace')
            if action == 'checkpoint':
                files, hashes, _ = inventory(workroot, plan['paths'])
                return self.client.call('connection_checkpoint', {'expected_state': a['expected_state'],
                    'files': files, 'summary': a['summary'], 'rationale': a['rationale'], 'unfinished': a.get('unfinished', []),
                    'branch': branch}, key)
            require(action in {'read', 'edit', 'test'}, 'reauthorization_required', 'Operation is not delegated')
            path = a.get('path')
            if action in {'read', 'edit'}:
                require(covered(path, plan['paths']), 'reauthorization_required', 'Path not approved')
            journal_dir = private_dir(self.meta/'operations')
            journal_path = journal_dir/(hashlib.sha256(key.encode()).hexdigest()+'.json')
            fingerprint = digest({'action': action, 'args': a})
            old = load(journal_path) if journal_path.exists() else None
            if old:
                require(old['fingerprint'] == fingerprint, 'idempotency_mismatch', 'Request ID reused with different operation')
                if old['phase'] == 'completed':
                    result = dict(old['result'])
                    if action == 'read':
                        raw = read_file(workroot, path)
                        require(hashlib.sha256(raw).hexdigest() == result['sha256'], 'stale_basis', 'File changed since this read request')
                        result['base64'] = base64.b64encode(raw).decode()
                    return result
                # An uncertain process must not execute twice. Reads/edits also require explicit reconciliation.
                raise Fault('operation_uncertain', 'Prior operation interrupted; inspect journal and current files before using a new request ID')
            command = plan['commands'].get(a.get('command')) if action == 'test' else None
            if action == 'test':
                require(command is not None, 'reauthorization_required', 'Command not approved')
                files, hashes, _ = inventory(workroot, plan['paths']); input_hash = digest(hashes)
                require(all(hashes.get(p) == h for p, h in plan['files'].items() if not covered(p, plan['write_paths'])),
                        'stale_basis', 'A read-only dependency or acceptance test changed; reapprove the baseline')
            elif action == 'edit': input_hash = a['expected_hash']
            else: input_hash = digest({'path': path})
            auth = {'operation': action, 'input_hash': input_hash, 'branch': branch}
            if a.get('from_review'): auth['from_review'] = a['from_review']
            if path: auth['path'] = path
            if command: auth.update(command=a['command'], command_hash=digest(command))
            authorized = self.client.call('authorize_connection_operation', auth, key+':start')
            row = {'phase': 'started', 'fingerprint': fingerprint, 'operation_id': authorized['id']}
            save(journal_path, row)
            try:
                if action == 'read':
                    raw = read_file(workroot, path)
                    result = {'path': path, 'sha256': hashlib.sha256(raw).hexdigest(), 'base64': base64.b64encode(raw).decode()}
                elif action == 'edit':
                    raw = a['content'].encode(); self.context()
                    write_file(workroot, path, raw, a['expected_hash'])
                    result = {'path': path, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
                else:
                    with tempfile.TemporaryDirectory(prefix='gantry-test-') as directory:
                        scratch = Path(directory).resolve()
                        for name, content in files.items():
                            dest = scratch/name; dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(base64.b64decode(content))
                        result = execute(command, scratch, plan['runtime_roots'], plan['sandbox'], self.context)
                    try: clean_bytes(result['output'].encode())
                    except Fault: result['output'] = '[Output withheld: possible credential]'
                summary = 'Scoped '+action+' completed'
                receipt = self.client.call('complete_connection_operation', {'operation_id': authorized['id'],
                    'status': 'failed' if action == 'test' and result['exit_code'] != 0 else 'completed',
                    'summary': summary, 'output_hash': digest(result),
                    'details': {k: v for k, v in result.items() if k != 'base64'}}, key+':finish')
                result['receipt'] = receipt
                # Read contents are not duplicated in journals; Core checkpoints retain approved bytes.
                saved_result = {k: v for k, v in result.items() if k != 'base64'}
                save(journal_path, {**row, 'phase': 'completed', 'result': saved_result})
                return result
            except Exception as exc:
                # Do not persist exception bodies or args: these can contain paths/content/credentials.
                save(journal_path, {**row, 'phase': 'interrupted', 'error_class': type(exc).__name__})
                raise


def disconnect(root):
    root = Path(root).resolve(); meta = private_dir(root/'.gantry')
    with locked(meta/'connect.lock'):
        receipt = meta/'connection.json'
        if receipt.exists():
            data = load(receipt)
            result = owner_client(meta).call('disconnect_connection', {'connection_id': data['connection_id']}, data['connection_id']+':revoke')
            archive = private_dir(meta/'disconnected')
            save(archive/(data['connection_id']+'.json'), data)
            receipt.unlink()
        else:
            pending = load(meta/'connect-pending.json') if (meta/'connect-pending.json').exists() else {}
            if pending.get('connection_id'):
                result = owner_client(meta).call('disconnect_connection', {'connection_id': pending['connection_id']},
                                                pending['connection_id']+':revoke')
            else: result = {'status': 'cancelled_pending'}
        # Ledger history remains; no token is retained in recovery files.
        for name in ('connect-pending.json', 'project-agent.token', 'project-mentor.token'):
            p = meta/name
            if p.exists(): p.unlink()
        return {'status': result['status'], 'active': False, 'history_preserved': True}
