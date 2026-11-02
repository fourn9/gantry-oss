"""Requirement coverage derived from pinned declarations, never physical certification."""
import copy
from .model import require, identifier

REFS = {'type':'array', 'maxItems':200, 'items':{'type':'object',
    'properties':{'requirement_id':{'type':'string'}, 'revision_id':{'type':'string'}},
    'required':['requirement_id','revision_id'], 'additionalProperties':False}}


def validate_refs(s, refs):
    require(isinstance(refs,list) and len(refs)<=200, 'invalid_input', 'Invalid requirement references')
    seen=set()
    for ref in refs:
        require(isinstance(ref,dict) and set(ref)=={'requirement_id','revision_id'},
                'invalid_input','Requirement ID and revision required')
        ident=identifier(ref['requirement_id']); rid=identifier(ref['revision_id'])
        require(ident not in seen,'invalid_input','Duplicate requirement ID'); seen.add(ident)
        entry=s.get('revisions',{}).get(rid,{})
        require(entry.get('type')=='requirement' and entry.get('id')==ident and not entry.get('retracted'),
                'invalid_input','Unknown or retracted requirement revision')
        # A candidate revision exists before adoption; only the adopted lineage is normative.
        current=s.get('entries',{}).get(ident,{})
        visited=set()
        while current.get('revision_id') and current['revision_id'] not in visited:
            if current['revision_id']==rid: break
            visited.add(current['revision_id'])
            current=s['revisions'].get(current.get('previous_revision'),{})
        require(current.get('revision_id')==rid,'invalid_input','Requirement revision is not in adopted history')
    return copy.deepcopy(refs)


def _subset_refs(baseline, refs):
    if refs is None: return copy.deepcopy(baseline)
    require(isinstance(refs, list) and len(refs) <= 200, 'invalid_input', 'Invalid work requirement references')
    require(all(ref in baseline for ref in refs), 'invalid_input', 'Work requirements must belong to input state')
    require(len({ref['requirement_id'] for ref in refs}) == len(refs), 'invalid_input', 'Duplicate requirement ID')
    return copy.deepcopy(refs)


def selected_refs(s, context, explicit=None):
    return _subset_refs(validate_refs(s, context.get('requirement_refs', [])), explicit)


def stale_refs(s, refs):
    return [r['requirement_id'] for r in refs if
        s['entries'].get(r['requirement_id'],{}).get('revision_id') != r['revision_id'] or
        s['entries'].get(r['requirement_id'],{}).get('retracted')]


def assess(s, context, engineering):
    refs=validate_refs(s,context.get('requirement_refs',[])); items=[]
    for check in engineering['checks']:
        _subset_refs(refs, check.get('requirement_refs',[]))
    for ref in refs:
        entry=s['revisions'][ref['revision_id']]
        plan=entry['data'].get('verification_checks',[])
        checks={c['id']:c for c in engineering['checks'] if ref in c.get('requirement_refs',[])}
        results=[{'check_id':ident, 'status':checks.get(ident,{}).get('effective_status','unverified'),
                  'reason':'not_linked_or_missing' if ident not in checks else 'declared_check',
                  'evidence':checks.get(ident,{}).get('evidence',{}),
                  'inputs':checks.get(ident,{}).get('inputs',{})} for ident in plan]
        pinned=('unmet' if any(r['status']=='fail' for r in results) else
                'met' if results and all(r['status']=='pass' for r in results) else 'unverified')
        stale=bool(stale_refs(s,[ref]))
        items.append({**ref,'description':entry['data'].get('description',entry['data'].get('title',entry['id'])),
            'status':'needs_review' if stale else pinned,'pinned_status':pinned,
            'current_revision':s['entries'][ref['requirement_id']]['revision_id'],
            'checks':results,'gaps':(['requirement_changed_or_retracted'] if stale else [])+
                (['verification_plan_missing'] if not plan else [])+
                [r['check_id'] for r in results if r['status']!='pass']})
    return {'configured':bool(refs),'items':items,
        'unlinked_requirements':context.get('requirements',[]),
        'limitations':['Coverage is relative to explicitly linked requirements and submitted evidence; not certification or formal adoption.',
                       'Unlisted requirements and undeclared physical dependencies are not inferred.']}


def work_links(s, state, con):
    """Purpose links are not evidence that a requirement was fulfilled."""
    result=[]; truncated=False
    for table,kind in [('dev_changes','change'),('dev_contracts','contract'),('bot_tasks','bot_task')]:
        rows=con.execute('SELECT id FROM records WHERE collection=? AND session_id=? ORDER BY id LIMIT 101',
                         (table,state['session_id'])).fetchall()
        truncated = truncated or len(rows)>100
        for row in rows[:100]:
            work=s[table][row[0]]
            refs=work.get('requirement_refs',[])
            result.append({'id':work['id'],'kind':kind,'title':work.get('title',''),
                'status':work.get('status'),'requirement_refs':refs,
                'link_status':'linked' if refs else 'unlinked',
                'input_state':work.get('base_state',work.get('input_state',work.get('state_id'))),
                'stale_requirements':stale_refs(s,refs)})
    return {'work':result, 'work_truncated':truncated, 'work_limit_per_kind':100}
