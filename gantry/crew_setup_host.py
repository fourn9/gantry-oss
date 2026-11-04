"""Customer-owned setup queue consumer. Core never supplies executable configuration."""
import copy
from pathlib import Path
import threading

from . import crew_setup_client as setup
from .model import Fault, digest, identifier, require, uid
from .project_connect import load, locked, private_dir, save


def host_configuration(backend, runtime_template, inference_config=None, mappings=None):
    template = setup._runtime_template(backend, runtime_template)
    if backend == 'codex-subscription':
        require(inference_config is None, 'invalid_input', 'Subscription inference does not use a customer command')
    else:
        require(isinstance(inference_config, dict) and set(inference_config) == {'command', 'executable_hash'},
                'invalid_input', 'Supply only the explicit customer inference command and executable_hash')
        setup._runtime_template(backend, {'name': 'Setup inference', **inference_config})
    mappings = copy.deepcopy(mappings or [])
    require(isinstance(mappings, list) and all(isinstance(m, dict) and
            {'role_id', 'principal_id', 'token_file'} <= set(m) <=
            {'role_id', 'principal_id', 'token_file', 'config_file'} for m in mappings),
            'invalid_input', 'Supply private role/principal/token/config mappings')
    return {'backend': backend, 'runtime_template': template,
            'inference_config': copy.deepcopy(inference_config), 'mappings': mappings}


def guarded_inference(infer):
    """Unknown outcomes require receipt recovery, including injected provider adapters."""
    def run(context, schema, directory):
        root = private_dir(directory); path = root/'host-inference.json'
        intent = digest({'context': context, 'schema': schema})
        if path.exists():
            saved = load(path)
            require(saved['intent'] == intent, 'idempotency_mismatch', 'Saved inference input differs')
            marker = root/'inference.json'
            if 'receipt' not in saved and marker.exists():
                provider = load(marker)
                if provider.get('phase') == 'completed' and provider.get('context') == context and provider.get('schema') == schema:
                    saved['receipt'] = provider['receipt']; save(path, saved)
            require('receipt' in saved, 'outcome_unknown', 'Prior inference outcome requires private receipt recovery')
            return saved['receipt']
        saved = {'intent': intent}; save(path, saved)
        saved['receipt'] = infer(context, schema, root)
        save(path, saved)
        return saved['receipt']
    return run


def public_prepared(review):
    return {k: review[k] for k in ('proposal_hash', 'runtime_plan_hash')} | {'roles': [
        {k: r[k] for k in ('role_id', 'principal_id', 'reused')} |
        {'name': r['environment']['name'], 'tools': r['environment']['tools']}
        for r in review['runtimes']]}


class _ConnectedClient:
    """Fence customer setup effects after the independent heartbeat loses authority."""
    def __init__(self, host):
        self.host = host
        self.url = getattr(host.client, 'url', 'local')

    def call(self, command, arguments=None, key=None):
        self.host.heartbeat()
        return self.host.client.call(command, arguments, key)


class CrewSetupHost:
    def __init__(self, client, host_id, name, journal, config, *, infer_fn=None,
                 workers=None, heartbeat_interval=15):
        self.client, self.host_id, self.name = client, identifier(host_id), name
        self.config = host_configuration(**config)
        self.config_hash = digest(self.config)
        self.root = private_dir(Path(journal).expanduser().absolute())
        self.instance_id = uid('setuphost')
        self.stop = threading.Event(); self.lost = threading.Event()
        require(0 < heartbeat_interval <= 20, 'invalid_input', 'Heartbeat interval must be at most 20 seconds')
        self.heartbeat_interval = heartbeat_interval
        self.workers = workers
        self.infer_fn = infer_fn
        self.lock = None; self.thread = None
        self.setup_client = _ConnectedClient(self)

    def __enter__(self):
        self.lock = locked(self.root/'host.lock'); self.lock.__enter__()
        try:
            self.binding = {**setup.binding_for(self.client, None), 'host_id': self.host_id,
                            'config_hash': self.config_hash}
            path = self.root/'host.json'
            if path.exists():
                require(load(path)['binding'] == self.binding, 'scope_denied',
                        'Host journal belongs to another endpoint, owner or configuration')
            else: save(path, {'binding': self.binding})
            self.client.call('register_crew_setup_host', {'host_id': self.host_id, 'instance_id': self.instance_id,
                'name': self.name, 'config_hash': self.config_hash, 'backend': self.config['backend'],
                'tools': self.config['runtime_template'].get('tools', [])}, 'setup-host-register:'+self.instance_id)
            if self.infer_fn is None:
                if self.config['backend'] == 'codex-subscription':
                    from .monthly_codex import infer_monthly
                    self.infer_fn = infer_monthly
                else:
                    from .bot_worker import infer_command
                    self.infer_fn = lambda context, schema, directory: infer_command(
                        self.config['inference_config'], context, schema, directory)
            if self.workers is None:
                from .crew_setup_host_workers import HostWorkers
                self.workers = HostWorkers(self.root/'workers')
            self.thread = threading.Thread(target=self._heartbeat, daemon=True); self.thread.start()
            return self
        except BaseException:
            self.lock.__exit__(None, None, None); self.lock = None
            raise

    def _heartbeat(self):
        while not self.stop.wait(self.heartbeat_interval):
            try: self.heartbeat()
            except Exception:
                self.lost.set()
                if self.workers: self.workers.stop_all()
                return

    def heartbeat(self):
        require(not self.lost.is_set(), 'runtime_offline', 'Setup host lost its connection')
        return self.client.call('heartbeat_crew_setup_host',
            {'host_id': self.host_id, 'instance_id': self.instance_id})

    def _preparation(self, setup_id):
        index = load(self.root/'setups'/digest(setup_id)/'prepared.json')
        require(index['binding'] == self.binding, 'scope_denied', 'Preparation belongs to another host')
        return self.root/'jobs'/digest(index['job_id'])/'preparation'

    def _mappings(self, setup_id):
        roles = self.setup_client.call('get_crew_setup', {'setup_id': setup_id})['proposal']['content']['roles']
        explicit = {m['role_id']: m for m in self.config['mappings']}
        path = self.root/'bot-bindings.json'
        saved = load(path) if path.exists() else {'binding': self.binding, 'bots': {}}
        require(saved['binding'] == self.binding, 'scope_denied', 'Bot mappings belong to another host')
        mappings = []
        for role in roles:
            if role['role_id'] in explicit: mappings.append(explicit[role['role_id']])
            elif role.get('existing_bot_id') in saved['bots']:
                mappings.append({'role_id': role['role_id'], **saved['bots'][role['existing_bot_id']]})
        return mappings

    def _remember_mappings(self, preparation):
        path = self.root/'bot-bindings.json'
        saved = load(path) if path.exists() else {'binding': self.binding, 'bots': {}}
        require(saved['binding'] == self.binding, 'scope_denied', 'Bot mappings belong to another host')
        for runtime in load(preparation/'preparation.json')['runtimes']:
            config = load(setup._private_file(runtime['config_file']))
            mapping = {'principal_id': runtime['principal_id'], 'token_file': config['token_file'],
                       'config_file': runtime['config_file']}
            old = saved['bots'].get(config['bot_id'])
            require(old is None or old == mapping, 'conflict', 'Existing private Bot mapping must be preserved')
            saved['bots'][config['bot_id']] = mapping
        save(path, saved)

    def _prepare(self, job, directory):
        review = setup.prepare(self.setup_client, job['setup_id'], directory/'preparation',
            self.config['backend'], self.config['runtime_template'], self._mappings(job['setup_id']))
        save(self.root/'setups'/digest(job['setup_id'])/'prepared.json',
             {'binding': self.binding, 'job_id': job['id']})
        return public_prepared(review)

    def _perform(self, job, directory):
        action = job['action']; sid = job['setup_id']
        if action == 'analyze':
            setup.analyze(self.setup_client, sid, directory/'analysis', guarded_inference(self.infer_fn),
                          {'host_config_hash': self.config_hash})
            return 'Proposal and inactive customer runtimes are ready for review.', self._prepare(job, directory)
        if action == 'prepare':
            return 'Edited proposal and inactive customer runtimes are ready for review.', self._prepare(job, directory)
        if action == 'stop':
            self.workers.stop_setup(sid)
            return 'Owned workers stopped. Any in-flight provider call may finish privately; queued work remains saved.', None
        require(action in {'activate', 'start'}, 'invalid_input', 'Unknown setup action')
        root = self._preparation(sid)
        prepared = setup._read_prepared(self.setup_client, sid, root)
        require(job.get('proposal_hash') == prepared['proposal_hash'] and
                job.get('runtime_plan_hash') == prepared['runtime_plan_hash'],
                'stale_basis', 'Approved proposal or runtime plan differs from the private preparation')
        if action == 'activate':
            setup.activate(self.setup_client, sid, root, job['proposal_hash'])
            setup.configure(self.setup_client, sid, root, job['runtime_plan_hash'])
            self._remember_mappings(root)
            return 'Crew created and configured. Workers have not been started.', None
        current = self.setup_client.call('get_crew_setup', {'setup_id': sid})
        require(current['execution_enabled'],
                'mode_disabled', 'Enable execution explicitly in Studio before starting workers')
        session = self.setup_client.call('development_state', {'session_id': current['session_id']})['session']
        require(job.get('session_version') == session['version'], 'stale_basis',
                'Execution policy changed after Start was approved')
        require(prepared.get('activation'), 'invalid_state', 'Activate and configure the reviewed Crew first')
        added = self.workers.start_setup(sid, prepared)
        try: setup.start_work(self.setup_client, sid, root)
        except BaseException:
            self.workers.stop_setup(sid, only=added)
            raise
        self.workers.run_setup(sid)
        return 'Customer workers started and the first task is saved.', None

    def tick(self):
        self.heartbeat()
        # Persist the claim key before calling Core so a lost response cannot claim another job.
        claim_path = self.root/'claim.json'
        claim = load(claim_path) if claim_path.exists() else {}
        if claim.get('instance_id') != self.instance_id or claim.get('finished'):
            claim = {'instance_id': self.instance_id, 'key': uid('setup-claim')}; save(claim_path, claim)
        result = self.client.call('claim_crew_setup_job',
            {'host_id': self.host_id, 'instance_id': self.instance_id}, claim['key'])
        job = result['job']
        if job is None:
            claim['finished'] = True; save(claim_path, claim); return None
        self.heartbeat()
        require(job['instance_id'] == self.instance_id and job['host_id'] == self.host_id and
                job['config_hash'] == self.config_hash, 'scope_denied', 'Claim belongs to another host instance')
        control = self.client.call('get_crew_setup_control', {'setup_id': job['setup_id']})
        current = next((j for j in control['jobs'] if j['id'] == job['id']), None)
        require(current is not None, 'outcome_unknown', 'Claim needs explicit reconciliation against its saved job')
        # Claim idempotency may replay an old running response after finish committed.
        # Retire that claim before replaying effects or moving to a resumed attempt.
        if current['status'] != 'running' or current['claim_count'] != job['claim_count']:
            claim['finished'] = True; save(claim_path, claim); return current
        directory = private_dir(self.root/'jobs'/digest(job['id'])); path = directory/'job.json'
        intent = {k: job.get(k) for k in ('id', 'setup_id', 'host_id', 'config_hash', 'action',
                                         'version', 'proposal_hash', 'runtime_plan_hash', 'session_version')}
        saved = load(path) if path.exists() else None
        try:
            require(saved is not None or (job['claim_count'] == 1 and not job.get('recovery_only')), 'outcome_unknown',
                    'Resumed job is missing its original private journal')
            if saved is None:
                saved = {'binding': self.binding, 'intent': intent}; save(path, saved)
            require(saved['binding'] == self.binding and saved['intent'] == intent,
                    'scope_denied', 'Job journal belongs to another immutable operation')
            if job.get('recovery_only'):
                require(job['action'] == 'start', 'invalid_input', 'Only an interrupted start supports stop-only recovery')
                self.workers.stop_setup(job['setup_id'])
                receipt = {'status': 'cancelled', 'summary': 'Stale start fenced. The saved first task and private journal are preserved; review the current policy before starting again.'}
                save(directory/'recovery.json', {'claim_count': job['claim_count'], **receipt})
            else:
                if not saved.get('completed') or job['action'] in {'start', 'stop'}:
                    summary, prepared = self._perform(job, directory)
                    saved['completed'] = {'status': 'succeeded', 'summary': summary}
                    if prepared: saved['completed']['prepared'] = prepared
                    save(path, saved)
                receipt = saved['completed']
        except Exception as exc:
            # Raw exceptions can contain command lines, paths or provider credentials.
            save(directory/'error.json', {'type': type(exc).__name__, 'message': str(exc)})
            receipt = {'status': 'held', 'summary': 'Setup operation is held. Inspect the private host journal and resume this same job after resolving the cause.'}
        require(not self.lost.is_set(), 'runtime_offline', 'Host heartbeat lost; preserve this operation for explicit resume')
        def finish(receipt):
            args = {'host_id': self.host_id, 'instance_id': self.instance_id, 'job_id': job['id'], **receipt}
            return self.client.call('finish_crew_setup_job', args,
                'setup-finish:'+digest([self.instance_id, job['id'], job['claim_count'], receipt]))
        try: result = finish(receipt)
        except Fault as exc:
            if not ((receipt['status'] == 'succeeded' and exc.code == 'stale_basis') or
                    (receipt['status'] == 'cancelled' and exc.code == 'runtime_unavailable')): raise
            save(directory/'error.json', {'type': type(exc).__name__, 'message': str(exc)})
            result = finish({'status': 'held', 'summary': 'Setup changed or worker shutdown is not confirmed. Review and resume this same job to reconcile its saved journal.'})
        claim['finished'] = True; save(claim_path, claim)
        return result

    def __exit__(self, *args):
        self.stop.set()
        if self.workers: self.workers.stop_all()
        if self.thread: self.thread.join(timeout=1)
        try:
            self.client.call('disconnect_crew_setup_host', {'host_id': self.host_id, 'instance_id': self.instance_id})
        except Exception: pass  # Core lease expires; never claim success while disconnected.
        if self.lock: self.lock.__exit__(*args); self.lock = None
