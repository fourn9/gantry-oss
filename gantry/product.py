"""Projects, incoming signals and sessions over the existing development ledger.

These are additive projections, not a second execution or adoption engine.
Each cloud workspace owns a separate ledger and artifact store.
"""
import base64
import copy
from . import manifest_store
import json
import os
import re
from contextlib import closing
from pathlib import PurePosixPath

from .model import Fault, require, uid, digest, canonical
from .continuity_adapter import SECRET, EXCLUDED


class ProductMixin:
    def _project(self, s, actor, pid):
        p = self._dev_get(s, 'product_projects', pid)
        self.zone_write(actor, p['zone'])
        return p

    def _integration(self, s, actor, iid):
        item = self._dev_get(s, 'product_integrations', iid)
        self._project(s, actor, item['project_id'])
        return item

    def _integration_view(self, item):
        return {**item, 'credential_configured': bool(os.environ.get(item.get('credential_ref', ''))),
                'authentication': 'server_credential' if item.get('credential_ref') else 'public_read_only'}

    def cmd_save_project(self, s, actor, a, fx, n, con):
        self._dev_human(actor)
        if a.get('project_id'):
            p = self._project(s, actor, a['project_id'])
            require(p['version'] == a.get('version'), 'stale_basis', 'Project changed')
            require(p['owner'] == actor['id'] or 'admin' in actor['permissions'], 'unauthorized', 'Project owner required')
            require(a.get('zone', p['zone']) == p['zone'], 'invalid_input', 'Project zone is fixed')
        else:
            zone = a.get('zone', 'root'); self.zone_write(actor, zone)
            require(s['entries'].get(zone, {}).get('type') == 'zone', 'invalid_input', 'Unknown zone')
            p = dict(id=uid('project'), owner=actor['id'], zone=zone, version=0, created_at=self.clock())
        require(len(a['name']) <= 120 and len(a['description']) <= 4000, 'invalid_input', 'Project text is too long')
        p.update(name=a['name'], description=a['description'], version=p['version'] + 1)
        if a.get('baseline_state'):
            state = self._continuity_state(s, actor, a['baseline_state'])
            require(s['dev_sessions'][state['session_id']]['zone'] == p['zone'], 'invalid_input', 'Baseline zone must match')
            p['baseline_state'] = state['id']
        return self._dev_save(s, fx, 'product_projects', p)

    def cmd_configure_integration(self, s, actor, a, fx, n, con):
        self.allowed(actor, 'admin'); self._dev_human(actor)
        self._project(s, actor, a['project_id'])
        if a.get('integration_id'):
            item = self._integration(s, actor, a['integration_id'])
            require(item['version'] == a.get('version'), 'stale_basis', 'Integration changed')
            require(item['project_id'] == a['project_id'] and item['provider'] == a['provider'],
                    'invalid_input', 'Provider and project are fixed; create another connection')
        else:
            item = dict(id=uid('integration'), version=0, project_id=a['project_id'], provider=a['provider'],
                        created_at=self.clock(), created_by=actor['id'])
        if a['provider'] == 'github':
            from .github_connector import validate_repository
            repo = validate_repository(a.get('repository'))
            require(not item.get('repository') or item['repository'].lower() == repo.lower(), 'invalid_input',
                    'Repository is fixed; create another connection to preserve provenance')
            reference = a.get('credential_ref', '')
            require(not reference or re.fullmatch(r'GANTRY_CONNECTOR_[A-Z0-9_]+', reference),
                    'invalid_input', 'Invalid operator credential reference')
            require(not reference or reference.startswith(getattr(self, 'credential_prefix', 'GANTRY_CONNECTOR_')),
                    'unauthorized', 'Credential reference must belong to this workspace')
            item.update(repository=repo, credential_ref=reference)
        item.update(name=a['name'], enabled=a['enabled'], version=item['version'] + 1,
                    status='configured' if a['enabled'] else 'disconnected', last_error=None)
        self._dev_save(s, fx, 'product_integrations', item)
        return self._integration_view(item)

    def sync_github(self, token, args, key):
        """External network I/O stays outside SQLite's writer transaction.

        Recheck the connection version and permission when persisting. Responses
        cannot be supplied by HTTP callers or masquerade as authenticated GitHub.
        """
        from .github_connector import fetch_repository
        require(isinstance(key, str) and 1 <= len(key) <= 200, 'invalid_input', 'Idempotency key required')
        with closing(self.store.connect()) as con:
            s = self.store.state(con); actor = self._authenticate(con, s, token, "sync_integration")
            self.allowed(actor, 'admin')
            item = self._integration(s, actor, args['integration_id'])
            cached = con.execute('SELECT * FROM requests WHERE actor=? AND key=?', (actor['id'], key)).fetchone()
            if cached:
                require(cached['fingerprint'] == digest({'command': 'sync_integration', 'args': args}),
                        'idempotency_mismatch', 'Key reused with different input')
                return manifest_store.unpack(con,json.loads(cached['response']))
            require(item['enabled'] and item['provider'] == 'github', 'mode_disabled', 'GitHub connection is disabled')
            require(self.clock() - item.get('last_attempt', 0) >= 10000, 'rate_limited', 'Wait 10 seconds before synchronizing again')
        try:
            data = fetch_repository(item)
        except Fault as exc:
            data = {'error': exc.as_dict()}
        return self.call(token, 'sync_integration', args, key,
                         _acquired=(item['version'], item.get('last_attempt', 0), data))

    def _signal(self, s, actor, item, data, fx, n, con):
        p = self._project(s, actor, item['project_id'])
        signal_id = 'signal_' + digest([item['id'], data['source_event_id']])[:32]
        old = s.get('product_signals', {}).get(signal_id)
        fingerprint = digest(data)
        if old and old['fingerprint'] == fingerprint:
            return old
        obj = dict(data, id=signal_id, project_id=p['id'], integration_id=item['id'],
                   fingerprint=fingerprint, received_at=self.clock(), version=(old or {}).get('version', 0) + 1)
        entry = self._entry(signal_id, 'incident', p['zone'], obj, (old or {}).get('revision_id'))
        self._save_entry(s, fx, entry)
        obj['revision_id'] = entry['revision_id']
        self._dev_save(s, fx, 'product_signals', obj)
        for link in s.get('product_sessions', {}).values():
            if link.get('signal_id') == signal_id or signal_id in link.get('signal_ids', []):
                d = s['dev_sessions'][link['id']]
                self._milestone(s, fx, n, d, 'submission', 'Source updated: ' + obj['title'], [entry['revision_id']])
        return obj

    def cmd_sync_integration(self, s, actor, a, fx, n, con):
        raise AssertionError('sync uses the acquired response argument')

    def _apply_sync(self, s, actor, a, fx, n, con, acquired):
        self.allowed(actor, 'admin')
        item = self._integration(s, actor, a['integration_id'])
        version, previous_attempt, data = acquired
        require(item['enabled'] and item['version'] == version, 'stale_basis', 'Connection changed during synchronization')
        require(item.get('last_attempt', 0) == previous_attempt, 'stale_basis',
                'Another synchronization completed; retry to avoid overwriting newer evidence')
        item['last_attempt'] = self.clock()
        if 'error' in data:
            item.update(status='error', last_error=data['error'])
            self._dev_save(s, fx, 'product_integrations', item)
            return {'integration': self._integration_view(item), 'synced': False, 'error': data['error']}
        updated = [self._signal(s, actor, item, row, fx, n, con)['id'] for row in data['signals']]
        item.update(status='connected', last_error=None, last_sync=self.clock(), coverage=data['coverage'],
                    partial=data['partial'], repository_id=data['repository_id'])
        self._dev_save(s, fx, 'product_integrations', item)
        return {'integration': self._integration_view(item), 'synced': True, 'signal_ids': updated,
                'requests': data['requests'], 'automatic_execution': False}

    def cmd_ingest_signal(self, s, actor, a, fx, n, con):
        self.allowed(actor, 'record'); item = self._integration(s, actor, a['integration_id'])
        require(item['enabled'] and item['provider'] == 'monitoring', 'mode_disabled', 'Monitoring intake is disabled')
        require(len(canonical(a)) < 256000, 'invalid_input', 'Signal exceeds 256 KB; upload logs separately')
        for ref in a.get('artifact_revisions', []): self._dev_artifact(s, ref)
        data = {k: v for k, v in a.items() if k not in {'integration_id', 'basis', 'intent'}}
        data.update(kind='observation', source_status='reported', capture_missing=['events not submitted by source'])
        result = self._signal(s, actor, item, data, fx, n, con)
        item.update(status='receiving', last_sync=self.clock())
        self._dev_save(s, fx, 'product_integrations', item)
        return result

    def cmd_upload_project_files(self, s, actor, a, fx, n, con):
        self.allowed(actor, 'record'); p = self._project(s, actor, a['project_id'])
        if a.get('session_id'):
            d = self._dev_session(s, actor, a['session_id'])
            link = s.get('product_sessions', {}).get(d['id'], {})
            require(link.get('project_id') == p['id'], 'invalid_input', 'Session belongs to another project')
        require(0 < len(a['files']) <= 200, 'invalid_input', 'Upload 1–200 files per batch')
        total = 0
        for path, content in a['files'].items():
            self.store.safe_name(path); name = PurePosixPath(path)
            require(not any(x in EXCLUDED for x in name.parts) and not name.name.startswith('.env')
                    and name.suffix.lower() not in {'.token', '.pem', '.key'}
                    and name.name not in {'credentials', 'credentials.json', 'auth.json'},
                    'credential_detected', 'Credential and private configuration files are not accepted')
            try: raw = base64.b64decode(content, validate=True)
            except (ValueError, TypeError): raise Fault('invalid_input', 'File contents must be base64')
            total += len(raw)
            require(len(raw) <= 32 * 1024 * 1024 and total <= 48 * 1024 * 1024, 'invalid_input', 'Upload limit: 32 MiB/file, 48 MiB/batch')
            require(not SECRET.search(raw), 'credential_detected', 'Potential credential detected; remove it before uploading')
        artifact = self.cmd_capture_artifact(s, actor, {'files': a['files'], 'zone': p['zone'],
            'source': {'type': 'browser_or_api_upload', 'project_id': p['id']},
            'capture_scope': 'explicitly uploaded saved files',
            'missing_dependencies': ['unsaved edits', 'unsubmitted dependencies', 'environment not verified']}, fx, n, con)
        upload = dict(id=uid('upload'), project_id=p['id'], session_id=a.get('session_id'),
                      category=a['category'], summary=a['summary'], snapshot=artifact['revision_id'],
                      file_count=len(a['files']), bytes=total, created_at=self.clock(), actor=actor['id'])
        self._dev_save(s, fx, 'product_uploads', upload)
        if a.get('session_id'):
            self._milestone(s, fx, n, d, 'submission', a['summary'], [artifact['revision_id']])
        return upload

    def cmd_create_product_session(self, s, actor, a, fx, n, con):
        self._dev_human(actor)
        return self._create_product_session(s, actor, a, fx, n, con)

    def _create_product_session(self, s, actor, a, fx, n, con, automation=None):
        p = self._project(s, actor, a['project_id'])
        source = self._dev_get(s, 'product_signals', a['signal_id']) if a.get('signal_id') else None
        require(not source or source['project_id'] == p['id'], 'invalid_input', 'Source belongs to another project')
        base_id = a.get('state_id', p.get('baseline_state'))
        base = self._continuity_state(s, actor, base_id) if base_id else None
        require(not (a.get('snapshot') and a.get('state_id')), 'invalid_input', 'Choose an uploaded snapshot or a saved state')
        snapshot = a.get('snapshot') or (base or {}).get('snapshot')
        require(snapshot, 'baseline_missing', 'Upload a starting bundle or select a saved development state')
        artifact = self._dev_artifact(s, snapshot)
        require(artifact['zone'] == p['zone'], 'invalid_input', 'Baseline zone must match project')
        if a.get('snapshot'): base = None
        missing = list((base or {}).get('capture', {}).get('missing', artifact['data'].get('missing_dependencies', [])))
        delegation = (automation or {}).get('session_template') or dict(mode='suggest', actors=[actor['id']],
            write_scope=[], recipes={}, max_executions=0, timeout_seconds=300, max_parallel=1)
        d = self._connect_development(s, actor, {'title': a['title'], 'snapshot': snapshot, 'zone': p['zone'],
            'capture': {'scope': 'saved input bundle', 'missing': missing}, 'unverified': ['Operational behavior'],
            'requirements': [a['goal']], 'constraints': ['Human review before formal adoption'],
            **delegation}, fx, n, con, owner=automation['authorized_by'] if automation else None)
        if automation:
            d.update(automation_project=p['id'], automation_version=automation['version'])
        paths = sorted(artifact['data']['files'])
        hierarchy = (base or {}).get('hierarchy') or [dict(id='robot', title=p['name'], kind='robot', paths=paths, editable=True)]
        context = copy.deepcopy((base or {}).get('context')) or dict(requirements=[a['goal']], constraints=d['constraints'],
            decisions=[], open_questions=['Operational configuration and reproduction conditions'], environment={})
        context['requirements'] = list(dict.fromkeys(context['requirements'] + [a['goal']]))
        # Preserve the actual source state as a parent: continuation is not a
        # brand-new import, and its initial diff must not label every file added.
        state = self._save_state(s, fx, n, d, snapshot, [base['id']] if base else [], hierarchy,
            context, a['goal'], d['capture'], d['unverified'], copied_from=base['id'] if base else None)
        d['active_state'] = state['id']; d['version'] += 1
        self._dev_save(s, fx, 'dev_sessions', d)
        link = dict(id=d['id'], project_id=p['id'], signal_id=(source or {}).get('id'),
                    source_revision=(source or {}).get('revision_id'), base_state=base_id if base else None,
                    goal=a['goal'], outcome='open', version=1, created_at=self.clock())
        self._dev_save(s, fx, 'product_sessions', link)
        if source:
            self._milestone(s, fx, n, s['dev_sessions'][d['id']], 'submission',
                            'Investigate ' + source['title'], [source['revision_id'], snapshot])
        return {'session': s['dev_sessions'][d['id']], 'state': state, 'link': link}

    def cmd_link_product_session(self, s, actor, a, fx, n, con):
        self._dev_human(actor); p = self._project(s, actor, a['project_id'])
        d = self._dev_session(s, actor, a['session_id'])
        require(d['zone'] == p['zone'], 'invalid_input', 'Session zone must match project')
        old = s.get('product_sessions', {}).get(d['id'])
        require(not old or old['project_id'] == p['id'], 'conflict', 'Session already linked to another project')
        link = old or dict(id=d['id'], project_id=p['id'], goal=d['title'], outcome='open', version=1, created_at=self.clock())
        return self._dev_save(s, fx, 'product_sessions', link)

    def cmd_set_session_outcome(self, s, actor, a, fx, n, con):
        d = self._dev_session(s, actor, a['session_id']); self._dev_human(actor, d)
        link = self._dev_get(s, 'product_sessions', d['id'])
        require(a['version'] == link['version'], 'stale_basis', 'Session changed')
        active = [e for e in s.get('dev_executions', {}).values() if e['session_id'] == d['id'] and e['status'] in {'running', 'cancelling'}]
        require(a['outcome'] == 'open' or not active, 'conflict', 'Stop active executions before pausing or closing')
        link.update(outcome=a['outcome'], reason=a['reason'], version=link['version'] + 1)
        return self._dev_save(s, fx, 'product_sessions', link)

    def cmd_add_session_note(self, s, actor, a, fx, n, con):
        self._dev_session(s, actor, a['session_id']); self.allowed(actor, 'record')
        require(len(a['body']) <= 16000, 'invalid_input', 'Note exceeds 16000 characters')
        return self._dev_save(s, fx, 'product_notes', dict(id=uid('note'), session_id=a['session_id'],
            body=a['body'], actor=actor['id'], created_at=self.clock()))

    def cmd_request_mentor(self, s, actor, a, fx, n, con):
        d = self._dev_session(s, actor, a['session_id']); self.allowed(actor, 'propose')
        require(d['mode'] != 'record', 'mode_disabled', 'Enable suggestions before requesting Mentor')
        require(s.get('product_sessions', {}).get(d['id'], {}).get('outcome', 'open') == 'open', 'mode_disabled', 'Reopen session first')
        return self._milestone(s, fx, n, d, 'submission', a['summary'], [d['snapshot']])

    def cmd_worker_heartbeat(self, s, actor, a, fx, n, con):
        self.allowed(actor, 'propose' if a['kind'] in {'mentor', 'analyst'} else 'work')
        for pid in a.get('project_ids', []): self._project(s, actor, pid)
        for sid in a['session_ids']: self._dev_session(s, actor, sid)
        wid = actor['id'] + ':' + a['worker_id']
        require(len(wid) < 240 and len(a['summary']) <= 1000, 'invalid_input', 'Worker description too long')
        return self._dev_save(s, fx, 'product_workers', dict(a, id=wid, actor=actor['id'], last_seen=self.clock()))

    def _session_summary(self, s, d):
        link = s.get('product_sessions', {}).get(d['id'], {})
        contracts = [x for x in s.get('dev_contracts', {}).values() if x['session_id'] == d['id']]
        executions = [x for x in s.get('dev_executions', {}).values() if x['session_id'] == d['id']]
        active = [e for e in executions if e['status'] in {'running', 'cancelling'}]
        assessed = {cid for r in s.get('analysis_runs', {}).values()
            if r.get('session_id') == d['id'] and r['status'] == 'completed'
            and r.get('result', {}).get('action') in {'propose', 'no_action'}
            for cid, version in r.get('basis', {}).get('contracts', {}).items()
            if any(c['id'] == cid and [c['version'], c['status']] == version for c in contracts)}
        workers = [w for w in s.get('product_workers', {}).values() if d['id'] in w['session_ids']
                   and self.clock() - w['last_seen'] < 90000 and w['status'] == 'working']
        if active or workers:
            status = 'running'; summary = 'Execution in progress' if active else workers[0]['summary']
            if active and all(e.get('deadline', self.clock() + 1) < self.clock() for e in active):
                status = 'attention'; summary = 'Execution deadline passed; reconcile the runner'
        elif link.get('outcome') == 'closed': status, summary = 'done', 'Session closed; adoption tracked separately'
        elif link.get('outcome') == 'paused': status, summary = 'attention', 'Paused'
        elif d.get('automation_project') and not s.get('automation_policies', {}).get(d['automation_project'], {}).get('enabled'):
            status, summary = 'attention', 'Automation paused'
        elif any(c['id'] not in assessed and (c['status'] == 'blocked' or c.get('last_check', {}).get('reasons')) for c in contracts):
            status, summary = 'attention', 'Execution conditions need attention'
        elif contracts: status, summary = 'review', 'Proposal ready' if any(c['status'] == 'proposed' for c in contracts) else 'Results ready for review'
        else: status, summary = 'queued', 'Waiting for Mentor or an external agent'
        return dict(id=d['id'], title=d['title'], project_id=link.get('project_id'), status=status, summary=summary,
            owner=d['owner'], actors=d['actors'], mode=d['mode'], active_state=d.get('active_state'),
            automation_project=d.get('automation_project'),
            created_at=d['created_at'], signal_id=link.get('signal_id'), contracts=len(contracts),
            executions=len(executions), active_executions=len(active), outcome=link.get('outcome', 'open'))

    def cmd_product_overview(self, s, actor, a, fx, n, con):
        projects = [p for p in s.get('product_projects', {}).values()
                    if 'admin' in actor['permissions'] or 'zones' not in actor or p['zone'] in actor['zones']]
        ids = {p['id'] for p in projects}
        sessions = self.cmd_development_state(s, actor, {}, fx, n, con)['sessions']
        session_ids = {d['id'] for d in sessions}
        return {'seq': s['seq'], 'projects': projects,
            'sessions': [self._session_summary(s, d) for d in sessions],
            'integrations': [self._integration_view(i) for i in s.get('product_integrations', {}).values() if i['project_id'] in ids],
            'signals': [{**{k: v[k] for k in ('id', 'project_id', 'integration_id', 'kind', 'title', 'source_status',
                         'received_at', 'repository', 'number', 'unit', 'revision_id') if k in v},
                         'assessment': s.get('signal_assessments', {}).get(v['id'])}
                        for v in s.get('product_signals', {}).values() if v['project_id'] in ids],
            'workers': [{**w, 'online': self.clock() - w['last_seen'] < 90000 and w['status'] != 'stopped'}
                        for w in s.get('product_workers', {}).values() if set(w['session_ids']) & session_ids or set(w.get('project_ids', [])) & ids],
            'permissions': {'admin': 'admin' in actor['permissions'], 'human': actor['kind'] == 'human'},
            'now': self.clock()}

    def cmd_project_details(self, s, actor, a, fx, n, con):
        p = self._project(s, actor, a['project_id'])
        return {'project': p, 'uploads': [u for u in s.get('product_uploads', {}).values() if u['project_id'] == p['id']],
                'baseline': self.cmd_get_development_state(s, actor, {'state_id': p['baseline_state']}, fx, n, con) if p.get('baseline_state') else None}

    def cmd_get_signal(self, s, actor, a, fx, n, con):
        signal = self._dev_get(s, 'product_signals', a['signal_id'])
        self._project(s, actor, signal['project_id'])
        return signal

    def cmd_session_details(self, s, actor, a, fx, n, con):
        d = self._dev_session(s, actor, a['session_id'])
        result = self.cmd_development_state(s, actor, {'session_id': d['id']}, fx, n, con)
        link = s.get('product_sessions', {}).get(d['id'], {})
        state_id = a.get('state_id') or d.get('active_state')
        if state_id:
            require(self._continuity_state(s, actor, state_id)['session_id'] == d['id'], 'invalid_input', 'State belongs to another session')
        result.update(summary=self._session_summary(s, d), link=link,
            source=s.get('product_signals', {}).get(link.get('signal_id')),
            state=self.cmd_get_development_state(s, actor, {'state_id': state_id}, fx, n, con) if state_id else None,
            states=self.cmd_list_development_states(s, actor, {'session_id': d['id'], 'limit': 100}, fx, n, con),
            analyses=[{k:v for k,v in x.items() if k not in {'context','fence'}} for x in s.get('analysis_runs', {}).values() if x.get('session_id') == d['id']],
            sources=[s['product_signals'][sid] for sid in link.get('signal_ids', []) if sid in s.get('product_signals', {})],
            notes=[x for x in s.get('product_notes', {}).values() if x['session_id'] == d['id']],
            uploads=[x for x in s.get('product_uploads', {}).values() if x.get('session_id') == d['id']])
        return result
