"""Local external-process adapter and milestone-driven Mentor host.

A recipe is a trusted local argv/env definition, delegated by its digest. Never
execute an argv supplied by Mentor. Workspaces are separate directories, not OS
security sandboxes. A durable journal refuses ambiguous process restart.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import signal
import shutil
import sys
import threading
import subprocess
import time
from .adapters import capture_saved_files, restore_files
from .model import Fault, canonical, digest, require, uid


def persist(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    with open(tmp, 'w') as f:
        os.chmod(tmp, 0o600); f.write(canonical(data)); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def capture_tree(client, root, key, zone='root'):
    root = Path(root).resolve(); names = []; missing = []
    for p in sorted(root.rglob('*')):
        if p.is_symlink(): missing.append('symlink:' + p.relative_to(root).as_posix())
        elif p.is_file(): names.append(p.relative_to(root).as_posix())
    require(names, 'capture_incomplete', 'Workspace has no regular files to capture')
    require(len(names) <= 10000, 'capture_incomplete', 'Workspace exceeds 10000-file snapshot limit')
    require(sum((root / n).stat().st_size for n in names) <= 1024**3,
            'capture_incomplete', 'Workspace exceeds 1 GiB snapshot limit')
    snapshots = capture_saved_files(client, root, names, key, zone,
                                   capture_scope='saved_workspace_files', missing_dependencies=missing)
    refs = {}
    for item in snapshots:
        for name, info in item['data']['files'].items():
            refs[name] = ([{'revision_id': c['revision_id'], 'path': c['path']} for c in info['chunks']]
                          if 'chunks' in info else [{'revision_id': item['revision_id'], 'path': name}])
    result = client.call('capture_artifact', {'files': {}, 'assembled_files': refs, 'zone': zone,
        'capture_scope': 'saved_workspace_files', 'missing_dependencies': missing}, key + ':manifest:' + digest(refs))
    return result, missing


def fingerprint(root):
    out = {}
    for p in sorted(Path(root).rglob('*')):
        if p.is_symlink(): out[p.relative_to(root).as_posix()] = 'symlink'
        elif p.is_file():
            with p.open('rb') as f:
                h = hashlib.sha256()
                for block in iter(lambda: f.read(1024 * 1024), b''): h.update(block)
            out[p.relative_to(root).as_posix()] = h.hexdigest()
    return digest(out)


def process_env(recipe):
    # Credentials stay in the adapter process; recipe may explicitly name tool env.
    return {'PATH': os.defpath, 'LANG': 'en_US.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1',
            **recipe.get('env', {})}


def validate_recipe(recipe):
    require(isinstance(recipe, dict) and set(recipe) <= {'argv', 'env', 'timeout_seconds', 'offline_grace_seconds'},
            'invalid_input', 'Recipe supports argv/env/timeout_seconds/offline_grace_seconds only')
    require(isinstance(recipe.get('argv'), list) and recipe['argv'] and
            all(isinstance(x, str) and x for x in recipe['argv']), 'invalid_input', 'Recipe argv required')
    require(isinstance(recipe.get('env', {}), dict) and
            all(isinstance(k, str) and isinstance(v, str) for k, v in recipe.get('env', {}).items()),
            'invalid_input', 'Recipe env must be string pairs')
    timeout = recipe.get('timeout_seconds', 300)
    require(type(timeout) is int and 1 <= timeout <= 7200, 'invalid_input', 'Invalid recipe timeout (1–7200 seconds)')
    grace = recipe.get('offline_grace_seconds', 5)
    require(type(grace) is int and 1 <= grace <= 120, 'invalid_input', 'Offline grace must be 1–120 seconds')
    return digest(recipe)


def stop_process(proc):
    if proc.poll() is None:
        try: os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError: pass
        try: proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL); proc.wait(timeout=3)


def mentor_once(client, session_id, provider, journal_dir):
    """Provider reads JSON context on stdin, emits one contract JSON on stdout.

    The operator selects the provider. It may be an LLM/agent bridge; Gantry has
    no hard-coded design answers. Errors leave the milestone pending.
    """
    validate_recipe(provider)
    state = client.call('development_state', {'session_id': session_id})
    require(not state['session'].get('automation_project'), 'analysis_required',
            'Use autonomy-worker for v1.1 delegated analysis')
    if state['session']['mode'] == 'record': return {'status': 'disabled', 'reason': 'record_only'}
    pending = [m for m in state['milestones'] if m['status'] == 'pending' and m['generation'] == state['session']['generation']]
    if not pending: return {'status': 'idle'}
    m = sorted(pending, key=lambda m: (m['created_at'], m['id']))[0]; root = Path(journal_dir).resolve() / m['id']; root.mkdir(parents=True, exist_ok=True)
    context = client.call('mentor_context', {'session_id': session_id, 'milestone_id': m['id']})
    result_path = root / 'proposal.json'
    if result_path.exists():
        saved = json.loads(result_path.read_text())
        require(saved['provider_hash'] == digest(provider), 'conflict', 'Mentor provider changed; use a new journal')
        contract = saved['contract']
    else:
        with open(root / 'stdout', 'w+') as out, open(root / 'stderr', 'w+') as err:
            proc = subprocess.Popen(provider['argv'], stdin=subprocess.PIPE, stdout=out, stderr=err,
                                    text=True, env=process_env(provider), cwd=root, start_new_session=True)
            try: proc.communicate(canonical(context), timeout=provider.get('timeout_seconds', 300))
            except subprocess.TimeoutExpired:
                stop_process(proc); raise Fault('mentor_failed', 'Mentor timed out; milestone remains pending')
            require(proc.returncode == 0, 'mentor_failed', 'Mentor provider failed; inspect local stderr')
            out.seek(0); raw = out.read(1024 * 1024 + 1)
            require(len(raw) <= 1024 * 1024, 'mentor_failed', 'Mentor response exceeds 1 MiB')
        contract = json.loads(raw)
        persist(result_path, {'provider_hash': digest(provider), 'contract': contract, 'context_seq': context['seq']})
    args = {'session_id': session_id, 'milestone_id': m['id'], 'contract': contract}
    if context['session'].get('active_state'):
        require(isinstance(contract, dict) and 'contract' in contract, 'invalid_input',
                'v1 Mentor provider must return contract, input_state and evidence')
        args = {**contract, 'session_id': session_id, 'milestone_id': m['id']}
    result = client.call('mentor_propose', args, 'mentor:' + m['id'])
    return {'status': 'proposed', 'contract': result}


def run_contract(client, contract_id, recipes, journal_dir, interval=0.25):
    """Claim and run once, or resume collection of a finished process.

    Journal and workspace survive process failure. Once launch intent is saved,
    uncertain jobs are never automatically launched again. Collection can retry.
    """
    root = Path(journal_dir).resolve() / contract_id; root.mkdir(parents=True, exist_ok=True)
    import fcntl
    with open(root / 'lock', 'a') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise Fault('conflict', 'Runner already owns this journal')
        journals = sorted(root.glob('attempt-*/journal.json'), key=lambda p: p.stat().st_mtime_ns)
        for path in journals:
            if json.loads(path.read_text())['phase'] != 'done':
                return _run_locked(client, contract_id, recipes, path.parent, interval)
        detail, contract = find_contract(client, contract_id)
        if contract['status'] != 'proposed' and journals:
            return json.loads(journals[-1].read_text())['result']
        attempt = root / ('attempt-' + str(contract['version'])); attempt.mkdir(exist_ok=True)
        return _run_locked(client, contract_id, recipes, attempt, interval)


def find_contract(client, contract_id):
    state = client.call('development_state')
    for d in state['sessions']:
        detail = client.call('development_state', {'session_id': d['id']})
        for c in detail['contracts']:
            if c['id'] == contract_id: return detail, c
    raise Fault('not_found', 'Contract not found')


def _run_locked(client, contract_id, recipes, root, interval):
    journal = root / 'journal.json'
    j = json.loads(journal.read_text()) if journal.exists() else {'phase': 'new', 'start_key': uid('start')}
    if j['phase'] == 'done': return j['result']
    if j['phase'] == 'launched' and 'job_id' not in j:
        raise Fault('job_uncertain', 'Process may have run. Reconcile this execution; never launch it twice', {'journal': str(journal), 'execution': j.get('execution')})
    if j['phase'] == 'new':
        if 'start_args' not in j:
            detail, contract = find_contract(client, contract_id)
            recipe = recipes.get(contract['recipe'])
            require(recipe is not None and validate_recipe(recipe) == contract['recipe_hash'], 'recipe_not_allowed', 'Local recipe digest differs')
            j.update(start_args={'contract_id': contract_id, 'version': contract['version']},
                     recipe=recipe, zone=detail['session']['zone'])
            persist(journal, j)
        # Exact request survives a lost response after the Core committed its claim.
        result = client.call('start_execution', j['start_args'], j['start_key'])
        if not result['allowed']:
            journal.unlink(); return result
        j.update(phase='preparing', execution=result['execution'], contract=result['contract'],
                 timeout=min(result['timeout_seconds'], j['recipe'].get('timeout_seconds', 300)))
        persist(journal, j)
    supervisor = None
    workspace = root / 'workspace'
    if j['phase'] == 'preparing':
        if not workspace.exists(): restore_files(client, j['execution']['input_snapshot'], workspace, cache_dir=root.parent.parent/'.gantry-cache')
        # Check server cancellation/deadline before launching anything.
        current = client.call('development_state', {'session_id': j['execution']['session_id']})
        e = next(x for x in current['executions'] if x['id'] == j['execution']['id'])
        require(e['status'] == 'running' and e['deadline'] > time.time_ns() // 1000000,
                'execution_expired', 'Execution cancelled or expired before launch; reconcile without running')
        j.update(phase='launched', job_id=uid('job'), missing=[], previous=fingerprint(workspace), outbox=[])
        persist(root/'job.json', {'job_id':j['job_id'], 'argv':j['recipe']['argv'],
            'env':process_env(j['recipe']), 'deadline':min(e['deadline']/1000, time.time()+j['timeout'])})
        _lease(root,j)
        persist(journal,j)  # Write intent before spawning. A crash here never silently relaunches.
        with open(root/'supervisor.log','ab') as log:
            supervisor = subprocess.Popen([sys.executable,str(Path(__file__).with_name('supervisor.py')),str(root)],
                stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,close_fds=True)
            threading.Thread(target=supervisor.wait,daemon=True).start()
    if j['phase'] == 'launched':
        try: _follow_job(client,root,j,journal,interval)
        finally:
            if supervisor is not None and (root/'receipt.json').exists() and json.loads((root/'receipt.json').read_text())['phase']=='finished': supervisor.wait(timeout=3)
    if j['phase'] == 'collecting':
        _drain_outbox(client,root,j,journal)
        snap, gaps = capture_tree(client, workspace, j['execution']['id'] + ':final', j['zone'])
        logfiles = {'recipe.json': base64.b64encode(canonical(j['recipe']).encode()).decode()}
        logfiles.update({name: base64.b64encode((root / name).read_bytes()[-1024*1024:]).decode()
                    for name in ('stdout.log', 'stderr.log')})
        for name in ('receipt.json','transport.jsonl'):
            if (root/name).exists(): logfiles[name] = base64.b64encode((root/name).read_bytes()).decode()
        logs = client.call('capture_artifact', {'files': logfiles, 'zone': j['zone'],
            'capture_scope': 'stdout_stderr_tail_1MiB'}, j['execution']['id'] + ':logs:' + digest(logfiles))
        # Final snapshot may be complete while intermediate/editor history is partial.
        args = {'execution_id': j['execution']['id'], 'output_snapshot': snap['revision_id'],
                'logs_snapshot': logs['revision_id'], 'exit_code': j['exit_code'],
                'execution_status': j['execution_status'], 'capture': {'scope': 'final_saved_workspace', 'missing': sorted(set(gaps + j['missing']))},
                'unverified': ['physical behavior beyond the declared completion check'],
                'summary': 'External recipe finished; completion checked against fixed contract',
                'hypothesis': j['contract']['hypothesis'], 'rationale': j['contract']['rationale']}
        j.update(phase='submitting', finish_args=args); persist(journal, j)
    result = client.call('finish_execution', j['finish_args'], j['execution']['id'] + ':finish')
    j.update(phase='done', result=result); persist(journal, j)
    return result


def _lease(root,j,cancel=False):
    persist(root/'lease.json', {'job_id':j['job_id'], 'cancel':cancel,
        'expires_at':time.time()+j['recipe'].get('offline_grace_seconds',5)})


def _drain_outbox(client,root,j,journal):
    for item in j.get('outbox',[]):
        if item.get('sent'): continue
        key=j['execution']['id']+':local:'+item['id']
        if 'snapshot' not in item:
            snap,gaps=capture_tree(client,root/'outbox'/item['id'],key,j['zone'])
            item.update(snapshot=snap['revision_id'],gaps=gaps); persist(journal,j)
        client.call('record_execution_step', {'execution_id':j['execution']['id'],'kind':'edit',
            'summary':'Saved workspace sampled at '+str(item['observed_at']), 'snapshot':item['snapshot'],
            'capture':{'scope':'sampled_saved_files','missing':['unsaved edits','changes between polls',*item['gaps']]},
            'hypothesis':j['contract']['hypothesis'],'rationale':j['contract']['rationale']},key+':record')
        item['sent']=True; persist(journal,j)
        shutil.rmtree(root/'outbox'/item['id'],ignore_errors=True)


def _copy_consistent_sample(workspace, folder, byte_budget, attempts=3):
    """Retry a racing saved-file sample, never publish a mixed copy.

    The capture remains a sampled view, not an acquisition of every intervening
    edit. Persistent instability still raises and becomes an explicit gap.
    """
    for attempt in range(attempts):
        keep = False
        try:
            before = fingerprint(workspace)
            names = [p for p in workspace.rglob('*') if p.is_file() and not p.is_symlink()]
            require(sum(p.stat().st_size for p in names) <= byte_budget,
                    'capture_incomplete', 'Local sample exceeds 1 GiB')
            shutil.copytree(workspace, folder, symlinks=True)
            if fingerprint(folder) == before:
                require(sum(p.stat().st_size for p in folder.rglob('*')
                            if p.is_file() and not p.is_symlink()) <= byte_budget,
                        'capture_incomplete', 'Local sample exceeds 1 GiB')
                keep = True
                return before, attempt
        except OSError:
            if attempt == attempts - 1:
                raise
        finally:
            if not keep:
                # An unqueued partial copy otherwise consumes the outbox budget
                # forever, even after the producer has stopped changing files.
                shutil.rmtree(folder, ignore_errors=True)
    raise Fault('capture_incomplete', 'Workspace changed throughout bounded sample retries')


def _follow_job(client,root,j,journal,interval):
    last_poll=0; wait_until=time.monotonic()+3
    while not (root/'receipt.json').exists() and time.monotonic()<wait_until: time.sleep(.05)
    require((root/'receipt.json').exists(),'job_uncertain','Launch intent has no receipt; reconcile without relaunch')
    while True:
        receipt=json.loads((root/'receipt.json').read_text())
        require(receipt['job_id']==j['job_id'],'integrity_error','Supervisor receipt identity mismatch')
        if receipt['phase']=='finished':
            reason=receipt['reason']; code=receipt['exit_code']
            j.update(phase='collecting',exit_code=code,
                execution_status='completed' if reason=='completed' and code==0 else 'cancelled' if reason=='cancelled' else 'failed')
            if reason not in {'completed','cancelled'}: j['missing'].append('process_stopped:'+reason)
            persist(journal,j); return
        import fcntl
        with open(root/'job.lock','a') as job_lock:
            try: fcntl.flock(job_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError: pass
            else:
                latest=json.loads((root/'receipt.json').read_text())
                require(latest['phase']=='finished','job_uncertain','Supervisor disappeared without a terminal receipt')
                continue
        # Local sampling is independent of an upstream request succeeding.
        try:
            now=fingerprint(root/'workspace')
            if now!=j['previous']:
                # Bounded local outbox: explicit gaps beyond this budget, never an unbounded copy storm.
                pending=sum(not x.get('sent') for x in j['outbox'])
                retained=sum(p.stat().st_size for p in (root/'outbox').rglob('*') if p.is_file() and not p.is_symlink()) if (root/'outbox').exists() else 0
                if pending>=32 or retained>=1024**3:
                    if 'local_outbox_limit' not in j['missing']: j['missing'].append('local_outbox_limit')
                else:
                    ident=uid('sample'); folder=root/'outbox'/ident
                    now,retries=_copy_consistent_sample(root/'workspace',folder,1024**3-retained)
                    if retries:
                        j['sampling_retries']=j.get('sampling_retries',0)+retries
                        with open(root/'transport.jsonl','a') as log:
                            log.write(canonical({'at':time.time(),'event':'sample_retry',
                                'retries':retries,'recovered':True,
                                'scope':'consistent saved-file sample; intervening edits not acquired'})+'\n')
                    j['outbox'].append({'id':ident,'observed_at':time.time(),'sent':False})
                j['previous']=now; persist(journal,j)
        except (OSError,Fault):
            if 'unstable_local_sample' not in j['missing']: j['missing'].append('unstable_local_sample')
            persist(journal,j)
        if time.monotonic()-last_poll>=.5:
            try:
                state=client.call('development_state',{'session_id':j['execution']['session_id']})
                live=next(x for x in state['executions'] if x['id']==j['execution']['id'])
                _lease(root,j,cancel=live['status']!='running')
                _drain_outbox(client,root,j,journal)
            except (OSError,Fault) as exc:
                # Business/authentication refusals are not network outages.
                transient=isinstance(exc,OSError) or getattr(exc,'code','') in {'temporarily_unavailable','rate_limited'}
                if not transient: _lease(root,j,cancel=True)
                with open(root/'transport.jsonl','a') as log:
                    log.write(canonical({'at':time.time(),'transient':transient,'code':getattr(exc,'code','transport_error')})+'\n')
            last_poll=time.monotonic()
        time.sleep(interval)


def tick(client, session_id, provider, recipes, journal_dir):
    """One bounded scheduling iteration; no always-on supervisor per agent."""
    state = client.call('development_state', {'session_id': session_id})
    if state['session']['mode'] == 'record': return {'status': 'record_only'}
    # Resume collection before considering more proposals. Never relaunch uncertain jobs.
    for c in state['contracts']:
        if c['status'] == 'running':
            local = Path(journal_dir) / 'runs' / c['id']
            if local.exists():
                return {'recovery': run_contract(client, c['id'], recipes, Path(journal_dir) / 'runs')}
    suggested = mentor_once(client, session_id, provider, Path(journal_dir) / 'mentor') if provider else {'status': 'provider_not_configured'}
    state = client.call('development_state', {'session_id': session_id})
    if state['session']['mode'] != 'execute': return {'mentor': suggested, 'execution': 'disabled'}
    for c in state['contracts']:
        if c['status'] == 'proposed':
            check = client.call('check_execution', {'contract_id': c['id']})
            reuse = client.call('reuse_contract', {'contract_id': c['id'], 'version': c['version']})
            if reuse['reused']: return {'mentor': suggested, 'reuse': reuse}
            if check['allowed']:
                return {'mentor': suggested, 'execution': run_contract(client, c['id'], recipes, Path(journal_dir) / 'runs')}
    return {'mentor': suggested, 'execution': 'no_ready_contract'}


def recover_run(client, contract_id, recipes, journal_dir, reason):
    """Explicit reconciliation after the operator has confirmed process termination.

    A surviving PID/group is refused. Never restore or rerun the external process;
    collect the saved workspace as an incomplete, failed attempt instead.
    """
    import fcntl
    root = Path(journal_dir).resolve() / contract_id
    require(root.exists(), 'not_found', 'Runner journal not found')
    with open(root / 'lock', 'a') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise Fault('conflict', 'Runner is still active')
        for journal in sorted(root.glob('attempt-*/journal.json')):
            j = json.loads(journal.read_text())
            if j['phase'] not in {'launched', 'preparing'}: continue
            if j.get('job_id'):
                with open(journal.parent/'job.lock','a') as job_lock:
                    try: fcntl.flock(job_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    except BlockingIOError: raise Fault('job_uncertain','Supervisor still owns this job; use normal resume')
            if j.get('pid'):
                try: os.killpg(j['pid'], 0)
                except ProcessLookupError: pass
                else: raise Fault('job_uncertain', 'Process group still exists; stop it before reconciliation')
            if not (journal.parent / 'workspace').exists():
                restore_files(client, j['execution']['input_snapshot'], journal.parent / 'workspace')
            for name in ('stdout.log', 'stderr.log'): (journal.parent / name).touch(exist_ok=True)
            j.update(phase='collecting', exit_code=-1, execution_status='failed',
                     missing=['unconfirmed_process_outcome: ' + reason])
            persist(journal, j)
            return _run_locked(client, contract_id, recipes, journal.parent, 0.25)
        raise Fault('invalid_state', 'No uncertain execution to reconcile')


def observe_saved_development(client, session_id, root, journal, hypothesis, rationale, summary, exit_code):
    """Import a completed external trial without pretending to have launched it.

    Mid-trial hooks may use observe_execution/record_execution_step directly.
    This final-only convenience adapter explicitly records its history gaps.
    """
    path = Path(journal)
    d = client.call('development_state', {'session_id': session_id})['session']
    binding = {'session_id': session_id, 'root': str(Path(root).resolve()), 'hypothesis': hypothesis,
               'rationale': rationale, 'summary': summary, 'exit_code': exit_code}
    j = json.loads(path.read_text()) if path.exists() else {'binding': binding, 'key': uid('observe'), 'input': d['snapshot']}
    require(j['binding'] == binding, 'conflict', 'Observation journal belongs to a different trial')
    if 'result' in j: return j['result']
    persist(path, j)
    capture = {'scope': 'final_saved_files_only', 'missing': ['intermediate operations', 'tool call history', 'unsaved edits']}
    if 'execution' not in j:
        j['execution'] = client.call('observe_execution', {'session_id':session_id, 'input_snapshot':j['input'],
            'tool':'external_saved_files', 'conditions':{'root':binding['root']}, 'hypothesis':hypothesis,
            'rationale':rationale, 'capture':capture}, j['key'] + ':begin')
        persist(path, j)
    if 'finish_args' not in j:
        snap, gaps = capture_tree(client, root, j['key'] + ':output', d['zone'])
        j['finish_args'] = {'execution_id':j['execution']['id'], 'output_snapshot':snap['revision_id'],
            'exit_code':exit_code, 'execution_status':'completed' if exit_code == 0 else 'failed',
            'capture':{'scope':capture['scope'],'missing':capture['missing']+gaps}, 'unverified':d['unverified'],
            'summary':summary, 'hypothesis':hypothesis, 'rationale':rationale}
        persist(path, j)
    j['result'] = client.call('finish_execution', j['finish_args'], j['key'] + ':finish'); persist(path, j)
    return j['result']
