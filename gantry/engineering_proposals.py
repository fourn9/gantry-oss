"""Mentor-inferred roles/checks, pinned by Core and handed to the developer.

No model-generated pass, shell command or authority change is accepted here.
"""
import copy
from .model import require


def bind_plan(plan, context, manifest, submission_id, state_id, findings, evidence_check):
    if not plan:
        return None
    existing = context.get('environment', {}).get('engineering', {})
    component_ids = {c['id'] for c in existing.get('components', [])}
    check_ids = {c['id'] for c in existing.get('checks', [])}
    result = copy.deepcopy(plan)
    result.update(source_submission=submission_id, input_state=state_id,
                  provenance='mentor_inferred', status='proposed')
    for kind, known in (('components', component_ids), ('checks', check_ids)):
        for item in result[kind]:
            require(item['id'] not in known, 'conflict', 'Proposal must not overwrite an existing role or check', id=item['id'])
            known.add(item['id'])
            require(item['paths'] and len(set(item['paths'])) == len(item['paths']),
                    'invalid_input', 'Proposals need distinct source paths')
            require(all(path in manifest for path in item['paths']), 'invalid_input', 'Proposal source not in pinned state')
            require(item['evidence'], 'invalid_input', 'Proposal requires cited evidence')
            evidence_check(item['evidence'])
            item['inputs'] = {path: manifest[path]['hash'] for path in item['paths']}
            item['provenance'] = 'mentor_inferred'
    for check in result['checks']:
        require(check['components'] and set(check['components']) <= component_ids,
                'invalid_input', 'Check refers to unknown components')
        require(check['finding_id'] in findings, 'invalid_input', 'Check must link to an actionable finding')
        components = {c['id']: c for c in existing.get('components', []) + result['components']}
        # The model cannot omit a declared component input from its new check.
        paths = set(check['paths'])
        for component_id in check['components']:
            paths.update(components[component_id]['inputs'])
        require(all(path in manifest for path in paths), 'stale_basis', 'Referenced component input is missing')
        check['paths'] = sorted(paths)
        check['inputs'] = {path: manifest[path]['hash'] for path in check['paths']}
    return result


def candidate_context(context, proposal, manifest):
    """Carry inferred declarations forward without replacing existing checks/results."""
    context = copy.deepcopy(context)
    if not proposal:
        return context
    engineering = context.setdefault('environment', {}).setdefault('engineering',
        {'version': 1, 'components': [], 'checks': []})
    for kind in ('components', 'checks'):
        ids = {x['id'] for x in engineering[kind]}
        for item in proposal[kind]:
            require(item['id'] not in ids, 'conflict', 'Candidate already contains proposed ID')
            require(all(path in manifest for path in item['paths']), 'stale_basis',
                    'Proposed component/check source removed; revise the proposal')
            entry = copy.deepcopy(item)
            entry['source_submission'] = proposal['source_submission']
            entry['source_state'] = proposal['input_state']
            entry['source_evidence'] = entry.pop('evidence')
            entry['proposal_inputs'] = entry['inputs']
            entry['inputs'] = {path: manifest[path]['hash'] for path in item['paths']}
            if kind == 'checks':
                entry.update(status='unverified', evidence={})
            engineering[kind].append(entry)
            ids.add(entry['id'])
    return context
