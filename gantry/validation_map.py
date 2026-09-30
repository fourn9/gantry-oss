"""Conservative cross-domain validation selection, never a physical approval."""
import copy
from collections import defaultdict,deque
from .contracts import register,S,A,O
from .model import require,uid,digest

register('record_validation_map',{'state_id':S,'evidence_views':A,'dependencies':{'type':'array','maxItems':10000,'items':O},
    'geometry':{'type':'array','maxItems':2000,'items':O},'checks':{'type':'array','maxItems':500,'items':O},
    'coverage':O},['state_id','evidence_views','dependencies','geometry','checks','coverage'])
register('plan_validation',{'before_map':S,'after_map':S},['before_map','after_map'])
register('get_validation_plan',{'plan_id':S},['plan_id'])


def box(g):
    require(g.get('unit') in {'m','mm'} and isinstance(g.get('frame'),str) and g['frame'], 'invalid_input','Explicit spatial unit/frame required')
    b=g.get('swept_bounds')
    require(isinstance(b,list) and len(b)==6 and all(type(v) in (int,float) for v in b), 'invalid_input','Six swept min/max bounds required')
    require(all(b[i]<=b[i+3] for i in range(3)),'invalid_input','Invalid swept bounds')
    scale=.001 if g['unit']=='mm' else 1.
    return [v*scale for v in b]


def select(before,after,changed):
    """Dependency traversal includes removed edges. Spatial proximity is broad phase.

    SQLite RTree supplies candidates, including swept extents. Source frame must
    match; an absent transformation is a gap, not assumed identity.
    """
    import sqlite3
    edges=defaultdict(set);affected=set(changed);reasons=defaultdict(list);gaps=[]
    for mp in (before,after):
        for e in mp['dependencies']:edges[e['prerequisite']].add(e['dependent'])
    for x in changed:reasons[x].append('component_or_context_changed')
    q=deque(sorted(changed))
    # Geometry for both versions avoids hiding the region vacated by a change.
    geometries=[g for mp in (before,after) for g in mp['geometry']]
    db=sqlite3.connect(':memory:')
    try:
        db.execute('CREATE VIRTUAL TABLE spatial USING rtree(id,x0,x1,y0,y1,z0,z1)')
        for i,g in enumerate(geometries):
            b=box(g);db.execute('INSERT INTO spatial VALUES (?,?,?,?,?,?,?)',(i,b[0],b[3],b[1],b[4],b[2],b[5]))
        by_subject=defaultdict(list)
        for i,g in enumerate(geometries):by_subject[g['subject_id']].append(i)
        visited=set()
        while q:
            subject=q.popleft()
            if subject in visited:continue
            visited.add(subject)
            if len(visited)>2000:gaps.append('dependency_exploration_limit');break
            nexts=set(edges[subject])
            for other in nexts:reasons[other].append('depends_on:'+subject)
            for i in by_subject[subject]:
                g=geometries[i];b=box(g)
                for row in db.execute('SELECT id FROM spatial WHERE x1>=? AND x0<=? AND y1>=? AND y0<=? AND z1>=? AND z0<=?',(b[0],b[3],b[1],b[4],b[2],b[5])):
                    target=geometries[row[0]]
                    if target['frame']!=g['frame']:continue
                    other=target['subject_id']
                    if other!=subject:nexts.add(other);reasons[other].append('swept_proximity:'+subject)
            for other in nexts-affected:affected.add(other);q.append(other)
        for mp in (before,after):
            frames={g['frame'] for g in mp['geometry']}
            if len(frames)>1 and changed:gaps.append('unresolved_coordinate_transforms')
            for x in affected:
                coverage=mp['coverage'].get(x,{})
                if coverage.get('dependencies')!='declared_complete':gaps.append('unknown_dependencies:'+x)
                if coverage.get('spatial') not in {'swept_envelope','not_applicable'}:gaps.append('unknown_swept_coverage:'+x)
                if coverage.get('spatial')=='swept_envelope' and not any(g['subject_id']==x for g in mp['geometry']):gaps.append('missing_swept_geometry:'+x)
    finally:db.close()
    # Union previous/new checks: deleting a check does not silently discharge it.
    checks={};retired=[]
    after_checks={c['id']:c for c in after['checks']}
    for c in before['checks']:
        if c['id'] not in after_checks or c!=after_checks[c['id']]:retired.append(c['id'])
    for mp in (before,after):
        for c in mp['checks']:
            if set(c['subjects'])&affected or c['kind']=='integration' and changed:checks[digest(c)]=c
    if changed and not any(c['kind']=='integration' for c in checks.values()):gaps.append('missing_integration_check')
    if retired:gaps.extend('check_definition_changed:'+x for x in retired)
    for x in affected:
        if not any(x in c['subjects'] for c in checks.values()):gaps.append('no_check_for:'+x)
    ordered=sorted(checks.values(),key=lambda c:(c['kind']=='integration',c['estimated_cost_ms'],c['id']))
    return {'changed':sorted(changed),'affected':sorted(affected),'reasons':{k:sorted(set(v)) for k,v in reasons.items()},
        'checks':ordered,'gaps':sorted(set(gaps)),'status':'needs_review' if gaps else 'planned',
        'verification':'unverified','execution_permission':False,'adoption':'unadopted',
        'coverage_basis':'adapter-submitted relationships and swept envelopes; not proof of complete physical dependencies'}


class ValidationMixin:
    def cmd_record_validation_map(self,s,actor,a,fx,n,con):
        self.allowed(actor,'record');state=self._continuity_state(s,actor,a['state_id'])
        subjects={x['id'] for x in state['hierarchy']}
        require(len(subjects)<=2000,'invalid_input','Validation hierarchy exceeds 2000 subjects')
        for vid in a['evidence_views']:
            v=self._dev_get(s,'evidence_views',vid)
            require(v['state_id']==state['id'],'stale_basis','Evidence belongs to another state')
        require(a['evidence_views'],'invalid_input','Native source evidence required')
        for e in a['dependencies']:
            require(set(e)=={'prerequisite','dependent','kind'} and e['prerequisite'] in subjects and e['dependent'] in subjects and e['kind'] in {'physical','electrical','control','generated_from','interface'},'invalid_input','Typed dependency with known subjects required')
        for g in a['geometry']:
            require(g.get('subject_id') in subjects,'invalid_input','Unknown geometry subject');box(g)
        require(set(a['coverage'])<=subjects,'invalid_input','Unknown coverage subject')
        for cov in a['coverage'].values():
            require(set(cov)=={'dependencies','spatial'} and cov['dependencies'] in {'declared_complete','partial','unknown'} and cov['spatial'] in {'swept_envelope','sampled','unknown','not_applicable'},'invalid_input','Explicit coverage required')
        ids=[]
        for c in a['checks']:
            require(set(c)=={'id','subjects','kind','recipe_hash','estimated_cost_ms'} and isinstance(c['subjects'],list) and set(c['subjects'])<=subjects and c['subjects'] and c['kind'] in {'local','integration'} and type(c['estimated_cost_ms']) is int and c['estimated_cost_ms']>=0 and isinstance(c['recipe_hash'],str) and len(c['recipe_hash'])==64,'invalid_input','Invalid check contract')
            ids.append(c['id'])
        require(len(set(ids))==len(ids),'invalid_input','Duplicate check ID')
        mp={k:copy.deepcopy(v) for k,v in a.items() if k not in {'basis','intent'}}
        mp.update(id=uid('validationmap'),session_id=state['session_id'],actor=actor['id'],created_seq=s['seq']+1)
        return self._dev_save(s,fx,'validation_maps',mp)

    def cmd_plan_validation(self,s,actor,a,fx,n,con):
        self.allowed(actor,'record')
        before=self._dev_get(s,'validation_maps',a['before_map']);after=self._dev_get(s,'validation_maps',a['after_map'])
        left=self._continuity_state(s,actor,before['state_id']);right=self._continuity_state(s,actor,after['state_id'])
        require(left['session_id']==right['session_id'],'invalid_input','Cross-session validation requires explicit integration first')
        changed={x for x in set(left['components'])|set(right['components']) if left['components'].get(x)!=right['components'].get(x)}
        if left['context']!=right['context']:changed.update(left['components']);changed.update(right['components'])
        # A mapping edit can reveal a previously unknown dependency even if files did not change.
        if any(before[k]!=after[k] for k in ('dependencies','geometry','checks','coverage')):changed.update(left['components']);changed.update(right['components'])
        for mp in (before,after):
            for vid in mp['evidence_views']:
                view=self._dev_get(s,'evidence_views',vid)
                for src in view['sources']: self._dev_artifact(s,src['revision_id'])
        result=select(before,after,changed)
        result.update(id=uid('validationplan'),session_id=right['session_id'],state_id=right['id'],
            before_map=before['id'],after_map=after['id'],input_fingerprint=digest({'state':right,'map':after}),
            created_seq=s['seq']+1)
        self._milestone(s,fx,n,self._dev_session(s,actor,right['session_id']),
            'validation_planned','Dependency and swept-space checks prepared',[result['id'],right['id']])
        return self._dev_save(s,fx,'validation_plans',result)

    def cmd_get_validation_plan(self,s,actor,a,fx,n,con):
        plan=self._dev_get(s,'validation_plans',a['plan_id']);self._continuity_state(s,actor,plan['state_id']);return plan
