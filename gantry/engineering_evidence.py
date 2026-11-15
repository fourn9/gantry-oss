"""Read-only projection of submitted engineering evidence; never a truth store."""
from collections import defaultdict, deque
import math
from .model import canonical, digest

LIMIT = 30
BUDGET = 24576


def subject(ident, namespace='hierarchy'):
    return {'namespace':namespace, 'id':ident}


def _observations(service, s, actor, state, manifest, con, seq, unknowns):
    # Callers also fingerprint the complete assessment, not just its ID. A
    # global ledger watermark would stale every in-flight review on its own
    # claim event. Aggregate only source metadata for this authorized state;
    # evidence payload retrieval remains limited to one bounded page.
    seq = con.execute('SELECT COALESCE(MAX(created_seq),0) FROM records WHERE collection=? AND state_id=? AND created_seq<=?',
        ('evidence_views',state['id'],seq)).fetchone()[0]
    page = service.cmd_query_evidence(s, actor, {'state_id':state['id'], 'as_of_seq':seq, 'limit':LIMIT}, [], None, con)
    groups = defaultdict(list); fields_scanned=0; fields_omitted=0; sources=[]
    for item in page['items']:
        view = service.cmd_get_evidence_view(s, actor, {'view_id':item['id']}, [], None, con)
        sources.append([view['id'],digest(view)])
        valid = []
        for source in view['sources']:
            artifact = service._dev_artifact(s, source['revision_id'])
            service.zone_write(actor, artifact['zone'])
            valid.append(artifact['data']['files'].get(source['path'],{}).get('hash') == source['sha256']
                and manifest.get(source['path'],{}).get('hash') == source['sha256'])
        remaining=max(0,200-fields_scanned)
        fields_omitted+=max(0,len(view['fields'])-remaining)
        for field in view['fields'][:remaining]:
            fields_scanned+=1
            source = view['sources'][field['source_index']]
            row = {k:field[k] for k in ('value','classification','method','unit','frame','time_basis') if k in field}
            row['provenance'] = {'view_id':view['id'], 'state_id':state['id'], 'field':field['name'],
                'source':source, 'request':{'view_id':view['id'], 'fields':[field['name']]}}
            row['applicable'] = valid[field['source_index']]
            reason = 'stale_source' if not row['applicable'] else 'unknown_value' if field['classification']=='unknown' else None
            if len(canonical(field['value']).encode()) > 1000:
                row.update(value=None, value_omitted=True); reason = reason or 'value_omitted'
            if reason:
                row['unknown_reason'] = reason
                unknowns.append({'reason':reason, 'view_id':view['id'], 'field':field['name'], 'state_id':state['id']})
            groups[(view['subject_id'],view['profile'],field['name'])].append(row)
        if view['missing']:
            unknowns.append({'reason':'capture_missing', 'view_id':view['id'], 'state_id':state['id'],
                'request':{'view_id':view['id']}})
    query = {'state_id':state['id'], 'as_of_seq':seq, 'limit':LIMIT}
    coverage = {'source_fingerprint':digest(sources), 'views_scanned':len(page['items']), 'fields_scanned':fields_scanned, 'fields_omitted':fields_omitted, 'as_of_seq':seq, 'request':query,
        'next_request':{**query,'after':page['next']} if page['next'] else None}
    if not page['items']: unknowns.append({'reason':'no_evidence_views', 'state_id':state['id']})
    return groups, coverage


def _finite(value):
    try: return type(value) in (int,float) and math.isfinite(value)
    except OverflowError: return False


def _signature(row):
    return canonical({k:row.get(k) for k in ('value','unit','frame','time_basis')})


def _fields(left, right, conflicts, unknowns):
    rows=[]
    for key in sorted(left.keys() | right.keys()):
        ident,profile,name=key
        row={'subject':subject(ident), 'profile':profile, 'name':name,
            'before':left.get(key,[]), 'after':right.get(key,[])}
        usable=[]; conflicting=False
        for side in ('before','after'):
            values=[v for v in row[side] if v['applicable'] and 'unknown_reason' not in v]
            usable.append(values)
            if len({_signature(v) for v in values})>1:
                conflicting=True
                conflicts.append({'subject':subject(ident),'profile':profile,'name':name,'side':side,
                    'view_ids':[v['provenance']['view_id'] for v in values]})
        a,b=usable
        if conflicting: status='conflict'
        elif not a or not b:
            status='unknown'
            unknowns.append({'reason':'insufficient_comparable_evidence','subject':subject(ident),'profile':profile,'field':name})
        elif any(a[0].get(k)!=b[0].get(k) for k in ('unit','frame','time_basis')):
            status='unknown'
            unknowns.append({'reason':'comparison_dimensions_differ','subject':subject(ident),'profile':profile,'field':name})
        else:
            status='unchanged' if _signature(a[0])==_signature(b[0]) else 'changed'
            av,bv=a[0]['value'],b[0]['value']
            if all(_finite(v) for v in (av,bv)) and _finite(bv-av):
                row['delta']=bv-av
        row['status']=status; rows.append(row)
    return rows


def _impacts(old, new, changes, baseline_id, state_id):
    changed={c['path'] for c in changes}; inputs=defaultdict(set); graph=defaultdict(list)
    edges={}
    for eng in (old,new):
        for component in eng['components']: inputs[component['id']].update(component['inputs'])
        for edge in eng.get('dependency_impact',{}).get('dependencies',[]):
            edges[canonical(edge)]=edge
    for edge in edges.values():graph[edge['prerequisite']].append(edge)
    found={}; queue=deque()
    for ident,paths in sorted(inputs.items()):
        if paths & changed:queue.append((ident,sorted(paths & changed),[]))
    partial=False
    while queue and len(found)<LIMIT:
        ident,paths,via=queue.popleft()
        if ident in found:continue
        found[ident]={'target':subject(ident,'engineering_component'),'changed_inputs':paths,'via':via,
            'check_ids':sorted({c['id'] for eng in (old,new) for c in eng['checks'] if ident in c['components']}),
            'basis':{'baseline_state_id':baseline_id,'state_id':state_id},
            'meaning':'Potential impact through declared input bindings and dependencies; checks remain authoritative'}
        if len(via)>=10 and graph[ident]:
            partial=True; continue
        for edge in graph[ident]:
            queue.append((edge['dependent'],paths,via+[edge]))
    return list(found.values()), partial or bool(queue)


def build(service, s, actor, before, after, left_manifest, right_manifest, old, new, changes, checks, con):
    unknowns=[]; conflicts=[]; seq=s['seq']
    left,lc=_observations(service,s,actor,before,left_manifest,con,seq,unknowns)
    right,rc=_observations(service,s,actor,after,right_manifest,con,seq,unknowns)
    fields=_fields(left,right,conflicts,unknowns)
    impacts,impact_partial=_impacts(old,new,changes,before['id'],after['id'])
    relevant={c for i in impacts for c in i['check_ids']}
    obligations=[{'id':c['id'],'status':c['status'],
        'components':[subject(i,'engineering_component') for i in c['components']],
        'reasons':c['reasons'],'evidence':c['evidence'],
        'request':{'state_id':after['id']}} for c in checks if c['id'] in relevant or c['required']]
    result={'version':1,'mode':'state_comparison','intent_prediction_supported':False,
        'baseline_state_id':before['id'],'state_id':after['id'],'fields':fields,'impacts':impacts,
        'check_obligations':obligations,'unknowns':unknowns,'conflicts':conflicts,
        'coverage':{'before':lc,'after':rc,'partial':bool(lc['next_request'] or rc['next_request'] or lc['fields_omitted'] or rc['fields_omitted'] or impact_partial or any(x['reason']=='value_omitted' for x in unknowns))},
        'limitations':['Submitted extraction semantics and dependency completeness are not independently certified.',
            'Equal field names within a profile/subject are declared correspondence, not native object matching.',
            'Missing observations do not prove physical addition or removal; incompatible dimensions are not converted.',
            'Dependency paths are bounded representative declared paths, not all possible physical effects.',
            'No intent-only prediction, execution permission, verification upgrade or adoption is implied.']}
    # Summary counts preserve coverage when a view contains many/large fields.
    lists=('fields','impacts','check_obligations','unknowns','conflicts')
    result['coverage']['counts']={k:len(result[k]) for k in lists}
    # Preserve the identity of scanned source views and derived rows before any
    # presentation clipping. This does not claim coverage beyond the scan limits.
    result['source_fingerprint']=digest({'baseline_state_id':before['id'],'state_id':after['id'],
        'sources':[lc['source_fingerprint'],rc['source_fingerprint']],
        'projection':{k:result[k] for k in lists}})
    for key in lists:
        if len(result[key])>LIMIT:result[key]=result[key][:LIMIT];result['coverage']['partial']=True
    while len(canonical(result).encode())>BUDGET:
        populated=[key for key in lists if result[key]]
        if not populated:break
        key=max(populated,key=lambda k:len(canonical(result[k]).encode()))
        result[key]=result[key][:len(result[key])//2];result['coverage']['partial']=True
    # Keep top-level compatibility: absence of optional native views alone does
    # not invalidate existing declared-check assessments.
    gap_codes={x['reason'] for x in unknowns if x['reason'] != 'no_evidence_views'}
    if conflicts:gap_codes.add('conflicting_observations')
    if result['coverage']['partial']:gap_codes.add('partial')
    return result, ['engineering_evidence:'+x for x in sorted(gap_codes)]
