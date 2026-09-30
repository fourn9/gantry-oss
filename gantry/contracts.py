"""Machine-readable command inputs shared by HTTP, CLI and MCP."""
from .model import require

S = {'type': 'string', 'minLength': 1}
I = {'type': 'integer', 'minimum': 1}
O = {'type': 'object'}
A = {'type': 'array', 'items': S}
V = {'proposal_id': S, 'version': I}
W = {'work_id': S, 'version': I}
CHANGE = {'type': 'object', 'required': ['id', 'type', 'data'], 'properties': {
    'id': S, 'type': S, 'data': O, 'zone': S,
    'expected_revision': {'type': ['string', 'null']}, 'retracted': {'type': 'boolean'}}, 'additionalProperties': False}
CHANGES = {'type': 'array', 'minItems': 1, 'maxItems': 200, 'items': CHANGE}
CONTRACTS = {}


def register(names, properties, required=(), description=''):
    for name in names.split():
        CONTRACTS[name] = {'description': description or name.replace('_', ' '),
                          'schema': {'type': 'object', 'properties': {**properties, 'basis': O, 'intent': O},
                                     'required': list(required), 'additionalProperties': False}}


register('propose', {'title': S, 'changes': CHANGES, 'rationale': S, 'evidence': A}, ['title', 'changes'],
         'Create an immutable design candidate as a draft. This does not adopt the design.')
register('amend', {**V, 'changes': CHANGES, 'title': S, 'rationale': S, 'evidence': A}, [*V, 'changes'],
         'Create a new proposal version. Previous approvals are not reused.')
register('submit rebase withdraw commit', V, V,
         'Operate on this exact proposal version. Commit requires current owner conditions and explicit human approval.')
register('commit', {**V, 'reason': S}, V,
         'Adopt this exact candidate after current owner conditions and explicit human approval; record the optional final reason.')
register('endorse object retract_review', {**V, 'reason': S}, [*V, 'reason'], 'Record the affected owner review with its reason.')
register('review_adoption', {**V, 'reason': S, 'verdict': {'enum': ['approve', 'request_changes', 'reject']}},
         [*V, 'reason', 'verdict'], 'Human adoption review. Agent credentials cannot approve adoption.')
register('publish_candidate', {**V, 'work_id': S}, V,
         'Share this fixed candidate with authorized subscribers/dependents. It remains unadopted.')
register('resolve_conflict', {'proposal_id': S, 'reason': S}, ['proposal_id', 'reason'])
register('reserve', {'proposal_id': S, 'seconds': {'type': 'integer', 'minimum': 1, 'maximum': 3600}, 'reason': S}, ['proposal_id'])
register('release_reservation', {'reservation_id': S}, ['reservation_id'])
register('record', {'type': S, 'zone': S, 'data': O, 'id': S, 'expected_revision': S,
                    'retracted': {'type': 'boolean'}, 'source_id': S, 'source_event_id': S}, ['type', 'data'],
         'Record an artifact reference, observation, result, operation or question. Cannot change an adopted design.')
register('capture_artifact', {'files': {'type': 'object', 'additionalProperties': {'type': 'string'}},
                            'assembled_files': {'type': 'object', 'additionalProperties': {
                                'type': 'array', 'minItems': 1, 'maxItems': 64, 'items': {
                                    'type': 'object', 'required': ['revision_id', 'path'],
                                    'properties': {'revision_id': S, 'path': S}, 'additionalProperties': False}}},
                            'zone': S, 'source': O, 'capture_scope': S, 'missing_dependencies': A}, ['files'],
         'Store base64 bytes (32 MiB/file, 64 MiB/request) or assemble ordered saved file parts. No nested parts. Up to 10000 logical files and 1 GiB total.')
register('restore_artifact', {'revision_id': S, 'metadata_only': {'type': 'boolean'}}, ['revision_id'],
         'Return saved bytes or metadata_only manifest. Chunked files require read_artifact_chunk; hashes cover each part and the complete file.')
register('read_artifact_chunk', {'revision_id': S, 'path': S, 'index': {'type': 'integer', 'minimum': 0}},
         ['revision_id', 'path', 'index'], 'Read one hash-verified part, at most 32 MiB. Ordinary files have only index 0.')
register('create_work', {'title': S, 'completion_condition': S, 'zone': S, 'design_id': S,
                         'proposal_id': S, 'reviewer': S, 'inputs': A, 'dependencies': {'type': 'array', 'items': {
                             'type': 'object', 'required': ['work_id'], 'properties': {'work_id': S,
                             'condition': {'enum': ['done_required', 'published_candidate_allowed']}, 'publication_id': S},
                             'additionalProperties': False}}}, ['title', 'completion_condition'])
register('claim_work renew_claim', {**W, 'seconds': {'type': 'integer', 'minimum': 1, 'maximum': 3600}}, W)
register('handoff_work', {**W, 'notes': S}, [*W, 'notes'])
register('submit_work', {**W, 'results': A, 'notes': S}, [*W, 'results'])
register('complete_work block_work cancel_work', {**W, 'reason': S}, [*W, 'reason'])
register('resume_work', W, W)
register('reconcile_work_basis', {**W, 'action': {'enum': ['keep', 'switch']}, 'reason': S, 'publication_id': S},
         [*W, 'action', 'reason'], 'Acknowledge an upstream update, keeping the old version with a reason or switching explicitly.')
register('discuss', {'target': S, 'body': S, 'zone': S, 'reply_to': S, 'evidence': A}, ['target', 'body'],
         'Record a discussion with fixed evidence revision IDs. basis is the common event provenance object; evidence is a list of immutable references.')
register('create_improvement', {'result_id': S, 'title': S, 'changes': CHANGES, 'rationale': S,
                               'completion_condition': S, 'zone': S}, ['result_id', 'title', 'changes'])
register('state', {'as_of_seq': {'type': 'integer', 'minimum': 0}})
register('design', {'design_id': S})
register('diff', {'before': S, 'after': S}, ['after'])
register('history', {'after_seq': {'type': 'integer', 'minimum': 0}, 'limit': I})
register('impact', {'proposal_id': S}, ['proposal_id'])
register('why', {'id': S, 'max_depth': I}, ['id'])
register('outcomes', {'decision_id': S}, ['decision_id'])
register('open', {'zone': S, 'due_before': S})
register('reviews export replay', {})
register('identity', {}, description='Read the authenticated identity, without credentials.')
register('review_context', {'proposal_id': S}, ['proposal_id'],
         'Read a consistent snapshot of the candidate diff, evidence, evaluations, work and review permissions.')
register('work', {'work_id': S})
register('context', {'work_id': S, 'view': {'enum': ['full', 'focused']},
                     'entry_ids': {'type': 'array', 'minItems': 1, 'maxItems': 200, 'items': S},
                     'discussion_limit': {'type': 'integer', 'minimum': 1, 'maximum': 100},
                     'before_discussion_seq': I}, ['work_id'],
         'Read work context. Full is unchanged. Focused requires entry_ids, follows declared dependencies in the fixed design, and pages related discussion. Explicit omissions are not an impact analysis or approval.')
register('operations', {'work_item': S})
register('subscribe', {'targets': A, 'zones': A, 'types': A, 'cursor': {'type': 'integer', 'minimum': 0}})
register('unsubscribe', {'subscription_id': S}, ['subscription_id'])
register('events', {'cursor': {'type': 'integer', 'minimum': 0}, 'limit': I,
                    'wait_ms': {'type': 'integer', 'minimum': 0, 'maximum': 25000}}, description='Poll durable notices from a ledger sequence cursor; deduplicate by event_id.')
register('verify', {'checkpoint': {'type': 'object', 'required': ['ledger_id', 'seq', 'hash'],
                                   'properties': {'ledger_id': S, 'seq': I, 'hash': S}}})


def validate(value, schema, path='arguments'):
    """Validate the JSON Schema subset used above; semantic checks stay in Service."""
    if 'enum' in schema:
        require(value in schema['enum'], 'invalid_input', 'Invalid choice', path=path)
    types = schema.get('type', [])
    if isinstance(types, str): types = [types]
    checks = {'object': lambda v: isinstance(v, dict), 'array': lambda v: isinstance(v, list),
              'string': lambda v: isinstance(v, str), 'integer': lambda v: isinstance(v, int) and not isinstance(v, bool),
              'boolean': lambda v: isinstance(v, bool), 'null': lambda v: v is None}
    require(not types or any(checks[t](value) for t in types), 'invalid_input', 'Incorrect value type', path=path)
    if isinstance(value, dict):
        for name in schema.get('required', []):
            require(name in value, 'invalid_input', 'Required field missing', path=path + '.' + name)
        properties = schema.get('properties', {})
        for name, child in value.items():
            extra = schema.get('additionalProperties', True)
            require(name in properties or extra is not False, 'invalid_input', 'Unknown field', path=path + '.' + name)
            if name in properties: validate(child, properties[name], path + '.' + name)
            elif isinstance(extra, dict): validate(child, extra, path + '.' + name)
    elif isinstance(value, list):
        require(len(value) >= schema.get('minItems', 0) and len(value) <= schema.get('maxItems', len(value)),
                'invalid_input', 'Invalid list size', path=path)
        for index, child in enumerate(value): validate(child, schema.get('items', {}), path + '[' + str(index) + ']')
    elif isinstance(value, str):
        require(len(value) >= schema.get('minLength', 0), 'invalid_input', 'Value cannot be empty', path=path)
        require(len(value) <= schema.get('maxLength', len(value)), 'invalid_input', 'Value too long', path=path)
    elif isinstance(value, int) and not isinstance(value, bool):
        require(value >= schema.get('minimum', value) and value <= schema.get('maximum', value),
                'invalid_input', 'Value out of range', path=path)

# Extension registrations share the validator and command registry.
from . import development_contracts  # noqa: E402,F401
from . import continuity_contracts  # noqa: E402,F401
from . import product_contracts  # noqa: E402,F401

from . import autonomy_contracts  # noqa: E402,F401

from . import evidence  # noqa: E402,F401

register('read_artifact_batch', {'revision_id': S, 'parts': {'type': 'array', 'minItems': 1, 'maxItems': 64, 'items': {'type': 'object', 'properties': {'path': S, 'index': {'type': 'integer', 'minimum': 0}}, 'required': ['path', 'index'], 'additionalProperties': False}}}, ['revision_id', 'parts'])
register('list_artifact_files', {'revision_id': S, 'after': S, 'limit': {'type':'integer','minimum':1,'maximum':500}}, ['revision_id'])

from . import review_contracts  # noqa: E402,F401

from . import mentor_jobs  # noqa: E402,F401

register('related_review_context', {'submission_id':S, 'limit':{'type':'integer','minimum':1,'maximum':50}, 'scan_limit':{'type':'integer','minimum':1,'maximum':500}, 'session_limit':{'type':'integer','minimum':1,'maximum':20}}, ['submission_id'])
