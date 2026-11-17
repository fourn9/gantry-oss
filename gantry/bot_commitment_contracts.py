"""Bot-authored responsibilities reference existing work; they grant no authority."""
from .contracts import register, S
from .bot_learning_contracts import TEXT, STRINGS, REF
from .bot_development import PAGE

DUE = {'type': ['integer', 'null'], 'minimum': 1}
CREATE = {**REF, 'summary': TEXT, 'completion': {**STRINGS, 'minItems': 1},
    'priority': {'enum': ['low', 'normal', 'high']}, 'priority_reason': TEXT,
    'due_at': DUE, 'task_ids': STRINGS}
UPDATE = {**REF, 'commitment_id': S, 'version': {'type': 'integer', 'minimum': 1},
    'status': {'enum': ['open', 'working', 'waiting', 'completed', 'cancelled']},
    'task_ids': STRINGS, 'due_at': DUE, 'reason': TEXT, 'evidence': STRINGS}
register('create_bot_commitment', CREATE, list(CREATE))
register('update_bot_commitment', {**UPDATE, 'priority': CREATE['priority'], 'priority_reason':TEXT}, list(UPDATE))
register('get_bot_commitment', {'commitment_id': S, **PAGE}, ['commitment_id'])
register('list_bot_commitments', {'session_id': S, 'bot_id': S, **PAGE,
    'active_only': {'type': 'boolean'}}, ['session_id', 'bot_id'])
