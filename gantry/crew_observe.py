"""Bounded read-only requests; no task dispatch or engineering decision policy."""
import json
from .contracts import validate
from .model import Fault, canonical, digest, require

READ_ACTIONS = ['read', 'context', 'inspect', 'inspect_json']
OBSERVE_SCHEMA = {'type':'object','properties':{'requests':{
    'type':'array','minItems':1,'maxItems':4,'items':{'type':'object','properties':{
        'action':{'enum':READ_ACTIONS},'arguments':{'type':'object'}},
        'required':['action','arguments'],'additionalProperties':False}}},
    'required':['requests'],'additionalProperties':False}


def observe(args, schemas, execute):
    validate(args, OBSERVE_SCHEMA)
    # Validate the complete batch before any retrieval. A nested mutation cannot
    # enter the broker through this route, even in a write-capable task.
    for request in args['requests']:
        validate(request['arguments'], schemas[request['action']])
        require(len(json.dumps(request).encode()) <= 4096, 'invalid_input', 'Observation request exceeds 4 KiB')
    items = []
    for index, request in enumerate(args['requests']):
        action = request['action']; arguments = dict(request['arguments'])
        if action == 'read': arguments['length'] = min(arguments.get('length', 2000), 2000)
        try: result = execute(action, arguments)
        except (Fault, FileNotFoundError) as exc:
            if isinstance(exc, Fault) and exc.code not in {'invalid_input','not_found','scope_denied','capture_incomplete'}: raise
            # Deliberately omit source-derived diagnostics here. A focused read
            # can retrieve them; the batch receipt preserves a nonsecret reason.
            result = {'error':exc.code if isinstance(exc, Fault) else 'not_found'}
        # Match result_preview's escaping/accounting, including non-ASCII text.
        if len(json.dumps(result).encode()) > 18000:
            result = {'truncated':True,'sha256':digest(result),
                'message':'Use this request with a narrower pointer/page. No page cursor was consumed.'}
        items.append({'index':index,'request':{**request,'arguments':arguments},'result':result})
    return {'items':items,'atomic_snapshot':False,
        'meaning':'Independent observations with individual versions; recheck mutable peer state before acting.'}


def observation_actions(actions):
    """Expand durable batch receipts for the same source-checking as single reads."""
    for source_index, action in enumerate(actions):
        action = {**action, '_source_action_index':source_index}
        if action.get('kind') != 'observe':
            yield action; continue
        details = action.get('details', {}); result = details.get('result', {})
        if not isinstance(result, dict) or not isinstance(result.get('items'), list):
            yield action; continue
        # Core actions are newest-first; batch subrequests ran in forward order.
        # Scan newest subrequest first, then the consumer renders time order.
        yield action  # Count even an empty batch in scan coverage.
        for index, item in reversed(list(enumerate(result['items'][:4]))):
            if not isinstance(item, dict): continue
            request = item.get('request', {})
            if not isinstance(request, dict) or request.get('action') not in READ_ACTIONS: continue
            yield {**action, 'kind':request['action'], 'observation_index':index,
                'details':{**details,'arguments':canonical(request.get('arguments', {})), 'result':item.get('result', {})}}
