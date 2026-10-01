"""Small capability-only MCP surface. No owner credential or generic API proxy."""
import json
import sys

from . import __version__
from .contracts import validate, S, A
from .model import Fault, canonical, require
from .project_connect import Project
from .review_contracts import REVIEW_OUTPUT


def schema(properties, required=()):
    return {'type': 'object', 'properties': properties, 'required': list(required), 'additionalProperties': False}


TOOLS = {
    'project_status': ('status', schema({}), 'Get this project state and fixed permissions.'),
    'project_read': ('read', schema({'path': S, 'request_id': S}, ['path', 'request_id']), 'Read an approved saved file; returns base64 and hash.'),
    'project_edit': ('edit', schema({'path': S, 'content': {'type': 'string'}, 'expected_hash': S, 'request_id': S},
        ['path', 'content', 'expected_hash', 'request_id']), 'Replace an approved UTF-8 file using its current hash, or absent for a new file. No delete.'),
    'project_test': ('test', schema({'command': S, 'request_id': S}, ['command', 'request_id']), 'Run one named approved command in an isolated scratch copy; no network or hardware.'),
    'project_checkpoint': ('checkpoint', schema({'expected_state': S, 'summary': S, 'rationale': S, 'unfinished': A, 'request_id': S},
        ['expected_state', 'summary', 'rationale', 'unfinished', 'request_id']), 'Save approved files and continuation context. Does not adopt or verify a design.')}

for action in ('read', 'edit', 'test', 'checkpoint'):
    TOOLS['project_'+action][1]['properties']['branch'] = S
for action in ('edit', 'test'):
    TOOLS['project_'+action][1]['properties']['from_review'] = S
TOOLS.update({
    'project_submit': ('submit', schema({'question': S, 'branch': S, 'request_id': S}, ['question', 'request_id']),
        'Share a saved milestone and request Mentor review against the delegated goal. No formal adoption.'),
    'project_review': ('review', schema({'submission_id': S}, ['submission_id']), 'Get grounded findings and their applicable input state.'),
    'project_respond': ('respond', schema({'submission_id': S, 'branch': S, 'responses': {'type': 'array', 'items': schema({'finding_id': S, 'explanation': S}, ['finding_id', 'explanation'])},
        'request_id': S}, ['submission_id', 'responses', 'request_id']), 'Link a corrected checkpoint to each Mentor finding.'),
    'project_assumption': ('assumption', schema({'statement': S, 'scope': A, 'evidence': A, 'dependencies': A,
        'adoption_blocker': S, 'decision_owner': {'enum': ['agent', 'human']}, 'branch': S, 'request_id': S},
        ['statement', 'scope', 'evidence', 'dependencies', 'adoption_blocker', 'decision_owner', 'request_id']),
        'Record a provisional assumption, applicability, evidence and adoption blocker. Not an accepted requirement.'),
    'project_branch': ('branch', schema({'name': S, 'base_state': S, 'purpose': S, 'request_id': S}, ['name', 'base_state', 'purpose', 'request_id']),
        'Restore an isolated candidate from a common immutable state within the delegated branch limit.'),
    'project_mentor_prepare': ('mentor-prepare', schema({'submission_id': S}, ['submission_id']),
        'Prepare a bounded review task for the current user model. Separate reviewer identity; no paid provider required.'),
    'project_mentor_finish': ('mentor-finish', schema({'submission_id': S, 'output': REVIEW_OUTPUT}, ['submission_id', 'output']),
        'Submit grounded structured findings under the delegated reviewer identity; cannot edit or adopt.'),
    'project_mentor_recover': ('mentor-recover', schema({'submission_id': S, 'reason': S}, ['submission_id', 'reason']),
        'After confirming the previous reviewer stopped, renew an expired lease and preserve saved input/output. No new model or tool invocation.'),
    'project_mentor_run': ('mentor-run', schema({'submission_id': S}, ['submission_id']),
        'Use an explicitly enabled user subscription for one submitted review. Never falls back to API billing.')})


def dispatch(project, name, arguments):
    require(name in TOOLS, 'unknown_command', 'Tool is not exposed by this project connection')
    action, spec, _ = TOOLS[name]; validate(arguments, spec)
    args = dict(arguments); key = args.pop('request_id', None)
    if action.startswith('mentor-'):
        from .project_mentor import prepare, finish, review, recover
        if action == 'mentor-prepare': return prepare(project, args['submission_id'])
        if action == 'mentor-finish': return finish(project, args['submission_id'], args['output'])
        if action == 'mentor-recover': return recover(project, args['submission_id'], args['reason'])
        return review(project, args['submission_id'])
    return project.operate(action, args, key)


def run(root):
    project = Project(root); project.context(); initialized = False
    while True:
        line = sys.stdin.readline(24*1024*1024+1)
        if not line: return
        request = None
        try:
            require(len(line) <= 24*1024*1024, 'invalid_input', 'Message exceeds limit')
            request = json.loads(line)
            require(isinstance(request, dict) and request.get('jsonrpc') == '2.0', 'invalid_input', 'Invalid JSON-RPC')
            method = request.get('method'); params = request.get('params', {})
            require(isinstance(params, dict), 'invalid_input', 'Object params required')
            if 'id' not in request:
                if method == 'notifications/initialized': initialized = True
                continue
            if method == 'initialize':
                from .project_guidance import GUIDANCE
                version = params.get('protocolVersion')
                result = {'protocolVersion': version if version in {'2024-11-05', '2025-03-26', '2025-06-18', '2025-11-25'} else '2025-11-25',
                    'capabilities': {'tools': {}}, 'serverInfo': {'name': 'gantry-project', 'version': __version__}, 'instructions': GUIDANCE}
            elif method == 'ping': result = {}
            elif not initialized: raise Fault('invalid_state', 'Initialize first')
            elif method == 'tools/list':
                context = project.context(); work = context['connection']['plan']['mode'] == 'work-capable'
                result = {'tools': [{'name': name, 'description': desc, 'inputSchema': spec,
                    'annotations': {'readOnlyHint': action in {'read', 'status'}}}
                    for name, (action, spec, desc) in TOOLS.items() if work or action in {'read', 'status', 'checkpoint', 'assumption'}]}
            elif method == 'tools/call':
                try:
                    value = dispatch(project, params.get('name'), params.get('arguments', {}))
                    result = {'content': [{'type': 'text', 'text': canonical(value)}], 'isError': False}
                except (Fault, OSError, ValueError) as exc:
                    value = exc.as_dict() if isinstance(exc, Fault) else {'code': 'local_operation_failed', 'message': 'Inspect local connection state; no operation was retried'}
                    result = {'content': [{'type': 'text', 'text': canonical(value)}], 'isError': True}
            else: raise Fault('unknown_command', 'Unknown MCP method')
            response = {'jsonrpc': '2.0', 'id': request['id'], 'result': result}
        except (Fault, ValueError, TypeError):
            response = {'jsonrpc': '2.0', 'id': request.get('id') if isinstance(request, dict) else None,
                        'error': {'code': -32602, 'message': 'Invalid MCP request'}}
        print(canonical(response), flush=True)
