"""Reuse PR review leases and user-supplied inference; never a publisher API key."""
from pathlib import Path
import base64
import json

from .model import require
from .connection_policy import clean_bytes
from .project_connect import LocalClient, private_dir
from .review_worker import prepare_review, finish_review


def setup(project, submission):
    context = project.context()
    require(context['connection']['plan']['mode'] == 'work-capable', 'mode_disabled', 'Review is not delegated')
    # User identity checks session membership before loading the separate reviewer credential.
    found = project.client.call('connection_review', {'submission_id': submission})
    require(found['id'] == submission, 'scope_denied', 'Unknown review')
    token_file = project.meta/'project-mentor.token'
    require(not token_file.is_symlink() and token_file.stat().st_mode & 0o077 == 0, 'unauthorized', 'Reviewer token must be private')
    client = LocalClient(project.client.service, token_file.read_text().strip())
    journal = private_dir(private_dir(project.meta/'reviews')/submission)
    return client, journal


def prepare(project, submission):
    client, journal = setup(project, submission)
    job = prepare_review(client, submission, journal)
    from .mentor_input import compact_review
    from .review_contracts import REVIEW_OUTPUT
    context = compact_review(job['context']); previews = {}; missing = []; remaining = 200000
    state = job['context']['development']['state']
    for name, info in job['context']['development']['manifest'].items():
        if Path(name).suffix.lower() not in {'.py', '.c', '.h', '.cpp', '.rs', '.json', '.xml', '.yaml', '.yml', '.toml', '.md'} or info['size'] > min(65536, remaining):
            missing.append(name); continue
        part = client.call('read_artifact_chunk', {'revision_id': state['snapshot'], 'path': name, 'index': 0})
        try: text = base64.b64decode(part['content']).decode('utf-8')
        except (UnicodeDecodeError, KeyError):
            missing.append(name); continue
        previews[name] = text; remaining -= info['size']
    context['saved_file_previews'] = previews; context['file_bodies_not_acquired'] = missing
    context['capture_limitations'] = ['CAD topology and physical behavior were not automatically inspected']
    evidence = {context['state_id'], context['base_state']}
    evidence.update(v['id'] for v in context.get('connection_evidence', {}).get('test_observations', []))
    evidence.update(v['revision_id'] for v in context.get('connection_evidence', {}).get('assumptions', []))
    evidence.update(v['id'] for v in context['development'].get('evaluations', []) if v['state_id'] == context['state_id'])
    # Registry schemas reuse A/S dictionaries. Break aliases before narrowing
    # evidence; deepcopy alone would also narrow paths and free-text lists.
    output_schema = json.loads(json.dumps(REVIEW_OUTPUT))
    def constrain(value):
        if not isinstance(value, dict): return
        for name, spec in value.get('properties', {}).items():
            if name == 'evidence': spec['items'] = {'type': 'string', 'enum': sorted(evidence)}
            else: constrain(spec)
        constrain(value.get('items'))
    constrain(output_schema)
    context['evidence_contract'] = 'Use exact IDs from the schema in evidence arrays. Put explanations in rationale/summary, never append text to an ID.'
    return {'context': context, 'output_schema': output_schema,
        'inference': 'user_client_required', 'independent_reviewer': False,
        'instruction': 'Use your existing model to inspect this saved change. Return grounded findings with code/CAD edits. Submit with mentor-finish. No owner decision is required within this delegation.'}


def finish(project, submission, output):
    clean_bytes(str(output).encode())
    client, journal = setup(project, submission)
    return finish_review(client, journal, output)


def review(project, submission):
    require(project.context()['connection']['plan']['delegation']['mentor'] == 'codex-subscription',
            'reauthorization_required', 'Automatic subscription inference was not delegated')
    prepared = prepare(project, submission)
    from .monthly_codex import infer_monthly
    receipt = infer_monthly(prepared['context'], prepared['output_schema'], project.meta/'reviews'/submission/'inference')
    return {'review': finish(project, submission, receipt['output']), 'provider': receipt['provider'],
            'automatic_inference': True, 'automatic_user_agent_launch': False}
