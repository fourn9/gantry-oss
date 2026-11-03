"""Explicit cross-tool bindings. No geometry inference or automatic remapping."""
from collections import defaultdict, deque
from .model import require


def impact(components, edges, manifest, bindings):
    require(isinstance(edges, list) and len(edges) <= 1000,
            'invalid_input', 'At most 1000 engineering dependencies')
    by_id = {c['id']: c for c in components}
    require(len(by_id) <= 1000, 'invalid_input', 'At most 1000 components')
    affected = set(); reasons = []; downstream = defaultdict(set); seen = set()
    for c in components:
        refs = c.get('native_refs', [])
        require(isinstance(refs, list) and len(refs) <= 50, 'invalid_input', 'Bounded native references required')
        for ref in refs:
            require(isinstance(ref, dict) and set(ref) == {'provider','document','object','revision','unit','frame','source_path'}
                    and all(isinstance(v,str) and 0 < len(v) <= 1000 for v in ref.values())
                    and ref['source_path'] in c['inputs'],
                    'invalid_input', 'Native reference must identify an original component input')
        if bindings(c['inputs']): affected.add(c['id'])
    for edge in edges:
        require(isinstance(edge,dict) and set(edge) == {'dependent','prerequisite','kind','status','rationale','inputs'},
                'invalid_input', 'Explicit version-bound dependency required')
        a,b = edge['prerequisite'],edge['dependent']
        require(isinstance(a,str) and isinstance(b,str) and a in by_id and b in by_id and a != b,
                'invalid_input', 'Dependency endpoints must be distinct known components')
        require(isinstance(edge['kind'],str) and edge['kind'] in {'uses_geometry','uses_interface','derived_from','depends_on'}
                and isinstance(edge['rationale'],str) and 0 < len(edge['rationale']) <= 4000
                and isinstance(edge['status'],str) and edge['status'] in {'confirmed','unverified'}, 'invalid_input', 'Dependency meaning and status required')
        require((a,b,edge['kind']) not in seen, 'invalid_input', 'Duplicate dependency')
        seen.add((a,b,edge['kind'])); downstream[a].add(b)
        stale = bindings(edge['inputs'])
        require(set(by_id[a]['inputs']) <= set(edge['inputs']), 'invalid_input', 'Dependency must bind all prerequisite inputs')
        if stale or edge['status'] != 'confirmed':
            affected.add(b)
            reasons.append({'prerequisite':a,'dependent':b,'kind':edge['kind'],
                            'stale_inputs':stale,'reason':'input_changed' if stale else 'compatibility_unverified'})
    queue = deque(sorted(affected)); paths = []
    while queue:
        a = queue.popleft()
        for b in sorted(downstream[a]):
            paths.append({'from':a,'to':b})
            if b not in affected:
                affected.add(b); queue.append(b)
    return {'affected_components':sorted(affected), 'reasons':reasons, 'propagation':paths,
            'dependencies':edges, 'coverage':'declared dependencies only; missing edges are not inferred',
            'native_reference_provenance':'submitted identifiers; native correspondence not independently verified'}
