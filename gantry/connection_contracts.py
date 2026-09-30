from .contracts import register, S, O, A

FILES = {'type': 'object', 'additionalProperties': {'type': 'string'}}
register('request_connection', {'plan': O, 'token_hash': S, 'mentor_token_hash': S}, ['plan', 'token_hash', 'mentor_token_hash'])
register('approve_connection', {'connection_id': S, 'plan_hash': S, 'files': FILES}, ['connection_id', 'plan_hash', 'files'])
register('inspect_connection disconnect_connection', {'connection_id': S}, ['connection_id'])
register('connection_context', {})
register('authorize_connection_operation', {'operation': S, 'path': S, 'command': S, 'command_hash': S,
    'input_hash': S, 'branch': S, 'from_review': S}, ['operation', 'input_hash'])
register('complete_connection_operation', {'operation_id': S, 'status': {'enum': ['completed', 'failed', 'interrupted']},
    'summary': S, 'output_hash': S, 'details': O}, ['operation_id', 'status', 'summary', 'output_hash', 'details'])
register('connection_checkpoint', {'expected_state': S, 'files': FILES, 'summary': S, 'rationale': S, 'unfinished': A, 'branch': S},
    ['expected_state', 'files', 'summary', 'rationale', 'unfinished'])
register('connection_submit', {'question': S, 'branch': S}, ['question'])
register('connection_review', {'submission_id': S}, ['submission_id'])
register('connection_respond', {'submission_id': S, 'responses': {'type': 'array', 'items': O}, 'branch': S}, ['submission_id', 'responses'])
register('connection_assumption', {'statement': S, 'scope': A, 'evidence': A, 'dependencies': A,
    'adoption_blocker': S, 'decision_owner': {'enum': ['agent', 'human']}, 'branch': S},
    ['statement', 'scope', 'evidence', 'dependencies', 'adoption_blocker', 'decision_owner'])
register('connection_branch', {'name': S, 'base_state': S, 'purpose': S}, ['name', 'base_state', 'purpose'])
