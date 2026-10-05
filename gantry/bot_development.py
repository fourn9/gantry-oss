"""Bot-owned development, independent of Mentor reviews and their job queue.

Uses Core transactions, continuity checkpoints and persistent Bot identities.
Assignments express delegated work, never formal adoption or a physical pass.
"""
import copy

from .contracts import register, S, A, I
from .development import in_scope
from .development_contracts import CAPTURE
from .model import require, uid, digest
from .persistent_bots import VERSION, FLAG

PAGE = {'after': S, 'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100}}
TASK = {'bot_id': S, 'state_id': S, 'kind': {'enum': ['plan', 'develop', 'verify', 'integrate', 'report']},
        'title': S, 'completion': A, 'write_scope': A, 'dependencies': A, 'after_tasks': A}
ASSIGNMENT = {'type': 'object', 'properties': TASK, 'required': list(TASK), 'additionalProperties': False}
EDIT = {'type': 'object', 'properties': {'path': S, 'content': {'type': 'string'}},
        'required': ['path', 'content'], 'additionalProperties': False}
REPORT = {'summary': S, 'rationale': S, 'unverified': A,
          'status': {'enum': ['completed', 'waiting', 'blocked', 'failed']},
          'assignments': {'type': 'array', 'maxItems': 16, 'items': ASSIGNMENT},
          'integrate_changes': {'type': 'array', 'maxItems': 32, 'items': {
              'type': 'object', 'properties': {'id': S, 'version': I},
              'required': ['id', 'version'], 'additionalProperties': False}}}
BOT_ANSWER = {'type': 'object', 'properties': {**REPORT, 'edits': {'type': 'array', 'maxItems': 100, 'items': EDIT}},
              'required': [*REPORT, 'edits'], 'additionalProperties': False}
register('configure_bot_project', {'session_id': S, 'organization_id': S, 'version': VERSION,
    'goal': S, 'acceptance': A, 'lead_bot_id': S, 'enabled': FLAG},
    ['session_id', 'organization_id', 'version', 'goal', 'acceptance', 'lead_bot_id', 'enabled'])
register('bind_development_bot', {'session_id': S, 'bot_id': S, 'principal_id': S, 'version': VERSION,
    'write_scope': A, 'can_assign': FLAG, 'can_integrate': FLAG, 'enabled': FLAG},
    ['session_id', 'bot_id', 'principal_id', 'version', 'write_scope', 'can_assign', 'can_integrate', 'enabled'])
register('assign_bot_task', {'session_id': S, 'requested_by_bot': S, 'parent_task_id': S, **TASK},
    ['session_id', *TASK])
register('get_bot_project list_bot_tasks', {'session_id': S, **PAGE}, ['session_id'])
register('get_bot_task', {'task_id': S}, ['task_id'])
register('claim_bot_task', {'task_id': S, 'version': I, 'runtime_fence': S}, ['task_id', 'version', 'runtime_fence'])
register('check_bot_task', {'task_id': S, 'fence': S}, ['task_id', 'fence'])
register('checkpoint_bot_task', {'task_id': S, 'fence': S, 'snapshot': S, 'summary': S,
    'rationale': S, 'unfinished': A, 'capture': CAPTURE},
    ['task_id', 'fence', 'snapshot', 'summary', 'rationale', 'unfinished', 'capture'])
register('finish_bot_task', {'task_id': S, 'fence': S, 'report': {
    'type': 'object', 'properties': REPORT, 'required': list(REPORT), 'additionalProperties': False}},
    ['task_id', 'fence', 'report'])
register('hold_bot_task', {'task_id': S, 'fence': S, 'reason': S}, ['task_id', 'fence', 'reason'])
register('recover_bot_task', {'task_id': S, 'version': I, 'runtime_fence': S, 'confirm_stopped': S},
    ['task_id', 'version', 'runtime_fence', 'confirm_stopped'])
register('cancel_bot_task', {'task_id': S, 'requested_by_bot': S, 'version': I, 'reason': S},
    ['task_id', 'version', 'reason'])
register('send_bot_message', {'task_id': S, 'from_bot_id': S, 'body': S,
    'kind': {'enum': ['question', 'answer', 'objection', 'dependency', 'handoff', 'report']},
    'blocking': FLAG, 'reply_to': S, 'evidence': A},
    ['task_id', 'from_bot_id', 'body', 'kind', 'blocking', 'evidence'])
register('resolve_bot_message', {'message_id': S, 'reason': S, 'evidence': A}, ['message_id', 'reason', 'evidence'])

TERMINAL = {'completed', 'failed', 'blocked', 'cancelled'}


class BotDevelopmentMixin:
    def _bd_project(self, s, actor, sid, active=True):
        d = self._dev_session(s, actor, sid)
        p = self._dev_get(s, 'bot_projects', sid)
        org = self._dev_get(s, 'organizations', p['organization_id'])
        if active:
            require(p['enabled'] and org['enabled'], 'mode_disabled', 'Bot development is disabled')
            require(not s.get('review_automation', {}).get(sid, {}).get('enabled'),
                    'conflict', 'Disable legacy review automation before running Bot development')
        return p, d

    def _bd_binding(self, s, sid, bid):
        return self._dev_get(s, 'bot_bindings', digest([sid, 'development:' + bid]))

    def _bd_actor(self, s, actor, sid, bid):
        p, d = self._bd_project(s, actor, sid)
        b = self._bd_binding(s, sid, bid)
        bot, org = self._persistent_identity(s, bid)
        require(b['enabled'] and bot['enabled'] and org['id'] == p['organization_id'],
                'mode_disabled', 'Bot binding is disabled')
        require(b['principal_id'] == actor['id'], 'unauthorized', 'Act only as your bound Bot')
        self.allowed(actor, 'work')
        return b, bot, p, d

    def _bd_owner(self, actor, p):
        return actor['kind'] == 'human' and actor['id'] == p['owner']

    def _bd_subordinate(self, s, manager, target):
        seen = set()
        while target and target not in seen:
            if target == manager: return True
            seen.add(target)
            target = self._dev_get(s, 'persistent_bots', target)['parent_bot_id']
        return False

    def _bd_task_rows(self, s, sid, con):
        return [self._dev_get(s, 'bot_tasks', r[0]) for r in con.execute(
            'SELECT id FROM records WHERE collection=? AND session_id=? ORDER BY id', ('bot_tasks', sid))]

    @staticmethod
    def _bd_public(task):
        return {k: copy.deepcopy(v) for k, v in task.items() if k not in {'fence', 'runtime_fence', 'stamp'}}

    def cmd_configure_bot_project(self, s, actor, a, fx, n, con):
        d = self._dev_session(s, actor, a['session_id']); self._dev_human(actor, d)
        org = self._organization_owner(s, actor, a['organization_id'])
        require(d['owner'] == org['owner'] and d.get('active_state'), 'invalid_input', 'Initialize an owner-matched development state')
        bot, _ = self._persistent_identity(s, a['lead_bot_id'])
        require(bot['organization_id'] == org['id'], 'scope_denied', 'Lead belongs to another organization')
        old = s.get('bot_projects', {}).get(d['id'], {})
        require(a['version'] == old.get('version', 0), 'stale_basis', 'Bot project changed')
        require(not old or old['organization_id'] == org['id'], 'scope_denied', 'Organization is immutable')
        require(a['acceptance'], 'invalid_input', 'Explicit acceptance conditions required')
        if a['enabled']:
            require(not s.get('review_automation', {}).get(d['id'], {}).get('enabled'), 'conflict', 'Disable review automation first')
            require(not any(j['status'] in {'pending', 'running', 'failed', 'interrupted'} for j in
                s.get('mentor_jobs', {}).values() if j['session_id'] == d['id']),
                'conflict', 'Reconcile legacy jobs, or use a separate Bot development session')
        if old and a['enabled'] and not old['enabled']:
            require(not any(t['status'] in {'running', 'held', 'waiting'} for t in self._bd_task_rows(s, d['id'], con)),
                    'conflict', 'Reconcile stopped Bot tasks before re-enabling the project')
        return self._dev_save(s, fx, 'bot_projects', dict(a, id=d['id'], owner=actor['id'],
            workflow='bot_development', version=a['version'] + 1, created_seq=s['seq'] + 1))

    def cmd_bind_development_bot(self, s, actor, a, fx, n, con):
        p, d = self._bd_project(s, actor, a['session_id'], active=False)
        self._organization_owner(s, actor, p['organization_id']); self._dev_human(actor, d)
        bot, org = self._persistent_identity(s, a['bot_id'])
        require(org['id'] == p['organization_id'], 'scope_denied', 'Bot belongs to another organization')
        principal = s['principals'].get(a['principal_id'])
        require(principal and principal.get('enabled', True) and a['principal_id'] in d['actors'],
                'unauthorized', 'Explicit participating principal required')
        self._dev_session(s, principal, d['id']); self.allowed(principal, 'work')
        self._dev_paths(a['write_scope'], True)
        require(all(in_scope(path, d['write_scope']) for path in a['write_scope']), 'scope_denied', 'Binding exceeds session scope')
        role = 'development:' + bot['id']; key = digest([d['id'], role])
        old = s.get('bot_bindings', {}).get(key, {})
        require(a['version'] == old.get('version', 0), 'stale_basis', 'Binding changed')
        require(all(not b['enabled'] or b['principal_id'] == a['principal_id'] for b in self._bot_bindings(s, bot['id'], con)),
                'unauthorized', 'Persistent Bot must retain its delegated principal across active bindings')
        rt = s.get('bot_runtimes', {}).get(bot['id'])
        require(not rt or rt['principal_id'] == a['principal_id'], 'unauthorized', 'Runtime principal differs')
        return self._dev_save(s, fx, 'bot_bindings', dict(a, id=key, role=role, workflow='bot_development',
            subject_id=bot['id'], version=a['version'] + 1, created_seq=s['seq'] + 1))

    def _bd_assign(self, s, actor, a, fx, n, con):
        p, d = self._bd_project(s, actor, a['session_id']); self.allowed(actor, 'work')
        b = self._bd_binding(s, d['id'], a['bot_id']); bot, org = self._persistent_identity(s, a['bot_id'])
        require(b['enabled'] and bot['enabled'] and org['id'] == p['organization_id'], 'mode_disabled', 'Assignee disabled')
        if not self._bd_owner(actor, p):
            sender, _, _, _ = self._bd_actor(s, actor, d['id'], a.get('requested_by_bot'))
            require(sender['can_assign'] and self._bd_subordinate(s, sender['bot_id'], b['bot_id']),
                    'unauthorized', 'Assignment exceeds the manager delegation')
        state = self._continuity_state(s, actor, a['state_id'])
        require(state['session_id'] == d['id'], 'scope_denied', 'Input belongs to another project')
        require(a['completion'], 'invalid_input', 'Task completion conditions required')
        self._dev_paths(a['write_scope'], True); self._dev_paths(a['dependencies'])
        require(all(in_scope(path, b['write_scope']) and in_scope(path, d['write_scope']) for path in a['write_scope']),
                'scope_denied', 'Task exceeds delegated scope')
        manifest = self._manifest(s, state['snapshot'])
        require(set(a['dependencies']) <= set(manifest), 'invalid_input', 'Dependency must exist in the input state')
        for dep in a['after_tasks']:
            other = self._dev_get(s, 'bot_tasks', dep)
            require(other['session_id'] == d['id'], 'scope_denied', 'Cross-project dependency')
        parent = a.get('parent_task_id')
        if parent:
            old = self._dev_get(s, 'bot_tasks', parent)
            require(old['session_id'] == d['id'] and old['status'] == 'running', 'invalid_state', 'Parent must be running')
            require(not self._bd_subordinate(s, bot['id'], old['bot_id']) or bot['id'] == old['bot_id'],
                    'invalid_input', 'Child work cannot be assigned to a parent manager')
        task = dict(a, id=uid('btask'), workflow='bot_development', subject_id=bot['id'], principal_id=b['principal_id'],
            status='pending', version=1, attempt=0, generation=d['generation'], discussion_version=0,
            dependency_hashes={path: manifest[path]['hash'] for path in a['dependencies']},
            children=[], reports=[], created_seq=s['seq'] + 1, created_at=self.clock(), author=actor['id'])
        self._dev_save(s, fx, 'bot_tasks', task)
        n.append({'type': 'bot_assignment', 'target': d['id'], 'session_id': d['id'], 'task_id': task['id'], 'zones': [d['zone']]})
        return self._bd_public(task)

    def cmd_assign_bot_task(self, s, actor, a, fx, n, con):
        require(not a.get('parent_task_id'), 'invalid_input', 'Create child work through the fenced parent report')
        return self._bd_assign(s, actor, a, fx, n, con)

    def cmd_get_bot_project(self, s, actor, a, fx, n, con):
        p, d = self._bd_project(s, actor, a['session_id'], active=False)
        return {'project': p, 'session': d, 'mentor_required': False,
                'bindings': [copy.deepcopy(b) for b in s.get('bot_bindings', {}).values()
                             if b['session_id'] == d['id'] and b.get('workflow') == 'bot_development']}

    def cmd_list_bot_tasks(self, s, actor, a, fx, n, con):
        self._bd_project(s, actor, a['session_id'], active=False)
        limit = a.get('limit', 30)
        rows = con.execute('SELECT id FROM records WHERE collection=? AND session_id=? AND id>? ORDER BY id LIMIT ?',
            ('bot_tasks', a['session_id'], a.get('after', ''), limit + 1)).fetchall()
        return {'items': [self._bd_public(s['bot_tasks'][r[0]]) for r in rows[:limit]],
                'next_cursor': rows[limit-1][0] if len(rows) > limit else None}

    def _bd_stamp(self, s, actor, task, con):
        b, bot, p, d = self._bd_actor(s, actor, task['session_id'], task['bot_id'])
        require(d['mode'] == 'execute', 'mode_disabled', 'Bot execution is not delegated')
        require(d['generation'] == task['generation'], 'stale_basis', 'Project baseline changed; assign a new task')
        require(all(in_scope(path, b['write_scope']) and in_scope(path, d['write_scope']) for path in task['write_scope']),
                'scope_denied', 'Delegated scope changed')
        require(task['principal_id'] == actor['id'], 'unauthorized', 'Task belongs to another principal')
        rt = self._runtime_fence(s, actor, bot['id'], task['runtime_fence'], con)
        dependencies = []
        for ident in task['after_tasks']:
            dep = self._dev_get(s, 'bot_tasks', ident)
            require(dep['status'] == 'completed', 'dependency_pending', 'Required task has not completed')
            dependencies.append([ident, dep['version']])
        ancestors = []; parent = bot['parent_bot_id']
        while parent:
            node = self._dev_get(s, 'persistent_bots', parent)
            ancestors.append([node['id'], node['version']]); parent = node['parent_bot_id']
        return {'project': p['version'], 'session': d['version'], 'binding': b['version'], 'bot': bot['version'],
                'organization': s['organizations'][bot['organization_id']]['version'], 'runtime': rt['version'],
                'discussion': task['discussion_version'], 'dependencies': dependencies, 'ancestors': ancestors}

    def _bd_checked(self, s, actor, a, con):
        task = self._dev_get(s, 'bot_tasks', a['task_id'])
        require(task['status'] == 'running' and task.get('fence') == a['fence'], 'stale_basis', 'Task lease replaced or stopped')
        require(task['stamp'] == self._bd_stamp(s, actor, task, con), 'stale_basis', 'Task context changed')
        return task

    def _bd_messages(self, s, task, con):
        return [self._dev_get(s, 'bot_task_messages', row[0]) for row in con.execute(
            'SELECT id FROM records WHERE collection=? AND subject_id=? ORDER BY created_seq, id', ('bot_task_messages', task['id']))]

    def cmd_get_bot_task(self, s, actor, a, fx, n, con):
        task = self._dev_get(s, 'bot_tasks', a['task_id'])
        p, d = self._bd_project(s, actor, task['session_id'], active=False)
        bot, org = self._persistent_identity(s, task['bot_id'])
        result = {'task': self._bd_public(task), 'project': p,
            'zone': d['zone'],
            'development': self.cmd_get_development_state(s, actor, {'state_id': task.get('output_state', task['state_id'])}, fx, n, con),
            'children': [self._bd_public(self._dev_get(s, 'bot_tasks', ident)) for ident in task['children']],
            'messages': self._bd_messages(s, task, con), 'bot': bot, 'organization': org,
            'limits': {'write_scope': task['write_scope'], 'constraints': d['constraints'], 'formal_adoption': False}}
        result['team'] = [{'binding': copy.deepcopy(b), 'bot': copy.deepcopy(s['persistent_bots'][b['bot_id']])}
            for b in s.get('bot_bindings', {}).values()
            if b['session_id'] == d['id'] and b.get('workflow') == 'bot_development' and b['enabled']]
        pending = list(task['children']); candidates = []; visited = set()
        while pending and len(visited) < 100:
            ident = pending.pop(0)
            if ident in visited: continue
            visited.add(ident); child = self._dev_get(s, 'bot_tasks', ident); pending.extend(child['children'])
            if child.get('change_id'):
                change = self._dev_get(s, 'dev_changes', child['change_id'])
                candidates.append({'task_id': ident, 'status': child['status'], 'change': change})
        result['candidate_changes'] = candidates
        result['candidates_truncated'] = bool(pending)
        if self._binding_access(s, actor, self._bd_binding(s, task['session_id'], task['bot_id'])):
            result['memory'] = self._persistent_memory_page(s, actor, bot, org, {'limit': 30}, con, recent=True)
        return result

    def cmd_claim_bot_task(self, s, actor, a, fx, n, con):
        task = self._dev_get(s, 'bot_tasks', a['task_id'])
        require(task['version'] == a['version'] and task['status'] == 'pending', 'conflict', 'Task is not pending at this version')
        task['runtime_fence'] = a['runtime_fence']; task['stamp'] = self._bd_stamp(s, actor, task, con)
        d = self._dev_session(s, actor, task['session_id'])
        require(sum(t['status'] == 'running' for t in self._bd_task_rows(s, d['id'], con)) < d['max_parallel'],
                'capacity_pending', 'Delegated concurrency reached')
        require(d['max_executions'] is None or d['used_executions'] < d['max_executions'], 'budget_exhausted', 'Execution allowance reached')
        d['used_executions'] += 1; self._dev_save(s, fx, 'dev_sessions', d)
        task.update(status='running', version=task['version'] + 1, attempt=task['attempt'] + 1, fence=uid('bclaim'))
        self._dev_save(s, fx, 'bot_tasks', task)
        return {'task': task, 'context': self.cmd_get_bot_task(s, actor, {'task_id': task['id']}, fx, n, con)}

    def cmd_check_bot_task(self, s, actor, a, fx, n, con):
        task = self._bd_checked(s, actor, a, con)
        return {'allowed': True, 'task_id': task['id'], 'attempt': task['attempt']}

    def cmd_checkpoint_bot_task(self, s, actor, a, fx, n, con):
        task = self._bd_checked(s, actor, a, con); self.allowed(actor, 'record')
        require(task['write_scope'], 'scope_denied', 'This assignment has no file write scope')
        if not task.get('change_id'):
            change = self.cmd_begin_change(s, actor, {'state_id': task['state_id'], 'title': task['title'],
                'purpose': task['title'], 'write_scope': task['write_scope'], 'dependencies': task['dependencies'],
                'assignee': actor['id']}, fx, n, con)
            task['change_id'] = change['id']
        change = self._dev_get(s, 'dev_changes', task['change_id'])
        result = self.cmd_checkpoint_change(s, actor, {'change_id': change['id'], 'version': change['version'],
            **{k: a[k] for k in ('snapshot', 'summary', 'rationale', 'unfinished', 'capture')}, 'work_status': 'working'}, fx, n, con)
        task.update(output_state=result['state']['id'], version=task['version'] + 1)
        self._dev_save(s, fx, 'bot_tasks', task)
        return result

    def _bd_wake_parent(self, s, task, fx, n, con):
        if not task.get('parent_task_id'): return
        parent = self._dev_get(s, 'bot_tasks', task['parent_task_id'])
        if parent['status'] == 'waiting' and all(s['bot_tasks'][i]['status'] in TERMINAL for i in parent['children']):
            parent.update(status='pending', version=parent['version'] + 1)
            self._dev_save(s, fx, 'bot_tasks', parent)
            n.append({'type': 'bot_reports_ready', 'session_id': parent['session_id'], 'target': parent['session_id'],
                'task_id': parent['id'], 'zones': [s['dev_sessions'][parent['session_id']]['zone']]})

    def cmd_finish_bot_task(self, s, actor, a, fx, n, con):
        task = self._bd_checked(s, actor, a, con); self.allowed(actor, 'record')
        report = copy.deepcopy(a['report']); b = self._bd_binding(s, task['session_id'], task['bot_id'])
        if report['status'] == 'completed':
            require(not any(m['blocking'] and m['status'] == 'open' for m in self._bd_messages(s, task, con)),
                    'dependency_pending', 'Resolve blocking discussion before completing work')
            require(all(s['bot_tasks'][i]['status'] in TERMINAL for i in task['children']),
                    'dependency_pending', 'Child work is still active')
        require(not report['assignments'] or report['status'] == 'waiting', 'invalid_input', 'Parent must wait for assigned work')
        for assignment in report['assignments']:
            child = self._bd_assign(s, actor, {**assignment, 'session_id': task['session_id'],
                'requested_by_bot': task['bot_id'], 'parent_task_id': task['id']}, fx, n, con)
            task['children'].append(child['id'])
        require(report['status'] != 'waiting' or any(s['bot_tasks'][i]['status'] not in TERMINAL for i in task['children']),
                'invalid_input', 'Waiting requires outstanding child work')
        if report['integrate_changes']:
            require(b['can_integrate'], 'unauthorized', 'Integration is not delegated to this Bot')
            require(not task.get('output_state'), 'invalid_state',
                    'Use a separate integration task for saved edits or an already integrated candidate')
            for ref in report['integrate_changes']:
                change = self._dev_get(s, 'dev_changes', ref['id'])
                require(all(in_scope(path, b['write_scope']) and in_scope(path, task['write_scope']) for path in self._changed(s,
                    s['dev_states'][change['base_state']]['snapshot'], s['dev_states'][change['head']]['snapshot'])),
                    'scope_denied', 'Integration exceeds Bot or task scope')
            integration = self.cmd_integrate_changes(s, actor, {'state_id': task['state_id'],
                'changes': report['integrate_changes'], 'summary': report['summary']}, fx, n, con)
            require(integration['integrated'], 'conflict', 'Candidate integration remains unresolved', conflicts=integration['conflicts'])
            task['output_state'] = integration['state']['id']
        if task.get('change_id'):
            change = self._dev_get(s, 'dev_changes', task['change_id'])
            if change['sharing'] == 'local' and change['checkpoints']:
                self.cmd_share_change(s, actor, {'change_id': change['id'], 'version': change['version']}, fx, n, con)
        task['reports'].append({'attempt': task['attempt'], 'report': report, 'principal_id': actor['id'],
            'state_id': task.get('output_state', task['state_id']), 'seq': s['seq'] + 1,
            'input_versions': copy.deepcopy(task['stamp']),
            'environment': copy.deepcopy(s['bot_runtimes'][task['bot_id']]['environment'])})
        task.update(status=report['status'], version=task['version'] + 1); task.pop('fence', None)
        self._dev_save(s, fx, 'bot_tasks', task)
        team = {'session_id': task['session_id'], 'version': s['bot_projects'][task['session_id']]['version']}
        state_id = task.get('output_state', task['state_id']); manifest = self._manifest(s, s['dev_states'][state_id]['snapshot'])
        memory = self._save_bot_memory(s, fx, team, actor, dict(session_id=task['session_id'], role=b['role'],
            state_id=state_id, visibility='role', observation=report['summary'], applicability='Recheck this task, state and acceptance before reuse.',
            limitations=report['unverified'], evidence=[task['id'], state_id], paths=sorted(manifest)[:100],
            assessment='inconclusive', source='bot_development', job_id=task['id']))
        org = s['organizations'][s['persistent_bots'][task['bot_id']]['organization_id']]
        if org.get('share_reflections'):
            self._bd_share_memory(s, actor, org, memory, fx)
        self._bd_wake_parent(s, task, fx, n, con)
        return {'task': self._bd_public(task), 'memory_id': memory['id'], 'formal_adoption': False}

    def _bd_share_memory(self, s, actor, org, memory, fx):
        # Internal helper only (not a registered API).
        self._dev_save(s, fx, 'organization_memories', dict(id=digest([org['id'], memory['id']]),
            organization_id=org['id'], subject_id=org['id'], memory_id=memory['id'], session_id=memory['session_id'],
            reason='Bot outcome reflection under owner sharing policy', organization_version=org['version'],
            shared_by=actor['id'], created_seq=s['seq'] + 1))

    def cmd_hold_bot_task(self, s, actor, a, fx, n, con):
        # Capture an interruption even when a dependency/profile changed; no edits or success accepted.
        task = self._dev_get(s, 'bot_tasks', a['task_id']); self._dev_session(s, actor, task['session_id'])
        require(task['principal_id'] == actor['id'] and task.get('fence') == a['fence'] and task['status'] == 'running',
                'unauthorized', 'Only the claimed executor may hold this task')
        task.update(status='held', hold_reason=a['reason'], version=task['version'] + 1)
        self._dev_save(s, fx, 'bot_tasks', task)
        return self._bd_public(task)

    def cmd_recover_bot_task(self, s, actor, a, fx, n, con):
        task = self._dev_get(s, 'bot_tasks', a['task_id'])
        require(task['version'] == a['version'] and task['status'] in {'running', 'held'}, 'conflict', 'Task changed or cannot be recovered')
        old_runtime = task['runtime_fence']; task['runtime_fence'] = a['runtime_fence']
        require(old_runtime != a['runtime_fence'], 'conflict', 'Stop the previous runtime before recovery')
        require(task['stamp'] == self._bd_stamp(s, actor, task, con), 'stale_basis', 'Changed context requires a new assignment')
        task.update(status='running', fence=uid('bclaim'), version=task['version'] + 1,
            recovery={'reason': a['confirm_stopped'], 'principal_id': actor['id'], 'at': self.clock()})
        self._dev_save(s, fx, 'bot_tasks', task)
        return {'task': task, 'context': self.cmd_get_bot_task(s, actor, {'task_id': task['id']}, fx, n, con)}

    def cmd_cancel_bot_task(self, s, actor, a, fx, n, con):
        task = self._dev_get(s, 'bot_tasks', a['task_id']); p, _ = self._bd_project(s, actor, task['session_id'], active=False)
        if not self._bd_owner(actor, p):
            b, _, _, _ = self._bd_actor(s, actor, task['session_id'], a.get('requested_by_bot'))
            require(b['can_assign'] and self._bd_subordinate(s, b['bot_id'], task['bot_id']), 'unauthorized', 'Manager authority required')
        require(task['version'] == a['version'] and task['status'] not in TERMINAL, 'conflict', 'Task already ended or changed')
        task.update(status='cancelled', version=task['version'] + 1, cancellation=a['reason']); task.pop('fence', None)
        self._dev_save(s, fx, 'bot_tasks', task); self._bd_wake_parent(s, task, fx, n, con)
        return self._bd_public(task)

    def _bd_evidence(self, s, actor, sid, refs):
        for ref in refs:
            obj = next((s[t][ref] for t in ('dev_states', 'bot_tasks', 'bot_task_messages') if ref in s.get(t, {})), None)
            require(obj and obj['session_id'] == sid, 'invalid_input', 'Evidence must belong to this project')

    def cmd_send_bot_message(self, s, actor, a, fx, n, con):
        task = self._dev_get(s, 'bot_tasks', a['task_id'])
        self._bd_actor(s, actor, task['session_id'], a['from_bot_id'])
        self._bd_evidence(s, actor, task['session_id'], a['evidence'])
        if a.get('reply_to'):
            parent = self._dev_get(s, 'bot_task_messages', a['reply_to'])
            require(parent['task_id'] == task['id'], 'scope_denied', 'Reply belongs to another task')
        msg = dict(a, id=uid('bmessage'), subject_id=task['id'], session_id=task['session_id'], status='open',
                   principal_id=actor['id'], created_seq=s['seq'] + 1)
        self._dev_save(s, fx, 'bot_task_messages', msg)
        task['discussion_version'] += 1; self._dev_save(s, fx, 'bot_tasks', task)
        return msg

    def cmd_resolve_bot_message(self, s, actor, a, fx, n, con):
        msg = self._dev_get(s, 'bot_task_messages', a['message_id'])
        p, _ = self._bd_project(s, actor, msg['session_id'])
        if not self._bd_owner(actor, p):
            self._bd_actor(s, actor, msg['session_id'], msg['from_bot_id'])
            require(actor['id'] == msg['principal_id'], 'unauthorized', 'Only author or owner can resolve')
        self._bd_evidence(s, actor, msg['session_id'], a['evidence'])
        require(msg['status'] == 'open', 'conflict', 'Already resolved')
        msg.update(status='resolved', resolution=a, resolved_by=actor['id'])
        self._dev_save(s, fx, 'bot_task_messages', msg)
        task = self._dev_get(s, 'bot_tasks', msg['task_id']); task['discussion_version'] += 1
        self._dev_save(s, fx, 'bot_tasks', task)
        return msg
