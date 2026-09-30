"""Explicit submission/review contracts, additive to development changes."""
from .contracts import register, S, I, A

def obj(fields, required=None):
    return {'type': 'object', 'properties': fields,
            'required': list(fields) if required is None else required, 'additionalProperties': False}

MEMBER = obj({'principal_id': S, 'role': S, 'parent_role': S,
              'side': {'enum': ['user', 'gantry']}}, ['principal_id', 'role', 'side'])
register('configure_review_team', {'session_id': S, 'version': {'type': 'integer', 'minimum': 0},
    'coordinator': S, 'required_roles': A, 'members': {'type': 'array', 'minItems': 1, 'maxItems': 32, 'items': MEMBER}},
    ['session_id', 'version', 'coordinator', 'required_roles', 'members'])
register('submit_change_review', {'change_id': S, 'version': I, 'question': S,
    'stage': {'enum': ['concept', 'preliminary', 'detailed', 'integration']},
    'acceptance': A, 'required_roles': A},
    ['change_id', 'version', 'question', 'stage', 'acceptance', 'required_roles'])
register('get_change_review', {'submission_id': S}, ['submission_id'])
register('list_change_reviews', {'session_id': S, 'after': S,
    'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100}}, ['session_id'])
register('claim_change_review', {'submission_id': S,
    'lease_seconds': {'type': 'integer', 'minimum': 10, 'maximum': 900}}, ['submission_id', 'lease_seconds'])
register('submit_specialist_review', {'submission_id': S, 'role': S,
    'summary': S, 'evidence': A, 'unresolved': A}, ['submission_id', 'role', 'summary', 'evidence', 'unresolved'])
FINDING = obj({'id': S, 'summary': S, 'paths': A, 'evidence': A,
    'proposed_change': S, 'completion_condition': S})
ENGINEERING_COMPONENT = obj({'id': S, 'role': S, 'assembly': S, 'paths': A,
    'rationale': S, 'evidence': A})
ENGINEERING_CHECK = obj({'id': S, 'scope': {'enum': ['placement', 'motion', 'service',
    'connection', 'structural', 'electrical', 'thermal', 'other']}, 'components': A,
    'paths': A, 'required': {'type': 'boolean'}, 'method': S, 'acceptance': S,
    'rationale': S, 'evidence': A, 'finding_id': S})
ENGINEERING_PLAN = obj({'components': {'type': 'array', 'maxItems': 100, 'items': ENGINEERING_COMPONENT},
    'checks': {'type': 'array', 'maxItems': 100, 'items': ENGINEERING_CHECK}, 'limitations': A})
# Legacy/manual reviews may omit the plan. The automated coordinator requests it.
ENGINEERING_PLAN['type'] = ['object', 'null']
REVIEW_OUTPUT = obj({'verdict': {'enum': ['ok', 'conditional', 'changes_requested', 'insufficient_evidence']},
    'scope': S, 'rationale': S, 'evidence': A, 'unverified': A,
    'findings': {'type': 'array', 'maxItems': 100, 'items': FINDING},
    'prediction': S, 'engineering_plan': ENGINEERING_PLAN},
    ['verdict', 'scope', 'rationale', 'evidence', 'unverified', 'findings', 'prediction'])
register('complete_change_review', {'submission_id': S, 'fence': S, 'context_fingerprint': S,
    'output': REVIEW_OUTPUT}, ['submission_id', 'fence', 'context_fingerprint', 'output'])
register('respond_to_change_review', {'submission_id': S, 'candidate_state': S, 'execution_id': S,
    'responses': {'type': 'array', 'maxItems': 100, 'items': obj({'finding_id': S, 'explanation': S})}},
    ['submission_id', 'candidate_state', 'responses'])
from .development_contracts import CONTRACT
register('propose_review_work', {'submission_id': S, 'finding_ids': A,
    'contract': obj(CONTRACT)}, ['submission_id', 'finding_ids', 'contract'])

register('reflect_change_review', {'submission_id': S, 'response_id': S,
    'assessment': {'enum': ['supported', 'contradicted', 'inconclusive']},
    'observation': S, 'applicability': S, 'limitations': A},
    ['submission_id', 'response_id', 'assessment', 'observation', 'applicability', 'limitations'])
