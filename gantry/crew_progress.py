"""A read-only, role-scoped view of progress for evidence-driven Worker tasks."""
import hashlib
import json

from .connection_policy import clean_bytes, safe_path
from . import crew_consultation, crew_literal
from .crew_json import pointer_value
from .crew_observe import observation_actions
from .development import in_scope
from .model import Fault, canonical, digest, require


def validate_guide(config):
    if 'evidence_guide' not in config:
        return
    guide = config['evidence_guide']
    require(config.get('agent_loop') and config.get('workflow') == 'bot_development'
            and isinstance(guide, dict) and set(guide) in ({'source'}, {'source','publish_observed'}, {'source','candidate','check_tool'},
                {'source','candidate','check_tool','consultation_policy'}),
            'invalid_input', 'An evidence guide needs a Bot action loop and a source, with optional candidate and check tool')
    crew_consultation.validate_source(guide['source'])
    if 'publish_observed' in guide:
        crew_literal.validate_publisher(guide['publish_observed'])
    if 'consultation_policy' in guide:
        crew_consultation.validate_policy(guide['consultation_policy'])
    if 'candidate' in guide:
        safe_path(guide['candidate'])
        require(isinstance(guide['check_tool'], str) and guide['check_tool'] in config.get('local_tools', {}),
                'invalid_input', 'Choose an installed check tool')


def check_definition(config, tool):
    return digest([tool, config.get('local_tools', {}).get(tool), config.get('sandbox'),
                   config.get('tool_runtime'), config.get('tool_evidence', {}).get(tool)])


def _receipts(full):
    for action in observation_actions(full.get('actions', [])[:64]):
        if action.get('task_id') != full['task']['id']:
            continue
        details = action.get('details', {})
        result = details.get('result')
        if not isinstance(result, dict):
            continue
        if action.get('kind') in {'edit','replace'}:
            # The receipt identifies the saved content even for a large edit body.
            yield action, {}, result
            continue
        encoded = details.get('arguments')
        if not isinstance(encoded, str) or len(encoded) > 8192:
            continue
        try:
            args = json.loads(encoded)
        except (ValueError, RecursionError):
            continue
        if isinstance(args, dict):
            yield action, args, result


def _observed(receipts, source, files, manifest):
    path = source['path']
    text = files.get(path)
    if path not in manifest or not isinstance(text, str) or hashlib.sha256(text.encode()).hexdigest() != manifest[path]['hash']:
        return None
    for action, args, result in receipts:
        if (action['kind'] != 'inspect_json' or args != source or result.get('error')
                or result.get('pointer') != source['pointer'] or result.get('next_offset') is not None):
            continue
        origin = result.get('source')
        value = result.get('value')
        if (not isinstance(origin, dict) or origin.get('sha256') != manifest[path]['hash'] or origin.get('path') != path
                or isinstance(value, (list,dict)) or len(canonical(value).encode()) > 1024):
            continue
        try:
            current = pointer_value(json.loads(text), source['pointer'])
            clean_bytes(canonical(value).encode())
            if canonical(current) == canonical(value):
                return {'value':value,'action_id':action['id'],'source_hash':origin['sha256']}
        except (ValueError, RecursionError, Fault):
            return None
    return None


def _consultation(full, receipts):
    questions = [q for q in full.get('consultations', []) if q.get('blocking')]
    if not questions:
        return None
    q = next((q for q in questions if q['status'] in {'open','answered'}), questions[-1])
    response = q.get('response_report') or {}
    request = response.get('request')
    view = {'id':q['id'],'status':q['status'],'request':request,'report_state':response.get('state_id'),'report':None}
    for action, args, result in receipts:
        if (action['kind'] != 'inspect' or not request or args != request or result.get('error') or
                result.get('task_id') != request['task_id'] or result.get('pointer') != request['pointer']
                or result.get('next_offset') is not None):
            continue
        report = result.get('value')
        if isinstance(report,dict):
            item = {k:report[k] for k in ('status','summary','unverified') if k in report}
            if isinstance(item.get('summary'),str) and len(canonical(item).encode()) <= 2048:
                try:
                    clean_bytes(canonical(item).encode())
                except Fault:
                    continue
                view['report'] = {**item,'action_id':action['id']}
                break
    return view


def evidence_guide(full, files, config, check_basis):
    task, dev = full['task'], full['development']
    state, manifest = dev['state']['id'], dev['manifest']
    source, candidate = config['source'], config.get('candidate')
    route = (crew_consultation.compare(full, files, config['consultation_policy'])
             if crew_consultation.applies(full, config) else None)
    if not route and (source['path'] not in manifest or source['path'] not in files):
        return None
    if candidate:
        if task['kind'] != 'develop' or (not route and candidate not in manifest) or not in_scope(candidate,task['write_scope']):
            return None
    elif task['kind'] != 'report' or not full.get('response_request'):
        return None
    receipts = list(_receipts(full))
    observed = _observed(receipts, source, files, manifest)
    consultation = _consultation(full, receipts)
    check = {'name':config.get('check_tool'),'status':'not_observed'}
    edit = previous_check = None
    for action, args, result in receipts:
        if (candidate and not edit and action['kind'] in {'edit','replace'} and result.get('path') == candidate
                and not result.get('error') and result.get('hash') == manifest.get(candidate, {}).get('hash') and candidate in manifest):
            edit = action['id']
        if candidate and action['kind'] == 'tool' and args.get('name') == check['name'] and not result.get('diagnostic'):
            if action.get('input_state') != state or not check_basis or result.get('check_definition') != check_basis:
                if previous_check is None:
                    previous_check = {'state_id':action.get('input_state'),'action_id':action['id'],
                                      'same_definition':bool(check_basis and result.get('check_definition') == check_basis)}
                continue
            if check['status'] != 'not_observed':
                continue
            passed = (not result.get('error') and type(result.get('exit_code')) is int and result['exit_code'] == 0
                      and bool(result.get('output_artifact')) and not result.get('reason'))
            check.update(status='passed' if passed else 'failed',action_id=action['id'])
    if (consultation and consultation['status'] == 'answered' and consultation['report']
            and (consultation['report'].get('status') != 'completed' or consultation['report_state'] != state)):
        phase, focus = 'reassess_peer_evidence', []
    elif consultation and consultation['status'] == 'answered':
        phase, focus = ('review_answer',['inspect']) if not consultation['report'] else ('assess_answer',['resolve'])
    elif consultation and consultation['status'] == 'open':
        phase, focus = 'await_answer',['finish']
    elif route and route['status'] != 'consistent' and not route['consulted']:
        phase, focus = 'consult_responsible_peer',['ask']
    elif not observed and not route:
        phase, focus = 'inspect_source',['inspect_json']
    elif not candidate:
        phase, focus = 'report_evidence',['finish']
    elif check['status'] == 'passed':
        phase, focus = 'review_for_submission',['finish']
    elif edit and check['status'] == 'not_observed':
        phase, focus = 'check_candidate',['tool']
    else:
        phase, focus = 'choose_candidate',(['edit','replace'] if route else ['edit','replace','ask'])
    extra = {'routing':route} if route else {}
    if route and 'literal_source' in config['consultation_policy']:
        extra['literal'] = crew_literal.candidate(full,route,config)
        if route['status']!='consistent' and not extra['literal']['value'] and not (consultation and consultation['status'] in {'open','answered'}):
            phase, focus = 'consult_responsible_peer',['ask']
    if crew_literal.publication_enabled(full,config):
        extra['publication'] = crew_literal.publication(full,config,observed)
    return {**extra, 'state_id':state,'source':source,'observed':observed,'candidate':candidate,'candidate_hash':manifest.get(candidate, {}).get('hash'),'edit_action_id':edit,
            'check':check,'previous_check':previous_check,'consultation':consultation,'phase':phase,'focus_actions':focus,
            'coverage':'Up to 64 recent task actions; missing receipts are unknown. The assigned contract still governs completion.'}


def choose_focused(choose, prompt, options, kinds, guide, candidate_write_hashes=None):
    """Optional bridge for choice-based providers. Keep every original action reachable."""
    if not guide:
        return choose(prompt, options)
    focus = [o for o in options if kinds[o] in guide['focus_actions']]
    if candidate_write_hashes and guide['check']['status'] == 'failed':
        # Only literals guaranteed to write the same bytes to the guided target
        # are redundant. A changed state, another file or new check clears this.
        focus = [o for o in focus if o not in candidate_write_hashes or
                 candidate_write_hashes[o] != guide['candidate_hash']]
    if not focus or len(focus) == len(options):
        return choose(prompt, options)
    escape = 'Show the full action menu'
    if escape in options:
        return choose(prompt, options)
    choice = choose(prompt, [*focus, escape])
    return choose(prompt, options) if choice == escape else choice
