"""Customer model chooses each action. This harness validates and executes it.

Model tools stay disabled: file/ledger/tool access is brokered here with scoped
credentials and durable receipts. No engineering choices are embedded in this code.
"""
import hashlib
import json
import shutil
from pathlib import Path

from .bot_development import BOT_ANSWER
from .contracts import CONTRACTS, S, validate
from .crew_json import INSPECT_JSON_SCHEMA, inspect_json, pointer_value
from .crew_observe import OBSERVE_SCHEMA, observe
from .crew_timing import span
from .connection_policy import safe_path, clean_bytes
from .continuity_adapter import capture_workspace
from .development import in_scope
from .model import Fault, canonical, digest, require
from .project_files import read_file, write_file
from .runner import persist
from . import project_sandbox

SCHEMA = {'type': 'object', 'properties': {
    'action': {'enum': ['observe', 'issue_open', 'issue_review', 'issue', 'issues', 'requirements', 'propose_requirements', 'integrate', 'read', 'inspect_json', 'edit', 'replace', 'context', 'records', 'inspect', 'tool', 'publish_physical', 'ask', 'resolve', 'decision', 'remember', 'working_state', 'experience_use', 'team', 'stop', 'finish']},
    'arguments_json': S, 'rationale': S}, 'required': ['action', 'arguments_json', 'rationale'], 'additionalProperties': False}
API_ACTIONS = {'issue_open': 'open_bot_issue', 'issue_review': 'review_bot_issue', 'ask': 'ask_bot', 'decision': 'record_bot_decision', 'remember': 'record_bot_experience',
               'working_state': 'update_bot_working_state', 'experience_use': 'record_bot_learning_use',
               'propose_requirements': 'propose_bot_requirements'}
GUIDE = {
    'observe': 'Retrieve 1-4 independent read/context/inspect/inspect_json requests in ONE turn: requests [{action,arguments}]. Read chunks deliver at most 2000 bytes each, with exact next_offset. Individual source versions/errors are preserved. Large results explicitly require narrower follow-up retrieval. No writes, tools, recursion or decisions. This is not an atomic cross-task snapshot. Prefer this when several known inputs are needed together.',
    'issue_open': 'Promote a saved followup: source_task_id, source_attempt, followup_id, owner_bot_id, paths, completion, verification_plan (saved physical plan path), check_ids. Explicitly declare scoped operational acceptance; preserve historical source. Returns stable issue ID and links this task. No adoption.',
    'issue_review': 'issue_id, version, status (working/verifying/deferred/reopened/resolved), state_id, reason, evidence; verification_task_ids for resolved. Responsible Bot or manager only, using an issue-linked task. Resolve the exact completed verification output state with fresh matching tool evidence and frozen passing checks. Completed child work alone is not resolution. Reopen explicitly for a new cycle. Optional reassessment while reopening sets a new verification_plan/check_ids/requirement_refs at this task state, preserves old acceptance and requires fresh verification; never silently drop requirements.',
    'issue': 'issue_id, optional state_id/after/limit and pointer/offset for detailed retrieval. Issue and paginated lifecycle history. effective_status is relative to selected state, not a universal pass.',
    'issues': 'optional state_id/after/limit. Page project issues, including those outside the default bounded context. Use issue_ids in assignments; children and consultations inherit links.',
    'requirements': 'Optional after/limit. Page existing adopted requirement definitions in this project zone. Discovery is not assignment or fulfillment. Use exact reference IDs and saved source hashes to propose links; do not invent requirements from prose.',
    'propose_requirements': 'links [{requirement_id,revision_id,rationale,evidence:[{path,hash}]}], summary. Propose links to existing adopted requirements in a separate shared metadata change. Never invent IDs. The active task remains unchanged; inspect the candidate, then a delegated manager selects it for subsequent work. Missing formal requirements remain unlinked until defined through the existing requirement approval process.',
    'integrate': 'state_id (current pinned input), changes [{id,version}], summary. Integrates shared candidates as an intermediate action, restores their exact combined files, and keeps this task running. Then inspect/edit/test yourself or finish waiting with a child assignment using the returned state_id. Does not verify or adopt. Requires integration delegation and no prior saved edits in this task; conflicts remain unresolved.',
    'read': 'path; optional offset and length (bytes, at most 6000 delivered per call). Returns the full chunk as UTF-8 text or base64 if a byte boundary splits UTF-8. Decode base64 to bytes; follow next_offset until null. Hash and size describe the entire source file.',
    'inspect_json': 'Read-only saved file: path, optional pointer (JSON pointer), offset, limit (1-30). Supports plain JSON or verified zlib-base64-json-v1 envelope, at most 16 MiB input / 64 MiB decoded. Optional nonempty_at filters the selected array by a literal relative JSON pointer, never an expression: excludes missing fields, null, false, zero and empty strings/arrays/objects. filter_counts distinguishes missing from empty/false. Returns source hashes, original source_indices and pagination. Values are bounded previews; follow exact pointers for nested omissions. Inspection is not validation or adoption.',
    'edit': 'path, content, expected_hash (sha256 from read, or absent). Within task scope only.',
    'replace': 'path, expected_hash (whole-file SHA-256 from read), old_text, new_text. Replace one exact unique nonempty UTF-8 match; new_text may be empty. All other bytes are preserved without re-emitting the file. No fuzzy/regex matching. Reread changed files; missing or ambiguous matches require more exact context. Within write_scope only.',
    'context': 'pointer (JSON pointer into full authorized context), optional offset/limit. At most 30 entries or 6000 string characters per page; follow next_offset. Nested values remain bounded previews; use exact nested pointers for omitted content.',
    'inspect': 'task_id. Read another task in this project, including its exact candidate and reports; use pointer/offset/limit to fetch a specific part. At most 30 entries or 6000 string characters per page; follow next_offset and exact nested pointers for omitted content.',
    'records': 'kind (actions/decisions/learning_uses), optional after/limit. Retrieves exact saved task history; paginated.',
    'publish_physical': 'plan_path: a frozen physical plan already saved in the current state. Imports reports from this workspace through the fenced Bot adapter; never adopts.',
    'tool': 'name from available_tools. No arbitrary argv. Results are observations, not adoption.',
    'ask': 'to_bot_id, question, evidence (state/task/message IDs). Creates a read-only response task. Optional memory_id requests independent evidence-based checking of a shared lesson by a different Bot/principal from you and its author. Then finish waiting.',
    'resolve': 'message_id, reason, evidence. Only the question author resolves its blocker after reading the answer.',
    'decision': 'verdict (authorize/revise/select/continue/stop/escalate), targets (task IDs), rationale, evidence, alternatives, conditions. Records your judgment, never grants access.',
    'remember': 'observation, applicability, limitations, evidence, used_memories. Save scoped provisional experience.',
    'working_state': 'version (current working_state.note.version or 0), focus, next_steps, commitments, unknowns, watch_paths, watch_tasks, due_at (UTC epoch milliseconds or null). Update ongoing commitments at meaningful boundaries. These are hypotheses, not requirements or permission. Watches alone do not authorize new tasks; owner standing delegation is separate.',
    'experience_use': 'Mid-task receipt: memory_id, action_ids, change, condition_check. Prefer finish.experience_uses when finishing; avoid a separate bookkeeping turn. Link a non-rejected planned memory to actual saved actions from this attempt. Never invent actions or claim causality from success alone.',
    'team': 'configuration for propose_bot_team: session_id,organization_id,lead_bot_id,goal,acceptance,members,rationale. Members specify bot_id,name,parent_bot_id,principal_id,profile,write_scope,can_assign,can_integrate. Proposes only; human activates. Existing principal privileges cannot be expanded.',
    'stop': 'task_id, reason. Cancels a task you manage; it does not cancel its children automatically.',
    'finish': 'summary, rationale, unverified, status (completed/waiting/blocked/failed), assignments, integrate_changes, edits. For a requested experience check, a completed report must include experience_check: {verdict (supported_for_scope/contradicted/inconclusive),reason,action_ids}. Cite actual check actions; do not claim physical proof. Optional experience_uses: [{memory_id,action_ids,change,condition_check}] records actual experience use atomically with this report, without another turn. Use []/null or omit if none; retrieval alone is not use. Link non-rejected planned memories and actual saved action IDs from this attempt, explain the change and applicability check. Do not duplicate already recorded links. Use edits=[]; edit action saves intermediate work. Assignments: bot_id,state_id,kind (plan/develop/verify/integrate/report),title,completion,write_scope,dependencies,after_tasks, optional candidate_id and requirement_refs (explicit requirement/revision pairs; [] means exploration). Omitted child references inherit the parent task. Managers choose assignments; candidate tags isolate alternatives. Do not finish completed with unresolved blocking questions.'}


def _schema(properties, required=None):
    return {'type': 'object', 'properties': properties, 'required': list(properties) if required is None else required, 'additionalProperties': False}


def action_schemas():
    # Build from the authoritative contracts, not hand-maintained prose alone.
    schemas = {'finish': BOT_ANSWER, 'inspect_json': INSPECT_JSON_SCHEMA, 'observe': OBSERVE_SCHEMA,
        'edit': _schema({'path': S, 'content': {'type': 'string'}, 'expected_hash': S}),
        'replace': _schema({'path': S, 'expected_hash': S, 'old_text': S, 'new_text': {'type': 'string'}}),
        'tool': _schema({'name': S}), 'publish_physical': _schema({'plan_path': S}),
        'read': _schema({'path': S, 'offset': {'type':'integer','minimum':0},
                         'length': {'type':'integer','minimum':1,'maximum':65536}}, ['path']),
        'context': _schema({'pointer': {'type':'string'}, 'offset': {'type':'integer','minimum':0},
                            'limit': {'type':'integer','minimum':1,'maximum':65536}}, ['pointer']),
        'inspect': _schema({'task_id': S, 'pointer': {'type':'string'}, 'offset': {'type':'integer','minimum':0},
                            'limit': {'type':'integer','minimum':1,'maximum':65536}}, ['task_id'])}
    for name, op in {**API_ACTIONS, 'integrate': 'integrate_bot_task', 'resolve': 'resolve_bot_question', 'team': 'propose_bot_team',
                     'records': 'get_bot_records', 'requirements': 'get_bot_requirements', 'issue': 'get_bot_issue', 'issues': 'list_bot_issues'}.items():
        schema = json.loads(json.dumps(CONTRACTS[op]['schema']))
        for key in ('task_id', 'fence', 'basis', 'intent'):
            schema['properties'].pop(key, None)
            if key in schema['required']: schema['required'].remove(key)
        if name in {'issue','issues'}:
            schema['properties'].update(pointer={'type':'string'}, offset={'type':'integer','minimum':0})
        schemas[name] = schema
    return schemas


def result_preview(result):
    def compact(value, depth=0):
        if isinstance(value, str) and len(value) > 8000:
            return {'preview': value[:8000], 'characters': len(value), 'truncated': True}
        if isinstance(value, dict): return {k: compact(v, depth+1) for k,v in value.items()}
        if isinstance(value, list): return [compact(v, depth+1) for v in value[:30]] + ([{'omitted_items': len(value)-30}] if len(value)>30 else [])
        return value
    preview = compact(result)
    if len(json.dumps(preview).encode()) > 96000:
        return {'truncated': True, 'message': 'Result too large for inline input. Inspect a specific context pointer or page records; the exact receipt is saved.',
                'top_level_keys': list(result) if isinstance(result, dict) else [], 'sha256': digest(result)}
    return preview


def _path(workspace, name, scope=None, create=False):
    safe_path(name)
    if scope is not None: require(in_scope(name, scope), 'scope_denied', 'Outside assigned write scope')
    path = workspace/name
    require(all(not p.is_symlink() for p in [workspace, path, *path.parents]), 'scope_denied', 'Symlink path refused')
    if create: path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _context_value(context, args):
    validate(args, action_schemas()['context'])
    value = pointer_value(context, args['pointer'])
    start = args.get('offset', 0); count = args.get('limit', 30)
    if isinstance(value, str):
        # Even escaped astral Unicode stays below the global inline JSON cap.
        page = value[start:start+min(args.get('limit', 6000), 6000)]
        end = start + len(page)
        return {'value': page, 'total': len(value), 'next_offset': end if end < len(value) else None}
    if isinstance(value, (dict, list)):
        count = min(count, 30)
        size = len(value)
        value = dict(list(value.items())[start:start+count]) if isinstance(value, dict) else value[start:start+count]
        return {'value': value, 'total': size, 'next_offset': start+count if start+count < size else None}
    return {'value': value}


def _tool(client, ref, config, args, workspace, step, scope, zone):
    validate(args, _schema({'name': S}))
    tools = config.get('local_tools', {})
    require(args['name'] in tools, 'scope_denied', 'Tool not in the owner-approved environment')
    command = tools[args['name']]
    require(set(command) == {'argv', 'timeout_seconds'} and isinstance(command['argv'], list)
            and command['argv'] and all(isinstance(x, str) for x in command['argv'])
            and type(command['timeout_seconds']) is int and 1 <= command['timeout_seconds'] <= 7200,
            'invalid_input', 'Invalid installed tool declaration')
    scratch = step/'scratch'
    from .bot_execution import safe_fingerprint
    safe_fingerprint(workspace)
    shutil.copytree(workspace, scratch)
    original_times = {p.relative_to(scratch).as_posix(): p.stat().st_mtime_ns for p in scratch.rglob('*') if p.is_file()}
    result = project_sandbox.execute(command, scratch, config.get('tool_runtime'), config.get('sandbox'),
                                    lambda: client.call('check_bot_task', ref))
    # Preserve the full bounded output in artifact storage; prompts see a bounded preview.
    import base64
    output = clean_bytes(result['output'].encode())
    artifact = client.call('capture_artifact', {'zone': zone, 'files': {'tool-output.txt': base64.b64encode(output).decode()}},
                           'crew-tool-output:' + digest([ref['task_id'], str(step), output.hex()]))
    result.update(output=result['output'][:32000], output_artifact=artifact['revision_id'],
                  output_truncated=len(result['output']) > 32000)
    # Execution happened even if later file validation rejects the entire import.
    # Keep its sanitized receipt separately; an error must not become test evidence.
    persist(step/'tool-execution.json', result)
    changes = []; refreshed = []
    try:
        for file in sorted(scratch.rglob('*')):
            rel = file.relative_to(scratch).as_posix()
            if rel in {'.test-output', 'home', 'tmp'} or rel.startswith(('home/', 'tmp/')): continue
            require(not file.is_symlink(), 'scope_denied', 'Tool created a symlink')
            if not file.is_file(): continue
            if original_times.get(rel) != file.stat().st_mtime_ns: refreshed.append(rel)
            raw = read_file(scratch, rel)
            original = workspace/rel
            before = read_file(workspace, rel) if original.exists() else None
            if raw != before:
                _path(workspace, rel, scope)
                changes.append((rel, raw, hashlib.sha256(before).hexdigest() if before is not None else 'absent'))
        # Validate all outputs before copying any. Deletions are explicit unsupported effects.
        require(all((scratch/f.relative_to(workspace)).exists() for f in workspace.rglob('*') if f.is_file()),
                'scope_denied', 'Tool deletion requires an explicit supported operation')
    except (Fault, FileNotFoundError) as exc:
        if isinstance(exc, Fault) and exc.code not in {'invalid_input', 'scope_denied', 'capture_incomplete'}:
            raise
        client.call('check_bot_task', ref)
        return {'error': 'tool_capture', 'cause': exc.code if isinstance(exc, Fault) else 'not_found',
                'message': str(exc)[:500] if isinstance(exc, Fault) else 'Output file unavailable during capture',
                'tool_result': result}
    client.call('check_bot_task', ref)
    for rel, raw, expected in changes:
        _path(workspace, rel, scope, create=True); write_file(workspace, rel, raw, expected)
    result['workspace_changes_applied'] = [rel for rel, _, _ in changes]
    result['refreshed_paths'] = refreshed
    return result


def _api_effect(client, operation, args, step, key):
    persist(step/'api-request.json', {'operation': operation, 'args': args, 'key': key})
    return client.call(operation, args, key)


def _execute(client, context, ref, config, action, args, workspace, step, key):
    scope = context['task']['write_scope']
    if action == 'observe':
        return observe(args, action_schemas(), lambda kind, request:
            _execute(client, context, ref, config, kind, request, workspace, step, key))
    require(context['task'].get('studio_mode') != 'ask' or action not in {'propose_requirements','integrate','edit','replace','tool','publish_physical','team','stop','issue_open','issue_review'},
            'scope_denied', 'Ask cannot edit, execute tools or change team work')
    if action == 'integrate':
        from .bot_execution import safe_fingerprint
        expected = digest({name: info['hash'] for name, info in context['development']['manifest'].items()})
        require(safe_fingerprint(workspace) == expected, 'stale_basis', 'Unsaved workspace changes; preserve them before integration')
        require(not set(args) & set(ref), 'invalid_input', 'Runtime supplies task identity')
        return _api_effect(client, 'integrate_bot_task', {**args, **ref}, step, key)
    if action == 'publish_physical':
        validate(args, _schema({'plan_path': S}))
        from .hardware import publish_bot
        return publish_bot(client, ref['task_id'], ref['fence'], workspace, args['plan_path'], key)
    if action == 'context': return _context_value(context, args)
    if action == 'inspect':
        validate(args, action_schemas()['inspect'])
        other = client.call('get_bot_task', {'task_id': args['task_id']})
        require(other['task']['session_id'] == context['task']['session_id'], 'scope_denied', 'Inspect this project only')
        return _context_value(other, {k: v for k, v in args.items() if k != 'task_id'} | {'pointer': args.get('pointer', '')})
    if action in {'issue', 'issues'}:
        require('task_id' not in args, 'invalid_input', 'Runtime supplies task identity')
        selected = {k:v for k,v in args.items() if k not in {'pointer','offset'}}
        result = client.call('get_bot_issue' if action == 'issue' else 'list_bot_issues', {**selected, 'task_id': ref['task_id']})
        return _context_value(result, {'pointer':args['pointer'], 'offset':args.get('offset',0)}) if 'pointer' in args else result
    if action in {'records', 'requirements'}:
        require('task_id' not in args, 'invalid_input', 'Runtime supplies task identity')
        return client.call('get_bot_records' if action == 'records' else 'get_bot_requirements', {**args, 'task_id': ref['task_id']})
    if action == 'inspect_json':
        validate(args, INSPECT_JSON_SCHEMA)
        _path(workspace, args['path'])
        return inspect_json(workspace, args, _context_value, result_preview)
    if action == 'read':
        validate(args, action_schemas()['read'])
        _path(workspace, args['path']); raw = read_file(workspace, args['path'])
        # Keep the entire chunk below result_preview's 8000-character string
        # bound, including base64; cursors must describe delivered bytes.
        start = args.get('offset', 0); value = raw[start:start+min(args.get('length', 6000), 6000)]
        try: data = {'text': value.decode('utf-8')}
        except UnicodeError:
            import base64
            data = {'base64': base64.b64encode(value).decode()}
        return {**data, 'hash': hashlib.sha256(raw).hexdigest(), 'size': len(raw),
                'next_offset': start+len(value) if start+len(value) < len(raw) else None}
    if action == 'edit':
        validate(args, _schema({'path': S, 'content': {'type': 'string'}, 'expected_hash': S}))
        _path(workspace, args['path'], scope, create=True)
        write_file(workspace, args['path'], args['content'].encode(), args['expected_hash'])
        return {'path': args['path'], 'hash': hashlib.sha256(args['content'].encode()).hexdigest()}
    if action == 'replace':
        validate(args, action_schemas()['replace'])
        _path(workspace, args['path'], scope)
        raw = read_file(workspace, args['path'])
        require(hashlib.sha256(raw).hexdigest() == args['expected_hash'], 'stale_basis', 'File changed; reread before replacing')
        try:
            raw.decode('utf-8')
            old = args['old_text'].encode('utf-8'); new = args['new_text'].encode('utf-8')
        except UnicodeError:
            raise Fault('invalid_input', 'Replace requires valid UTF-8 text')
        offset = raw.find(old)
        require(offset >= 0 and raw.find(old, offset+1) < 0, 'invalid_input',
                'Replace needs exactly one matching old_text; read the target and include unique surrounding text')
        updated = clean_bytes(raw[:offset] + new + raw[offset+len(old):])
        write_file(workspace, args['path'], updated, args['expected_hash'])
        return {'path': args['path'], 'hash': hashlib.sha256(updated).hexdigest()}
    if action == 'tool': return _tool(client, ref, config, args, workspace, step, scope, context['zone'])
    if action in API_ACTIONS:
        require(not set(args) & {'task_id', 'fence', 'basis', 'intent'}, 'invalid_input', 'Task identity is supplied by the runtime')
        return _api_effect(client, API_ACTIONS[action], {**args, **ref}, step, key)
    if action == 'resolve':
        require(not set(args) & set(ref), 'invalid_input', 'Task identity is supplied by the runtime')
        return _api_effect(client, 'resolve_bot_question', {**args, **ref}, step, key)
    if action == 'team':
        require(args.get('session_id') == context['task']['session_id'] and args.get('organization_id') == context['organization']['id'],
                'scope_denied', 'Propose a team for this project only')
        require(not set(args) & set(ref), 'invalid_input', 'Runtime supplies task identity')
        return _api_effect(client, 'propose_bot_team', {**args, **ref}, step, key)
    if action == 'stop':
        validate(args, _schema({'task_id': S, 'reason': S}))
        target = client.call('get_bot_task', {'task_id': args['task_id']})['task']
        require(target['id'] != ref['task_id'], 'invalid_input', 'Finish your own task with a report')
        return _api_effect(client, 'stop_bot_task', {**ref, 'target_task_id': target['id'],
            'version': target['version'], 'reason': args['reason']}, step, key)
    raise Fault('invalid_input', 'Unknown action')


def _return_effect(client, saved, marker, field, operation, key, ref):
    """Reconcile the exact old request first; rotate only after a definite rejection."""
    request_key = field + '_key'
    saved.setdefault(request_key, key); persist(marker, saved)
    try: return client.call(operation, saved[field], saved[request_key])
    except Fault as exc:
        if exc.code != 'stale_basis' or saved[field]['fence'] == ref['fence']: raise
        client.call('check_bot_task', ref)
        saved[field].update(ref); saved[request_key] = key + ':recovered:' + digest(ref)[:16]
        persist(marker, saved)
        return client.call(operation, saved[field], saved[request_key])


def _materialize_integration(client, workspace, step, saved, key):
    """Keep predecessor files and reconcile the exact state before the next action."""
    from .continuity_adapter import restore_development_state
    from .bot_execution import safe_fingerprint
    result = saved['result']; state_id = result['state']['id']
    detail = client.call('get_development_state', {'state_id': state_id})
    expected = digest({name: info['hash'] for name, info in detail['manifest'].items()})
    if saved.get('materialized'):
        require(safe_fingerprint(workspace) == expected, 'stale_basis', 'Integrated workspace changed before receipt reconciliation')
        return
    backup = step/'pre-integration-workspace'
    # Retain the predecessor even across interruption between the two renames.
    if workspace.exists() and safe_fingerprint(workspace) == expected:
        saved['materialized'] = state_id
        return
    if workspace.exists():
        require(safe_fingerprint(workspace) == saved['before'] and not backup.exists(),
                'stale_basis', 'Local files changed while integration was being materialized')
    else:
        require(backup.exists() and safe_fingerprint(backup) == saved['before'],
                'outcome_unknown', 'Missing predecessor workspace')
    restored = restore_development_state(client, state_id, step/'integrated-restore', key+':restore')
    source = Path(restored['workspace'])
    require(safe_fingerprint(source) == expected, 'integrity_error', 'Restored integration differs from pinned manifest')
    if workspace.exists():
        require(safe_fingerprint(workspace) == saved['before'] and not backup.exists(),
                'stale_basis', 'Workspace changed during integration restore; no switch performed')
        workspace.rename(backup)
    require(safe_fingerprint(backup) == saved['before'], 'stale_basis', 'Predecessor changed during switch; files retained for recovery')
    source.rename(workspace)
    saved['materialized'] = state_id


def _publish_tool_evidence(client, ref, config, workspace, saved, marker, key):
    """Publish an installed tool's reports without re-running the tool on retry."""
    name = json.loads(saved['receipt']['output']['arguments_json'])['name']
    mapping = config.get('tool_evidence', {}).get(name)
    if mapping is None or saved.get('evidence_done'): return
    if 'tool_result' not in saved:
        saved['tool_result'] = saved['result']; persist(marker, saved)
    try:
        validate(mapping, _schema({'plan_path': S}))
        if 'evidence_args' not in saved:
            from .hardware import _physical_checkpoint
            full = client.call('get_bot_task', {'task_id': ref['task_id']})
            baseline = client.call('get_development_state', {'state_id': full['task']['state_id']})
            args = _physical_checkpoint(client, full['development'], workspace, full['zone'],
                mapping['plan_path'], key+':evidence:capture', baseline, execution={
                    'input_state': saved.get('input_state'),
                    'action_key': key, 'exit_code': saved['tool_result']['exit_code'],
                    'output_artifact': saved['tool_result']['output_artifact'],
                    'refreshed_paths': saved['tool_result'].get('refreshed_paths', [])})
            args.pop('work_status')
            saved['evidence_args'] = {**ref, **args}; persist(marker, saved)
        result = _return_effect(client, saved, marker, 'evidence_args', 'checkpoint_bot_task', key+':evidence', ref)
        saved['result'] = {**saved['tool_result'], 'evidence_publication': {
            'state_id': result['state']['id'], 'checks': result['state']['context']['environment']['engineering']['checks'],
            'formal_adoption': False}}
    except (Fault, ValueError) as exc:
        if isinstance(exc, Fault) and exc.code not in {'invalid_input', 'conflict', 'capture_incomplete', 'not_found', 'stale_basis', 'scope_denied'}:
            raise
        # Stale acceptance files can be corrected by a new assignment. Changed
        # task authority itself must still hold the worker, not become feedback.
        client.call('check_bot_task', ref)
        saved['result'] = {'error': 'evidence_publication', 'message': str(exc)[:500],
            'cause': exc.code if isinstance(exc, Fault) else 'invalid_input',
            'tool_result': saved['tool_result']}
    saved['evidence_done'] = True
    saved['evidence_record_args'] = {**ref, 'kind': 'tool_evidence', 'details': {
        'result': saved['result'], 'tool': name, 'plan_path': mapping.get('plan_path') if isinstance(mapping, dict) else None}}
    persist(marker, saved)


def action_input(full, workspace, config, last_result, number):
    from .bot_execution import _input, _fit_optional_previews
    context = _input(full, workspace)
    context.update(action_guide=GUIDE, action_schemas=action_schemas(),
        available_tools=config.get('local_tools', {}), tool_evidence=config.get('tool_evidence', {}),
        last_result=result_preview(last_result), round=number,
        instruction=context['instruction'] + ' Choose ONE action each turn; put its JSON object in arguments_json. '
        'Use observe to fetch up to four independent observations in one turn. '
        'Use context to fetch omitted records, inspect to retrieve peer tasks, read for files, tool for real tests, and edit for changes. '
        'Use your own judgment; report, ask or delegate rather than invent evidence. '
        'Record consequential decisions and reusable lessons. Organization workers run independently.')
    _fit_optional_previews(context, list(full['development']['manifest']), limit=480000)
    if len(canonical(context).encode()) > 480000 and last_result is not None:
        context['last_result'] = {'truncated': True, 'sha256': digest(last_result),
            'error': last_result.get('error') if isinstance(last_result, dict) else None,
            'detail_reference': {'operation': 'get_bot_records', 'kind': 'actions', 'task_id': full['task']['id']}}
    require(len(canonical(context).encode()) <= 480000, 'context_limit',
            'Complete action input exceeds budget; reduce task scope or runtime configuration')
    return context


def run_actions(client, initial, ref, infer, config, root):
    from .bot_execution import safe_fingerprint
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    state_path = root/'loop.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {'next': 0, 'last_result': None}
    if not state_path.exists(): persist(state_path, state)
    workspace = Path(initial['workspace'])
    while True:
        number = state['next']; step = root/str(number); step.mkdir(exist_ok=True)
        marker = step/'action.json'; saved = json.loads(marker.read_text()) if marker.exists() else None
        with span(step, 'context'):
            full = client.call('refresh_bot_task', ref)
        if saved is None:
            input_path = step/'input.json'
            with span(step, 'context'):
                context = json.loads(input_path.read_text()) if input_path.exists() else action_input(full, workspace, config, state['last_result'], number)
            persist(input_path, context)
            with span(step, 'model'):
                receipt = infer(context, SCHEMA, step/'model'); validate(receipt['output'], SCHEMA)
            saved = {'phase': 'prepared', 'receipt': receipt, 'before': safe_fingerprint(workspace),
                     'input_state': full['development']['state']['id'],
                     'discussion_version': context['task']['discussion_version']}
            persist(marker, saved)
        output = saved['receipt']['output']; action = output['action']
        key = 'crew-action:' + digest([ref['task_id'], initial['task']['attempt'], number])
        if saved['phase'] == 'executing':
            request_path = step/'api-request.json'
            require(request_path.exists(), 'outcome_unknown', 'Interrupted local tool/edit; inspect receipt before a new task')
            request = json.loads(request_path.read_text())
            try: result = client.call(request['operation'], request['args'], request['key'])
            except Fault as exc:
                if exc.code != 'stale_basis' or 'fence' not in request['args'] or request['args']['fence'] == ref['fence']: raise
                client.call('check_bot_task', ref)
                require(saved['discussion_version'] == full['task']['discussion_version'], 'stale_basis', 'Request context changed')
                request['args'].update(ref); request['key'] = key + ':recovered:' + digest(ref)[:16]
                persist(request_path, request)
                result = client.call(request['operation'], request['args'], request['key'])
            saved.update(phase='completed', result=result); persist(marker, saved)
        if (saved['phase'] == 'prepared' or action == 'finish') and saved.get('discussion_version') != full['task']['discussion_version']:
            saved.update(phase='stale', result={'error': 'stale_basis', 'discarded_model_answer': True})
            persist(marker, saved)
            state.update(next=number+1, last_result=saved['result']); persist(state_path, state); continue
        if saved['phase'] == 'prepared':
            try: client.call('check_bot_task', ref)
            except Fault as exc:
                if exc.code != 'stale_basis': raise
                saved.update(phase='stale', result={'error': 'stale_basis', 'discarded_model_answer': True})
                persist(marker, saved)
                state.update(next=number+1, last_result=saved['result']); persist(state_path, state); continue
            try:
                try: args = json.loads(output['arguments_json'])
                except ValueError: raise Fault('invalid_input', 'Action arguments are not JSON')
                require(isinstance(args, dict), 'invalid_input', 'Arguments must be an object')
                if action == 'finish':
                    validate(args, BOT_ANSWER)
                    require(not args['edits'], 'invalid_input', 'Use edit actions to preserve intermediate work')
                    if args['status'] == 'completed':
                        require(not any(m['blocking'] and m['status'] != 'resolved' for m in full['messages']),
                                'dependency_pending', 'Resolve blocking questions before completion')
                    saved.update(phase='completed', result={'report': args}); persist(marker, saved)
                else:
                    saved['phase'] = 'executing'; persist(marker, saved)
                    with span(step, 'action'):
                        result = _execute(client, full, ref, config, action, args, workspace, step, key)
                    saved.update(phase='completed', result=result); persist(marker, saved)
            except (Fault, FileNotFoundError) as exc:
                if isinstance(exc, Fault) and exc.code not in {'invalid_input', 'scope_denied', 'not_found',
                    'dependency_pending', 'evidence_required', 'conflict', 'invalid_state', 'capture_incomplete',
                    'sandbox_unavailable', 'reauthorization_required'}: raise
                saved.update(phase='completed', result={'error': exc.code if isinstance(exc, Fault) else 'invalid_input',
                                                      'message': str(exc)[:500], 'details': exc.details if isinstance(exc, Fault) else {}}); persist(marker, saved)
        if action == 'integrate' and saved['result'].get('integrated'):
            _materialize_integration(client, workspace, step, saved, key)
            persist(marker, saved)
        # Locally durable effect receipts are reconciled before advancing the model.
        if 'record_args' not in saved:
            try: client.call('check_bot_task', ref)
            except Fault as exc:
                if exc.code != 'stale_basis' or action != 'finish': raise
                saved.update(phase='stale', result={'error': 'stale_basis', 'discarded_model_answer': True})
                persist(marker, saved)
                state.update(next=number+1, last_result=saved['result']); persist(state_path, state); continue
            saved['record_args'] = {**ref, 'kind': action, 'details': {'rationale': output['rationale'],
                'arguments': output['arguments_json'], 'result': saved['result'],
                'workspace_before': saved['before'], 'workspace_after': safe_fingerprint(workspace),
                'provider': saved['receipt'].get('provider', {'kind': 'injected_test_inference'}), 'round': number}}
            persist(marker, saved)
        with span(step, 'record'):
            _return_effect(client, saved, marker, 'record_args', 'record_bot_action', key + ':record', ref)
        if action != 'integrate' and safe_fingerprint(workspace) != saved['before']:
            with span(step, 'checkpoint'):
                if 'checkpoint_args' not in saved:
                    snapshot, missing = capture_workspace(client, workspace, key+':capture', full['zone'])
                    saved['checkpoint_args'] = {**ref, 'snapshot': snapshot['revision_id'], 'summary': output['rationale'],
                        'rationale': output['rationale'], 'unfinished': ['Intermediate Bot action; not adopted'],
                        'capture': {'scope': 'Brokered action and saved workspace', 'missing': missing}}
                    persist(marker, saved)
                _return_effect(client, saved, marker, 'checkpoint_args', 'checkpoint_bot_task', key + ':checkpoint', ref)
        if action == 'tool' and 'error' not in saved.get('tool_result', saved['result']):
            with span(step, 'record'):
                _publish_tool_evidence(client, ref, config, workspace, saved, marker, key)
        if saved.get('evidence_record_args'):
            _return_effect(client, saved, marker, 'evidence_record_args', 'record_bot_action', key+':evidence-record', ref)
        if action == 'finish' and 'report' in saved['result']:
            report = saved['result']['report']
            if 'final_args' not in saved:
                saved.update(final_args={**ref, 'report': {k: v for k, v in report.items() if k != 'edits'}},
                             phase='finalizing')
                persist(marker, saved)
            try:
                with span(step, 'record'):
                    result = _return_effect(client, saved, marker, 'final_args', 'finish_bot_task', key+':finish', ref)
            except Fault as exc:
                # Only definite contract rejections are correction requests. Transport
                # uncertainty and changed authority/basis must not launch a new turn.
                if exc.code not in {'invalid_input', 'invalid_state', 'dependency_pending', 'conflict', 'not_found', 'scope_denied'}:
                    raise
                client.call('check_bot_task', ref)
                saved.update(phase='rejected', result={'error': exc.code, 'message': str(exc)[:500], 'details': exc.details})
                saved['feedback_args'] = {**ref, 'kind': 'finish', 'details': {
                    'rationale': output['rationale'], 'arguments': output['arguments_json'],
                    'result': saved['result'], 'round': number, 'stage': 'core_validation'}}
                persist(marker, saved)
            else:
                saved.update(phase='finished', final_result=result); persist(marker, saved)
                return {'output': report, 'provider': {'kind': 'bot_action_loop', 'rounds': number+1},
                        'checkpoint_fingerprint': safe_fingerprint(workspace), 'final_result': result}
        if saved.get('feedback_args'):
            _return_effect(client, saved, marker, 'feedback_args', 'record_bot_action', key+':feedback', ref)
        state.update(next=number+1, last_result=saved['result']); persist(state_path, state)


def reconcile_finish(client, root):
    """Recover a committed finish before requiring an active task/lease again."""
    root = Path(root); state_path = root/'loop.json'
    if not state_path.exists(): return None
    state = json.loads(state_path.read_text()); marker = root/str(state['next'])/'action.json'
    if not marker.exists(): return None
    saved = json.loads(marker.read_text())
    if saved['phase'] == 'finished': return saved['final_result']
    if saved['phase'] != 'finalizing' or 'final_args_key' not in saved: return None
    try: result = client.call('finish_bot_task', saved['final_args'], saved['final_args_key'])
    except Fault as exc:
        # A stopped worker may have been held before the uncertain request reached
        # Core. The normal recovery path must revalidate and renew that lease.
        if exc.code in {'stale_basis', 'mode_disabled'}: return None
        raise
    saved.update(phase='finished', final_result=result); persist(marker, saved)
    return result
