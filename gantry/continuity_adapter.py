"""Saved-file checkpoint/restore adapter. No CAD UI or hidden reasoning capture."""
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path
from .adapters import capture_saved_files, restore_files
from .model import digest, require


EXCLUDED = {'.git', '.gantry', '.gantry-cache', '__pycache__', '.venv', 'node_modules', '.aws', '.ssh', '.codex'}
SECRET = re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|'
                    rb'\b(?:ghp_|github_pat_|sk-proj-)[A-Za-z0-9_-]{16,}|'
                    rb'(?i:api[_-]?key|access[_-]?token|password)\s*[=:]\s*[\"\x27]?[A-Za-z0-9_/-]{20,}')


def capture_workspace(client, root, key, zone='root'):
    root = Path(root).resolve(); names = []; missing = []
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root); name = rel.as_posix()
        if any(part in EXCLUDED for part in rel.parts):
            if path.is_dir() and path.name in EXCLUDED: missing.append('excluded:' + name)
            continue
        if path.is_symlink(): missing.append('symlink:' + name); continue
        if not path.is_file(): continue
        if path.name.startswith('.env') or path.suffix.lower() in {'.token', '.pem', '.key'} or path.name in {'credentials', 'credentials.json', 'auth.json'}:
            missing.append('credential_file_excluded:' + name); continue
        # Scan the entire stream, not just the first block; do not echo secret values.
        with path.open('rb') as f:
            tail = b''
            for block in iter(lambda: f.read(1024 * 1024), b''):
                require(not SECRET.search(tail + block), 'credential_detected', 'Potential credential in ' + name)
                tail = block[-256:]
        names.append(name)
    require(names and len(names) <= 10000, 'capture_incomplete', 'Capture needs 1–10000 files; narrow the workspace')
    snapshots = capture_saved_files(client, root, names, key, zone,
        capture_scope='saved_files_at_checkpoint', missing_dependencies=missing)
    refs = {}
    for item in snapshots:
        for name, info in item['data']['files'].items():
            refs[name] = ([{'revision_id': c['revision_id'], 'path': c['path']} for c in info['chunks']]
                          if 'chunks' in info else [{'revision_id': item['revision_id'], 'path': name}])
    artifact = client.call('capture_artifact', {'files': {}, 'assembled_files': refs, 'zone': zone,
        'capture_scope': 'saved_files_at_checkpoint', 'missing_dependencies': missing}, key + ':manifest:' + digest(refs))
    return artifact, missing


def checkpoint_workspace(client, change_id, version, root, summary, rationale, unfinished, status, key, engineering_review=None):
    # Fixed expected version rejects a concurrent checkpoint instead of rebasing silently.
    detail = client.call('development_state')
    change = None
    for session in detail['sessions']:
        listing = client.call('list_development_states', {'session_id': session['id']})
        change = next((c for c in listing['changes'] if c['id'] == change_id), None)
        if change: break
    require(change, 'not_found', 'Change not found')
    require(change['version'] == version, 'stale_basis', 'Change advanced')
    artifact, missing = capture_workspace(client, root, key, session['zone'])
    return client.call('checkpoint_change', {'change_id': change_id, 'version': version,
        'snapshot': artifact['revision_id'], 'summary': summary, 'rationale': rationale,
        'unfinished': unfinished, 'work_status': status,
        **({'engineering_review': engineering_review} if engineering_review else {}),
        'capture': {'scope': 'saved files at checkpoint', 'missing': missing + ['unsaved edits and intermediate tool calls']}}, key + ':checkpoint')


def restore_development_state(client, state_id, destination, key):
    detail = client.call('get_development_state', {'state_id': state_id})
    target = Path(destination).absolute()
    if target.exists():
        # A lost receipt response must not require destructive overwrite or another copy.
        require(not target.is_symlink() and (target/'context.json').is_file(), 'invalid_input', 'Use a new restore destination')
        saved = json.loads((target/'context.json').read_text())
        require(saved.get('state', {}).get('id') == state_id, 'conflict', 'Destination contains another state')
        require(not (target/'workspace').is_symlink(), 'integrity_error', 'Workspace must not be a symlink')
        hashes = {}
        for path in (target/'workspace').rglob('*'):
            require(not path.is_symlink(), 'integrity_error', 'Restored workspace contains a symlink')
            if path.is_file(): hashes[path.relative_to(target/'workspace').as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        receipt = client.call('record_state_restore', {'state_id': state_id, 'hashes': hashes,
            'limitations': saved['state']['capture']['missing'] + ['Environment installation and credentials not verified']}, key)
        return {'destination': str(target), 'workspace': str(target/'workspace'), 'context': str(target/'context.json'), 'receipt': receipt}
    # Bundle keeps the exact workspace separate from handoff metadata.
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.gantry-state-', dir=target.parent))
    try:
        restore_files(client, detail['state']['snapshot'], staging / 'workspace', cache_dir=target.parent/'.gantry-cache')
        from .runner import persist
        persist(staging / 'context.json', detail)
        hashes = {p.relative_to(staging / 'workspace').as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in (staging / 'workspace').rglob('*') if p.is_file()}
        require(not target.exists(), 'invalid_input', 'Destination appeared during restore')
        staging.rename(target)
    finally:
        if staging.exists(): shutil.rmtree(staging)
    receipt = client.call('record_state_restore', {'state_id': state_id, 'hashes': hashes,
        'limitations': detail['state']['capture']['missing'] + ['Environment installation and credentials not verified']}, key)
    return {'destination': str(target), 'workspace': str(target / 'workspace'),
            'context': str(target / 'context.json'), 'receipt': receipt}
