"""Structured Bot dispositions reuse assignments and consultations, not a scheduler."""
import copy
from collections import deque
from .contracts import S, A
from .requirement_traceability import REFS, _subset_refs
from .model import require

FOLLOWUPS = {'type': ['array', 'null'], 'maxItems': 40, 'items': {'type': 'object',
    'properties': {'id': S, 'summary': S, 'disposition': {'enum': ['fix', 'verify', 'consult', 'defer']},
        'reason': S, 'evidence': A, 'requirement_refs': REFS,
        'assignment_index': {'type': ['integer', 'null'], 'minimum': 0},
        'message_id': {'type': ['string', 'null']}},
    'required': ['id', 'summary', 'disposition', 'reason', 'evidence', 'requirement_refs'],
    'additionalProperties': False}}


def validate_followups(service, s, actor, task, report):
    items = report.get('followups') or []
    require(len({i['id'] for i in items}) == len(items), 'invalid_input', 'Distinct follow-up IDs required')
    for item in items:
        require(item['summary'].strip() and item['reason'].strip(), 'invalid_input', 'Follow-up purpose and reason required')
        service._bd_evidence(s, actor, task['session_id'], item['evidence'])
        _subset_refs(task.get('requirement_refs', []), item['requirement_refs'])
        disposition = item['disposition']; index = item.get('assignment_index'); message = item.get('message_id')
        if disposition in {'fix', 'verify'}:
            assignments = report['assignments']
            require(index is not None and index < len(assignments) and not message,
                    'invalid_input', 'Executable follow-up requires a report assignment')
            assignment = assignments[index]
            require(assignment['kind'] in ({'verify'} if disposition == 'verify' else {'develop', 'integrate'}),
                    'invalid_input', 'Follow-up disposition and assignment kind differ')
            require(all(ref in assignment.get('requirement_refs', task.get('requirement_refs', [])) for ref in item['requirement_refs']),
                    'invalid_input', 'Follow-up requirement must reach the assigned work')
        elif disposition == 'consult':
            require(index is None and message in task.get('consultations', []),
                    'invalid_input', 'Consult follow-up requires this task\'s actual consultation')
        else:
            require(index is None and not message, 'invalid_input', 'Deferred work cannot claim a dispatched assignment')


def bind_followups(report, children):
    for item in report.get('followups') or []:
        if item['disposition'] in {'fix', 'verify'}:
            item['assigned_task_id'] = children[item['assignment_index']]


def view(s, task):
    """Keep residual work visible when a report says completed; never infer closure."""
    result = []; pending = deque([task['id']]); visited = set(); truncated = False
    while pending and len(visited) < 100:
        ident = pending.popleft()
        if ident in visited: continue
        visited.add(ident); source = s['bot_tasks'][ident]; pending.extend(source['children'])
        truncated |= len(source['reports']) > 100
        for report in reversed(source['reports'][-100:]):
            for item in report['report'].get('followups') or []:
                if len(result) == 500:
                    return {'followups': result, 'followups_truncated': True}
                row = copy.deepcopy(item)
                child = s['bot_tasks'].get(item.get('assigned_task_id'))
                message = s.get('bot_task_messages', {}).get(item.get('message_id'))
                status = ('work_completed_review_required' if child and child['status'] == 'completed' else
                          'work_'+child['status'] if child else
                          'consultation_'+message['status'] if message else 'deferred')
                result.append({**row, 'source_task_id': source['id'], 'source_attempt': report['attempt'],
                    'state_id': report['state_id'], 'status': status, 'product_complete': False})
    return {'followups': result, 'followups_truncated': truncated or bool(pending)}
