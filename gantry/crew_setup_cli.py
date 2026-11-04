"""Explicit export preview, customer inference, and separately approved Crew setup."""
import base64
import hashlib
import json
from pathlib import Path

from .model import digest, require


def add_parser(sub):
    p = sub.add_parser('crew-setup', help='Prepare a sourced persistent Crew and private customer runtimes')
    p.add_argument('action', choices=['start', 'review', 'resume', 'analyze', 'propose', 'prepare', 'activate', 'configure', 'start-work'])
    p.add_argument('--setup-id')
    p.add_argument('--session-id')
    p.add_argument('--state-id')
    p.add_argument('--organization-id')
    p.add_argument('--name')
    p.add_argument('--notes', default='')
    p.add_argument('--root', default='.', help='Directory containing selected organizational exports')
    p.add_argument('--source', action='append', default=[], help='PROVIDER=relative/file; generic, notion, linear, jira, spreadsheet')
    p.add_argument('--apply', action='store_true', help='Save selected exports after preview; never start workers')
    p.add_argument('--journal', help='Private local directory for this operation; preserve for retries')
    p.add_argument('--backend', choices=['codex-subscription', 'customer-command'])
    p.add_argument('--inference-config', help='Private JSON with approved customer command and executable_hash')
    p.add_argument('--runtime-template', help='Private customer worker/tool JSON, without credentials or Bot IDs')
    p.add_argument('--bindings', help='Private JSON role/principal/token_file/config_file mappings for reused identities')
    p.add_argument('--proposal', help='Reviewed corrected proposal JSON for propose')
    p.add_argument('--approve', help='Exact proposal hash for activate; exact runtime plan hash for configure')


def _json(path):
    from .crew_setup_client import _private_file
    path = _private_file(path)
    require(path.stat().st_size <= 1024*1024, 'context_limit', 'Configuration exceeds 1 MiB')
    return json.loads(path.read_text())


def _capture(root, labels):
    from .connection_policy import safe_path
    from .project_files import read_file
    from .crew_sources import parse_source
    require(len(labels) <= 30, 'invalid_input', 'Select at most 30 organizational files')
    root = Path(root).expanduser().absolute(); files = {}; sources = []; preview = []; total = 0
    for item in labels:
        provider, separator, path = item.partition('=')
        require(separator and provider in {'generic', 'notion', 'linear', 'jira', 'spreadsheet'},
                'invalid_input', 'Use --source PROVIDER=relative/file')
        safe_path(path)
        require(path not in files, 'invalid_input', 'Each selected file needs exactly one provider')
        raw = read_file(root, path); total += len(raw)
        require(total <= 32*1024*1024, 'capture_incomplete', 'Selected exports exceed 32 MiB')
        parsed = parse_source(path, raw, provider)
        files[path] = base64.b64encode(raw).decode(); sources.append({'path': path, 'provider': provider})
        preview.append({'path': path, 'provider': provider, 'size': len(raw), 'hash': hashlib.sha256(raw).hexdigest(),
                        'evidence_records': len(parsed['records']), 'limitations': parsed['limitations']})
    return files, sources, preview


def _start(client, a):
    from .project_connect import private_dir, save, load, locked
    from .crew_setup_client import binding_for
    from .contracts import CONTRACTS, validate
    require(a.session_id and a.state_id and a.name, 'invalid_input', 'Select --session-id, --state-id and --name')
    files, sources, preview = _capture(a.root, a.source)
    args = {'session_id': a.session_id, 'state_id': a.state_id, 'organization_name': a.name,
            'notes': a.notes, 'files': files, 'sources': sources}
    if a.organization_id: args['organization_id'] = a.organization_id
    validate(args, CONTRACTS['start_crew_setup']['schema'])
    if not a.apply:
        return {'session_id': a.session_id, 'state_id': a.state_id, 'sources': preview,
                'sent': False, 'executed': False, 'next': 'Review selected sources, then repeat with --apply --journal PRIVATE_DIRECTORY.'}
    require(a.journal, 'invalid_input', 'Use --journal to preserve the exact upload for retries')
    root = private_dir(Path(a.journal).expanduser().absolute())
    with locked(root/'upload.lock'):
        path = root/'upload.json'
        intent = {'binding': binding_for(client, None), 'root': str(Path(a.root).expanduser().absolute()), 'arguments_hash': digest(args)}
        if path.exists():
            saved = load(path)
            require(saved['intent'] == intent, 'conflict', 'Upload journal has different sources or setup; use a new journal')
        else:
            require(_capture(a.root, a.source)[2] == preview, 'capture_incomplete', 'Selected exports changed during capture')
            saved = {'intent': intent, 'args': args, 'key': 'crew-upload:'+digest(intent)}; save(path, saved)
        if 'result' not in saved:
            result = client.call('start_crew_setup', saved['args'], saved['key'])
            saved['result'] = {'setup_id': result['id'], 'version': result['version'], 'status': result['status'],
                'session_id': result['session_id'], 'state_id': result['state_id'], 'sent': True, 'executed': False}
            save(path, saved)
        return saved['result']


def run(client, a):
    from . import crew_setup_client as setup
    if a.action == 'start': return _start(client, a)
    require(a.setup_id, 'invalid_input', 'Select --setup-id')
    if a.action in {'review', 'resume'}: return client.call('get_crew_setup', {'setup_id': a.setup_id})
    require(a.journal, 'invalid_input', 'Use --journal to preserve this operation for retries')
    if a.action in {'analyze', 'propose'}:
        if a.action == 'propose':
            require(a.proposal, 'invalid_input', 'Select --proposal with the corrected proposal JSON')
            proposal = _json(a.proposal)
            infer = lambda context, schema, directory: {'output': proposal, 'provider': {'kind': 'owner-edited-proposal'}}
            descriptor = {'proposal_hash': digest(proposal)}
        else:
            require(a.backend, 'invalid_input', 'Choose --backend explicitly; there is no paid fallback')
            descriptor = {'backend': a.backend}
            if a.backend == 'codex-subscription':
                require(not a.inference_config, 'invalid_input', 'Subscription analysis does not use --inference-config')
                from .monthly_codex import infer_monthly
                infer = infer_monthly
            else:
                require(a.inference_config, 'invalid_input', 'Supply --inference-config for the customer command')
                from .bot_worker import infer_command
                config = _json(a.inference_config); descriptor['config'] = config
                infer = lambda context, schema, directory: infer_command(config, context, schema, directory)
        return setup.analyze(client, a.setup_id, a.journal, infer, descriptor)
    if a.action == 'prepare':
        require(a.backend and a.runtime_template, 'invalid_input', 'Select --backend and --runtime-template explicitly')
        return setup.prepare(client, a.setup_id, a.journal, a.backend, _json(a.runtime_template), _json(a.bindings) if a.bindings else None)
    if a.action in {'activate', 'configure'}:
        require(a.approve, 'invalid_input', 'Supply the exact reviewed --approve hash')
        return getattr(setup, a.action)(client, a.setup_id, a.journal, a.approve)
    return setup.start_work(client, a.setup_id, a.journal)
