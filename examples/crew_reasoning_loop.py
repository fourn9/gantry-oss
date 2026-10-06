"""Opt-in real subscription reasoning over an anonymous engineering fixture.

No hard-coded model answers. Local setup creates delegation, objective and tools;
Bots select work, candidate values, consultation and integration themselves.
Output contains private credentials and model journals. Never publish it.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import secrets
import sys
import threading
import time

from bot_development_loop import LocalClient, profile
from gantry.agent_connection import PROFILES
from gantry.bot_worker import BotWorker, environment_manifest
from gantry.model import require
from gantry.project_sandbox import backend, runtime_roots
from gantry.runner import persist
from gantry.service import Service, token_hash

CHECK = '''import json
from pathlib import Path
h = json.loads(Path('geometry.json').read_text())['reach']
s = json.loads(Path('control.json').read_text())['limit']
print(json.dumps(dict(reach=h, limit=s, material_score=h*h, match=h==s, feasible=2<=h<=3 and h==s)), flush=True)
assert 2 <= h <= 3 and h == s, 'Reach must be 2..3 and hardware/software must match'
'''


def setup(root):
    root.mkdir(parents=True, exist_ok=False, mode=0o700)
    persist(root/'source-manifest.json', {str(p): __import__('hashlib').sha256(p.read_bytes()).hexdigest() for p in sorted(Path('gantry').glob('*.py'))})
    service = Service(root/'ledger'); owner = LocalClient(service, service.bootstrap()['token'])
    persist(root/'owner-private.json', {'token': owner.token})
    roles = {'lead': None, 'hardware': 'lead', 'software': 'lead', 'designer': 'hardware', 'controller': 'software'}
    scopes = {name: ['geometry.json', 'control.json'] if name == 'lead' else
              ['geometry.json'] if name in {'hardware', 'designer'} else ['control.json'] for name in roles}
    clients = {}; configs = {}
    for name in roles:
        token = secrets.token_urlsafe(32)
        proposal = owner.call('propose', {'title': 'Delegate anonymous acceptance Bot', 'changes': [{'id': name,
            'type': 'principal', 'data': {'kind': 'agent', 'permissions': ['read', 'record', 'work'],
            'zones': ['root'], 'allowed_commands': sorted(PROFILES['bot']), 'token_hash': token_hash(token)}}]})
        ref = {'proposal_id': proposal['id'], 'version': proposal['version']}
        owner.call('submit', ref); owner.call('endorse', {**ref, 'reason': 'Acceptance scope'})
        owner.call('review_adoption', {**ref, 'verdict': 'approve', 'reason': 'Delegation only, no design adoption'})
        owner.call('commit', ref); clients[name] = LocalClient(service, token)
        token_path = root/(name+'.token'); token_path.write_text(token); token_path.chmod(0o600)
    files = {'geometry.json': '{"reach":1}', 'control.json': '{"limit":1}', 'check.py': CHECK}
    snapshot = owner.call('capture_artifact', {'files': {p: base64.b64encode(v.encode()).decode() for p,v in files.items()}})['revision_id']
    goal = 'Increase reach to between 2 and 3, keep software limit exactly equal to hardware reach, and minimize material_score = reach squared among feasible candidates.'
    acceptance = ['Matching hardware/software values satisfy check.py', 'Compare at least two candidate states with measured evidence',
                  'Department managers delegate to specialists; record rationale and an applicable lesson', 'No physical validity or speedup claim']
    session = owner.call('connect_development', {'title': 'Anonymous organization reasoning acceptance', 'snapshot': snapshot,
        'requirements': acceptance, 'constraints': ['Do not edit check.py', 'No physical actions'],
        'capture': {'scope': 'Anonymous Python fixture', 'missing': ['Actual CAD and physical evidence']},
        'unverified': ['Physical behavior'], 'mode': 'execute', 'actors': list(roles),
        'write_scope': ['geometry.json', 'control.json'], 'recipes': {}, 'max_executions': None, 'max_parallel': 5, 'timeout_seconds': 300})
    sid = session['id']
    state = owner.call('initialize_continuity', {'session_id': sid, 'version': session['version'],
        'hierarchy': [{'id': 'assembly', 'title': 'Anonymous assembly', 'kind': 'subsystem', 'paths': list(files), 'editable': True}],
        'context': {'requirements': acceptance, 'constraints': ['No physical operation'], 'decisions': [],
                    'open_questions': ['Physical validity'], 'environment': {'kind': 'Python fixture'}}, 'summary': 'Anonymous starting state'})
    owner.call('configure_organization', {'organization_id': 'example', 'version': 0, 'name': 'Example organization',
        'profile': profile(goal), 'enabled': True, 'share_reflections': True})
    members = []
    for name, parent in roles.items():
        p = profile(goal)
        p['responsibilities'] = ([f'Manage {name}; delegate to your subordinate Bots; compare actual reports.']
            if name in {'lead', 'hardware', 'software'} else [f'Implement and evaluate the {name} assignment.'])
        p['onboarding'] += ['Consult peers with ask when needed; finish waiting after delegation or consultation.',
            'Use context to inspect omitted child reports and candidate states. In report-only consultations return analysis without edits.',
            'Use candidate_id for alternatives. All child tasks must stay within your assignment scope.',
            'Evidence IDs are real task/state/message IDs. Resolve your answered blocking questions before completing.',
            'Integration is an unedited task: use exact change IDs and versions. Never combine conflicting alternatives.',
            'Run the check tool on the final integrated state in a delegated verification task if needed.']
        members.append(dict(bot_id=name, name=name, parent_bot_id=parent, principal_id=name, profile=p,
            write_scope=scopes[name], can_assign=name in {'lead', 'hardware', 'software'}, can_integrate=name=='lead'))
    proposed = owner.call('propose_bot_team', dict(session_id=sid, organization_id='example', lead_bot_id='lead',
        goal=goal, acceptance=acceptance, members=members, rationale='Acceptance organization with both department managers and specialists'))
    owner.call('activate_bot_team', {'proposal_id': proposed['id']})
    for name in roles:
        config = dict(bot_id=name, name=name, workflow='bot_development', backend='codex_subscription', agent_loop=True,
            environment_definition='Anonymous scoped Python acceptance; real customer subscription reasoning', tools=['check'],
            local_tools={'check': {'argv': [sys.executable, '-B', 'check.py'], 'timeout_seconds': 10}},
            tool_runtime=runtime_roots(), sandbox=backend(), token_file=str(root/(name+'.token')))
        configs[name] = config; persist(root/(name+'.json'), config)
        owner.call('configure_bot_runtime', {'bot_id': name, 'version': 0, 'principal_id': name,
            'enabled': True, 'environment': environment_manifest(config)})
    task = owner.call('assign_bot_task', dict(session_id=sid, bot_id='lead', state_id=state['id'], kind='plan',
        title=goal, completion=acceptance, write_scope=scopes['lead'], dependencies=['check.py'], after_tasks=[]))
    persist(root/'setup.json', {'session_id': sid, 'root_task_id': task['id'], 'state_id': state['id'], 'goal': goal})
    return owner, clients, configs, task


def run(output, seconds):
    root = Path(output).absolute(); owner, clients, configs, task = setup(root)
    stop = threading.Event(); errors = []; started = time.monotonic()
    def consume(name):
        try:
            with BotWorker(clients[name], configs[name], root/'journals') as worker:
                while not stop.is_set():
                    results = worker.tick()
                    for result in results:
                        if result.get('status') == 'held':
                            errors.append({'bot': name, 'result': result}); stop.set()
                    stop.wait(1)
        except Exception as exc:
            errors.append({'bot': name, 'error': type(exc).__name__, 'message': str(exc)}); stop.set()
    with ThreadPoolExecutor(max_workers=len(clients)) as pool:
        futures = [pool.submit(consume, name) for name in clients]
        while not stop.wait(2):
            current = owner.call('get_bot_task', {'task_id': task['id']})
            if current['task']['status'] in {'completed', 'failed', 'blocked', 'cancelled'} or time.monotonic()-started >= seconds:
                stop.set()
        for future in futures: future.result()
    tasks = []; cursor = None
    while True:
        page = owner.call('list_bot_tasks', {'session_id': task['session_id'], 'limit': 100, **({'after': cursor} if cursor else {})})
        tasks.extend(page['items']); cursor = page['next_cursor']
        if not cursor: break
    report = dict(reasoning='Real Codex subscription; separate role contexts', task=owner.call('get_bot_task', {'task_id': task['id']}),
        tasks=tasks, errors=errors, elapsed_seconds=round(time.monotonic()-started, 2),
        parent_engineering_interventions=0, limits=['Anonymous fixture; no CAD fidelity or speedup evidence'],
        verify=owner.call('verify'))
    persist(root/'report.json', report)
    return {'report': str(root/'report.json'), 'root_status': report['task']['task']['status'], 'errors': errors}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True); parser.add_argument('--live-codex', action='store_true')
    parser.add_argument('--seconds', type=int, default=1200, help='Observation window for this acceptance exercise only')
    args = parser.parse_args(); require(args.live_codex, 'opt_in_required', 'Explicit --live-codex uses your subscription')
    print(json.dumps(run(args.output, args.seconds), indent=2))
