"""Additive v1.0 development-state contracts; existing execution APIs remain valid."""
from .contracts import register, S, I, O, A
from .development_contracts import CAPTURE

NODE = {'type': 'object', 'properties': {'id': S, 'parent': S, 'title': S,
    'kind': S, 'paths': A, 'editable': {'type': 'boolean'}, 'external_uri': S},
    'required': ['id', 'title', 'kind', 'paths', 'editable'], 'additionalProperties': False}
CONTEXT = {'type': 'object', 'properties': {'requirements': A, 'constraints': A,
    'decisions': A, 'open_questions': A, 'environment': O},
    'required': ['requirements', 'constraints', 'decisions', 'open_questions', 'environment'],
    'additionalProperties': False}
WORK = {'enum': ['working', 'paused', 'completed', 'failed']}
register('initialize_continuity', {'session_id': S, 'version': I,
    'hierarchy': {'type': 'array', 'minItems': 1, 'items': NODE}, 'context': CONTEXT,
    'summary': S}, ['session_id', 'version', 'hierarchy', 'context', 'summary'])
register('get_development_state', {'state_id': S}, ['state_id'])
register('list_development_states', {'session_id': S, 'offset': {'type': 'integer', 'minimum': 0},
    'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100}}, ['session_id'])
register('begin_change', {'state_id': S, 'title': S, 'purpose': S, 'write_scope': A,
    'dependencies': A, 'assignee': S}, ['state_id', 'title', 'purpose', 'write_scope', 'dependencies', 'assignee'])
register('checkpoint_change', {'change_id': S, 'version': I, 'snapshot': S,
    'summary': S, 'rationale': S, 'unfinished': A, 'work_status': WORK,
    'capture': CAPTURE, 'context': CONTEXT, 'work_ids': A, 'engineering_review': S},
    ['change_id', 'version', 'snapshot', 'summary', 'rationale', 'unfinished', 'work_status', 'capture'])
register('share_change', {'change_id': S, 'version': I}, ['change_id', 'version'])
register('integrate_changes', {'state_id': S, 'changes': {'type': 'array', 'minItems': 1,
    'items': {'type': 'object', 'properties': {'id': S, 'version': I}, 'required': ['id', 'version'],
    'additionalProperties': False}}, 'summary': S}, ['state_id', 'changes', 'summary'])
register('select_development_state', {'state_id': S, 'version': I, 'reason': S}, ['state_id', 'version', 'reason'])
register('propose_state_adoption', {'state_id': S, 'reason': S}, ['state_id', 'reason'])
register('record_state_evaluation', {'state_id': S, 'execution_id': S, 'scope': S},
    ['state_id', 'execution_id', 'scope'])
register('record_state_restore', {'state_id': S, 'hashes': O, 'limitations': A}, ['state_id', 'hashes', 'limitations'])
register('mentor_reflect', {'session_id': S, 'contract_id': S, 'summary': S,
    'lessons': A, 'limitations': A}, ['session_id', 'contract_id', 'summary', 'lessons', 'limitations'])
