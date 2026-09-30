"""v0.11 contracts: all surfaces share these exact schemas."""
from .contracts import register, S, I, O, A

MODE = {'enum': ['record', 'suggest', 'execute']}
CAPTURE = {'type': 'object', 'properties': {'scope': S, 'missing': A},
           'required': ['scope', 'missing'], 'additionalProperties': False}
REF = {'session_id': S}
POLICY = {'mode': MODE, 'actors': A, 'write_scope': A, 'recipes': O,
          'max_executions': {'type': 'integer', 'minimum': 0},
          'timeout_seconds': {'type': 'integer', 'minimum': 1, 'maximum': 7200},
          'max_parallel': {'type': 'integer', 'minimum': 1, 'maximum': 16}}
register('connect_development', {'title': S, 'zone': S, 'snapshot': S, 'requirements': A,
    'constraints': A, 'capture': CAPTURE, 'unverified': A, **POLICY},
    ['title', 'snapshot', 'capture', 'unverified', *POLICY])
register('configure_development', {**REF, 'version': I, 'reason': S, **POLICY},
    ['session_id', 'version', 'reason', *POLICY])
register('advance_development', {**REF, 'version': I, 'snapshot': S, 'reason': S,
    'capture': CAPTURE, 'unverified': A}, ['session_id', 'version', 'snapshot', 'reason', 'capture', 'unverified'])
register('development_state', REF)
register('mentor_context', {**REF, 'milestone_id': S}, ['session_id'])
register('signal_development', {**REF, 'kind': {'enum': ['submission', 'failure', 'dependency_changed']},
    'summary': S, 'references': A}, ['session_id', 'kind', 'summary', 'references'])
CONTRACT = {'title': S, 'input_snapshot': S, 'write_scope': A, 'recipe': S, 'recipe_hash': S,
    'expected_outputs': A, 'completion': {'type': 'object', 'properties': {
        'description': S, 'require_exit_zero': {'type': 'boolean'}, 'required_files': A,
        'verdict_file': S}, 'required': ['description', 'require_exit_zero', 'required_files'],
        'additionalProperties': False}, 'dependencies': A, 'hypothesis': S, 'rationale': S}
register('mentor_propose', {**REF, 'milestone_id': S, 'input_state': S, 'evidence': A,
    'alternatives': A, 'selection_reason': S, 'contract': {'type': 'object',
    'properties': CONTRACT, 'required': list(CONTRACT), 'additionalProperties': False}},
    ['session_id', 'milestone_id', 'contract'])
register('check_execution', {'contract_id': S}, ['contract_id'])
register('start_execution', {'contract_id': S, 'version': I}, ['contract_id', 'version'])
register('observe_execution', {**REF, 'input_snapshot': S, 'tool': S, 'conditions': O,
    'hypothesis': S, 'rationale': S, 'capture': CAPTURE},
    ['session_id', 'input_snapshot', 'tool', 'conditions', 'hypothesis', 'rationale', 'capture'])
register('record_execution_step', {'execution_id': S, 'kind': {'enum': ['edit', 'tool', 'diagnosis', 'failure', 'checkpoint']},
    'summary': S, 'snapshot': S, 'capture': CAPTURE, 'hypothesis': S, 'rationale': S},
    ['execution_id', 'kind', 'summary', 'capture', 'hypothesis', 'rationale'])
register('finish_execution', {'execution_id': S, 'output_snapshot': S, 'exit_code': {'type': 'integer'},
    'capture': CAPTURE, 'unverified': A, 'summary': S, 'hypothesis': S, 'rationale': S,
    'execution_status': {'enum': ['completed', 'failed', 'cancelled']}, 'logs_snapshot': S},
    ['execution_id', 'output_snapshot', 'exit_code', 'capture', 'unverified', 'summary', 'hypothesis',
     'rationale', 'execution_status'])
register('cancel_execution', {'execution_id': S, 'reason': S}, ['execution_id', 'reason'])
register('retry_contract', {'contract_id': S, 'version': I, 'reason': S}, ['contract_id', 'version', 'reason'])
register('reuse_contract', {'contract_id': S, 'version': I}, ['contract_id', 'version'])
register('invalidate_submission', {'contract_id': S, 'version': I, 'reason': S}, ['contract_id', 'version', 'reason'])
