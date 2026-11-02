"""Version-bound feedback for the next engineering decision, not a design decision.

No new store: current views are derived; Bot reports retain the view they used.
Dependencies and measurements remain attributed declarations, with explicit gaps.
"""
from .contracts import register, S
from .development import in_scope
from .engineering_context import assess as engineering
from .requirement_traceability import assess as requirements
from .model import digest, require, canonical, Fault
from .validation_map import select

register('get_design_assessment', {'baseline_state_id': S, 'state_id': S},
         ['baseline_state_id', 'state_id'])


def _definition(check):
    return {k: check.get(k) for k in ('scope', 'components', 'required', 'requirement_refs', 'physical_plan')} | {
        'input_paths': sorted(check.get('inputs', {}))}


def bounded(result):
    """Keep a complete identity but bound nested model/API context to 96 KiB."""
    if len(canonical(result).encode()) <= 98304: return result
    def compact(value, count=30):
        if isinstance(value, dict): return {k:compact(v) for k,v in list(value.items())[:count]}
        if isinstance(value, list): return [compact(v) for v in value[:count]]
        if isinstance(value, str): return value[:1000]
        return value
    view = compact(result)
    view.update(partial=True, status='needs_review',
        omissions='Nested content clipped. Inspect source states/checks with get_development_state and query_evidence; narrow work scope for a complete review.',
        item_counts={k:len(v) for k,v in result.items() if isinstance(v, (dict,list))})
    if len(canonical(view).encode()) > 98304:
        def tiny(value):
            if isinstance(value,str):return value.encode('utf-8')[:160].decode('utf-8',errors='ignore')
            if isinstance(value,list):return [tiny(x) for x in value[:3]]
            if isinstance(value,dict):return {k:tiny(v) for k,v in list(value.items())[:6]}
            return value
        def check_summary(row):
            return {k:tiny(row[k]) for k in ('id','status','before_status','required','affected','reasons') if k in row}
        view.update(changes=[tiny(x) for x in result.get('changes',[])[:20]],
            checks=[check_summary(c) for c in result.get('checks',[])[:20]],
            open_checks=[check_summary(c) for c in result.get('open_checks',[])[:20]],
            requirements={'configured':result.get('requirements',{}).get('configured',False),
                'items':[{k:tiny(r[k]) for k in ('requirement_id','revision_id','status','before_status') if k in r}
                         for r in result.get('requirements',{}).get('items',[])[:20]]},
            impact={'affected_components':[tiny(x) for x in result.get('impact',{}).get('affected_components',[])[:20]],
                    'validation_maps':result.get('impact',{}).get('validation_maps',[])},
            gaps=[tiny(x) for x in result.get('gaps',[])[:20]])
        view['omissions'] = 'Detailed derived impact omitted. Inspect exact source states with get_development_state and query_evidence; narrow the work scope before a complete review.'
    # JSON escaping and multibyte text can outgrow a character-based preview.
    while len(canonical(view).encode()) > 98304:
        lists = [view.get(k,[]) for k in ('changes','checks','open_checks','gaps')]
        lists += [view.get('requirements',{}).get('items',[]),
                  view.get('impact',{}).get('affected_components',[])]
        if not any(lists): break
        for items in lists: del items[len(items)//2:]
    return view


def state_maps(s, state_id):
    records = s.get('validation_maps', {})
    if hasattr(records, 'con'):
        ids = [r[0] for r in records.con.execute(
            'SELECT id FROM records WHERE collection=? AND state_id=? ORDER BY id LIMIT 2',
            ('validation_maps',state_id))]
        return [records[i] for i in ids]
    return sorted((m for m in records.values() if m['state_id']==state_id),key=lambda m:m['id'])[:2]


def map_fingerprint(service, s, state_ids):
    basis=[]
    for sid in state_ids:
        for mp in state_maps(s,sid):
            sources=[]
            for vid in mp['evidence_views']:
                view=service._dev_get(s,'evidence_views',vid)
                for src in view['sources']:
                    try:
                        artifact=service._dev_artifact(s,src['revision_id'])
                        valid=artifact['data']['files'].get(src['path'],{}).get('hash')==src['sha256']
                    except Fault: valid=False
                    sources.append([vid,src,valid])
            basis.append([mp,sources])
    return digest(basis) if basis else None


def applicable_map(service, s, actor, state, manifest, gaps):
    maps=state_maps(s,state['id'])
    if len(maps)!=1:
        if maps:gaps.append('dependency_map_ambiguous:'+state['id'])
        return None
    mp=maps[0]; applicable=True
    for vid in mp['evidence_views']:
        view=service._dev_get(s,'evidence_views',vid)
        for src in view['sources']:
            artifact=service._dev_artifact(s,src['revision_id'])
            service.zone_write(actor,artifact['zone'])
            if manifest.get(src['path'],{}).get('hash')!=src['sha256']:
                gaps.append('dependency_map_source_stale:'+src['path']); applicable=False
        gaps.extend('dependency_map_capture:'+x for x in view['missing'])
    return mp if applicable else None


def adjust_impacted_checks(eng, causes, subjects):
    for c in eng['checks']:
        paths=set().union(*(causes.get(i,set()) for i in set(c['components'])|set(subjects.get(c['id'],[]))))
        missing=paths-set(c['inputs'])
        c['impact_gaps']=['impact_input_unbound:'+p for p in sorted(missing)]
        if missing and c['effective_status'] in {'pass','not_applicable'}:c['effective_status']='unknown'


def build(service, s, actor, baseline_id, state_id, con):
    before = service._continuity_state(s, actor, baseline_id)
    after = service._continuity_state(s, actor, state_id)
    require(before['session_id'] == after['session_id'], 'scope_denied', 'Compare states in the same project')
    left, right = [service._manifest(s, x['snapshot']) for x in (before, after)]
    paths = sorted(p for p in set(left) | set(right) if left.get(p, {}).get('hash') != right.get(p, {}).get('hash'))
    changes = [{'path': p, 'before': left.get(p, {}).get('hash'), 'after': right.get(p, {}).get('hash'),
                'kind': 'added' if p not in left else 'removed' if p not in right else 'modified'} for p in paths]
    old, new = [engineering(x['context'], m) for x, m in ((before, left), (after, right))]
    gaps = []
    # Path/component and check-input links work without a spatial/dependency map.
    affected = set(); reasons = {}; mapped_paths = set(); causes = {}
    design_inputs = {p for e in (old,new) for c in e['components'] for p in c['inputs']}
    evidence_paths = {p for e in (old,new) for c in e['checks'] for p in c.get('evidence',{})}
    causal_paths = set(paths) - (evidence_paths - design_inputs)
    def touch(ident, why):
        affected.add(ident); reasons.setdefault(ident, set()).add(why)
    for state, eng in ((before, old), (after, new)):
        for node in state['hierarchy']:
            hits = [p for p in causal_paths if in_scope(p, node['paths'])]
            if hits:
                touch(node['id'], 'hierarchy_paths_changed'); mapped_paths.update(hits)
                causes.setdefault(node['id'],set()).update(hits)
        for component in eng['components']:
            hits = set(paths) & set(component['inputs'])
            if hits:
                touch(component['id'], 'component_inputs_changed'); mapped_paths.update(hits)
                causes.setdefault(component['id'],set()).update(hits)
        for check in eng['checks']:
            if set(paths) & (set(check['inputs']) | set(check.get('evidence', {}))):
                for ident in check['components']: touch(ident, 'check_input_or_evidence:' + check['id'])

    maps = [applicable_map(service,s,actor,st,m,gaps) for st,m in ((before,left),(after,right))]
    map_result = None
    if all(maps):
        seeds = {i for i in set(before['components']) | set(after['components'])
                 if before['components'].get(i) != after['components'].get(i)}
        subjects = {n['id'] for st in (before,after) for n in st['hierarchy']}
        seeds.update(affected & subjects)
        if any(maps[0][k] != maps[1][k]
                for k in ('dependencies', 'geometry', 'coverage', 'checks')):
            seeds.update(before['components']); seeds.update(after['components'])
        map_result = select(maps[0], maps[1], seeds)
        for ident in map_result['affected']:
            for why in map_result['reasons'].get(ident, []): touch(ident, why)
        gaps.extend(map_result['gaps'])
    else: gaps.append('dependency_map_missing')

    # Propagate changed causes, not merely affected IDs, through declared paths.
    if map_result:
        for _ in range(len(affected)):
            updated=False
            for target, why in map_result['reasons'].items():
                for reason in why:
                    if not reason.startswith(('depends_on:','swept_proximity:')):continue
                    source=reason.split(':',1)[1]; old_causes=causes.get(target,set())
                    new_causes=old_causes|causes.get(source,set())
                    if new_causes!=old_causes:causes[target]=new_causes;updated=True
            if not updated:break
    subjects={}
    for c in (map_result or {}).get('checks',[]):subjects.setdefault(c['id'],set()).update(c['subjects'])
    adjust_impacted_checks(new,causes,subjects)
    cover_before, cover_after = [requirements(s,x['context'],e) for x,e in ((before,old),(after,new))]
    old_requirements = {x['requirement_id']:x for x in cover_before['items']}
    current_requirements = {x['requirement_id']:x for x in cover_after['items']}
    requirement_rows = [{**x,'before_status':old_requirements.get(x['requirement_id'],{}).get('status')}
                        for x in cover_after['items']]
    for ident in old_requirements.keys()-current_requirements.keys():gaps.append('requirement_removed:'+ident)
    for item in requirement_rows:
        if item['status']!='met':gaps.append('requirement:'+item['requirement_id']+':'+item['status'])
    if not cover_after['configured']:gaps.append('requirements_unlinked')

    previous = {c['id']: c for c in old['checks']}; current = {c['id']: c for c in new['checks']}
    planned = {c['id'] for c in (map_result or {}).get('checks', [])}
    planned.update(c['check_id'] for item in cover_after['items'] for c in item['checks'])
    checks = []; open_checks = []
    for ident in sorted(previous.keys() | current.keys() | planned):
        a, b = previous.get(ident), current.get(ident)
        check = b or a or {}; why = []
        impacted = ident in planned or bool(set(check.get('components', [])) & affected)
        if not b: why.append('check_removed' if a else 'check_missing')
        if a and b and _definition(a) != _definition(b): why.append('check_definition_changed')
        if b:
            why.extend('stale_input:' + p for p in b['stale_inputs'])
            why.extend('stale_evidence:' + p for p in b['stale_evidence'])
            why.extend(b.get('physical_result', {}).get('reasons', []))
            why.extend(b.get('impact_gaps', []))
        status = b.get('effective_status', 'unverified') if b else 'unverified'
        if status not in {'pass','not_applicable'}: why.append('check_' + status)
        required = bool(check.get('required') or (a or {}).get('required') or ident in planned)
        row = {'id': ident, 'status': status, 'before_status': (a or {}).get('effective_status'),
               'required': required, 'affected': impacted, 'components': check.get('components', []),
               'requirement_refs': check.get('requirement_refs', []), 'reasons': sorted(set(why)),
               'evidence': check.get('evidence', {}),
               'comparisons': check.get('physical_result', {}).get('comparisons', [])}
        checks.append(row)
        if why and (required or impacted): open_checks.append(row)
    gaps.extend('check:' + c['id'] for c in open_checks)
    unmapped = sorted(causal_paths - mapped_paths)
    if unmapped: gaps.append('changed_paths_without_component_mapping')
    gaps.extend('capture:' + str(x) for x in after['capture'].get('missing', []))
    result = {'baseline_state_id': baseline_id, 'state_id': state_id,
        'changes': changes, 'change_count': len(changes),
        'impact': {'affected_components': sorted(affected),
            'reasons': {k: sorted(v) for k, v in sorted(reasons.items())},
            'validation_maps': [m['id'] if m else None for m in maps],
            'unmapped_paths': unmapped, 'scope': 'Declared paths/check inputs, plus explicitly state-bound dependency maps'},
        'requirements': {**cover_after, 'items': requirement_rows}, 'checks': checks, 'open_checks': open_checks,
        'gaps': sorted(set(gaps)), 'status': 'needs_review' if gaps else 'declared_checks_satisfied',
        'formal_adoption': False, 'partial': False,
        'limitations': ['Declared dependencies may be incomplete; test adequacy requires engineering judgment.',
                       'Tool exit status alone is not requirement evidence; no physical certification or automatic adoption.']}
    result['id'] = 'assessment_' + digest(result)
    return bounded(result)


class DesignAssessmentMixin:
    def cmd_get_design_assessment(self, s, actor, a, fx, n, con):
        return build(self, s, actor, a['baseline_state_id'], a['state_id'], con)
