"""Bot-authored consultation, decisions and experience; no engineering policy."""
import copy

from .contracts import register, S, A, I
from .bot_development import PAGE
from .model import require, uid

REF = {'task_id': S, 'fence': S}
register('refresh_bot_task', REF, list(REF))
register('stop_bot_task', {**REF, 'target_task_id': S, 'version': I, 'reason': S}, [*REF, 'target_task_id', 'version', 'reason'])
register('get_bot_records', {'task_id': S, 'kind': {'enum': ['actions', 'decisions']}, **PAGE}, ['task_id', 'kind'])
register('resolve_bot_question', {**REF, 'message_id': S, 'reason': S, 'evidence': A},
         [*REF, 'message_id', 'reason', 'evidence'])
register('ask_bot', {**REF, 'to_bot_id': S, 'question': S, 'evidence': A},
         [*REF, 'to_bot_id', 'question', 'evidence'])
register('record_bot_decision', {**REF, 'verdict': {'enum': [
    'authorize', 'revise', 'select', 'continue', 'stop', 'escalate']},
    'targets': A, 'rationale': S, 'evidence': A, 'alternatives': A, 'conditions': A},
    [*REF, 'verdict', 'targets', 'rationale', 'evidence', 'alternatives', 'conditions'])
register('record_bot_action', {**REF, 'kind': S, 'details': {'type': 'object'}}, [*REF, 'kind', 'details'])
register('record_bot_experience', {**REF, 'observation': S, 'applicability': S,
    'limitations': A, 'evidence': A, 'used_memories': A},
    [*REF, 'observation', 'applicability', 'limitations', 'evidence', 'used_memories'])


class CrewCoordinationMixin:
    def cmd_stop_bot_task(self, s, actor, a, fx, n, con):
        task = self._bd_checked(s, actor, a, con)
        require(task['id'] != a['target_task_id'], 'invalid_input', 'Report your own completion status')
        target = self._dev_get(s, 'bot_tasks', a['target_task_id'])
        require(target['session_id'] == task['session_id'], 'scope_denied', 'Stop this project only')
        return self.cmd_cancel_bot_task(s, actor, {'task_id': a['target_task_id'], 'version': a['version'],
            'reason': a['reason'], 'requested_by_bot': task['bot_id']}, fx, n, con)

    def cmd_resolve_bot_question(self, s, actor, a, fx, n, con):
        task = self._bd_checked(s, actor, a, con)
        message = self._dev_get(s, 'bot_task_messages', a['message_id'])
        require(message['task_id'] == task['id'], 'scope_denied', 'Question belongs to another task')
        result = self.cmd_resolve_bot_message(s, actor, {k: a[k] for k in ('message_id', 'reason', 'evidence')}, fx, n, con)
        task['stamp'] = self._bd_stamp(s, actor, task, con)
        self._dev_save(s, fx, 'bot_tasks', task)
        return result

    def cmd_get_bot_records(self, s, actor, a, fx, n, con):
        task = self._dev_get(s, 'bot_tasks', a['task_id'])
        self._bd_project(s, actor, task['session_id'], active=False)
        table = 'bot_' + a['kind']; limit = a.get('limit', 20)
        rows = con.execute('SELECT id FROM records WHERE collection=? AND subject_id=? AND id>? ORDER BY id LIMIT ?',
                           (table, task['id'], a.get('after', ''), limit + 1)).fetchall()
        return {'items': [self._dev_get(s, table, row[0]) for row in rows[:limit]],
                'next_cursor': rows[limit-1][0] if len(rows) > limit else None}

    def _crew_records(self, s, con, table, tid):
        rows = con.execute('SELECT id FROM records WHERE collection=? AND subject_id=? ORDER BY created_seq DESC,id DESC LIMIT 20', (table, tid))
        return [self._dev_get(s, table, row[0]) for row in rows]


    def _crew_context(self, s, actor, task, con):
        consultations = [self._dev_get(s, 'bot_task_messages', i) for i in task.get('consultations', [])]
        request = self._dev_get(s, 'bot_task_messages', task['reply_request_id']) if task.get('reply_request_id') else None
        return {'consultations': consultations, 'response_request': copy.deepcopy(request),
                'decisions': self._crew_records(s, con, 'bot_decisions', task['id']),
                'actions': self._crew_records(s, con, 'bot_actions', task['id']),
                'action_history': {'total': con.execute('SELECT count(*) FROM records WHERE collection=? AND subject_id=?',
                    ('bot_actions', task['id'])).fetchone()[0], 'retrieval': 'get_bot_records', 'kind': 'actions', 'recent_limit': 20},
                'decision_history': {'retrieval': 'get_bot_records', 'kind': 'decisions', 'recent_limit': 20}}

    def cmd_refresh_bot_task(self, s, actor, a, fx, n, con):
        task = self._dev_get(s, 'bot_tasks', a['task_id'])
        require(task['status'] == 'running' and task.get('fence') == a['fence'], 'stale_basis', 'Task stopped')
        stamp = self._bd_stamp(s, actor, task, con)
        require({k: v for k, v in stamp.items() if k != 'discussion'} ==
                {k: v for k, v in task['stamp'].items() if k != 'discussion'},
                'stale_basis', 'Authority or inputs changed; create a new assignment')
        task['stamp'] = stamp
        self._dev_save(s, fx, 'bot_tasks', task)
        return self.cmd_get_bot_task(s, actor, {'task_id': task['id']}, fx, n, con)

    def cmd_ask_bot(self, s, actor, a, fx, n, con):
        task = self._bd_checked(s, actor, a, con)
        require(a['to_bot_id'] != task['bot_id'], 'invalid_input', 'Consult another Bot')
        self._bd_evidence(s, actor, task['session_id'], a['evidence'])
        response = self._bd_assign(s, actor, {'session_id': task['session_id'],
            'requested_by_bot': task['bot_id'], 'bot_id': a['to_bot_id'],
            'state_id': task.get('output_state', task['state_id']), 'kind': 'report',
            'title': a['question'], 'completion': ['Answer the recorded question with evidence and limitations'],
            'write_scope': [], 'dependencies': [], 'after_tasks': [],
            **({'candidate_id': task['candidate_id']} if task.get('candidate_id') else {})}, fx, n, con, consultation=True)
        msg = dict(id=uid('bmessage'), subject_id=task['id'], task_id=task['id'],
            session_id=task['session_id'], from_bot_id=task['bot_id'], to_bot_id=a['to_bot_id'],
            principal_id=actor['id'], body=a['question'], kind='question', blocking=True,
            evidence=a['evidence'], status='open', response_task_id=response['id'], created_seq=s['seq'] + 1)
        self._dev_save(s, fx, 'bot_task_messages', msg)
        response['reply_request_id'] = msg['id']; self._dev_save(s, fx, 'bot_tasks', response)
        task.setdefault('consultations', []).append(msg['id'])
        task['discussion_version'] += 1
        task['stamp'] = self._bd_stamp(s, actor, task, con)
        self._dev_save(s, fx, 'bot_tasks', task)
        return {'message': msg, 'response_task': self._bd_public(response)}

    def _crew_return_response(self, s, task, fx, n):
        mid = task.get('reply_request_id')
        if not mid: return
        request = self._dev_get(s, 'bot_task_messages', mid)
        if request['status'] != 'open': return
        source = self._dev_get(s, 'bot_tasks', request['task_id'])
        report = task['reports'][-1]['report'] if task['reports'] else {'summary': task.get('cancellation', task['status'])}
        answer = dict(id=uid('bmessage'), subject_id=source['id'], task_id=source['id'],
            session_id=source['session_id'], from_bot_id=task['bot_id'], to_bot_id=source['bot_id'],
            principal_id=task['principal_id'], body=report['summary'], kind='answer', blocking=False,
            reply_to=mid, evidence=[task['id']], status='open', created_seq=s['seq'] + 1)
        self._dev_save(s, fx, 'bot_task_messages', answer)
        request.update(status='answered', answer_id=answer['id']); self._dev_save(s, fx, 'bot_task_messages', request)
        source['discussion_version'] += 1
        if source['status'] == 'waiting':
            source.update(status='pending', version=source['version'] + 1)
        self._dev_save(s, fx, 'bot_tasks', source)
        n.append({'type': 'bot_response_ready', 'session_id': source['session_id'],
                  'target': source['session_id'], 'task_id': source['id']})

    def cmd_record_bot_decision(self, s, actor, a, fx, n, con):
        task = self._bd_checked(s, actor, a, con)
        b = self._bd_binding(s, task['session_id'], task['bot_id'])
        self._bd_evidence(s, actor, task['session_id'], a['evidence'])
        targets = []
        for tid in a['targets']:
            target = self._dev_get(s, 'bot_tasks', tid)
            require(target['session_id'] == task['session_id'], 'scope_denied', 'Cross-project decision')
            require(tid == task['id'] or b['can_assign'] and self._bd_subordinate(s, task['bot_id'], target['bot_id']),
                    'unauthorized', 'Decision exceeds the Bot responsibility')
            targets.append({'id': tid, 'version': target['version'],
                            'state_id': target.get('output_state', target['state_id'])})
        decision = dict({k: copy.deepcopy(v) for k, v in a.items() if k != 'fence'},
            id=uid('bdecision'), subject_id=task['id'], session_id=task['session_id'], bot_id=task['bot_id'],
            principal_id=actor['id'], input_state=task.get('output_state', task['state_id']), target_versions=targets,
            created_seq=s['seq'] + 1, formal_adoption=False)
        self._dev_save(s, fx, 'bot_decisions', decision)
        # A decision is not an access grant. Managers apply it through scoped assignments/cancellation.
        return decision

    def cmd_record_bot_action(self, s, actor, a, fx, n, con):
        task = self._bd_checked(s, actor, a, con)
        action = dict(id=uid('baction'), subject_id=task['id'], session_id=task['session_id'],
            task_id=task['id'], bot_id=task['bot_id'], principal_id=actor['id'],
            attempt=task['attempt'], input_state=task.get('output_state', task['state_id']), kind=a['kind'], details=copy.deepcopy(a['details']),
            created_seq=s['seq'] + 1)
        return self._dev_save(s, fx, 'bot_actions', action)

    def cmd_record_bot_experience(self, s, actor, a, fx, n, con):
        task = self._bd_checked(s, actor, a, con)
        self._bd_evidence(s, actor, task['session_id'], a['evidence'])
        # Validate reuse against authorized memory retrieval, never against caller-supplied text.
        bot, org = self._persistent_identity(s, task['bot_id'])
        allowed = set(); cursor = None
        while a['used_memories']:
            page = self._persistent_memory_page(s, actor, bot, org, {'limit': 100, **({'after': cursor} if cursor else {})}, con)
            allowed.update(m['id'] for m in page['items']); cursor = page['next_cursor']
            if not cursor: break
        require(set(a['used_memories']) <= allowed, 'unauthorized', 'Experience is not readable by this Bot')
        b = self._bd_binding(s, task['session_id'], task['bot_id'])
        memory = self._save_bot_memory(s, fx, {'session_id': task['session_id'],
            'version': s['bot_projects'][task['session_id']]['version']}, actor, dict(
            session_id=task['session_id'], role=b['role'], state_id=task.get('output_state', task['state_id']),
            visibility='role', observation=a['observation'], applicability=a['applicability'],
            limitations=a['limitations'], evidence=a['evidence'] or [task['id']], paths=task['dependencies'],
            assessment='inconclusive', source='bot_reflection', job_id=task['id']))
        memory['used_memories'] = a['used_memories']; self._dev_save(s, fx, 'bot_memories', memory)
        if org.get('share_reflections'): self._bd_share_memory(s, actor, org, memory, fx)
        return memory
