"""Durable, bounded refresh of unaccepted plans, never execution replay."""
import json
from pathlib import Path

from .model import require
from .runner import persist

MAX_REFRESHES = 3
REFRESH_REASONS = {'experience_changed', 'working_context_changed'}


def refresh_state(root):
    root = Path(root); marker = root/'refresh.json'
    require(not marker.is_symlink(), 'scope_denied', 'Learning refresh cannot be a symlink')
    state = json.loads(marker.read_text()) if marker.exists() else {'generation': 0, 'history': []}
    require(type(state.get('generation')) is int and 0 <= state['generation'] <= MAX_REFRESHES
            and isinstance(state.get('history'), list) and len(state['history']) == state['generation'],
            'invalid_input', 'Invalid learning refresh journal')
    return state


def active_directory(root):
    root = Path(root); generation = refresh_state(root)['generation']
    directory = root/'replans'/str(generation) if generation else root
    require(not directory.is_symlink() and not (root/'replans').is_symlink(),
            'scope_denied', 'Learning refresh directory cannot be a symlink')
    return directory


def advance(root, reason):
    state = refresh_state(root)
    require(state['generation'] < MAX_REFRESHES, 'stale_basis',
            'Experience keeps changing; automatic replan allowance exhausted')
    saved = json.loads((active_directory(root)/'plan.json').read_text())
    require('result' not in saved, 'outcome_unknown', 'An accepted plan cannot be replaced')
    state['history'].append({'generation': state['generation'], 'plan_id': saved['packet']['id'],
                             'reason': reason})
    state['generation'] += 1
    # Keep every previous plan, response and inference marker in place. The pointer
    # is committed before preparing the new generation, so reconnect resumes it.
    persist(Path(root)/'refresh.json', state)


def inference_markers(root):
    root = Path(root)
    return [root/'inference'/'model'/'inference.json',
            *sorted(root.glob('replans/*/inference/model/inference.json'))]
