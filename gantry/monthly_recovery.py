"""Explicit, journaled recovery of answer-free monthly Codex rate limits."""
import json
import os
import re
import shutil
import time
from pathlib import Path

from .model import Fault, require, uid
from .runner import persist


def ensure_stopped(state):
    require(state.get('phase') != 'started' or state.get('pid'), 'outcome_unknown',
            'Started invocation has no process identity; reconcile it before recovery')
    if not state.get('pid') or state.get('phase') == 'completed': return
    try: os.kill(state['pid'], 0)
    except ProcessLookupError: return
    except PermissionError: pass
    raise Fault('outcome_unknown', 'Previous provider process may still be running')


def rate_limit_state(root, state):
    """Recognize terminal provider events, never text from an agent response."""
    root = Path(root)
    if state.get('phase') == 'failed' and state.get('code') == 'provider_rate_limited': return state
    if state.get('phase') != 'started': return None
    ensure_stopped(state)
    if (root/'answer.json').exists() and (root/'answer.json').stat().st_size: return None
    events = root/'events.jsonl'
    if not events.is_file() or events.stat().st_size > 1024*1024: return None
    last = None
    for line in events.read_text().splitlines():
        try: event = json.loads(line)
        except ValueError: return None
        if not isinstance(event, dict): return None
        item = event.get('item')
        if isinstance(item, dict) and item.get('type') == 'agent_message': return None
        if event.get('type') in {'turn.failed', 'turn.completed'}: last = event
    if not last or last.get('type') != 'turn.failed': return None
    error = last.get('error', {})
    if not isinstance(error, dict): return None
    if not (error.get('status') == 429 or error.get('code') == 429 or
            re.search(r'\b(?:HTTP\s+|status(?:\s+code)?\s*[:=]?\s*)429\b|\b429\s+Too Many Requests\b',
                      str(error.get('message', '')), re.IGNORECASE)): return None
    failures = state.get('failures', 0) + 1
    now = time.time()
    state = {**state, 'phase': 'failed', 'code': 'provider_rate_limited',
             'failures': failures, 'failed_at': now,
             'retry_at': now + min(900, 60 * 2**min(failures-1, 4))}
    persist(root/'inference.json', state)
    return state


def rate_limit_fault(state):
    return Fault('provider_rate_limited', 'Codex returned 429; task is held. Explicit recovery is required.',
                 {'retry_at': state['retry_at'], 'failures': state['failures'],
                  'cooldown_source': 'local backoff; provider reset time is unknown'})


def prepare_retry(root, reason, check_only=False):
    require(isinstance(reason, str) and bool(reason.strip()), 'invalid_input', 'Confirm previous processes stopped')
    root = Path(root); marker = root/'inference.json'
    require(marker.is_file(), 'outcome_unknown', 'No recognized provider journal; inspect before recovery')
    state = json.loads(marker.read_text()); ensure_stopped(state)
    if state.get('phase') in {'completed', 'retry_ready'}: return
    failure = rate_limit_state(root, state)
    require(failure is not None, 'outcome_unknown', 'Only a confirmed answer-free Codex 429 can be retried here')
    if time.time() < failure['retry_at']: raise rate_limit_fault(failure)
    if check_only: return
    archive = root/'recoveries'/uid('retry'); archive.mkdir(parents=True, mode=0o700)
    for source in root.iterdir():
        if source.is_file():
            require(not source.is_symlink(), 'scope_denied', 'Provider journal must contain regular files')
            shutil.copy2(source, archive/source.name)
            (archive/source.name).chmod(0o600)
    persist(archive/'recovery.json', {'reason': reason, 'at': time.time(), 'failure_code': failure['code']})
    # This atomic marker arms one explicit retry. A crash before Popen can resume
    # it; a crash after a started marker remains uncertain. Completed tool/API
    # receipts live outside this directory and are never touched.
    persist(marker, {'phase': 'retry_ready', 'context': state['context'], 'schema': state['schema'],
                     'failures': failure['failures'], 'recovery': archive.name})
