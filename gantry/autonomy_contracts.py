"""v1.1 autonomous analysis: delegated, leased, bounded, and replayable."""
from .contracts import register, S, O, A
from .development_contracts import POLICY, CONTRACT


def obj(properties, required=None):
    return {'type': 'object', 'properties': properties, 'required': list(properties) if required is None else required,
            'additionalProperties': False}


def integer(low, high):
    return {'type': 'integer', 'minimum': low, 'maximum': high}


PROVIDER = obj({'kind': {'enum': ['disabled', 'fixture', 'external', 'openai']}, 'model': S,
    'max_input_tokens': integer(1024, 200000), 'max_output_tokens': integer(256, 16000),
    'timeout_seconds': integer(5, 120), 'input_microusd_per_million': integer(0, 10**10),
    'output_microusd_per_million': integer(0, 10**10)})
LIMITS = {'max_daily_calls': integer(1, 10000), 'max_daily_microusd': integer(0, 10**12),
    'max_monthly_microusd': integer(0, 10**13), 'max_active_sessions': integer(1, 100),
    'max_sessions_per_day': integer(1, 1000), 'max_replans_per_session': integer(1, 100),
    'max_daily_executions': integer(0, 10000), 'cooldown_seconds': integer(1, 86400),
    'max_attempts_per_trigger': integer(1, 10)}
register('configure_automation', {'project_id': S, 'version': integer(0, 10**9),
    'enabled': {'type': 'boolean'}, 'analysts': A, 'provider': PROVIDER,
    'session_template': obj(POLICY), **LIMITS, 'reason': S},
    ['project_id', 'version', 'enabled', 'analysts', 'provider', 'session_template', *LIMITS, 'reason'])
register('automation_status', {'project_id': S})
register('claim_analysis', {'project_id': S, 'worker_id': S, 'kind': {'enum': ['triage', 'mentor']}},
    ['project_id', 'worker_id', 'kind'])
register('get_analysis', {'analysis_id': S}, ['analysis_id'])
USAGE = obj({'input_tokens': integer(0, 10**7), 'output_tokens': integer(0, 10**7)})
register('complete_analysis', {'analysis_id': S, 'fence': S, 'output': O,
    'usage': USAGE, 'provider_response_id': S}, ['analysis_id', 'fence', 'output'])
register('fail_analysis', {'analysis_id': S, 'fence': S, 'code': S}, ['analysis_id', 'fence', 'code'])
TRIAGE_DECISION = obj({'action': {'enum': ['start', 'attach', 'defer', 'dismiss']},
    'signal_ids': {'type': 'array', 'minItems': 1, 'maxItems': 40, 'items': S},
    'title': S, 'goal': S, 'rationale': S, 'evidence': {'type': 'array', 'minItems': 1, 'items': S},
    'priority': {'enum': ['high', 'normal', 'low']}, 'session_id': {'type': ['string', 'null']}})
TRIAGE_OUTPUT = obj({'decisions': {'type': 'array', 'minItems': 1, 'maxItems': 40, 'items': TRIAGE_DECISION}})
MENTOR_PROPOSAL = obj({'input_state': S, 'evidence': A, 'alternatives': A,
    'selection_reason': S, 'contract': obj(CONTRACT)})
MENTOR_OUTPUT = obj({'action': {'enum': ['propose', 'wait', 'no_action']}, 'rationale': S,
    'evidence': {'type': 'array', 'minItems': 1, 'items': S},
    'proposal': {'type': ['object', 'null'], 'properties': MENTOR_PROPOSAL['properties'],
                 'required': MENTOR_PROPOSAL['required'], 'additionalProperties': False}})
