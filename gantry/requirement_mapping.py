"""Sourced proposals link existing normative requirements; they never create one."""
import copy
from .contracts import S
from .model import require
from .requirement_traceability import validate_refs, stale_refs

LINKS = {'type': ['array', 'null'], 'maxItems': 100, 'items': {'type': 'object',
    'properties': {'requirement_id': S, 'revision_id': S, 'rationale': S,
        'evidence': {'type': 'array', 'minItems': 1, 'maxItems': 100, 'items': {'type': 'object',
            'properties': {'path': S, 'hash': S}, 'required': ['path', 'hash'], 'additionalProperties': False}}},
    'required': ['requirement_id', 'revision_id', 'rationale', 'evidence'], 'additionalProperties': False}}


def validate_links(service, s, actor, links, manifest):
    refs = [{k: item[k] for k in ('requirement_id', 'revision_id')} for item in links]
    validate_refs(s, refs)
    require(not stale_refs(s, refs), 'stale_basis', 'Requirement changed; reassess the mapping')
    for link in links:
        service.zone_write(actor, s['revisions'][link['revision_id']]['zone'])
        require(link['rationale'].strip(), 'invalid_input', 'Mapping rationale required')
        require(all(manifest.get(e['path'], {}).get('hash') == e['hash'] for e in link['evidence']),
                'stale_basis', 'Requirement mapping must cite the saved source hashes')
    return refs


def mapped_context(context, links, refs, source):
    result = copy.deepcopy(context)
    by_id = {ref['requirement_id']: ref for ref in result.get('requirement_refs', [])}
    for ref in refs:
        require(ref['requirement_id'] not in by_id or by_id[ref['requirement_id']] == ref,
                'conflict', 'Mapping cannot silently replace a pinned requirement revision')
        by_id[ref['requirement_id']] = ref
    result['requirement_refs'] = list(by_id.values())
    result.setdefault('environment', {}).setdefault('requirement_mappings', []).append({
        'links': copy.deepcopy(links), 'source': source, 'provenance': 'explicit proposal; not evidence of fulfillment'})
    return result
