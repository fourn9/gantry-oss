"""Opt-in transfer of a categorical observation, with its immutable read receipt."""
import hashlib
import json

from .connection_policy import clean_bytes
from .contracts import A, S, validate
from .crew_consultation import MAX_SOURCE, distinct_keys, validate_source
from .crew_json import pointer_value
from .crew_observe import observation_actions
from .model import Fault, canonical, identifier, require
from .project_files import read_file

FIELD = {'type':'string','maxLength':512}
OBSERVATION = {'type':'object','properties':{'path':S,'pointer':FIELD,'action_id':S,'sha256':S,
                                             'value':{'type':'string','minLength':1,'maxLength':128}},
               'required':['path','pointer','action_id','sha256','value'],'additionalProperties':False}
SUBMISSION = {'type':'object','properties':{'summary':S,'rationale':S,'unverified':A},
              'required':['summary','rationale','unverified'],'additionalProperties':False}


AFTER_EDIT = {'type':'object','properties':{'name':S,'submit_on_pass':SUBMISSION},
              'required':['name','submit_on_pass'],'additionalProperties':False}


def validate_publisher(policy):
    require(isinstance(policy,dict) and set(policy)=={'requester','allowed_values'}, 'invalid_input',
            'Declare the requesting Bot and values approved for sharing')
    identifier(policy['requester'])
    values=policy['allowed_values']
    require(isinstance(values,list) and 0 < len(values) <= 64 and
            all(isinstance(v,str) and v.strip() and len(v)<=128 for v in values),
            'invalid_input','Declare bounded categorical values')
    clean_bytes(canonical(values).encode())


def publication_enabled(full, config):
    request = full.get('response_request') or {}
    policy = config.get('publish_observed') or {}
    return bool(policy and full['task']['kind']=='report' and not full['task'].get('experience_check')
                and request.get('consultation_basis') and request.get('from_bot_id') == policy['requester'])


def summary(observation):
    label = observation['pointer'].split('/')[-1] or 'value'
    return 'Report '+label+': '+observation['value']


def publisher_files(full, workspace, role):
    source = role['source']['path']
    if full['development']['manifest'].get(source,{}).get('size',MAX_SOURCE+1)<=MAX_SOURCE:
        try:
            return {source:read_file(workspace,source).decode()}
        except (UnicodeError,OSError):
            pass
    return {}


def publication(full, config, observed):
    if (not publication_enabled(full,config) or not observed
            or observed['value'] not in config['publish_observed']['allowed_values']):
        return None
    observation = {**config['source'],'action_id':observed['action_id'],'sha256':observed['source_hash'],
                   'value':observed['value']}
    return {'observation':observation,'summary':summary(observation)}


def verify_report(service, state, actor, task, report):
    if 'observation' not in report:
        return
    obs = report['observation']
    source = {k:obs[k] for k in ('path','pointer')}
    validate_source(source)
    message = state.get('bot_task_messages',{}).get(task.get('reply_request_id'),{})
    require(task['kind']=='report' and not task.get('experience_check') and message.get('consultation_basis')
            and message.get('response_task_id')==task['id'] and report['status']=='completed'
            and not report['integrate_changes'] and report['summary']==summary(obs),
            'invalid_input','A cited observation must answer its routed question verbatim')
    sid = task.get('output_state',task['state_id'])
    saved = service._continuity_state(state,actor,sid)
    info = service._manifest(state,saved['snapshot']).get(obs['path'])
    require(info and info['size']<=MAX_SOURCE and info['hash']==obs['sha256'],
            'evidence_required','Source revision no longer matches')
    record = state.get('bot_actions',{}).get(obs['action_id'],{})
    require(record.get('task_id')==task['id'] and record.get('input_state')==sid,
            'evidence_required','Cite your read action on this state')
    read = False
    for action in observation_actions([record]):
        if action.get('kind')!='inspect_json':
            continue
        details = action.get('details',{})
        result = details.get('result')
        try:
            args = json.loads(details.get('arguments',''))
        except (TypeError,ValueError,RecursionError):
            continue
        if (args==source and isinstance(result,dict) and not result.get('error') and result.get('next_offset') is None
                and result.get('pointer')==obs['pointer'] and result.get('value')==obs['value']
                and isinstance(result.get('source'),dict) and result['source'].get('path')==obs['path']
                and result['source'].get('sha256')==info['hash']):
            read = True
            break
    require(read,'evidence_required','Reported value differs from the linked read')
    raw = clean_bytes(b''.join(service.store.verified_parts(info)))
    try:
        value = pointer_value(json.loads(raw,object_pairs_hook=distinct_keys),obs['pointer'])
    except (ValueError,UnicodeError,RecursionError,Fault):
        raise Fault('evidence_required','Reported field is unavailable') from None
    clean_bytes(canonical(obs['value']).encode())
    require(value==obs['value'],'evidence_required','Report differs from immutable source bytes')


def selected_value(full, route, source, allowed):
    if route['status']=='consistent':
        return route['sources'][0]['value']
    if not route['consulted']:
        return None
    current = full['development']['manifest'].get(source['path'],{}).get('hash')
    values = set()
    for q in full.get('consultations',[]):
        obs = q.get('reviewed_observation') or {}
        if (q.get('status')=='resolved' and q.get('to_bot_id')==route['peer']
                and q.get('reviewed_basis')==route['basis'] and q.get('answer_id')
                and q['answer_id'] in q.get('resolution',{}).get('evidence',[])
                and current and obs.get('sha256')==current and obs.get('value') in allowed
                and all(obs.get(k)==v for k,v in source.items())):
            values.add(obs['value'])
    return values.pop() if len(values)==1 else None


def candidate(full, route, config):
    policy = config['consultation_policy']
    value = selected_value(full,route,policy['literal_source'],policy['allowed_values'])
    target = config['candidate']
    current = full['development']['manifest'].get(target,{}).get('hash','absent')
    return {'path':target,'value':value,'expected_hash':current,
            'matches':value is not None and hashlib.sha256(value.encode()).hexdigest()==current}


def check_arguments(args, guide):
    """Keep exploratory measurement available while requiring a saved literal for acceptance."""
    if not guide or not guide.get('literal') or args.get('name')!=guide['check']['name']:
        return args, False
    fields = {'name':S,'submit_on_pass':SUBMISSION,'diagnostic_reason':S}
    validate(args,{'type':'object','properties':fields,'required':['name'],'additionalProperties':False})
    diagnostic = 'diagnostic_reason' in args
    require(not (diagnostic and 'submit_on_pass' in args), 'invalid_input','A diagnostic cannot authorize submission')
    require(diagnostic or guide['literal']['matches'], 'evidence_required',
            'Save the reviewed value before its acceptance check. For a baseline measurement, provide diagnostic_reason.')
    return {'name':args['name']}, diagnostic


def continuation(token, full, guide, preferences):
    if not token or not guide or not (guide.get('literal') or {}).get('matches'):
        return None
    task = full['task']
    if (token['task']!=task['id'] or token['attempt']!=task['attempt'] or token['discussion']!=task['discussion_version']
            or token['state']!=full['development']['state']['id'] or token['preferences']!=preferences
            or any(m['blocking'] and m['status']!='resolved' for m in full['messages'])):
        return None
    if 'edit' in token:
        if token['edit']!=guide.get('edit_action_id') or token['name']!=guide['check']['name']:
            return None
        return {'output':{'action':'tool','arguments_json':canonical({'name':token['name'],'submit_on_pass':token['report']}),
                          'rationale':token['report']['rationale']},
                'provider':{'kind':'conditional_check','edit_action_id':token['edit']}}
    if guide['check'].get('action_id')!=token['check'] or guide['check']['status']!='passed':
        return None
    args = {**token['report'],'status':'completed','assignments':[],'integrate_changes':[],'edits':[]}
    return {'output':{'action':'finish','arguments_json':canonical(args),'rationale':args['rationale']},
            'provider':{'kind':'conditional_submission','check_action_id':token['check']}}


def offer(guide):
    """Arguments the Bot can accept, review or decline; reporting fields remain the Bot's decision."""
    if guide.get('publication') and guide['phase']=='report_evidence':
        return {'action':'finish','arguments':guide['publication']}
    literal = guide.get('literal')
    if not literal or literal['value'] is None:
        return None
    if guide['phase']=='choose_candidate' and not literal['matches']:
        return {'action':'edit','arguments':{'path':literal['path'],'content':literal['value'],
                                            'expected_hash':literal['expected_hash']}}
    if literal['matches'] and guide['phase'] in {'check_candidate','choose_candidate'} and guide['check']['status']=='not_observed':
        return {'action':'tool','arguments':{'name':guide['check']['name']}}
    if literal['matches'] and guide['phase']=='review_for_submission':
        return {'action':'finish','arguments':{'status':'completed'},'check_action_id':guide['check']['action_id']}
    return None


def verify_submission(state, task, report, guard):
    """Recheck the Bot's recorded intent inside the finish transaction."""
    check = state.get('bot_actions',{}).get(guard['action_id'],{})
    require(check.get('kind')=='tool' and check.get('task_id')==task['id']
            and check.get('input_state')==task.get('output_state',task['state_id'])
            and check.get('attempt')==task['attempt'] and task['discussion_version']==guard['discussion_version'],
            'stale_basis','Conditional check no longer covers the task')
    details = check['details']
    result = details.get('result')
    try:
        args = json.loads(details.get('arguments',''))
    except (TypeError,ValueError,RecursionError):
        args = None
    require(isinstance(args,dict) and isinstance(args.get('submit_on_pass'),dict)
            and report=={**args['submit_on_pass'],'status':'completed','assignments':[],'integrate_changes':[]}
            and isinstance(result,dict) and type(result.get('exit_code')) is int and result['exit_code']==0
            and result.get('output_artifact') and result.get('check_definition')
            and not result.get('reason') and not result.get('error') and not result.get('diagnostic'), 'evidence_required',
            'A completed installed check and its exact conditional report are required')
