"""Synthetic customer bridge, real Bot/Core/file loop, no Mentor or paid model.

Run from the repository after installation:
  python examples/bot_development_loop.py --output /new/private/demo-directory
The directory contains tokens and journals: do not share it as diagnostic feedback.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import secrets
import sys

from gantry.agent_connection import PROFILES
from gantry.bot_worker import BotWorker, environment_manifest
from gantry.model import require
from gantry.runner import persist
from gantry.service import Service, token_hash


class LocalClient:
    def __init__(self, service, token): self.service, self.token = service, token
    def call(self, name, args=None, key=None):
        return self.service.call(self.token, name, args or {}, key or secrets.token_hex(16))


def profile(name):
    return dict(mission=name, responsibilities=['Report exact inputs and unknowns'], focus_paths=[],
        workflow=['Read saved context'], report_when=['After work or failure'], style='Evidence before conclusions',
        onboarding=['No physical operation or formal adoption'])


BRIDGE = '''import json, sys
from pathlib import Path
r = json.load(sys.stdin); c = r['context']; task = c['task']; name = c['bot']['id']
out = dict(summary='Synthetic customer bridge report', rationale='Fixed synthetic interface exercise',
           unverified=['Physical behavior'], status='completed', assignments=[], integrate_changes=[], edits=[])
if name == 'lead' and not task['children']:
    out['status'] = 'waiting'
    for target, path in [('mechanical', 'geometry.txt'), ('control', 'control.txt')]:
        out['assignments'].append(dict(bot_id=target, state_id=task['state_id'], kind='develop',
            title='Update '+target, completion=['Save candidate and report unknowns'],
            write_scope=[path], dependencies=[], after_tasks=[]))
elif name == 'lead':
    out['integrate_changes'] = [dict(id=x['change']['id'], version=x['change']['version'])
                               for x in c['candidate_changes'] if x['status']=='completed']
else:
    name = 'geometry.txt' if name == 'mechanical' else 'control.txt'
    (Path(c['workspace'])/name).write_text('2')
    assert (Path(c['workspace'])/name).read_text() == '2'
print(json.dumps(out))
'''


def run(output):
    root = Path(output).absolute(); root.mkdir(parents=True, exist_ok=False, mode=0o700)
    service = Service(root/'ledger'); credential = service.bootstrap()['token']
    owner = LocalClient(service, credential)
    token_file = root/'owner.token'; token_file.write_text(credential); token_file.chmod(0o600)
    clients = {}; configs = {}
    for name in ('lead', 'mechanical', 'control'):
        token = secrets.token_urlsafe(32)
        path = root/(name+'.token'); path.write_text(token); path.chmod(0o600)
        proposal = owner.call('propose', {'title': 'Delegate synthetic Bot', 'changes': [{'id': name,
            'type': 'principal', 'data': {'kind': 'agent', 'permissions': ['read', 'record', 'work'],
                'zones': ['root'], 'allowed_commands': sorted(PROFILES['bot']), 'token_hash': token_hash(token)}}]})
        ref = {'proposal_id': proposal['id'], 'version': proposal['version']}
        owner.call('submit', ref); owner.call('endorse', {**ref, 'reason': 'Synthetic example scope'})
        owner.call('review_adoption', {**ref, 'reason': 'Delegate fixture access only', 'verdict': 'approve'})
        owner.call('commit', ref); clients[name] = LocalClient(service, token)
    files = {'geometry.txt': '1', 'control.txt': '1'}
    snapshot = owner.call('capture_artifact', {'files': {p: base64.b64encode(v.encode()).decode() for p,v in files.items()}})['revision_id']
    session = owner.call('connect_development', {'title': 'Independent Bot example', 'snapshot': snapshot,
        'requirements': ['Matching saved values'], 'constraints': ['No hardware operation'],
        'capture': {'scope': 'Synthetic files', 'missing': ['Real engineering data']}, 'unverified': ['Physical behavior'],
        'mode': 'execute', 'actors': list(clients), 'write_scope': list(files), 'recipes': {},
        'max_executions': None, 'max_parallel': 3, 'timeout_seconds': 300})
    sid = session['id']
    state = owner.call('initialize_continuity', {'session_id': sid, 'version': session['version'],
        'hierarchy': [{'id': 'assembly', 'title': 'Synthetic assembly', 'kind': 'subsystem', 'paths': list(files), 'editable': True}],
        'context': {'requirements': ['Matching saved values'], 'constraints': ['No hardware operation'],
            'decisions': [], 'open_questions': ['Physical behavior'], 'environment': {'fixture': 'customer Python bridge'}},
        'summary': 'Existing synthetic baseline'})
    owner.call('configure_organization', {'organization_id': 'example', 'version': 0, 'name': 'Example team',
        'profile': profile('Example organization'), 'enabled': True, 'share_reflections': True})
    for name in clients:
        owner.call('configure_bot', {'bot_id': name, 'organization_id': 'example', 'version': 0,
            'name': name, 'parent_bot_id': None if name == 'lead' else 'lead', 'profile': profile(name), 'enabled': True})
    owner.call('configure_bot_project', {'session_id': sid, 'organization_id': 'example', 'version': 0,
        'goal': 'Update and combine two synthetic domains', 'acceptance': ['Saved files agree; unknowns retained'],
        'lead_bot_id': 'lead', 'enabled': True})
    bridge = root/'customer-bridge'; bridge.write_text('#!'+sys.executable+'\n'+BRIDGE); bridge.chmod(0o700)
    for name in clients:
        scope = list(files) if name == 'lead' else ['geometry.txt' if name == 'mechanical' else 'control.txt']
        owner.call('bind_development_bot', {'session_id': sid, 'bot_id': name, 'principal_id': name, 'version': 0,
            'write_scope': scope, 'can_assign': name == 'lead', 'can_integrate': name == 'lead', 'enabled': True})
        config = {'bot_id': name, 'name': name, 'backend': 'external_agent', 'workflow': 'bot_development',
            'command': [str(bridge)], 'executable_hash': hashlib.sha256(bridge.read_bytes()).hexdigest(),
            'environment_definition': 'Synthetic deterministic bridge, no LLM', 'tools': ['fixture local editing'],
            'url': 'http://127.0.0.1:8765', 'token_file': str(root/(name+'.token'))}
        configs[name] = config; persist(root/(name+'.json'), config)
        owner.call('configure_bot_runtime', {'bot_id': name, 'version': 0, 'principal_id': name,
            'enabled': True, 'environment': environment_manifest(config)})
    task = owner.call('assign_bot_task', {'session_id': sid, 'bot_id': 'lead', 'state_id': state['id'],
        'kind': 'plan', 'title': 'Plan and integrate', 'completion': ['Save integrated candidate with limitations'],
        'write_scope': list(files), 'dependencies': [], 'after_tasks': []})
    # Each context/process starts with durable records. Workers normally poll independently.
    turns = []
    for name in ('lead', 'mechanical', 'control', 'lead'):
        with BotWorker(clients[name], configs[name], root/'journals') as worker:
            turns.append({'bot': name, 'results': worker.tick()})
    result = owner.call('get_bot_task', {'task_id': task['id']})
    require(result['task']['status'] == 'completed', 'demo_failed', 'Example did not finish')
    final = owner.call('get_development_state', {'state_id': result['task']['output_state']})
    from gantry.continuity_adapter import restore_development_state
    restore_development_state(clients['lead'], final['state']['id'], root/'restored', 'example-restore')
    require(all((root/'restored'/'workspace'/name).read_text() == '2' for name in files), 'demo_failed', 'Saved bytes differ')
    report = {'scenario': 'Independent Bot development with synthetic reasoning', 'mentor_jobs':
        len(owner.call('review_automation_status', {'session_id': sid})['jobs']), 'session_id': sid,
        'task_id': task['id'], 'state_id': final['state']['id'], 'status': final['status'],
        'compatibility': final['state'].get('compatibility'), 'restored_files': list(files),
        'replay': owner.call('replay'), 'verification': owner.call('verify'), 'turns': turns,
        'limitations': ['Fixture inference; no real design quality or speedup claim',
                       'Intermediate native tool capture needs a customer bridge; not a Fusion integration']}
    persist(root/'report.json', report)
    return {'report': str(root/'report.json'), 'mentor_jobs': report['mentor_jobs'], 'status': final['status']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', required=True)
    print(json.dumps(run(parser.parse_args().output), indent=2))
