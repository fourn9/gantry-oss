"""Durable Bot responsibility and explicit outcome reconciliation, not a scheduler."""
import copy

from . import bot_commitment_contracts
from .bot_development import TERMINAL
from .model import require, uid, digest

CLOSED = {'completed', 'cancelled'}


class BotCommitmentsMixin:
    def _commitment_task_chain(self, s, task):
        chain = []; seen = set(); sid = task['session_id']
        while True:
            require(task['id'] not in seen and len(chain) < 100, 'invalid_state', 'Invalid or excessive task handoff chain')
            require(task['session_id'] == sid, 'scope_denied', 'Task successor belongs to another project')
            seen.add(task['id']); chain.append(task)
            if not task.get('successor_task_id'): return chain
            task = self._dev_get(s, 'bot_tasks', task['successor_task_id'])

    def _commitment_access(self, s, actor, sid, bid, principal_id=None):
        project, _ = self._bd_project(s, actor, sid, active=False)
        if self._bd_owner(actor, project): return
        binding, _, _, _ = self._bd_actor(s, actor, sid, bid)
        require(principal_id is None or binding['principal_id'] == principal_id,
                'unauthorized', 'Commitment belongs to a previous executor')

    def _commitment_links(self, s, actor, task, ids):
        require(len(ids) == len(set(ids)), 'invalid_input', 'Distinct task links required')
        binding = self._bd_binding(s, task['session_id'], task['bot_id'])
        linked = []
        for ident in ids:
            other = self._dev_get(s, 'bot_tasks', ident)
            require(other['session_id'] == task['session_id'], 'scope_denied', 'Link work in this project')
            require(other['bot_id'] == task['bot_id'] or binding['can_assign'] and
                    self._bd_subordinate(s, task['bot_id'], other['bot_id']),
                    'unauthorized', 'Link your own work or work delegated within your hierarchy')
            for current in self._commitment_task_chain(s, other):
                owner = self._bd_binding(s, current['session_id'], current['bot_id'])
                require(owner['enabled'] and owner['principal_id'] == current['principal_id'],
                        'unauthorized', 'Linked work belongs to a disabled or reassigned executor')
                self._continuity_state(s, actor, current.get('output_state', current['state_id']))
                linked.append(current)
        return linked

    def _commitment_view(self, s, record):
        result = {k: copy.deepcopy(v) for k, v in record.items() if k != 'wake_signal'}
        result['linked_tasks'] = []
        for ident in record['task_ids']:
            chain = self._commitment_task_chain(s, s['bot_tasks'][ident]); t = chain[-1]
            result['linked_tasks'].append(dict(id=ident, bot_id=t['bot_id'], status=t['status'],
                current_task_id=t['id'], report_seq=t['reports'][-1]['seq'] if t['reports'] else None,
                state_id=t.get('output_state', t['state_id']), handoff_count=len(chain)-1))
        return result

    def _commitment_signal(self, s, record):
        # Only the responsibility and its explicitly linked outcomes can wake it.
        # Recording an unrelated report or touching working-note prose cannot.
        tasks = self._commitment_view(s, record)['linked_tasks']
        return digest({'version': record['version'], 'tasks': tasks,
            'due_at': record['due_at'] if record['due_at'] is not None and self.clock() >= record['due_at'] else None})

    def _commitment_wake_batch(self, s, actor, policy, con):
        page = self._commitment_page(s, policy['session_id'], policy['bot_id'], con,
            policy.get('commitment_cursor') or '', 100, active=True)
        pending = []
        for item in page['items']:
            self._commitment_access(s, actor, item['session_id'], item['bot_id'], item['principal_id'])
            self._commitment_links(s, actor, item, item['task_ids'])
            record = s['bot_commitments'][item['id']]
            signal = self._commitment_signal(s, record)
            if signal != record.get('wake_signal'): pending.append((record, signal))
        return pending, page['next_cursor']

    def _commitment_event(self, s, fx, record, task, kind, reason, evidence):
        return self._dev_save(s, fx, 'bot_commitment_events', dict(id=uid('bcevent'),
            subject_id=record['id'], commitment_id=record['id'], session_id=record['session_id'],
            bot_id=record['bot_id'], principal_id=task['principal_id'], task_id=task['id'],
            commitment_version=record['version'], kind=kind, status=record['status'],
            priority=record['priority'], priority_reason=record['priority_reason'],
            task_ids=copy.deepcopy(record['task_ids']), due_at=record['due_at'],
            reason=reason, evidence=copy.deepcopy(evidence), created_seq=s['seq']+1))

    def cmd_create_bot_commitment(self, s, actor, a, fx, n, con):
        task = self._bd_checked(s, actor, a, con)
        require(task.get('studio_mode') != 'ask' and not task.get('reply_request_id'),
                'scope_denied', 'Read-only consultation cannot establish responsibility')
        require(a['summary'].strip() and a['priority_reason'].strip() and
                all(v.strip() for v in a['completion']), 'invalid_input', 'Describe the responsibility and its acceptance')
        self._commitment_links(s, actor, task, a['task_ids'])
        record = dict({k: copy.deepcopy(a[k]) for k in bot_commitment_contracts.CREATE if k not in {'task_id', 'fence'}},
            id=uid('bcommit'), subject_id=task['bot_id'], bot_id=task['bot_id'], session_id=task['session_id'],
            principal_id=actor['id'], source_task_id=task['id'], version=1, status='open',
            created_seq=s['seq']+1, evidence_status='bot_owned_responsibility', formal_adoption=False)
        self._dev_save(s, fx, 'bot_commitments', record)
        self._commitment_event(s, fx, record, task, 'created', a['priority_reason'], [task['id']])
        return self._commitment_view(s, record)

    def cmd_update_bot_commitment(self, s, actor, a, fx, n, con):
        task = self._bd_checked(s, actor, a, con)
        record = self._dev_get(s, 'bot_commitments', a['commitment_id'])
        require(task['session_id'] == record['session_id'] and task['bot_id'] == record['bot_id'] and
                actor['id'] == record['principal_id'], 'unauthorized', 'Only the responsible Bot can reconcile its commitment')
        require(task.get('studio_mode') != 'ask' and not task.get('reply_request_id'),
                'scope_denied', 'Read-only consultation cannot reconcile responsibility')
        require(a['version'] == record['version'], 'stale_basis', 'Commitment changed')
        require(a['reason'].strip(), 'invalid_input', 'Explain the outcome decision')
        require(('priority' in a) == ('priority_reason' in a), 'invalid_input', 'Reprioritization requires both priority and its reason')
        if 'priority' in a:
            require(a['priority_reason'].strip(), 'invalid_input', 'Explain why this priority changed')
            record.update(priority=a['priority'], priority_reason=a['priority_reason'])
        retired = set(record['task_ids']) - set(a['task_ids'])
        require(all(t['status'] in TERMINAL for ident in retired for t in
                self._commitment_task_chain(s, s['bot_tasks'][ident])),
                'invalid_input', 'Cannot retire unfinished or held work from responsibility')
        linked = self._commitment_links(s, actor, task, a['task_ids'])
        self._bd_evidence(s, actor, task['session_id'], a['evidence'])
        if a['status'] in CLOSED:
            require(a['evidence'], 'invalid_input', 'Closing responsibility requires cited evidence')
            require(all(t['status'] in TERMINAL for t in linked),
                    'dependency_pending', 'Reconcile unfinished, held or handed-off work before closing responsibility')
        record.update({k: copy.deepcopy(a[k]) for k in ('status', 'task_ids', 'due_at', 'reason', 'evidence')})
        record.update(version=record['version']+1, decision_task_id=task['id'], updated_seq=s['seq']+1)
        # The Bot has just reconciled these exact facts. Future task outcomes or
        # a newly reached due time remain signals; this decision is not one.
        if task.get('continuation_id'):
            record['wake_signal'] = self._commitment_signal(s, record)
        self._dev_save(s, fx, 'bot_commitments', record)
        self._commitment_event(s, fx, record, task, 'reconciled', a['reason'], a['evidence'])
        return self._commitment_view(s, record)

    def cmd_get_bot_commitment(self, s, actor, a, fx, n, con):
        record = self._dev_get(s, 'bot_commitments', a['commitment_id'])
        self._commitment_access(s, actor, record['session_id'], record['bot_id'], record['principal_id'])
        limit = a.get('limit', 30)
        seq, ident = 0, ''
        if a.get('after'):
            try: number, ident = a['after'].split(':', 1); seq = int(number)
            except ValueError: require(False, 'invalid_input', 'Invalid commitment history cursor')
            require(seq >= 0 and ident, 'invalid_input', 'Invalid commitment history cursor')
        rows = con.execute('SELECT id,created_seq FROM records WHERE collection=? AND subject_id=? '
            'AND (created_seq>? OR (created_seq=? AND id>?)) ORDER BY created_seq,id LIMIT ?',
            ('bot_commitment_events', record['id'], seq, seq, ident, limit+1)).fetchall()
        return {**self._commitment_view(s, record),
            'history': [copy.deepcopy(s['bot_commitment_events'][r[0]]) for r in rows[:limit]],
            'next_cursor': str(rows[limit-1][1])+':'+rows[limit-1][0] if len(rows)>limit else None}

    def _commitment_page(self, s, sid, bid, con, after='', limit=20, active=False):
        condition = " AND COALESCE(json_extract(body,'$.value.status'),json_extract(body,'$.status')) NOT IN ('completed','cancelled')" if active else ''
        rows = con.execute('SELECT id FROM records WHERE collection=? AND session_id=? AND subject_id=? AND id>?' +
            condition + ' ORDER BY id LIMIT ?', ('bot_commitments', sid, bid, after, limit+1)).fetchall()
        return {'items': [self._commitment_view(s, s['bot_commitments'][r[0]]) for r in rows[:limit]],
            'next_cursor': rows[limit-1][0] if len(rows)>limit else None}

    def cmd_list_bot_commitments(self, s, actor, a, fx, n, con):
        self._commitment_access(s, actor, a['session_id'], a['bot_id'])
        page = self._commitment_page(s, a['session_id'], a['bot_id'], con, a.get('after', ''),
            a.get('limit', 30), a.get('active_only', False))
        for record in page['items']:
            self._commitment_access(s, actor, record['session_id'], record['bot_id'], record['principal_id'])
        return page
