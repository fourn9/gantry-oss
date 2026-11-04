"""Separate local Core instances; no existing project or owner credential is used."""
import secrets

from .agent_connection import PROFILES
from .bot_worker import BotWorker, environment_manifest
from .model import require
from .runner import persist
from .service import Service, token_hash


class LocalClient:
    def __init__(self, service, token):
        self.service, self.token = service, token
        self.before = None; self.after = None

    def call(self, name, args=None, key=None):
        if self.before: self.before(name)
        result = self.service.call(self.token, name, args or {}, key or secrets.token_hex(16))
        if self.after: self.after(name, args or {}, result)
        return result


def profile():
    return dict(mission='Complete the assigned development task with recorded evidence',
        responsibilities=['Preserve acceptance and report unknowns'], focus_paths=[],
        workflow=['Inspect inputs', 'Edit within scope', 'Verify', 'Report'], report_when=['After work or failure'],
        style='Concise evidence and limitations', onboarding=['No physical operations or formal adoption'])


def assignment(sid, state, frozen, title=None):
    return {'session_id': sid, 'bot_id': 'evaluation-bot', 'state_id': state, 'kind': 'develop',
        'title': title or frozen['goal'], 'completion': frozen['acceptance'],
        'write_scope': frozen['write_scope'], 'dependencies': list(frozen['files']), 'after_tasks': []}


def setup(root, frozen, settings, supplied):
    root.mkdir(mode=0o700)
    service = Service(root/'ledger'); owner_token = service.bootstrap()['token']
    owner = LocalClient(service, owner_token); token = secrets.token_urlsafe(32)
    persist(root/'credentials.json', {'owner': owner_token, 'bot': token})
    p = owner.call('propose', {'title': 'Delegate isolated experiment only', 'changes': [{
        'id': 'evaluation-bot', 'type': 'principal', 'data': {'kind': 'agent', 'permissions': ['read','record','work'],
        'zones': ['root'], 'allowed_commands': sorted(PROFILES['bot']), 'token_hash': token_hash(token)}}]})
    ref = {'proposal_id': p['id'], 'version': p['version']}
    owner.call('submit', ref); owner.call('endorse', {**ref, 'reason': 'Isolated experimental scope'})
    owner.call('review_adoption', {**ref, 'reason': 'Access delegation only, no design adoption', 'verdict': 'approve'})
    owner.call('commit', ref); client = LocalClient(service, token)
    snapshot = owner.call('capture_artifact', {'files': frozen['files']})['revision_id']
    session = owner.call('connect_development', {'title': frozen['name'], 'snapshot': snapshot,
        'requirements': frozen['acceptance'], 'constraints': ['Preserve read-only acceptance files; no hardware operation'],
        'capture': {'scope': 'Explicit frozen files', 'missing': ['Unselected external dependencies']},
        'unverified': ['Physical behavior'], 'mode': 'execute', 'actors': ['evaluation-bot'],
        'write_scope': frozen['write_scope'], 'recipes': {}, 'max_executions': None,
        'max_parallel': 1, 'timeout_seconds': min(3600, settings['seconds'])})
    sid = session['id']
    state = owner.call('initialize_continuity', {'session_id': sid, 'version': session['version'],
        'hierarchy': [{'id': 'assembly', 'title': 'Selected project', 'kind': 'subsystem',
            'paths': list(frozen['files']), 'editable': True}],
        'context': {'requirements': frozen['acceptance'], 'constraints': ['No physical operation'],
            'decisions': [], 'open_questions': ['Physical behavior'], 'environment': frozen['environment']},
        'summary': 'Frozen baseline; no acceptance yet'})
    owner.call('configure_organization', {'organization_id': 'evaluation', 'version': 0, 'name': 'Evaluation',
        'profile': profile(), 'enabled': True, 'share_reflections': False})
    owner.call('configure_bot', {'bot_id': 'evaluation-bot', 'organization_id': 'evaluation', 'version': 0,
        'name': 'Development Bot', 'parent_bot_id': None, 'profile': profile(), 'enabled': True})
    owner.call('configure_bot_project', {'session_id': sid, 'organization_id': 'evaluation', 'version': 0,
        'lead_bot_id': 'evaluation-bot', 'goal': frozen['goal'], 'acceptance': frozen['acceptance'], 'enabled': True})
    owner.call('bind_development_bot', {'session_id': sid, 'bot_id': 'evaluation-bot', 'principal_id': 'evaluation-bot',
        'version': 0, 'write_scope': frozen['write_scope'], 'can_assign': False, 'can_integrate': False, 'enabled': True})
    config = {'bot_id': 'evaluation-bot', 'name': 'Evaluation runtime', 'backend': 'codex_subscription',
        'workflow': 'bot_development', 'agent_loop': True, 'experience_learning': True,
        'environment_definition': {'model': settings['model'], 'reasoning_effort': settings['reasoning_effort'],
            'environment': frozen['environment']},
        'local_tools': {'verify': {'argv': [frozen['environment']['executable'], '-B', frozen['verifier']['script']],
            'timeout_seconds': frozen['verifier']['timeout_seconds']}},
        'tool_runtime': frozen['environment']['runtime'], 'sandbox': frozen['environment']['sandbox']}
    if settings.get('learning_mode') == 'selective': config['learning_mode'] = 'selective'
    persist(root/'runtime-config.json', config)
    owner.call('configure_bot_runtime', {'bot_id': 'evaluation-bot', 'version': 0, 'principal_id': 'evaluation-bot',
        'enabled': True, 'environment': environment_manifest(config)})
    # Same setup task in both arms. Notes are imported assertions, not fabricated
    # successful runs. Cancelling does not enqueue a reflection/summary memory.
    seed = owner.call('assign_bot_task', assignment(sid, state['id'], frozen, 'Import declared starting context'))
    def no_inference(*args):
        require(False, 'invalid_state', 'Setup must never invoke inference')
    with BotWorker(client, config, root/'setup-journal', infer_fn=no_inference) as worker:
        claim = client.call('claim_bot_task', {'task_id': seed['id'], 'version': seed['version'],
            'runtime_fence': worker.runtime['fence']})
        if supplied:
            for note in frozen['experiences']:
                client.call('record_bot_experience', {'task_id': seed['id'], 'fence': claim['task']['fence'],
                    'observation': note['observation']+'\nDeclared source: '+note['source'],
                    'applicability': note['applicability'], 'limitations': note['limitations'] + [
                        'Imported hypothesis; original outcome and applicability have not been independently verified'],
                    'evidence': [seed['id']], 'used_memories': []})
        owner.call('cancel_bot_task', {'task_id': seed['id'], 'version': claim['task']['version'],
            'reason': 'Context import finished; this was not an engineering trial'})
    return owner, client, config, sid, state['id']
