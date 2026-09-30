"""Restartable PR handoff; no model purchase or tool execution is implicit.

prepare exports the exact Core context for a Gantry-owned reviewer. finish accepts
its structured output. The user-owned developer uses checkpoint/response APIs.
A caller may inject a local inference function into review_once for automation.
"""
import json
from pathlib import Path
from contextlib import contextmanager
from .model import require, uid
from .runner import persist
from .contracts import validate, CONTRACTS


@contextmanager
def journal_lock(directory):
    import fcntl
    root = Path(directory); root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(root / '.lock', 'a') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        yield root


def ready_context(client, submission_id):
    context = client.call('get_change_review', {'submission_id': submission_id})
    require(context['applicable'], 'stale_basis', 'Resubmit the current change before review')
    require(set(context['required_roles']) <= set(context['specialists']), 'review_pending', 'Collect required specialist reports before inference')
    return context


def prepare_review(client, submission_id, journal, lease_seconds=900):
    with journal_lock(journal) as root:
        path = root / 'review.json'
        if path.exists():
            job = json.loads(path.read_text())
            require(job['submission_id'] == submission_id, 'conflict', 'Use one journal per submission')
            if job['phase'] == 'prepared':
                context = ready_context(client, submission_id)
                require(context['status'] == 'running' and context.get('lease_until', 0) == job['lease_until'] and context['lease_until'] > context['server_time'],
                        'lease_lost', 'Prepare a new attempt in a new journal after lease expiry')
                job['context'] = context; persist(path, job)
                return job
            if job['phase'] != 'claiming': return job
        else:
            job = dict(submission_id=submission_id, phase='claiming', claim_key=uid('review_claim'), lease_seconds=lease_seconds)
            persist(path, job)
        ready_context(client, submission_id)
        # Lost claim ACK is replayed with the same key, never a second reservation.
        lease = client.call('claim_change_review', {'submission_id': submission_id,
            'lease_seconds': job['lease_seconds']}, job['claim_key'])
        context = ready_context(client, submission_id)
        job.update(phase='prepared', fence=lease['fence'], lease_until=lease['lease_until'], context=context)
        persist(path, job)
        return job


def finish_review(client, journal, output):
    with journal_lock(journal) as root:
        path = root / 'review.json'; job = json.loads(path.read_text())
        if job['phase'] == 'completed':
            require(output == job['output'], 'idempotency_mismatch', 'Review already completed with different output')
            return job['result']
        require(job['phase'] in {'prepared', 'response_saved', 'request_started'}, 'invalid_state', 'Prepare review first')
        if job['phase'] == 'response_saved':
            require(output == job['output'], 'idempotency_mismatch', 'Retry must retain saved output')
        args = {'submission_id': job['submission_id'], 'fence': job['fence'],
            'context_fingerprint': job['context']['context_fingerprint'], 'output': output}
        validate(args, CONTRACTS['complete_change_review']['schema'])
        job.update(phase='response_saved', output=output); persist(path, job)
        result = client.call('complete_change_review', args, job['claim_key'] + ':complete')
        job.update(phase='completed', result=result); persist(path, job)
        return result


def review_once(client, submission_id, journal, infer_fn):
    job = prepare_review(client, submission_id, journal)
    if job['phase'] == 'completed': return job['result']
    if job['phase'] == 'response_saved': return finish_review(client, journal, job['output'])
    with journal_lock(journal) as root:
        job = json.loads((root / 'review.json').read_text())
        require(job['phase'] == 'prepared', 'outcome_unknown', 'Inference was started; recover output explicitly, do not rerun blindly')
        job['phase'] = 'request_started'; persist(root / 'review.json', job)
    output = infer_fn(job['context'])
    return finish_review(client, journal, output)
