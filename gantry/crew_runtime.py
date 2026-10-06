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
from .connection_policy import safe_path, clean_bytes
from .continuity_adapter import capture_workspace
from .development import in_scope
from .model import Fault, digest, require
from .project_files import read_file, write_file
from .runner import persist
from . import project_sandbox

SCHEMA = {'type': 'object', 'properties': {
    'action': {'enum': ['read', 'edit', 'context', 'records', 'inspect', 'tool', 'ask', 'resolve', 'decision', 'remember', 'team', 'stop', 'finish']},
    'arguments_json': S, 'rationale': S}, 'required': ['action', 'arguments_json', 'rationale'], 'additionalProperties': False}
API_ACTIONS = {'ask': 'ask_bot', 'decision': 'record_bot_decision', 'remember': 'record_bot_experience'}
GUIDE = {
    'read': 'path; optional offset and length (bytes). Returns exact hash and bounded text/base64.',
    'edit': 'path, content, expected_hash (sha256 from read, or absent). Within task scope only.',
    'context': 'pointer (JSON pointer into full authorized context), optional offset, limit for arrays/maps.',
    'inspect': 'task_id. Read another task in this project, including its exact candidate and reports; use pointer/offset/limit to fetch a specific part.',
    'records': 'kind (actions/decisions), optional after/limit. Retrieves exact saved task history; paginated.',
    'tool': 'name from available_tools. No arbitrary argv. Results are observations, not adoption.',
    'ask': 'to_bot_id, question, evidence (state/task/message IDs). Creates a read-only response task. Then finish waiting.',
    'resolve': 'message_id, reason, evidence. Only the question author resolves its blocker after reading the answer.',
    'decision': 'verdict (authorize/revise/select/continue/stop/escalate), targets (task IDs), rationale, evidence, alternatives, conditions. Records your judgment, never grants access.',
    'remember': 'observation, applicability, limitations, evidence, used_memories. Save scoped provisional experience.',
    'team': 'configuration for propose_bot_team: session_id,organization_id,lead_bot_id,goal,acceptance,members,rationale. Members specify bot_id,name,parent_bot_id,principal_id,profile,write_scope,can_assign,can_integrate. Proposes only; human activates. Existing principal privileges cannot be expanded.',
    'stop': 'task_id, reason. Cancels a task you manage; it does not cancel its children automatically.',
    'finish': 'summary, rationale, unverified, status (completed/waiting/blocked/failed), assignments, integrate_changes, edits. Use edits=[]; edit action saves intermediate work. Assignments: bot_id,state_id,kind (plan/develop/verify/integrate/report),title,completion,write_scope,dependencies,after_tasks, optional candidate_id. Managers choose assignments; candidate tags isolate alternatives. Do not finish completed with unresolved blocking questions.'}


def _schema(properties, required=None):
    return {'type': 'object', 'properties': properties, 'required': list(properties) if required is None else required, 'additionalProperties': False}


def action_schemas():
    # Build from the authoritative contracts, not hand-maintained prose alone.
    schemas = {'finish': BOT_ANSWER,
        'edit': _schema({'path': S, 'content': {'type': 'string'}, 'expected_hash': S}),
        'tool': _schema({'name': S})}
    for name, op in {**API_ACTIONS, 'resolve': 'resolve_bot_question', 'team': 'propose_bot_team',
                     'records': 'get_bot_records'}.items():
        schema = json.loads(json.dumps(CONTRACTS[op]['schema']))
        for key in ('task_id', 'fence', 'basis', 'intent'):
            schema['properties'].pop(key, None)
            if key in schema['required']: schema['required'].remove(key)
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
    validate(args, _schema({'pointer': {'type': 'string'}, 'offset': {'type': 'integer', 'minimum': 0},
                           'limit': {'type': 'integer', 'minimum': 1, 'maximum': 65536}}, ['pointer']))
    value = context
    pointer = args['pointer']; require(not pointer or pointer.startswith('/'), 'invalid_input', 'Use a JSON pointer')
    for segment in pointer.split('/')[1:]:
        segment = segment.replace('~1', '/').replace('~0', '~')
        try: value = value[int(segment)] if isinstance(value, list) else value[segment]
        except (KeyError, IndexError, ValueError, TypeError): raise Fault('not_found', 'Context pointer not found')
    start = args.get('offset', 0); count = args.get('limit', 30)
    if isinstance(value, str):
        count = args.get('limit', 8192)
        return {'value': value[start:start+count], 'total': len(value), 'next_offset': start+count if start+count < len(value) else None}
    if isinstance(value, (dict, list)):
        count = min(count, 100)
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
    result = project_sandbox.execute(command, scratch, config.get('tool_runtime'), config.get('sandbox'),
                                    lambda: client.call('check_bot_task', ref))
    # Preserve the full bounded output in artifact storage; prompts see a bounded preview.
    import base64
    output = clean_bytes(result['output'].encode())
    artifact = client.call('capture_artifact', {'zone': zone, 'files': {'tool-output.txt': base64.b64encode(output).decode()}},
                           'crew-tool-output:' + digest([ref['task_id'], str(step), output.hex()]))
    result.update(output=result['output'][:32000], output_artifact=artifact['revision_id'],
                  output_truncated=len(result['output']) > 32000)
    changes = []
    for file in sorted(scratch.rglob('*')):
        rel = file.relative_to(scratch).as_posix()
        if rel in {'.test-output', 'home', 'tmp'} or rel.startswith(('home/', 'tmp/')): continue
        require(not file.is_symlink(), 'scope_denied', 'Tool created a symlink')
        if not file.is_file(): continue
        raw = read_file(scratch, rel)
        original = workspace/rel
        before = read_file(workspace, rel) if original.exists() else None
        if raw != before:
            _path(workspace, rel, scope)
            changes.append((rel, raw, hashlib.sha256(before).hexdigest() if before is not None else 'absent'))
    # Validate all outputs before copying any. Deletions are explicit unsupported effects.
    require(all((scratch/f.relative_to(workspace)).exists() for f in workspace.rglob('*') if f.is_file()),
            'scope_denied', 'Tool deletion requires an explicit supported operation')
    client.call('check_bot_task', ref)
    for rel, raw, expected in changes:
        _path(workspace, rel, scope, create=True); write_file(workspace, rel, raw, expected)
    result['workspace_changes_applied'] = [rel for rel, _, _ in changes]
    return result


def _api_effect(client, operation, args, step, key):
    persist(step/'api-request.json', {'operation': operation, 'args': args, 'key': key})
    return client.call(operation, args, key)


def _execute(client, context, ref, config, action, args, workspace, step, key):
    scope = context['task']['write_scope']
    if action == 'context': return _context_value(context, args)
    if action == 'inspect':
        validate(args, _schema({'task_id': S, 'pointer': {'type': 'string'},
            'offset': {'type': 'integer', 'minimum': 0}, 'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100}}, ['task_id']))
        other = client.call('get_bot_task', {'task_id': args['task_id']})
        require(other['task']['session_id'] == context['task']['session_id'], 'scope_denied', 'Inspect this project only')
        return _context_value(other, {k: v for k, v in args.items() if k != 'task_id'} | {'pointer': args.get('pointer', '')})
    if action == 'records':
        require('task_id' not in args, 'invalid_input', 'Runtime supplies task identity')
        return client.call('get_bot_records', {**args, 'task_id': ref['task_id']})
    if action == 'read':
        validate(args, _schema({'path': S, 'offset': {'type': 'integer', 'minimum': 0},
            'length': {'type': 'integer', 'minimum': 1, 'maximum': 65536}}, ['path']))
        _path(workspace, args['path']); raw = read_file(workspace, args['path'])
        start = args.get('offset', 0); value = raw[start:start+args.get('length', 32768)]
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


def run_actions(client, initial, ref, infer, config, root):
    from .bot_execution import _input, safe_fingerprint
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    state_path = root/'loop.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {'next': 0, 'last_result': None}
    workspace = Path(initial['workspace'])
    while True:
        number = state['next']; step = root/str(number); step.mkdir(exist_ok=True)
        marker = step/'action.json'; saved = json.loads(marker.read_text()) if marker.exists() else None
        full = client.call('refresh_bot_task', ref)
        if saved is None:
            input_path = step/'input.json'
            context = json.loads(input_path.read_text()) if input_path.exists() else _input(full, workspace)
            if not input_path.exists(): context.update(action_guide=GUIDE, action_schemas=action_schemas(), available_tools=config.get('local_tools', {}),
                last_result=result_preview(state['last_result']), round=number,
                instruction=context['instruction'] + ' Choose ONE action each turn; put its JSON object in arguments_json. '
                'Use context to fetch omitted records, inspect to retrieve peer tasks, read for files, tool for real tests, and edit for changes. '
                'Use your own judgment; report, ask or delegate rather than invent evidence. '
                'Record consequential decisions and reusable lessons. Organization workers run independently.')
            persist(input_path, context)
            receipt = infer(context, SCHEMA, step/'model'); validate(receipt['output'], SCHEMA)
            saved = {'phase': 'prepared', 'receipt': receipt, 'before': safe_fingerprint(workspace),
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
                    result = _execute(client, full, ref, config, action, args, workspace, step, key)
                    saved.update(phase='completed', result=result); persist(marker, saved)
            except (Fault, FileNotFoundError) as exc:
                if isinstance(exc, Fault) and exc.code not in {'invalid_input', 'scope_denied', 'not_found',
                    'dependency_pending', 'conflict', 'invalid_state', 'capture_incomplete',
                    'sandbox_unavailable', 'reauthorization_required'}: raise
                saved.update(phase='completed', result={'error': exc.code if isinstance(exc, Fault) else 'invalid_input',
                                                      'message': str(exc)[:500], 'details': exc.details if isinstance(exc, Fault) else {}}); persist(marker, saved)
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
        _return_effect(client, saved, marker, 'record_args', 'record_bot_action', key + ':record', ref)
        if safe_fingerprint(workspace) != saved['before']:
            if 'checkpoint_args' not in saved:
                snapshot, missing = capture_workspace(client, workspace, key+':capture', full['zone'])
                saved['checkpoint_args'] = {**ref, 'snapshot': snapshot['revision_id'], 'summary': output['rationale'],
                    'rationale': output['rationale'], 'unfinished': ['Intermediate Bot action; not adopted'],
                    'capture': {'scope': 'Brokered action and saved workspace', 'missing': missing}}
                persist(marker, saved)
            _return_effect(client, saved, marker, 'checkpoint_args', 'checkpoint_bot_task', key + ':checkpoint', ref)
        if action == 'finish' and 'report' in saved['result']:
            return {'output': saved['result']['report'], 'provider': {'kind': 'bot_action_loop', 'rounds': number+1},
                    'checkpoint_fingerprint': safe_fingerprint(workspace)}
        state.update(next=number+1, last_result=saved['result']); persist(state_path, state)
