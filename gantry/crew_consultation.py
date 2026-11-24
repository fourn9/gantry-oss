"""Compare explicitly registered categorical claims on the assigned saved revision."""
import hashlib
import json

from .connection_policy import clean_bytes, safe_path
from .crew_json import pointer_value
from .development import in_scope
from .model import Fault, canonical, digest, identifier, require
from .project_files import read_file

MAX_SOURCE = 65536


def validate_source(source):
    require(isinstance(source, dict) and set(source) == {'path', 'pointer'}
            and isinstance(source['pointer'], str) and len(source['pointer']) <= 512
            and (not source['pointer'] or source['pointer'].startswith('/')),
            'invalid_input', 'Specify a file and a JSON pointer')
    safe_path(source['path'])


def validate_policy(policy):
    require(isinstance(policy, dict) and set(policy) == {'peer', 'sources', 'allowed_values'},
            'invalid_input', 'Specify the responsible peer, comparable sources and their allowed values')
    identifier(policy['peer'])
    sources, values = policy['sources'], policy['allowed_values']
    require(isinstance(sources, list) and 2 <= len(sources) <= 4, 'invalid_input', 'Choose two to four saved sources')
    for source in sources:
        validate_source(source)
    require(len(set(map(canonical, sources))) == len(sources), 'invalid_input', 'Source references must be distinct')
    require(isinstance(values, list) and 1 <= len(values) <= 64
            and all(isinstance(v, str) and v.strip() and len(v) <= 128 for v in values)
            and len(set(values)) == len(values), 'invalid_input', 'Declare distinct nonempty categorical values')
    clean_bytes(canonical(values).encode())


def applies(full, guide):
    task = full['task']
    return bool(guide.get('consultation_policy') and task['kind'] == 'develop'
                and in_scope(guide['candidate'], task['write_scope']))


def saved_sources(full, workspace, guide):
    manifest = full['development']['manifest']
    files = {}
    for source in guide['consultation_policy']['sources']:
        path = source['path']
        if path in files or manifest.get(path, {}).get('size', MAX_SOURCE+1) > MAX_SOURCE:
            continue
        try:
            files[path] = read_file(workspace, path).decode('utf-8')
        except (Fault, UnicodeError, OSError):
            continue
    return files


def distinct_keys(pairs):
    obj = dict(pairs)
    if len(obj) != len(pairs):
        raise ValueError('Ambiguous JSON key')
    return obj


def compare(full, files, policy):
    manifest = full['development']['manifest']
    claims = []
    for source in policy['sources']:
        path = source['path']
        source_hash = manifest.get(path, {}).get('hash')
        claim = {**source, 'hash': source_hash, 'value': None}
        text = files.get(path)
        if isinstance(text, str):
            try:
                raw = text.encode()
                if len(raw) <= MAX_SOURCE and hashlib.sha256(raw).hexdigest() == source_hash:
                    value = pointer_value(json.loads(raw, object_pairs_hook=distinct_keys), source['pointer'])
                    if value in policy['allowed_values']:
                        claim['value'] = value
            except (ValueError, Fault, RecursionError):
                pass
        claims.append(claim)
    values = {c['value'] for c in claims}
    status = 'missing' if None in values else 'consistent' if len(values) == 1 else 'conflict'
    basis = digest([full['task']['id'], policy, claims])
    peer = policy['peer']
    consulted = any(q.get('to_bot_id') == peer and q.get('status') == 'resolved'
                    and q.get('consultation_basis') == basis and q.get('reviewed_basis') == basis
                    and q.get('answer_id') and q['answer_id'] in q.get('resolution', {}).get('evidence', [])
                    for q in full.get('consultations', []))
    return {'status': status, 'sources': claims, 'peer': peer, 'basis': basis, 'consulted': consulted}
