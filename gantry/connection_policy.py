"""Deny-by-default policy shared by Core and the local project bridge."""
import base64
import hashlib
import re
from pathlib import PurePosixPath

from .continuity_adapter import EXCLUDED, SECRET
from .model import require

EXCLUDED = EXCLUDED | {'.cursor', '.claude', '.idea', '.vscode', 'venv', 'env',
    '.tox', '.pytest_cache', '.mypy_cache', '.ruff_cache', '.npm', '.cache'}
PRIVATE_NAMES = {'credentials', 'credentials.json', 'auth.json', '.mcp.json',
    '.netrc', '.pypirc', '.npmrc', 'id_rsa', 'id_ed25519', '.git-credentials'}
PRIVATE_SUFFIXES = {'.token', '.pem', '.key', '.p12', '.pfx', '.sqlite', '.sqlite3', '.db'}
MAX_TOTAL = 32 * 1024 * 1024
MAX_FILE = 16 * 1024 * 1024
MAX_FILES = 1000  # Match the existing atomic capture_artifact contract.
REVIEW_COUNT_POLICY = ('Gantry does not cap local project review submissions. Legacy max_reviews values '
    'are historical only; reviews_used is an audit count. Provider limits and connection expiry still apply.')
CONNECTION_LIMIT_POLICY = ('Local review and test counts are unlimited; legacy max_reviews/max_tests are historical. '
    'New connections have no automatic expiry unless the owner chooses --ttl. Existing explicit expiry remains '
    'until the owner removes it with project unlimit. Counts remain audit records; command timeouts, scopes, '
    'revocation, branch limits and provider limits still apply.')
OPERATIONS = ['identity', 'connection_context', 'authorize_connection_operation',
    'complete_connection_operation', 'connection_checkpoint', 'connection_submit', 'connection_review',
    'connection_respond', 'connection_assumption', 'connection_branch', 'connection_team', 'connection_team_read']


def effective_delegation(delegation):
    """Expose current behavior without rewriting an approved historical plan."""
    return {**delegation, 'max_reviews': None, 'max_tests': None}


def connection_expiry(connection):
    return connection.get('effective_expires_at', connection['plan']['expires_at'])


def safe_path(value, directory=False):
    require(isinstance(value, str) and value and not any(ord(c) < 32 for c in value),
            'scope_denied', 'A printable relative path is required')
    name = value[:-1] if directory and value.endswith('/') else value
    p = PurePosixPath(name)
    require(name not in {'.', '..'} and not p.is_absolute() and '\\' not in name and name == p.as_posix()
            and all(x not in {'.', '..'} for x in p.parts), 'scope_denied', 'Invalid relative path')
    require(not any(x.lower() in EXCLUDED or x.lower() in PRIVATE_NAMES or x.lower().startswith('.env')
                    or PurePosixPath(x).suffix.lower() in PRIVATE_SUFFIXES for x in p.parts),
            'scope_denied', 'Private or generated path excluded')
    require(not any(x.lower().startswith('.gantry') for x in p.parts), 'scope_denied', 'Gantry metadata excluded')
    return value


def covered(path, scopes):
    safe_path(path)
    return any(path == p or (p.endswith('/') and path.startswith(p)) for p in scopes)


def clean_bytes(raw):
    require(len(raw) <= MAX_FILE, 'capture_incomplete', 'File exceeds connect limit (16 MiB)')
    require(not SECRET.search(raw), 'credential_detected', 'Potential credential; content not retained')
    return raw


def decode_files(files, scopes):
    require(isinstance(files, dict) and 0 < len(files) <= MAX_FILES, 'capture_incomplete', 'Connect supports 1–1000 files')
    result = {}; total = 0
    for path, encoded in files.items():
        require(covered(path, scopes), 'scope_denied', 'File outside approved paths')
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError):
            require(False, 'invalid_input', 'Invalid file encoding')
        clean_bytes(raw); total += len(raw)
        require(total <= MAX_TOTAL, 'capture_incomplete', 'Connect snapshot exceeds 32 MiB; narrow scope')
        result[path] = hashlib.sha256(raw).hexdigest()
    return result


def validate_plan(plan):
    require(set(plan) == {'project', 'root', 'mode', 'paths', 'write_paths', 'commands', 'expires_at',
            'files', 'missing', 'detected', 'client', 'sandbox', 'runtime_roots', 'delegation'},
            'invalid_input', 'Unexpected connection plan fields')
    require(plan['mode'] in {'record-only', 'work-capable'}, 'invalid_input', 'Invalid connection mode')
    require(plan['expires_at'] is None or (type(plan['expires_at']) is int and plan['expires_at'] > 0),
            'invalid_input', 'expires_at must be null or an epoch millisecond integer')
    require(isinstance(plan['paths'], list) and 0 < len(plan['paths']) <= 2000,
            'invalid_input', 'Explicit paths required')
    for path in plan['paths']: safe_path(path, True)
    require(isinstance(plan['write_paths'], list) and len(plan['write_paths']) <= 2000, 'invalid_input', 'Invalid write scope')
    for path in plan['write_paths']:
        safe_path(path, True)
        require(covered(path.rstrip('/'), plan['paths']) or path in plan['paths'], 'scope_denied', 'Write scope must be readable')
    require(bool(plan['write_paths']) == (plan['mode'] == 'work-capable'), 'invalid_input', 'Work mode requires explicit write paths')
    require(isinstance(plan['commands'], dict) and len(plan['commands']) <= 20, 'invalid_input', 'Too many commands')
    for name, command in plan['commands'].items():
        require(re.fullmatch('[a-zA-Z0-9_-]{1,80}', name), 'invalid_input', 'Invalid command name')
        require(set(command) == {'argv', 'timeout_seconds'} and isinstance(command['argv'], list)
                and 0 < len(command['argv']) <= 50 and all(isinstance(x, str) and x and '\x00' not in x for x in command['argv']),
                'invalid_input', 'Command must be exact argv without a shell')
        require(type(command['timeout_seconds']) is int and 1 <= command['timeout_seconds'] <= 300,
                'invalid_input', 'Command timeout must be 1–300 seconds')
    require(plan['mode'] == 'work-capable' or not plan['commands'], 'invalid_input', 'Record-only cannot execute commands')
    require(plan['client'] in {'claude', 'codex', 'cursor', 'generic'}, 'invalid_input', 'Unknown client')
    require(isinstance(plan['files'], dict) and 0 < len(plan['files']) <= MAX_FILES, 'invalid_input', 'Connect requires 1–1000 files')
    for name, value in plan['files'].items():
        require(covered(name, plan['paths']) and isinstance(value, str) and re.fullmatch('[a-f0-9]{64}', value),
                'invalid_input', 'Invalid approved manifest')
    delegation = plan['delegation']
    require(set(delegation) == {'goal', 'done', 'constraints', 'hold', 'max_reviews', 'max_tests', 'max_branches', 'mentor'},
            'invalid_input', 'A complete delegation contract is required')
    require(isinstance(delegation['goal'], str) and delegation['goal'].strip() and
            all(isinstance(delegation[k], list) and delegation[k] and all(isinstance(v, str) and v for v in delegation[k])
                for k in ('done', 'constraints', 'hold')), 'invalid_input', 'Goal, completion and hold conditions required')
    # Retain the old field for stored plans/approval hashes. It no longer gates
    # review submission; null is the explicit value in newly prepared plans.
    old_limit = delegation['max_reviews']
    require(old_limit is None or (type(old_limit) is int and 1 <= old_limit <= 20),
            'invalid_input', 'max_reviews must be null or a legacy value from 1–20')
    old_tests = delegation['max_tests']
    require(old_tests is None or (type(old_tests) is int and 1 <= old_tests <= 20),
            'invalid_input', 'max_tests must be null or a legacy value from 1–20')
    require(type(delegation['max_branches']) is int and 1 <= delegation['max_branches'] <= 20,
            'invalid_input', 'Branch limit must be 1–20')
    require(delegation['mentor'] in {'client', 'codex-subscription'}, 'invalid_input', 'Unsupported Mentor connection')
    clean_bytes(str(plan).encode())
