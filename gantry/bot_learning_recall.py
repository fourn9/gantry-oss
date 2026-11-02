"""Transparent bounded retrieval. Lexical/path matches are not applicability proof."""
import copy
import re

from .model import Fault, digest
from .development import in_scope


def tokens(value):
    return set(re.findall(r'[^\W_]+', str(value).lower(), re.UNICODE))


def authorized_memories(core, s, actor, task, con, after=''):
    bot, org = core._persistent_identity(s, task['bot_id'])
    found = {}; cursor = after
    for _ in range(10):
        page = core._persistent_memory_page(s, actor, bot, org, {'limit': 100, 'after': cursor}, con)
        for memory in page['items']:
            try: core._learning_source(s, actor, task, memory['id'])
            except Fault: continue
            found[memory['id']] = memory
        cursor = page['next_cursor']
        if not cursor: break
    return found, cursor


def context_basis(s, task, state_id=None):
    state = s['dev_states'][state_id or task.get('output_state', task['state_id'])]
    context = state['context']
    session = s['dev_sessions'][task['session_id']]
    project = s['bot_projects'][task['session_id']]
    return digest({'requirements': context['requirements'], 'constraints': context['constraints'],
        'environment': context['environment'], 'delegated_constraints': session['constraints'],
        'project_goal': project['goal'], 'project_acceptance': project['acceptance'],
        'task_completion': task['completion']})


def recall(core, s, actor, task, con, after='', limit=20):
    memories, cursor = authorized_memories(core, s, actor, task, con, after)
    query = tokens([task['title'], task['completion'], task['dependencies']])
    paths = set(task['dependencies'] + task['write_scope'])
    state = s['dev_states'][task.get('output_state', task['state_id'])]
    manifest = core._manifest(s, state['snapshot'])
    environment = s['bot_runtimes'][task['bot_id']]['environment_hash']
    links = {}
    for memory in memories.values():
        for relation in ('supersedes', 'contradicts'):
            targets = memory.get('lesson', {}).get(relation, [])
            if memory.get(relation): targets = [*targets, memory[relation]]
            for target in targets: links.setdefault(target, []).append({'kind': relation, 'memory_id': memory['id']})
    basis = context_basis(s, task)
    ranked = []
    for memory in memories.values():
        lesson = memory.get('lesson', {})
        overlap = query & tokens([memory['observation'], memory['applicability'], lesson])
        matching_paths = {p for p in memory.get('paths', []) if p in paths or in_scope(p, task['write_scope'])}
        refs = memory.get('requirement_refs')
        matching_requirements = set(r['requirement_id'] for r in refs or []) & set(r['requirement_id'] for r in task.get('requirement_refs', []))
        if not overlap and not matching_paths and not matching_requirements: continue
        flags = []
        if any(manifest.get(p, {}).get('hash') != h for p, h in memory.get('input_hashes', {}).items()): flags.append('input_changed')
        if refs is None: flags.append('requirements_not_captured')
        elif refs != task.get('requirement_refs', []): flags.append('requirements_changed')
        if not memory.get('context_basis'): flags.append('context_not_captured')
        elif memory['context_basis'] != basis: flags.append('context_changed')
        if not memory.get('environment_hash'): flags.append('environment_not_captured')
        elif memory['environment_hash'] != environment: flags.append('environment_changed')
        if links.get(memory['id']): flags.append('replacement_or_contradiction')
        if cursor or after: flags.append('recall_incomplete')
        # Feedback is reported utility with its own source access, not a reward model.
        rows = con.execute('SELECT id FROM records WHERE collection=? AND subject_id=? ORDER BY created_seq DESC,id DESC LIMIT 101',
                           ('bot_experience_feedback', memory['id'])).fetchall()
        counts = dict(helpful=0, harmful=0, unknown=0)
        for row in rows[:100]:
            entry = core._dev_get(s, 'bot_experience_feedback', row[0])
            try: core._dev_session(s, actor, entry['session_id'])
            except Fault: continue
            counts[entry['outcome']] += 1
        result = copy.deepcopy(memory)
        result.update(relevance={'tokens': sorted(overlap), 'paths': sorted(matching_paths),
            'requirements': sorted(matching_requirements)}, applicability_flags=flags,
            allowed_uses=['recheck', 'reject'] if flags else ['apply', 'recheck', 'reject'],
            related_updates=links.get(memory['id'], []), reported_utility=counts,
            utility_truncated=len(rows)>100, evidence_status='reported_experience_not_independent_verification')
        score = len(overlap)*3 + len(matching_paths)*2 + len(matching_requirements)*4
        ranked.append((score, counts['helpful']-counts['harmful'], memory['created_seq'], memory['id'], result))
    ranked.sort(key=lambda x: x[:4], reverse=True)
    return {'method': 'scoped_lexical_paths_requirements', 'items': [r[-1] for r in ranked[:limit]],
        'scanned_authorized': len(memories), 'next_cursor': cursor, 'truncated': bool(cursor) or len(ranked)>limit,
        'coverage': 'At most 1000 indexed source rows per page; ranked top results within this page only',
        'source_digest': digest(memories)}


def planning_view(packet):
    """Keep complete source inventories in Core, not repeated in model prompts."""
    result = copy.deepcopy(packet)
    result['full_packet'] = {'operation': 'get_bot_learning_plan', 'plan_id': packet['id'], 'sha256': digest(packet)}
    for memory in result['recall']['items']:
        hashes = memory.get('input_hashes', {})
        paths = memory.get('paths', [])
        memory['input_hash_count'] = len(hashes)
        memory['input_hashes'] = dict(list(hashes.items())[:20])
        memory['path_count'] = len(paths)
        memory['paths'] = paths[:20]
        memory['inventory_preview_truncated'] = len(hashes)>20 or len(paths)>20
    return result
