"""Outbound-only worker: cloud proposals and customer-PC execution are separate.

The operator supplies the provider and trusted recipes. Neither incoming issues
nor browser users can submit argv. Iterations are bounded; no paid provider is
configured by default. Existing runner journals protect restart/recovery.
"""
import json
import time
import threading
from pathlib import Path
from .model import Fault, require, uid
from .runner import mentor_once, tick


def worker_once(client, kind, config, journal, worker_id):
    overview = client.call('product_overview')
    require(config.get('session_ids') or config.get('project_ids') or config.get('all_authorized_sessions') is True,
            'invalid_input', 'Explicit session_ids, project_ids or all_authorized_sessions required')
    sessions = [s for s in overview['sessions'] if s['outcome'] == 'open' and
                (config.get('all_authorized_sessions') is True or s['id'] in config.get('session_ids', [])
                 or s.get('project_id') in config.get('project_ids', []))]
    if kind == 'sync':
        require(config.get('integration_ids'), 'invalid_input', 'Explicit integration_ids required for synchronization')
        return [client.call('sync_integration', {'integration_id': iid}) for iid in config['integration_ids']]
    require(kind in {'mentor', 'runner'}, 'invalid_input', 'Invalid worker kind')
    if kind == 'mentor': require(config.get('mentor'), 'invalid_input', 'Mentor provider is not configured')
    if kind == 'runner': require(config.get('recipes'), 'invalid_input', 'Trusted local recipes are required')
    stop = threading.Event(); current = {'status': 'idle', 'summary': 'Polling delegated sessions'}
    active_ids = [s['id'] for s in sessions]
    def heartbeat():
        return client.call('worker_heartbeat', {'worker_id': worker_id, 'kind': kind,
            'session_ids': list(active_ids), **current})
    def keepalive():
        while not stop.wait(25):
            try: heartbeat()
            except (Fault, OSError): pass
    heartbeat(); thread = threading.Thread(target=keepalive, daemon=True); thread.start()
    try:
        for s in sessions:
            if kind == 'mentor' and (s['mode'] == 'record' or s.get('automation_project')): continue
            if kind == 'runner' and s['mode'] != 'execute': continue
            current.update(status='working', summary=('Proposing from evidence' if kind == 'mentor' else 'Checking delegated work'))
            active_ids[:] = [s['id']]
            heartbeat()
            root = Path(journal) / s['id']
            result = (mentor_once(client, s['id'], config['mentor'], root / 'mentor') if kind == 'mentor'
                      else tick(client, s['id'], None, config['recipes'], root))
            if result.get('status') == 'proposed' or isinstance(result.get('execution'), dict) or result.get('recovery'):
                return {'session_id': s['id'], **result}  # one bounded action per iteration
        return {'status': 'idle'}
    except Exception:
        current.update(status='error', summary='Worker failed; inspect its private local logs')
        raise
    finally:
        stop.set(); thread.join(timeout=1)
        if current['status'] != 'error': current.update(status='idle', summary='Iteration complete')
        heartbeat()


def run_worker(client, kind, config, journal, iterations=1, interval=30, worker_id=None):
    require(1 <= iterations <= 10000 and interval >= 10, 'invalid_input', 'Invalid iteration or polling budget')
    root = Path(journal); root.mkdir(parents=True, exist_ok=True, mode=0o700)
    worker_id = worker_id or kind + '-worker'
    for index in range(iterations):
        try:
            result = worker_once(client, kind, config, root, worker_id)
            print(json.dumps({'iteration': index + 1, 'result': result}), flush=True)
        except (Fault, OSError, ValueError) as exc:
            print(json.dumps({'iteration': index + 1, 'error': exc.as_dict() if isinstance(exc, Fault)
                              else {'code': 'worker_failed', 'message': 'Inspect worker configuration and journal'}}), flush=True)
        if index + 1 < iterations: time.sleep(interval)
    if kind in {'mentor', 'runner'}:
        client.call('worker_heartbeat', {'worker_id': worker_id, 'kind': kind,
            'session_ids': config.get('session_ids', []), 'status': 'stopped', 'summary': 'Configured iteration budget finished'})
