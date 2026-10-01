"""Explicit local reconciliation, followed by fenced Core recovery.

The private journal is the handoff artifact between workers using the same
delegated principal. It contains source data; it is never a telemetry payload.
"""
import fcntl
import json
import os
from pathlib import Path

from .model import Fault, digest, require, uid
from .runner import persist


def _stopped(receipt):
    if not receipt.get('pid'):
        return  # Older journals require the explicit operator assertion below.
    try:
        os.killpg(receipt['pid'], 0)
    except ProcessLookupError:
        return
    raise Fault('job_uncertain', 'Recorded process group still exists; stop it before recovery')


def recover_job(client, job_id, journal, reason, *, retry_inference=False,
                collect_interrupted_verification=False):
    """Prepare recovery only. The normal worker performs subsequent work.

    Provider retries use a new directory and allowance, never overwrite an
    uncertain invocation. Lost Core acknowledgements reuse a durable request.
    """
    require(isinstance(reason, str) and reason.strip(), 'invalid_input', 'Confirm termination with a reason')
    root = Path(journal) / digest(job_id)
    from .mentor_daemon import tree_fingerprint
    path = root / 'job.json'
    require(path.is_file() and not path.is_symlink(), 'not_found', 'Original worker journal required')
    with open(root / 'lock', 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Fault('conflict', 'Worker still owns the journal')
        j = json.loads(path.read_text())
        require(j.get('job', {}).get('id') == job_id, 'invalid_input', 'Journal job mismatch')
        if j['phase'] == 'done':
            return {'job_id': job_id, 'status': 'completed', 'result': j['result']}
        if j['phase'] == 'returning' and not j.get('pending_recovery'):
            # A lost success response is not an expired job to execute again.
            try:
                result = client.call('finish_mentor_job', {'job_id': job_id, 'fence': j['job']['fence'],
                    'output': j['output'], 'provider': j['receipt']['provider']}, j['key'] + ':finish')
            except Fault as exc:
                if exc.code not in {'stale_basis', 'conflict'}:
                    raise
            else:
                j.update(phase='done', result=result); persist(path, j)
                return {'job_id': job_id, 'status': 'completed', 'result': result}
        if not j.get('pending_recovery'):
            model_dir = root / j.get('model_directory', 'model')
            marker = model_dir / 'inference.json'
            model = json.loads(marker.read_text()) if marker.exists() else {}
            _stopped(model)
            require(not retry_inference or j['phase'] == 'inference',
                    'invalid_state', 'Cannot discard a saved model result or repeat applied edits')
            if j['phase'] == 'inference' and model and model.get('phase') != 'completed':
                require(retry_inference, 'outcome_unknown', 'Inspect provider journal and explicitly request a new inference attempt')
            if model.get('phase') == 'completed':
                require(not retry_inference, 'invalid_state', 'Completed model receipt must be reused')
            verification = root / 'verification.json'
            report = json.loads(verification.read_text()) if verification.exists() else None
            if report:
                _stopped(report)
            interrupted = bool(report and report['status'] != 'completed')
            require(not interrupted or collect_interrupted_verification, 'outcome_unknown',
                    'Verification outcome unknown; explicitly collect as incomplete, or inspect the original journal')
            require(not collect_interrupted_verification or (interrupted and j['phase'] == 'edits_applied'),
                    'invalid_state', 'No interrupted verification to collect')
            if j['phase'] == 'verified':
                require(tree_fingerprint(root / 'workspace') == j['output_fingerprint'],
                        'stale_basis', 'Verified workspace was changed')
            recovery_id = uid('recovery')
            # Archive the exact local checkpoint before changing its fence/phase.
            persist(root / 'recoveries' / (recovery_id + '.json'), j)
            pending = {'key': recovery_id, 'retry_inference': retry_inference,
                'collect_interrupted_verification': interrupted,
                'args': {'job_id': job_id, 'fence': j['job']['fence'], 'reason': reason,
                    'checkpoint_hash': digest(j), 'confirmed_stopped': True,
                    'retry_inference': retry_inference, 'lease_seconds': 900}}
            if interrupted:
                # Never rerun a potentially side-effecting verifier. Preserve
                # partial files and explicitly report the missing outcome.
                pending['incomplete_verification'] = {**report, 'status': 'completed', 'exit_code': -1,
                    'outcome': 'interrupted_unknown', 'recovery_reason': reason,
                    'output_fingerprint': tree_fingerprint(root / 'workspace')}
            j['pending_recovery'] = pending; persist(path, j)
        pending = j['pending_recovery']
        renewed = client.call('recover_mentor_job', pending['args'], pending['key'])
        if pending['retry_inference']:
            j['model_directory'] = 'model-' + pending['key']
        if pending['collect_interrupted_verification']:
            require(tree_fingerprint(root / 'workspace') == pending['incomplete_verification']['output_fingerprint'],
                    'stale_basis', 'Partial workspace changed during recovery')
            persist(root / 'verification.json', pending['incomplete_verification'])
        j['job'] = renewed
        j.setdefault('recovery_receipts', []).append(pending)
        j.pop('pending_recovery'); persist(path, j)
        return {'job_id': job_id, 'status': 'ready_to_resume', 'phase': j['phase'],
                'retry_inference': pending['retry_inference'], 'automatic_adoption': False}
