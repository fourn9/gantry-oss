"""Owner-opted, bounded recovery of positively identified inference stops."""
import json
import math
import time

from .model import Fault, digest, require
from .runner import persist


def policy(config):
    if 'recovery_policy' not in config: return None
    value = config['recovery_policy']
    require(config.get('workflow') == 'bot_development' and isinstance(value, dict)
            and set(value) == {'max_attempts', 'cooldown_seconds'}
            and type(value.get('max_attempts')) is int and 1 <= value['max_attempts'] <= 3
            and type(value.get('cooldown_seconds')) is int and 1 <= value['cooldown_seconds'] <= 86400,
            'invalid_input', 'Recovery needs a development policy: max_attempts 1..3, cooldown_seconds 1..86400')
    return dict(value)


def _safe_path(path, root):
    require(path.is_relative_to(root) and not root.is_symlink(),
            'scope_denied', 'Recovery journal must not use symlinks')
    current = path
    while current != root:
        require(not current.is_symlink(), 'scope_denied', 'Recovery journal must not use symlinks')
        current = current.parent


def _read(path, root):
    _safe_path(path, root)
    require(path.is_file(), 'journal_missing', 'Original recovery journal required')
    value = json.loads(path.read_text())
    require(isinstance(value, dict), 'recovery_journal_invalid', 'Recovery journal must be an object')
    return value


def recover_held(worker, job):
    """Return held metadata or use the existing recovery transaction once.

    Only a pending inference with no uncertain local effect is eligible. Core
    remains responsible for authority, requirements, dependencies and fences.
    """
    from .bot_inference_recovery import pending_inference
    from .monthly_recovery import ensure_stopped, prepare_retry
    root = worker.root/'jobs'
    directory = root/'development'/digest(job['id'])/str(job['attempt'])
    marker = directory/'auto-recovery.json'
    result = {'job_id': job['id'], 'status': 'held'}
    state = None

    def held(reason):
        if state is not None:
            state.update(status='held', reason=reason)
            persist(marker, state)
        return {**result, 'reason': reason}

    try:
        journal = _read(directory/'task.json', root)
        _safe_path(marker, root)
        _safe_path(marker.with_suffix('.tmp'), root)
        saved_state = _read(marker, root) if marker.exists() else {'attempts': 0, 'observed_at': time.time()}
        require(isinstance(saved_state, dict) and type(saved_state.get('attempts')) is int
                and 0 <= saved_state['attempts'] <= 3
                and all(type(saved_state.get(key)) in {int, float} and math.isfinite(saved_state[key])
                        and saved_state[key] >= 0 for key in ['observed_at', *(['last_attempt_at'] if 'last_attempt_at' in saved_state else [])]),
                'recovery_journal_invalid', 'Recovery allowance journal is invalid')
        state = saved_state
        if state.get('blocked'): return held(state['reason'])
        if state['attempts'] >= worker.recovery_policy['max_attempts']: return held('recovery_limit')
        require(job['status'] in {'held', 'running'} and journal['phase'] == 'inference',
                'outcome_unknown', 'Only a saved pending inference is eligible')
        for action in directory.glob('actions/*/action.json'):
            require(_read(action, root)['phase'] != 'executing', 'outcome_unknown', 'Local effect is uncertain')
        inference = pending_inference(directory, journal, worker.config)
        require(inference is not None, 'outcome_unknown', 'Pending effect requires explicit reconciliation')
        saved = _read(inference/'inference.json', root)
        for path in [directory/'model'/'inference.json', directory/'learning'/'inference'/'model'/'inference.json',
                     *directory.glob('actions/*/model/inference.json')]:
            if path.exists():
                receipt = _read(path, root)
                require(receipt.get('phase') == 'completed' or
                        (type(receipt.get('pid')) is int and receipt['pid'] > 0),
                        'outcome_unknown', 'Unfinished inference needs a process identity')
                if receipt.get('pid') is not None:
                    require(type(receipt['pid']) is int and receipt['pid'] > 0, 'outcome_unknown', 'Invalid process identity')
                    ensure_stopped({'phase': 'started', 'pid': receipt['pid']})
                ensure_stopped(receipt)
        retry = saved.get('phase') != 'completed'
        require(saved.get('phase') != 'retry_ready', 'outcome_unknown', 'Previously armed retry needs reconciliation')
        if retry:
            require(worker.config.get('backend') == 'codex_subscription', 'outcome_unknown',
                    'Only the monthly adapter can attest a stopped inference retry')
            for path in inference.iterdir(): _safe_path(path, root)
            answer = inference/'answer.json'; events = inference/'events.jsonl'
            require(not answer.exists() or answer.stat().st_size == 0, 'outcome_unknown', 'Response evidence needs inspection')
            require(events.is_file() and events.stat().st_size <= 1024*1024,
                    'outcome_unknown', 'Complete bounded provider events required')
            for line in events.read_text().splitlines():
                event = json.loads(line)
                require(isinstance(event, dict) and event.get('type') != 'turn.completed'
                        and not (isinstance(event.get('item'), dict) and event['item'].get('type') == 'agent_message'),
                        'outcome_unknown', 'Response evidence needs inspection')
            prepare_retry(inference, 'Automatic recovery of confirmed stopped inference', check_only=True)
        else:
            require(isinstance(saved.get('receipt'), dict) and 'output' in saved['receipt'],
                    'outcome_unknown', 'Completed inference receipt required')
        due = state.get('last_attempt_at', state['observed_at']) + worker.recovery_policy['cooldown_seconds']
        if time.time() < due: return held('recovery_cooldown')
        from .bot_worker import environment_manifest
        require(digest(environment_manifest(worker.config)) == worker.runtime['environment_hash'],
                'stale_basis', 'Owner-approved environment changed')
        if journal['claim']['task']['runtime_fence'] == worker.runtime['fence']:
            state['restart_fence'] = digest(worker.runtime['fence'])
            worker.restart.set()
            return held('recovery_restart_required')
        # Reserve before mutation/inference. Uncertain acknowledgement consumes
        # this allowance; restarting never silently resets the task-attempt cap.
        state.update(attempts=state['attempts']+1, last_attempt_at=time.time(), status='recovering',
                     reason='known_stopped_inference' if retry else 'saved_inference')
        persist(marker, state)
        try:
            from .crew_timing import span
            with span(directory, 'recovery'):
                recovered = worker.recover(job['id'], 'Automatic recovery of confirmed stopped inference', retry_inference=retry)
        except (Fault, OSError, ValueError) as exc:
            reason = exc.code if isinstance(exc, Fault) else type(exc).__name__
            state['blocked'] = reason not in {'provider_timeout', 'provider_rate_limited'}
            return held(reason)
        state.update(status='recovered', reason='known_stopped_inference' if retry else 'saved_inference')
        persist(marker, state)
        return recovered
    except (Fault, OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        return held(exc.code if isinstance(exc, Fault) else 'recovery_journal_invalid')
