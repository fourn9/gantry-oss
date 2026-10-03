"""Customer-owned persistent Bot runtime. No model is selected implicitly.

The process supervisor (launchd/systemd/container) keeps this worker alive. Core's
submission queue survives its absence; uncertain work requires explicit recovery.
"""
import fcntl
import json
import os
import signal
import subprocess
import threading
from pathlib import Path

from .client import Client
from .contracts import validate
from .model import Fault, require, uid, digest, canonical
from .monthly_codex import infer_monthly
from .mentor_daemon import process_job
from .runner import persist, process_env, stop_process


def environment_manifest(config):
    """Commit public local configuration, not credentials, in the runtime declaration."""
    return {'name': config['name'], 'backend': config['backend'], 'tools': config.get('tools', []),
            'definition': digest({k: config.get(k) for k in
                ('backend', 'command', 'executable_hash', 'cad_python', 'verification', 'environment_definition')})}


def infer_command(config, context, schema, directory):
    argv = config['command']
    require(isinstance(argv, list) and argv and all(isinstance(x, str) and x for x in argv),
            'invalid_input', 'Explicit customer inference argv required')
    executable = Path(argv[0])
    require(executable.is_absolute() and executable.is_file() and not executable.is_symlink(),
            'invalid_input', 'Use an absolute regular inference executable')
    import hashlib
    require(hashlib.sha256(executable.read_bytes()).hexdigest() == config['executable_hash'],
            'stale_basis', 'Inference executable changed; approve a new environment')
    root = Path(directory); root.mkdir(parents=True, exist_ok=True, mode=0o700)
    marker = root / 'inference.json'
    if marker.exists():
        saved = json.loads(marker.read_text())
        require(saved['context'] == context and saved['schema'] == schema, 'idempotency_mismatch', 'Inference input changed')
        require(saved['phase'] == 'completed', 'outcome_unknown', 'Prior inference outcome unknown; explicitly recover')
        return saved['receipt']
    request = canonical({'context': context, 'schema': schema})
    require(len(request.encode()) <= 750000, 'context_limit', 'Narrow the submitted change')
    persist(marker, {'phase': 'started', 'context': context, 'schema': schema})
    # A deliberately installed customer program; this is NOT an OS sandbox.
    # No host credentials or environment are passed. The bridge owns its model login.
    with open(root/'answer.json', 'w') as output, open(root/'stderr.log', 'w') as errors:
        proc = subprocess.Popen(argv, cwd=root, env=process_env({}), stdin=subprocess.PIPE,
            stdout=output, stderr=errors, text=True, start_new_session=True)
        persist(marker, {'phase': 'started', 'context': context, 'schema': schema, 'pid': proc.pid})
        try: proc.communicate(request, timeout=300)
        except subprocess.TimeoutExpired:
            stop_process(proc); raise Fault('provider_timeout', 'Customer inference timed out; inspect the saved receipt')
    require(proc.returncode == 0, 'provider_failed', 'Customer inference failed; inspect private stderr')
    require((root/'answer.json').stat().st_size <= 1024*1024, 'context_limit', 'Inference output exceeds 1 MiB')
    output = json.loads((root/'answer.json').read_text()); validate(output, schema)
    receipt = {'output': output, 'provider': {'kind': 'customer_command', 'executable_hash': config['executable_hash']}}
    persist(marker, {'phase': 'completed', 'context': context, 'schema': schema, 'receipt': receipt})
    return receipt


class BotWorker:
    def __init__(self, client, config, journal, infer_fn=None):
        self.client, self.config = client, config
        self.bot_id = config['bot_id']
        self.root = Path(journal) / digest(self.bot_id)
        require(not self.root.is_symlink(), 'scope_denied', 'Runtime root must not be a symlink')
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        self.runtime = None; self.stop = threading.Event(); self.lost = threading.Event(); self.lock = None
        # The override exists for deterministic acceptance tests, not exposed in CLI.
        self.infer = infer_fn
        if self.infer is None:
            require(config.get('backend') in {'external_agent', 'codex_subscription'}, 'invalid_input', 'Choose a customer inference backend')
            if config['backend'] == 'codex_subscription': self.infer = infer_monthly
            else:
                require(config.get('command') and config.get('executable_hash'), 'invalid_input', 'Install/configure a customer JSON inference bridge first')
                self.infer = lambda ctx, schema, directory: infer_command(config, ctx, schema, directory)

    def __enter__(self):
        self.lock = open(self.root/'runtime.lock', 'a')
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            view = self.client.call('get_persistent_bot', {'bot_id': self.bot_id})
            rt = view['runtime']; expected = digest(environment_manifest(self.config))
            require(rt and rt['environment_hash'] == expected, 'stale_basis', 'Owner must approve this exact environment manifest')
            self.runtime = self.client.call('start_bot_runtime', {'bot_id': self.bot_id, 'version': rt['version'],
                'instance_id': uid('worker'), 'environment_hash': expected})
            persist(self.root/'runtime.json', self.runtime)
            self.thread = threading.Thread(target=self._heartbeat, daemon=True); self.thread.start()
            return self
        except BaseException:
            self.lock.close(); self.lock = None; raise

    def _heartbeat(self):
        while not self.stop.wait(15):
            try: self.client.call('heartbeat_bot_runtime', {'bot_id': self.bot_id, 'fence': self.runtime['fence']})
            except Exception:
                # Do not begin more work after communication/authority loss. Core
                # also rejects stale fences before edits, verification and return.
                self.lost.set(); return

    def tick(self):
        require(self.runtime and not self.lost.is_set(), 'runtime_offline', 'Reconnect the stopped runtime first')
        self.client.call('heartbeat_bot_runtime', {'bot_id': self.bot_id, 'fence': self.runtime['fence']})
        results = []; after = None
        while True:
            page = self.client.call('bot_inbox', {'bot_id': self.bot_id, **({'after': after} if after else {})})
            for job in page['jobs']:
                if job['status'] != 'pending':
                    results.append({'job_id': job['id'], 'status': 'held', 'reason': 'explicit_recovery_required'})
                    continue
                require(not self.lost.is_set(), 'runtime_offline', 'Runtime heartbeat lost')
                try:
                    result = process_job(self.client, job['id'], self.root/'jobs', self.infer,
                        self.config.get('cad_python'), self.config.get('verification'), self.runtime['fence'])
                except (Fault, OSError, ValueError) as exc:
                    result = {'job_id': job['id'], 'status': 'held',
                              'reason': exc.code if isinstance(exc, Fault) else type(exc).__name__}
                results.append(result)
            after = page['next_cursor']
            if not after: break
        persist(self.root/'last-tick.json', {'bot_id': self.bot_id, 'results': results})
        return results

    def recover(self, job_id, reason, retry_inference=False, collect_interrupted_verification=False):
        from .mentor_recovery import recover_job
        require(self.runtime and not self.lost.is_set(), 'runtime_offline', 'Runtime is offline')
        result = recover_job(self.client, job_id, self.root/'jobs', reason,
            retry_inference=retry_inference, collect_interrupted_verification=collect_interrupted_verification,
            runtime_fence=self.runtime['fence'])
        if result['status'] == 'completed': return result
        saved = json.loads((self.root/'jobs'/digest(job_id)/'job.json').read_text())
        if saved['job'].get('bot_execution', {}).get('runtime_fence') != self.runtime['fence']:
            # A prior recovery committed but its acknowledgement was lost. First
            # reconcile that same durable request, then fence the confirmed stopped
            # predecessor to this runtime without another inference reservation.
            recover_job(self.client, job_id, self.root/'jobs', reason, runtime_fence=self.runtime['fence'])
        return process_job(self.client, job_id, self.root/'jobs', self.infer,
            self.config.get('cad_python'), self.config.get('verification'), self.runtime['fence'])

    def __exit__(self, *args):
        self.stop.set()
        if self.runtime:
            self.thread.join(timeout=1)
            try: self.client.call('stop_bot_runtime', {'bot_id': self.bot_id, 'fence': self.runtime['fence']})
            except Exception as exc:
                # Preserve an uncertain shutdown without treating the job as complete.
                persist(self.root/'shutdown.json', {'status': 'lease_expiry_required',
                    'reason': exc.code if isinstance(exc, Fault) else type(exc).__name__})
        if self.lock: self.lock.close()


def configured_client(config):
    token_file = Path(config['token_file'])
    require(token_file.is_file() and not token_file.is_symlink(), 'invalid_input', 'Regular private token file required')
    require(token_file.stat().st_mode & 0o077 == 0, 'unauthorized', 'Token file must be owner-only (chmod 600)')
    return Client(config['url'], token_file.read_text().strip())


def run_bot(config, journal, iterations=0, interval=10):
    require(type(iterations) is int and iterations >= 0 and 1 <= interval <= 60, 'invalid_input', 'Invalid polling settings')
    done = threading.Event(); previous = signal.signal(signal.SIGTERM, lambda *_: done.set())
    count = 0
    try:
        with BotWorker(configured_client(config), config, journal) as worker:
            while not done.is_set() and (iterations == 0 or count < iterations):
                result = worker.tick(); print(json.dumps({'bot_id': worker.bot_id, 'results': result}), flush=True)
                count += 1
                if iterations == 0 or count < iterations: done.wait(interval)
    except KeyboardInterrupt: pass
    finally: signal.signal(signal.SIGTERM, previous)


def service_manifest(config_path, journal, executable, platform):
    """Generate an opt-in user service; never install or launch it behind the owner."""
    config = Path(config_path).expanduser().resolve()
    require(config.is_file(), 'not_found', 'Worker configuration file required')
    command = Path(executable).expanduser().absolute()
    require(command.is_file(), 'not_found', 'Installed Gantry executable required')
    root = Path(journal).expanduser().resolve()
    args = [str(command), 'bot-worker', '--config', str(config), '--journal', str(root)]
    if platform == 'launchd':
        import plistlib
        return plistlib.dumps({'Label': 'dev.gantry.bot.' + digest(str(config))[:12],
            'ProgramArguments': args, 'RunAtLoad': True, 'KeepAlive': True,
            'ThrottleInterval': 30, 'ProcessType': 'Background', 'Umask': 0o077}).decode()
    require(platform == 'systemd', 'invalid_input', 'Use launchd or systemd')
    def quote(arg):
        require(not any(c in arg for c in '\n\r\x00'), 'invalid_input', 'Invalid service path')
        return '"' + arg.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%').replace('$', '$$') + '"'
    return ('[Unit]\nDescription=Gantry customer Bot\nAfter=network-online.target\n\n[Service]\nType=simple\n'
            + 'ExecStart=' + ' '.join(quote(a) for a in args)
            + '\nRestart=on-failure\nRestartSec=30\nUMask=0077\nNoNewPrivileges=yes\n\n[Install]\nWantedBy=default.target\n')
