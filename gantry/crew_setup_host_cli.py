"""One-time private connection followed by the persistent foreground customer host."""
import json
from pathlib import Path
import signal
import threading

from .client import Client, validate_url
from .crew_setup_cli import _json
from .model import require, uid


def add_parser(sub):
    p = sub.add_parser('crew-setup-host', help='Connect a customer host once, then control Crew setup in Studio')
    p.add_argument('action', choices=['connect', 'run'])
    p.add_argument('--journal', required=True, help='Owner-only persistent directory; preserve it for recovery')
    p.add_argument('--host-id', help='Stable local host ID (generated once when omitted)')
    p.add_argument('--name', default='Customer setup host')
    p.add_argument('--backend', choices=['codex-subscription', 'customer-command'])
    p.add_argument('--runtime-template', help='Private approved customer worker/tool JSON')
    p.add_argument('--inference-config', help='Private customer inference command/executable_hash JSON')
    p.add_argument('--bindings', help='Private existing role/principal/token/config mapping JSON')
    p.add_argument('--interval', type=float, default=3)
    p.add_argument('--iterations', type=int, default=0, help='0 keeps the host running until interrupted')


def connection(a):
    from .crew_setup_client import _private_file
    from .crew_setup_host import host_configuration
    from .project_connect import load, locked, private_dir, save
    root = private_dir(Path(a.journal).expanduser().absolute())
    path = root/'connection.json'
    with locked(root/'connect.lock'):
        if a.action == 'run':
            require(not any((a.backend, a.runtime_template, a.inference_config, a.bindings, a.host_id)),
                    'invalid_input', 'Run uses the saved connection; preserve its approved configuration')
            return load(_private_file(path))
        require(a.token_file, 'invalid_input', 'Connect once with the existing owner --token-file')
        token_file = _private_file(a.token_file)
        require(a.backend and a.runtime_template, 'invalid_input', 'Choose --backend and --runtime-template explicitly')
        config = host_configuration(a.backend, _json(a.runtime_template),
            _json(a.inference_config) if a.inference_config else None, _json(a.bindings) if a.bindings else None)
        old = load(_private_file(path)) if path.exists() else None
        value = {'url': validate_url(a.url), 'token_file': str(token_file),
            'host_id': a.host_id or (old['host_id'] if old else uid('setuphost')),
            'name': a.name, 'config': config}
        require(old is None or old == value, 'conflict', 'Connection differs; preserve the existing host journal and configuration')
        if old is None: save(path, value)
        return value


def run(a):
    from .crew_setup_client import _private_file
    from .crew_setup_host import CrewSetupHost
    require(a.iterations >= 0 and 1 <= a.interval <= 60, 'invalid_input', 'Invalid host polling settings')
    saved = connection(a)
    token = _private_file(saved['token_file']).read_text().strip()
    client = Client(saved['url'], token)
    done = threading.Event(); previous = signal.signal(signal.SIGTERM, lambda *_: done.set())
    try:
        with CrewSetupHost(client, saved['host_id'], saved['name'], a.journal, saved['config']) as host:
            print(json.dumps({'host_id': host.host_id, 'online': True, 'backend': host.config['backend'],
                'message': 'Connected. Keep this process running; continue setup in Studio.'}), flush=True)
            count = 0
            while not done.is_set() and (a.iterations == 0 or count < a.iterations):
                result = host.tick()
                if result:
                    print(json.dumps({k: result[k] for k in ('id', 'action', 'status', 'summary')}), flush=True)
                count += 1
                if a.iterations == 0 or count < a.iterations: done.wait(a.interval)
    except KeyboardInterrupt: pass
    finally: signal.signal(signal.SIGTERM, previous)
