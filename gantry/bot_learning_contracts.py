"""Bounded, Bot-authored experience decisions; not physical certification."""
from .contracts import register, S, I
from .bot_development import PAGE

TEXT = {**S, 'maxLength': 4000}
STRINGS = {'type': 'array', 'maxItems': 40, 'items': TEXT}

def obj(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}

def items(schema, maximum=40):
    return {'type': 'array', 'maxItems': maximum, 'items': schema}

PLAN = obj({'decisions': items(obj({'memory_id': S, 'use': {'enum': ['apply', 'recheck', 'reject']}, 'reason': TEXT})),
    'steps': {**STRINGS, 'minItems': 1}, 'consult_bot_ids': STRINGS, 'unknowns': STRINGS, 'rationale': TEXT})
LESSON = obj({'kind': {'enum': ['procedure', 'failure', 'preference', 'coordination']},
    'observation': TEXT, 'strategy': TEXT, 'when_to_use': TEXT, 'when_not_to_use': STRINGS,
    'paths': STRINGS, 'tags': STRINGS, 'evidence': {**STRINGS, 'minItems': 1},
    'supersedes': STRINGS, 'contradicts': STRINGS})
# Optional for compatibility with existing stored reflections and customer bridges.
LESSON['properties']['procedure_steps'] = {**STRINGS, 'type':['array','null']}
REFLECTION = obj({'lessons': items(LESSON, 10), 'feedback': items(obj({'memory_id': S,
    'outcome': {'enum': ['helpful', 'harmful', 'unknown']}, 'reason': TEXT, 'evidence': {**STRINGS, 'minItems': 1}})),
    'unknowns': STRINGS})
# Self-assessment is a reported signal, never an independent verification result.
REFLECTION['properties']['self_assessment'] = obj({'needs_independent_check': {'type': 'boolean'},
    'concerns': STRINGS, 'reason': TEXT})
REFLECTION['properties']['self_assessment']['type'] = ['object', 'null']
REF = {'task_id': S, 'fence': S}
register('prepare_bot_learning', {**REF, **PAGE, 'limit': {'type':'integer', 'minimum':1, 'maximum':40},
    'compact': {'type':'boolean'}}, list(REF))
register('submit_bot_learning_plan', {**REF, 'plan_id': S, 'output': PLAN}, [*REF, 'plan_id', 'output'])
register('complete_empty_bot_learning', {**REF, 'plan_id': S}, [*REF, 'plan_id'])
register('get_bot_learning_plan', {'plan_id': S}, ['plan_id'])
register('get_bot_reflection', {'reflection_id': S}, ['reflection_id'])
register('list_bot_reflections', {'bot_id': S, **PAGE}, ['bot_id'])
register('complete_bot_reflection', {'reflection_id': S, 'version': I, 'output': REFLECTION},
         ['reflection_id', 'version', 'output'])
