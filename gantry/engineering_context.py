"""Version-bound engineering declarations, not an automatic physics certifier.

Stored in immutable state context.environment.engineering. Original native files
remain authoritative; the view exposes declared roles and coverage, never guesses.
"""
from .model import require


def assess(context, manifest):
    contract = context.get('environment', {}).get('engineering')
    if contract is None:
        return {'configured': False, 'components': [], 'checks': [], 'input_mismatches': [],
                'review_gaps': [], 'limitations': ['Engineering roles and verification coverage not declared.']}
    require(isinstance(contract, dict) and contract.get('version') == 1,
            'invalid_input', 'engineering.version must be 1')
    components = contract.get('components', [])
    checks = contract.get('checks', [])
    require(isinstance(components, list) and isinstance(checks, list), 'invalid_input', 'Invalid engineering lists')
    ids = set(); mismatches = []; gaps = []; view = []
    def bindings(items):
        require(isinstance(items, dict) and bool(items), 'invalid_input', 'Nonempty path/hash bindings required')
        require(all(isinstance(p, str) and isinstance(h, str) and len(h)==64 for p,h in items.items()),
                'invalid_input', 'Bindings require paths and SHA-256 hashes')
        return [p for p,h in items.items() if manifest.get(p, {}).get('hash') != h]
    for c in components:
        require(isinstance(c, dict) and isinstance(c.get('id'), str) and c['id'] not in ids,
                'invalid_input', 'Unique component IDs required')
        ids.add(c['id'])
        require(isinstance(c.get('role'), str) and isinstance(c.get('assembly'), str),
                'invalid_input', 'Component role and assembly required')
        stale = bindings(c.get('inputs'))
        mismatches.extend(stale)
    check_ids = set()
    for check in checks:
        require(isinstance(check, dict) and isinstance(check.get('id'), str) and check['id'] not in check_ids,
                'invalid_input', 'Unique check IDs required')
        check_ids.add(check['id'])
        require(check.get('scope') in {'placement','motion','service','connection','structural','electrical','thermal','other'},
                'invalid_input', 'Specify an engineering check scope')
        require(isinstance(check.get('required'), bool) and check.get('status') in {'unverified','pass','fail','unknown','not_applicable'},
                'invalid_input', 'Specify required and check status')
        require(isinstance(check.get('components'), list) and bool(check['components']) and set(check['components']) <= ids,
                'invalid_input', 'Check must identify known components')
        stale = bindings(check.get('inputs'))
        evidence = check.get('evidence', {})
        require(isinstance(evidence, dict), 'invalid_input', 'Evidence must bind paths and hashes')
        evidence_stale = bindings(evidence) if evidence else []
        effective = check['status']
        if stale or evidence_stale or (effective == 'pass' and not evidence): effective = 'unknown'
        if effective == 'not_applicable' and not check.get('reason'): effective = 'unknown'
        if check['required'] and effective not in {'pass','not_applicable'}: gaps.append(check['id'])
        view.append({**check, 'effective_status': effective, 'stale_inputs': stale,
                     'stale_evidence': evidence_stale, 'provenance': 'submitted declaration; not independently certified'})
    return {'configured': True, 'components': components, 'checks': view,
            'input_mismatches': sorted(set(mismatches)),
            'review_gaps': sorted(set(gaps + ['input:'+x for x in mismatches])),
            'limitations': ['Hash equality does not prove physical compatibility or semantic agreement between CAD and settings.']}
