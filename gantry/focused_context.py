"""Opt-in work retrieval; never substitutes for impact or adoption checks."""
from .model import require


def build_focused_context(service, s, actor, args, work, proposal, design, fx, notices, con):
    roots = args.get('entry_ids')
    require(bool(roots) and design is not None, 'invalid_input',
            'Focused context requires entry_ids and a work-bound design')
    contents = {key: s['revisions'][rid] for key, rid in design['entries'].items()}
    require(all(key in contents for key in roots), 'invalid_input',
            'All requested entries must exist in the work-bound design')
    selected = set(roots)
    pending = sorted(selected, reverse=True)
    paths = {key: [key] for key in roots}
    relations = sorted((key, entry['data']) for key, entry in contents.items()
                       if entry['type'] == 'relation' and not entry.get('retracted')
                       and entry['data']['kind'] in {'depends_on', 'implements', 'uses_interface'})
    unresolved = []
    while pending:
        source = pending.pop()
        for relation_id, relation in relations:
            if relation['source'] != source:
                continue
            selected.add(relation_id)
            target = relation['target']
            if target not in contents:
                unresolved.append({'relation_id': relation_id, 'target': target})
            elif target not in selected:
                selected.add(target)
                paths[target] = paths[source] + [relation_id, target]
                pending.append(target)
    targets = {work['id'], work.get('proposal_id'), work.get('design_id')} - {None}
    all_discussions = service._discussion_entries(s, targets, con)
    # Work/design discussion is always relevant. Proposal-wide discussion from
    # another candidate stays retrievable through full context, not relabeled.
    related = [entry for entry in all_discussions
               if entry['data']['target'] != work.get('proposal_id')
               or entry['data'].get('design_revision') in {None, design['id']}]
    before = args.get('before_discussion_seq', s['seq'] + 1)
    eligible = [entry for entry in related if entry['seq'] < before]
    page = eligible[-args.get('discussion_limit', 20):]
    more = len(eligible) > len(page)
    operation_revisions = service.cmd_operations(s, actor, {'work_item': work['id']}, fx, notices, con)['items']
    operations = sorted((entry for entry in s['entries'].values()
                         if entry['type'] == 'development_operation' and not entry.get('retracted')
                         and entry['data'].get('work_item') == work['id']), key=lambda entry: entry['id'])
    summary_fields = ['id', 'title', 'version', 'status', 'author', 'candidate_id', 'rationale']
    return {
        'seq': s['seq'], 'work': work, 'design': design,
        'proposal': {key: proposal[key] for key in summary_fields if key in proposal} if proposal else None,
        'contents': {key: contents[key] for key in sorted(selected)},
        'discussions': page,
        'questions': service.cmd_open(s, actor, {'zone': work['zone']}, fx, notices, con)['items'],
        'operations': operations,
        'scope': {
            'view': 'focused', 'partial': True, 'requested_entry_ids': sorted(set(roots)),
            'dependency_paths': paths, 'unresolved_dependencies': unresolved,
            'dependency_rule': 'Outgoing depends_on / implements / uses_interface in the work-bound design; not reverse impact or undeclared dependencies.',
            'omitted_entry_count': len(contents) - len(selected),
            'proposal_detail': 'Current proposal summary; full context contains changes and review data.',
            'proposal_current_candidate_matches_work': proposal is None or proposal['candidate_id'] == design['id'],
            'omitted_other_candidate_discussion_count': len(all_discussions) - len(related),
            'unversioned_proposal_discussion_count': sum(entry['data']['target'] == work.get('proposal_id')
                                                       and entry['data'].get('design_revision') is None for entry in related),
            'unversioned_discussion_policy': 'Included with unknown design basis; never relabeled as current-candidate evidence.',
            'discussion_total_for_scope': len(related), 'discussion_order': 'Ascending seq within each newest-first page',
            'has_older_discussions': more,
            'next_before_discussion_seq': page[0]['seq'] if more else None,
            'operation_revisions': 'Current non-retracted entry heads only; operations returns historical revisions.',
            'omitted_operation_revision_count': len(operation_revisions) - len(operations),
            'questions': 'All open questions in the work zone; not filtered by requested entries.',
            'full_context_request': {'work_id': work['id']},
        },
    }
