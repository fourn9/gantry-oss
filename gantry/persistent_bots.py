"""Permanent identities and customer runtimes layered on the existing review queue.

Bindings do not grant session access. All memory reads recheck source access.
Runtime declarations contain public metadata, never credentials or shell commands.
"""
import copy

from .contracts import register, S, A
from .review_contracts import BOT_PROFILE, TEXT
from .model import require, uid, digest, Fault

VERSION = {'type': 'integer', 'minimum': 0}
FLAG = {'type': 'boolean'}
register('configure_organization', {'organization_id': S, 'version': VERSION, 'name': S,
    'profile': BOT_PROFILE, 'enabled': FLAG, 'share_reflections': FLAG}, ['organization_id', 'version', 'name', 'profile', 'enabled'])
register('configure_bot', {'bot_id': S, 'organization_id': S, 'version': VERSION,
    'name': S, 'parent_bot_id': {'type': ['string', 'null']}, 'profile': BOT_PROFILE, 'enabled': FLAG},
    ['bot_id', 'organization_id', 'version', 'name', 'parent_bot_id', 'profile', 'enabled'])
register('bind_bot', {'bot_id': S, 'session_id': S, 'role': S, 'version': VERSION, 'enabled': FLAG},
    ['bot_id', 'session_id', 'role', 'version', 'enabled'])
register('get_persistent_bot', {'bot_id': S}, ['bot_id'])
register('list_organization_bots', {'organization_id': S, 'after': S,
    'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100}}, ['organization_id'])
register('list_persistent_memories', {'bot_id': S, 'after': S,
    'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100}}, ['bot_id'])
register('share_organization_memory', {'organization_id': S, 'memory_id': S, 'reason': TEXT},
    ['organization_id', 'memory_id', 'reason'])
ENVIRONMENT = {'type': 'object', 'additionalProperties': False, 'properties': {
    'name': S, 'definition': S, 'tools': A,
    'backend': {'enum': ['external_agent', 'codex_subscription']}},
    'required': ['name', 'definition', 'tools', 'backend']}
register('configure_bot_runtime', {'bot_id': S, 'version': VERSION, 'principal_id': S,
    'enabled': FLAG, 'environment': ENVIRONMENT}, ['bot_id', 'version', 'principal_id', 'enabled', 'environment'])
register('start_bot_runtime', {'bot_id': S, 'version': VERSION, 'instance_id': S, 'environment_hash': S},
    ['bot_id', 'version', 'instance_id', 'environment_hash'])
register('heartbeat_bot_runtime', {'bot_id': S, 'fence': S}, ['bot_id', 'fence'])
register('stop_bot_runtime', {'bot_id': S, 'fence': S}, ['bot_id', 'fence'])
register('bot_inbox', {'bot_id': S, 'after': S, 'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100}}, ['bot_id'])


class PersistentBotMixin:
    def _organization_owner(self, s, actor, oid):
        org = self._dev_get(s, 'organizations', oid)
        require(actor['kind'] == 'human' and actor['id'] == org['owner'],
                'human_approval_required', 'Organization owner required')
        self.allowed(actor, 'work')
        return org

    def _persistent_identity(self, s, bot_id):
        bot = self._dev_get(s, 'persistent_bots', bot_id)
        org = self._dev_get(s, 'organizations', bot['organization_id'])
        return bot, org

    def _bot_bindings(self, s, bot_id, con):
        rows = con.execute('SELECT id FROM records WHERE collection=? AND subject_id=? ORDER BY id',
                           ('bot_bindings', bot_id)).fetchall()
        return [self._dev_get(s, 'bot_bindings', row[0]) for row in rows]

    def _binding_access(self, s, actor, binding):
        try:
            d = self._dev_session(s, actor, binding['session_id'])
            team = self._review_team(s, actor, d['id'])
            member = self._bot_role(s, actor, team, binding['role'], owner_read=True)
            return binding['enabled'] and member['principal_id'] == binding['principal_id']
        except Fault:
            return False

    def _persistent_access(self, s, actor, bot_id, con):
        bot, org = self._persistent_identity(s, bot_id)
        owner = actor['kind'] == 'human' and actor['id'] == org['owner']
        require(owner or any(self._binding_access(s, actor, b) for b in self._bot_bindings(s, bot_id, con)),
                'unauthorized', 'No active authorized binding for this Bot')
        return bot, org

    def cmd_configure_organization(self, s, actor, a, fx, n, con):
        require(actor['kind'] == 'human', 'human_approval_required', 'Human organization owner required')
        self.allowed(actor, 'work')
        old = s.get('organizations', {}).get(a['organization_id'])
        if old: self._organization_owner(s, actor, old['id'])
        require(a['version'] == (old or {}).get('version', 0), 'stale_basis', 'Organization changed')
        return self._dev_save(s, fx, 'organizations', dict(a, id=a['organization_id'],
            version=a['version'] + 1, owner=actor['id'],
            share_reflections=a.get('share_reflections', (old or {}).get('share_reflections', False)), updated_at=self.clock()))

    def cmd_configure_bot(self, s, actor, a, fx, n, con):
        self._organization_owner(s, actor, a['organization_id'])
        old = s.get('persistent_bots', {}).get(a['bot_id'])
        require(not old or old['organization_id'] == a['organization_id'], 'unauthorized', 'Bot cannot change organization')
        require(a['version'] == (old or {}).get('version', 0), 'stale_basis', 'Bot changed')
        parent = a['parent_bot_id']; seen = {a['bot_id']}
        while parent:
            require(parent not in seen, 'invalid_input', 'Bot hierarchy must be acyclic')
            seen.add(parent)
            p = self._dev_get(s, 'persistent_bots', parent)
            require(p['organization_id'] == a['organization_id'], 'scope_denied', 'Parent belongs to another organization')
            parent = p['parent_bot_id']
        return self._dev_save(s, fx, 'persistent_bots', dict(a, id=a['bot_id'],
            subject_id=a['organization_id'], version=a['version'] + 1, owner=actor['id'], updated_at=self.clock()))

    def cmd_bind_bot(self, s, actor, a, fx, n, con):
        bot, org = self._persistent_identity(s, a['bot_id'])
        self._organization_owner(s, actor, org['id'])
        d = self._dev_session(s, actor, a['session_id']); self._dev_human(actor, d)
        require(d['owner'] == org['owner'], 'unauthorized', 'Session and organization must have the same human owner')
        team = self._review_team(s, actor, d['id'])
        member = next((m for m in team['members'] if m['role'] == a['role']), None)
        require(member is not None, 'invalid_input', 'Bind an existing delegated role first')
        key = digest([a['session_id'], a['role']])
        old = s.get('bot_bindings', {}).get(key)
        require(a['version'] == (old or {}).get('version', 0), 'stale_basis', 'Binding changed')
        require(not old or old['bot_id'] == bot['id'], 'conflict', 'A session role retains its original Bot identity')
        # A binding never rewrites or silently reassociates work in flight.
        rows = con.execute('SELECT id FROM records WHERE collection=? AND session_id=?', ('mentor_jobs', d['id'])).fetchall()
        for row in rows:
            job = s['mentor_jobs'][row[0]]
            role = self._persistent_job_role(team, job)
            require(job['status'] != 'running' or role != a['role'], 'conflict', 'Stop/reconcile the active job before rebinding')
        runtime = s.get('bot_runtimes', {}).get(bot['id'])
        require(not runtime or runtime['principal_id'] == member['principal_id'], 'unauthorized', 'Runtime principal differs from session role')
        return self._dev_save(s, fx, 'bot_bindings', dict(a, id=key, subject_id=bot['id'],
            principal_id=member['principal_id'], version=a['version'] + 1, created_seq=s['seq'] + 1))

    def _persistent_job_role(self, team, job):
        if job['kind'] != 'developer': return job['role']
        roles = [m['role'] for m in team['members'] if m['side'] == 'user' and m['principal_id'] == job['principal_id']]
        require(len(roles) == 1, 'invalid_input', 'Developer needs one explicit role')
        return roles[0]

    def _persistent_binding(self, s, sid, role):
        return s.get('bot_bindings', {}).get(digest([sid, role]))

    def cmd_get_persistent_bot(self, s, actor, a, fx, n, con):
        bot, org = self._persistent_access(s, actor, a['bot_id'], con)
        bindings = [b for b in self._bot_bindings(s, bot['id'], con) if self._binding_access(s, actor, b)]
        runtime = copy.deepcopy(s.get('bot_runtimes', {}).get(bot['id']))
        if runtime:
            runtime.pop('fence', None)
            runtime['presence'] = 'online' if runtime['enabled'] and runtime.get('lease_until', 0) > self.clock() else 'offline'
        return {'bot': bot, 'organization': org, 'bindings': bindings, 'runtime': runtime,
                'memory_retrieval': 'list_persistent_memories', 'source_seq': s['seq']}

    def cmd_list_organization_bots(self, s, actor, a, fx, n, con):
        # Only the owner can enumerate the entire organization, including private assignments.
        self._organization_owner(s, actor, a['organization_id'])
        limit = a.get('limit', 30)
        rows = con.execute('SELECT id FROM records WHERE collection=? AND subject_id=? AND id>? ORDER BY id LIMIT ?',
            ('persistent_bots', a['organization_id'], a.get('after', ''), limit + 1)).fetchall()
        return {'items': [self.cmd_get_persistent_bot(s, actor, {'bot_id': row[0]}, fx, n, con) for row in rows[:limit]],
                'next_cursor': rows[limit-1][0] if len(rows) > limit else None}

    def _persistent_memory_page(self, s, actor, bot, org, a, con, recent=False):
        limit = a.get('limit', 30)
        # Both sources are indexed and independently bounded. Paging covers all records.
        params = ('bot_memories', bot['id'], 'organization_memories', org['id'], a.get('after', ''), limit + 1)
        if recent:
            rows = con.execute('SELECT id, collection FROM records WHERE '
                '((collection=? AND subject_id=?) OR (collection=? AND subject_id=?)) AND id>? '
                'ORDER BY created_seq DESC, id DESC LIMIT ?', params).fetchall()
        else:
            rows = con.execute('SELECT id, collection FROM records WHERE '
                '((collection=? AND subject_id=?) OR (collection=? AND subject_id=?)) AND id>? '
                'ORDER BY id LIMIT ?', params).fetchall()
        items = []
        for ident, table in rows[:limit]:
            item = self._dev_get(s, table, ident)
            memory = self._dev_get(s, 'bot_memories', item['memory_id']) if table == 'organization_memories' else item
            # Membership alone does not disclose source projects or former principals' memories.
            binding = self._persistent_binding(s, memory['session_id'], memory['role'])
            try:
                self._dev_session(s, actor, memory['session_id'])
                if table == 'bot_memories':
                    require(binding and binding['bot_id'] == bot['id'] and self._binding_access(s, actor, binding),
                            'unauthorized', 'Source role access was revoked')
                else:
                    require(binding and binding['enabled'], 'unauthorized', 'Source binding was revoked')
            except Fault:
                continue
            items.append({**memory, 'memory_scope': 'organization' if table == 'organization_memories' else 'bot',
                          'share_id': ident if table == 'organization_memories' else None})
        return {'items': items, 'truncated': len(rows) > limit,
                'next_cursor': rows[limit-1][0] if len(rows) > limit and not recent else None,
                'retrieval': 'list_persistent_memories pages all authorized experience',
                'coverage': 'Authorized source sessions only; inaccessible records omitted. Page until next_cursor is null.'}

    def cmd_list_persistent_memories(self, s, actor, a, fx, n, con):
        bot, org = self._persistent_access(s, actor, a['bot_id'], con)
        return self._persistent_memory_page(s, actor, bot, org, a, con)

    def cmd_share_organization_memory(self, s, actor, a, fx, n, con):
        org = self._organization_owner(s, actor, a['organization_id'])
        memory = self._dev_get(s, 'bot_memories', a['memory_id'])
        require(memory.get('bot_id'), 'invalid_input', 'Only a bound Bot memory can be shared')
        bot, _ = self._persistent_access(s, actor, memory['bot_id'], con)
        self._dev_session(s, actor, memory['session_id'])
        require(bot['organization_id'] == org['id'], 'scope_denied', 'Memory belongs to another organization')
        return self._dev_save(s, fx, 'organization_memories', dict(a, id=digest([org['id'], memory['id']]),
            subject_id=org['id'], session_id=memory['session_id'], shared_by=actor['id'], created_seq=s['seq'] + 1))

    def _augment_persistent_context(self, s, actor, team, role, result, con):
        binding = self._persistent_binding(s, team['session_id'], role)
        if not binding: return
        require(self._binding_access(s, actor, binding), 'unauthorized', 'Persistent Bot binding disabled or changed')
        bot, org = self._persistent_identity(s, binding['bot_id'])
        require(bot['enabled'] and org['enabled'], 'mode_disabled', 'Bot or organization disabled')
        result.update(bot_id=bot['id'], identity_scope='organization', bot_version=bot['version'],
            binding_version=binding['version'], organization=org,
            profile=bot['profile'], session_profile=result['profile'],
            parent_bot_id=bot['parent_bot_id'],
            persistent_memory=self._persistent_memory_page(s, actor, bot, org, {'limit': 30}, con, recent=True))
        runtime = s.get('bot_runtimes', {}).get(bot['id'])
        result['execution_environment'] = ({'version': runtime['version'], 'environment': runtime['environment'],
            'environment_hash': runtime['environment_hash'], 'host': 'customer-managed'} if runtime else None)
        result['profile_status'] = 'persistent_bot'
        result['persistent_memory']['applicability'] = 'Experience is a hypothesis; source state, project, paths and requirements must be rechecked.'

    def cmd_configure_bot_runtime(self, s, actor, a, fx, n, con):
        bot, org = self._persistent_identity(s, a['bot_id']); self._organization_owner(s, actor, org['id'])
        require(a['principal_id'] in s['principals'] and s['principals'][a['principal_id']].get('enabled', True),
                'invalid_input', 'Enabled delegated principal required')
        bindings = self._bot_bindings(s, bot['id'], con)
        require(bindings and all(b['principal_id'] == a['principal_id'] for b in bindings if b['enabled']),
                'unauthorized', 'Runtime must use the existing bound principal')
        old = s.get('bot_runtimes', {}).get(bot['id'], {})
        require(a['version'] == old.get('version', 0), 'stale_basis', 'Runtime changed')
        return self._dev_save(s, fx, 'bot_runtimes', dict(a, id=bot['id'], version=a['version'] + 1,
            environment_hash=digest(a['environment']), owner=actor['id'], lease_until=0))

    def _runtime_actor(self, s, actor, bot_id, con):
        bot, org = self._persistent_access(s, actor, bot_id, con)
        rt = self._dev_get(s, 'bot_runtimes', bot_id)
        require(bot['enabled'] and org['enabled'] and rt['enabled'], 'mode_disabled', 'Bot runtime disabled')
        require(actor['id'] == rt['principal_id'], 'unauthorized', 'Runtime belongs to another principal')
        return rt

    def cmd_start_bot_runtime(self, s, actor, a, fx, n, con):
        rt = self._runtime_actor(s, actor, a['bot_id'], con)
        require(rt['version'] == a['version'] and rt['environment_hash'] == a['environment_hash'],
                'stale_basis', 'Runtime environment changed')
        require(rt.get('lease_until', 0) <= self.clock(), 'conflict', 'Another runtime is online')
        rt.update(instance_id=a['instance_id'], fence=uid('runtime'), lease_until=self.clock() + 60000,
                  last_seen=self.clock())
        return self._dev_save(s, fx, 'bot_runtimes', rt)

    def _runtime_fence(self, s, actor, bot_id, fence, con):
        rt = self._runtime_actor(s, actor, bot_id, con)
        require(rt.get('fence') == fence and rt.get('lease_until', 0) > self.clock(),
                'stale_basis', 'Runtime lease expired or was replaced')
        return rt

    def cmd_heartbeat_bot_runtime(self, s, actor, a, fx, n, con):
        rt = self._runtime_fence(s, actor, a['bot_id'], a['fence'], con)
        rt.update(last_seen=self.clock(), lease_until=self.clock() + 60000)
        self._dev_save(s, fx, 'bot_runtimes', rt)
        return {'bot_id': rt['id'], 'lease_until': rt['lease_until']}

    def cmd_stop_bot_runtime(self, s, actor, a, fx, n, con):
        rt = self._runtime_fence(s, actor, a['bot_id'], a['fence'], con)
        rt.update(lease_until=0); rt.pop('fence', None)
        self._dev_save(s, fx, 'bot_runtimes', rt)
        return {'bot_id': rt['id'], 'status': 'offline'}

    def cmd_bot_inbox(self, s, actor, a, fx, n, con):
        bot, org = self._persistent_access(s, actor, a['bot_id'], con)
        require(bot['enabled'] and org['enabled'], 'mode_disabled', 'Bot disabled')
        limit = a.get('limit', 30); jobs = []
        for binding in self._bot_bindings(s, bot['id'], con):
            if not self._binding_access(s, actor, binding): continue
            team = self._review_team(s, actor, binding['session_id'])
            member = next(m for m in team['members'] if m['role'] == binding['role'])
            kind_role = ('developer' if member['side'] == 'user' else binding['role'])
            from .indexed import job_page
            rows = job_page(con, binding['session_id'], kind_role, binding['principal_id'], a.get('after', ''), limit + 1)
            for row in rows:
                job = self._dev_get(s, 'mentor_jobs', row[0])
                if self._persistent_job_role(team, job) != binding['role']: continue
                jobs.append({k: job[k] for k in ('id', 'session_id', 'kind', 'role', 'status', 'created_at', 'principal_id')})
        jobs.sort(key=lambda j: j['id'])
        return {'bot_id': bot['id'], 'jobs': jobs[:limit],
                'next_cursor': jobs[limit-1]['id'] if len(jobs) > limit else None,
                'wake_source': 'durable submission, dependent report, correction and reflection jobs',
                'automatic_retry': False}

    def _persistent_job_check(self, s, actor, job, team, con, claim=None):
        role = self._persistent_job_role(team, job)
        binding = self._persistent_binding(s, job['session_id'], role)
        if not binding:
            require(not job.get('bot_execution'), 'stale_basis', 'Bot binding no longer exists')
            return
        require(self._binding_access(s, actor, binding), 'unauthorized', 'Bot binding changed')
        bot, org = self._persistent_identity(s, binding['bot_id'])
        require(bot['enabled'] and org['enabled'], 'mode_disabled', 'Bot disabled')
        rt = s.get('bot_runtimes', {}).get(bot['id'])
        stamp = {'bot_id': bot['id'], 'bot_version': bot['version'], 'organization_version': org['version'],
                 'binding_version': binding['version'], 'runtime_version': rt['version'] if rt else None}
        if claim is not None:
            if rt: self._runtime_fence(s, actor, bot['id'], claim.get('runtime_fence'), con)
            job['bot_execution'] = dict(stamp, runtime_fence=claim.get('runtime_fence'))
        else:
            saved = job.get('bot_execution', {})
            require(all(saved.get(k) == v for k, v in stamp.items()), 'stale_basis', 'Bot onboarding or runtime changed')
            if rt: self._runtime_fence(s, actor, bot['id'], saved.get('runtime_fence'), con)

    def _remember_bot_job(self, s, actor, job, team, result, fx):
        role = self._persistent_job_role(team, job)
        binding = self._persistent_binding(s, job['session_id'], role)
        if not binding or job['kind'] == 'reflection': return  # Reflection already saves its evidence-backed lesson.
        state_id = result.get('candidate', s['change_reviews'][job['submission_id']]['state_id'])
        manifest = self._manifest(s, s['dev_states'][state_id]['snapshot'])
        if not manifest: return
        output = job['output']
        self._save_bot_memory(s, fx, team, actor, dict(session_id=job['session_id'], role=role, state_id=state_id,
            visibility='role', observation=output.get('summary', output.get('rationale', 'Recorded job output'))[:4000],
            applicability='Recheck the source submission and its fixed acceptance before applying this experience.',
            limitations=['Reported experience, not demonstrated general competence or a physical pass.'] + output.get('unresolved', output.get('unverified', []))[:10],
            evidence=[job['submission_id'], state_id], paths=sorted(manifest)[:100], assessment='inconclusive',
            source='bot_job', job_id=job['id']))
