"""Explicit Bot selections of existing conditional procedure lessons."""
from .contracts import register, S
from .bot_learning_contracts import REF, TEXT

register('record_bot_procedure_decision', {**REF, 'memory_id':S,
    'version':{'type':'integer', 'minimum':0},
    'status':{'enum':['candidate', 'preferred', 'retired']}, 'reason':TEXT,
    'check_ids':{'type':'array', 'maxItems':10, 'items':S}},
    [*REF, 'memory_id', 'version', 'status', 'reason', 'check_ids'])
