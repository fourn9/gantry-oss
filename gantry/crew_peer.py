"""Bounded navigation of an already-authorized peer task response."""
import json
from .crew_json import pointer_value
from .model import digest, require

PAGE_BYTES = 14000
SECTIONS = {'reports':'/task/reports', 'own_change':'/own_change', 'actions':'/actions',
    'development':'/development', 'candidate_changes':'/candidate_changes',
    'design_assessment':'/design_assessment', 'action_history':'/action_history', 'children':'/children', 'messages':'/messages'}


def _size(value):
    return len(json.dumps(value).encode())


def _request(task_id, pointer, source=None, **page):
    return {**(source or {}), 'task_id':task_id, 'pointer':pointer, **page}


def _reference(value, task_id, pointer, source=None):
    result = {'omitted':True, 'request':_request(task_id, pointer, source),
        'type':'object' if isinstance(value, dict) else 'array' if isinstance(value, list) else 'string' if isinstance(value, str) else 'null' if value is None else 'scalar'}
    if isinstance(value, (dict, list, str)): result['total'] = len(value)
    return result


def _preview(value, task_id, pointer, source=None):
    if isinstance(value, (dict, list, str)) and (_size(value) > 2000 or
            isinstance(value, (dict, list)) and len(value) > 30):
        return _reference(value, task_id, pointer, source)
    if isinstance(value, dict):
        return {k:_preview(v, task_id, pointer+'/'+k.replace('~','~0').replace('/','~1'), source) for k,v in value.items()}
    if isinstance(value, list):
        return [_preview(v, task_id, pointer+'/'+str(i), source) for i,v in enumerate(value)]
    return value


def inspect_peer(other, args, paginate, source=None):
    task_id = args['task_id']
    if not any(k in args for k in ('pointer','offset','limit')):
        sections = {}
        for name, pointer in SECTIONS.items():
            # Only advertise actual public result sections; never enumerate private
            # memory, learning plans or working notes, even for a manager principal.
            root, *rest = pointer.strip('/').split('/')
            if root not in other or rest and rest[0] not in other[root]: continue
            value = pointer_value(other, pointer)
            sections[name] = _reference(value, task_id, pointer, source)
        task = other['task']
        return {'view':'overview', 'task':{k:task[k] for k in
            ('id','version','status','attempt','state_id','output_state','change_id') if k in task},
            'sections':sections,
            'history':{kind:{'action':'records', 'request':{'task_id':task_id,'kind':kind,'limit':10}}
                for kind in ('actions','decisions')},
            'meaning':'Saved peer results, not independent verification or adoption. Follow section request arguments with inspect. Actions are the authorized history window, not necessarily all history; recheck task version before acting.'}
    pointer = args.get('pointer', '')
    selected = pointer_value(other, pointer)
    request = {k:v for k,v in args.items() if k != 'task_id'} | {'pointer':pointer}
    page = paginate(other, request)
    start = args.get('offset', 0)
    if isinstance(selected, str):
        # Count JSON-escaped bytes, while the cursor continues to count delivered
        # characters. This also survives the stricter observe per-item budget.
        while _size(page['value']) > PAGE_BYTES - 2000:
            page['value'] = page['value'][:max(1, len(page['value'])//2)]
        end = start + len(page['value'])
        page['next_offset'] = end if end < len(selected) else None
    elif isinstance(selected, (dict, list)):
        if isinstance(selected, dict):
            page['value'] = {k:_preview(v, task_id, pointer+'/'+k.replace('~','~0').replace('/','~1'), source)
                for k,v in page['value'].items()}
        else:
            page['value'] = [_preview(v, task_id, pointer+'/'+str(start+i), source) for i,v in enumerate(page['value'])]
        # Reduce delivered entries, never silently consume omitted entries.
        while _size(page['value']) > PAGE_BYTES - 2000 and len(page['value']) > 1:
            value = page['value']; count = len(value)//2
            page['value'] = dict(list(value.items())[:count]) if isinstance(value, dict) else value[:count]
        end = start + len(page['value'])
        page['next_offset'] = end if end < len(selected) else None
    page.update(pointer=pointer, task_id=task_id, task_version=other['task'].get('version'))
    page['next_request'] = (_request(task_id, pointer, source, offset=page['next_offset'],
        **({'limit':args['limit']} if 'limit' in args else {})) if page.get('next_offset') is not None else None)
    require(_size(page) <= 18000, 'context_limit', 'Peer page exceeds delivery budget; select a shorter pointer or smaller page')
    return page


def inspect_records(records, task, args, paginate):
    # Bind nested pointers to the exact authorized page: concurrent receipts can
    # change ID-ordered pages, so refuse stale pages instead of returning another record.
    source = {k:args[k] for k in ('task_id','kind','after','limit') if k in args}
    source.setdefault('limit', 10)
    page_hash = digest(records)
    require(args.get('page_hash', page_hash) == page_hash, 'stale_basis',
        'Peer history page changed; repeat records with the same task_id/kind/after/limit without page_hash')
    source['page_hash'] = page_hash
    page = inspect_peer({'task':task, **records}, {'task_id':task['id'],
        'pointer':args.get('pointer','/items'), **({'offset':args['offset']} if 'offset' in args else {})},
        paginate, source)
    page['page_hash'] = page_hash
    page['next_cursor'] = records['next_cursor']
    page['next_records_request'] = ({**{k:v for k,v in source.items() if k != 'page_hash'}, 'after':records['next_cursor']}
        if records['next_cursor'] is not None else None)
    if args.get('pointer','/items') == '/items':
        page['items'] = page.pop('value')
        if page['next_request'] is None: page['next_request'] = page['next_records_request']
    return page
