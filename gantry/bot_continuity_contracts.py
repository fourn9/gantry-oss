"""Working context, explicit standing delegation and experience/action links."""
from .contracts import register, S
from .bot_development import PAGE, LEARNING_USE
from .bot_learning_contracts import TEXT, STRINGS, REF

CONTENT = {'focus': TEXT, 'next_steps': STRINGS, 'commitments': STRINGS, 'unknowns': STRINGS,
           'watch_paths': STRINGS, 'watch_tasks': STRINGS,
           'due_at': {'type': ['integer', 'null'], 'minimum': 1}}
register('update_bot_working_state', {**REF, 'version': {'type':'integer', 'minimum':0}, **CONTENT},
         [*REF, 'version', *CONTENT])
register('get_bot_working_state', {'session_id':S, 'bot_id':S}, ['session_id','bot_id'])
register('configure_bot_continuation', {'session_id':S, 'bot_id':S,
    'version':{'type':'integer', 'minimum':0}, 'enabled':{'type':'boolean'},
    'write_scope':STRINGS, 'dependencies':STRINGS, 'completion':{**STRINGS, 'minItems':1},
    'routine': {'type': ['object', 'null'], 'additionalProperties': False,
        'properties': {'interval_ms': {'type': 'integer', 'minimum': 1},
                       'first_due_at': {'type': 'integer', 'minimum': 1}},
        'required': ['interval_ms', 'first_due_at']}},
    ['session_id','bot_id','version','enabled','write_scope','dependencies','completion'])
register('poll_bot_continuations', {'bot_id':S, 'runtime_fence':S, **PAGE}, ['bot_id','runtime_fence'])
register('record_bot_learning_use', {**REF, **LEARNING_USE}, [*REF, *LEARNING_USE])
