"""Scoped peer opinions about a lesson, never a physical pass or adoption."""
import copy

from .model import Fault, digest, require, uid
from .requirement_traceability import stale_refs


def source(core, s, task, pin):
    requester = core._dev_get(s, 'bot_tasks', pin['request_task_id'])
    require(requester['session_id'] == task['session_id'], 'scope_denied', 'Check within one project')
    for target in (requester, task):
        actor = core._dev_get(s, 'principals', target['principal_id'])
        require(actor.get('enabled', True) and (actor.get('expires_at') is None or core.clock() < actor['expires_at']),
            'unauthorized', 'Check participant credential revoked or expired')
        core.allowed(actor, 'read')
        require('allowed_commands' not in actor or 'get_bot_task' in actor['allowed_commands'],
            'unauthorized', 'Check participant read permission revoked')
        binding = core._bd_binding(s, target['session_id'], target['bot_id'])
        require(binding['enabled'] and binding['principal_id'] == actor['id'], 'unauthorized', 'Check participant changed')
        core._bd_actor(s, actor, target['session_id'], target['bot_id'])
        memory = core._learning_source(s, actor, target, pin['memory_id'])
    author=s['principals'][memory['principal_id']]
    require(author.get('enabled',True) and (author.get('expires_at') is None or core.clock() < author['expires_at']),
        'unauthorized', 'Lesson author credential revoked or expired')
    require(memory['session_id'] == task['session_id'], 'scope_denied', 'Check a lesson from this project')
    require(task['bot_id'] not in {requester['bot_id'], memory['bot_id']} and
        task['principal_id'] not in {requester['principal_id'], memory['principal_id']},
        'unauthorized', 'Use an independent Bot and principal, including independence from the author')
    require(digest(memory) == pin['memory_hash'], 'stale_basis', 'Lesson changed')
    require(task['state_id'] == pin['state_id'] and not task.get('output_state') and
        requester.get('output_state', requester['state_id']) == pin['state_id'], 'stale_basis', 'Check inputs changed')
    require(not stale_refs(s, pin['requirement_refs']), 'stale_basis', 'Check requirements changed')
    return memory


def prepare(core, s, actor, requester, response, memory_id, con):
    memory = core._learning_source(s, actor, requester, memory_id)
    pin = dict(memory_id=memory_id, memory_hash=digest(memory), request_task_id=requester['id'],
        state_id=response['state_id'], requirement_refs=copy.deepcopy(response.get('requirement_refs', [])))
    source(core, s, response, pin)
    pin["related_updates"] = correction_links(core, s, response, pin, con)
    return pin


def correction_links(core, s, task, pin, con):
    from .bot_learning_recall import authorized_memories
    actor = s['principals'][task['principal_id']]
    memories, cursor = authorized_memories(core, s, actor, task, con)
    require(not cursor, 'context_limit', 'Lesson correction scan incomplete')
    return sorted(m['id'] for m in memories.values() if any(
        pin['memory_id'] in m.get('lesson', {}).get(r, []) or m.get(r) == pin['memory_id']
        for r in ('supersedes', 'contradicts')))


def validate(core, s, task, con):
    pin = task.get('experience_check')
    if not pin: return
    source(core, s, task, pin)
    require(correction_links(core, s, task, pin, con) == pin['related_updates'],
        'stale_basis', 'Lesson received a correction; request a fresh check')


def view(core, s, actor, task, con):
    if not task.get('experience_check'): return None
    pin = task['experience_check']
    try:
        # Sharing a project task does not grant access to private learning context.
        requester = s['bot_tasks'][pin['request_task_id']]
        project = s['bot_projects'][task['session_id']]
        require(actor['id'] in {task['principal_id'], requester['principal_id']} or core._bd_owner(actor, project),
            'unauthorized', 'Check belongs to its participants and owner')
        memory = core._learning_source(s, actor, task, pin['memory_id'])
        validate(core, s, task, con)
    except Fault as exc:
        return {'available': False, 'reason': exc.code, 'usable': False}
    record = core._dev_get(s, 'bot_experience_checks', task['experience_check_result']) if task.get('experience_check_result') else None
    return {'available': True, 'memory': copy.deepcopy(memory), 'basis': copy.deepcopy(pin),
        'result': copy.deepcopy(record), 'limits': 'Independent identity; model biases may be shared. Not physical certification.'}


def finish(core, s, actor, task, report, fx, con):
    outcome = report.pop('experience_check', None)
    if not task.get('experience_check'):
        require(not outcome, 'invalid_input', 'No experience check was requested'); return
    require(not report['assignments'] and not report['integrate_changes'], 'scope_denied', 'Peer check is read-only')
    require((report['status'] == 'completed') == bool(outcome), 'invalid_input', 'Completed check requires an evidence-based verdict')
    if outcome:
        validate(core, s, task, con)
        require(len(set(outcome['action_ids'])) == len(outcome['action_ids']), 'invalid_input', 'Use distinct evidence actions')
        for ident in outcome['action_ids']:
            action = core._dev_get(s, 'bot_actions', ident)
            require(action['task_id'] == task['id'] and action['attempt'] == task['attempt'] and
                action['principal_id'] == actor['id'], 'invalid_input', 'Cite observations from this check attempt')
    record = dict(id=uid('bcheck'), subject_id=task['experience_check']['memory_id'],
        session_id=task['session_id'], task_id=task['id'], bot_id=task['bot_id'], principal_id=actor['id'],
        status=report['status'], basis=copy.deepcopy(task['experience_check']), report=copy.deepcopy(report),
        **copy.deepcopy(outcome or {'verdict':None,'reason':report['rationale'],'action_ids':[]}),
        created_seq=s['seq']+1, evidence_status='peer_report_not_physical_verification', formal_adoption=False)
    core._dev_save(s, fx, 'bot_experience_checks', record)
    task['experience_check_result'] = record['id']
    # Public task reports/messages cannot disclose private lesson interpretation.
    report.update(summary='Experience check '+report['status'], rationale='See the authorized experience_check result',
        unverified=['Peer opinion is not physical certification'])


def recalled(core, s, actor, task, memory, con):
    rows = con.execute('SELECT id FROM records WHERE collection=? AND subject_id=? ORDER BY created_seq DESC,id DESC LIMIT 6',
        ('bot_experience_checks', memory['id'])).fetchall()
    results = []
    for row in rows[:5]:
        record = core._dev_get(s, 'bot_experience_checks', row[0])
        checked = core._dev_get(s, 'bot_tasks', record['task_id'])
        visible = view(core, s, actor, checked, con)
        if not visible or not visible['available']: continue
        same = record['basis']['state_id'] == task.get('output_state', task['state_id']) and record['basis']['requirement_refs'] == task.get('requirement_refs', [])
        results.append({**copy.deepcopy(record), 'same_basis': same})
    return results
