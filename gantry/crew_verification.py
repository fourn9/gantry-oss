"""Bot-authored verification intent against saved acceptance, never execution."""
import copy
import hashlib
import json

from .contracts import validate
from .development import in_scope
from .model import canonical, digest, require
from .physical_evidence import evaluate
from .physical_execution import read
from .store import Store

TEXT = {'type': 'string', 'minLength': 1, 'maxLength': 2000}
NAMES = {'type': 'array', 'maxItems': 20, 'items': TEXT}
FIELDS = {'plan_path': TEXT, 'check_ids': {**NAMES, 'minItems': 1}, 'purpose': TEXT,
    'question': TEXT, 'assumptions': NAMES, 'missing_inputs': NAMES, 'tool_name': TEXT,
    'expected_outputs': {**NAMES, 'minItems': 1}, 'next_steps': {'type': 'object',
        'properties': {k: TEXT for k in ('pass', 'fail', 'unknown')},
        'required': ['pass', 'fail', 'unknown'], 'additionalProperties': False}}
SCHEMA = {'type': 'object', 'properties': FIELDS, 'required': list(FIELDS), 'additionalProperties': False}


def plan_verification(client, full, config, args, workspace):
    validate(args, SCHEMA)
    require(len(set(args['check_ids'])) == len(args['check_ids']), 'invalid_input', 'Select distinct check IDs')
    require(len(set(args['expected_outputs'])) == len(args['expected_outputs']), 'invalid_input', 'Use distinct report paths')
    path = args['plan_path']; Store.safe_name(path)
    for name in args['expected_outputs']: Store.safe_name(name)
    task = full['task']; current = full['development']; manifest = current['manifest']
    baseline = client.call('get_development_state', {'state_id': task['state_id']})
    missing = []
    tool = config.get('local_tools', {}).get(args['tool_name'])
    if tool is None: missing.append({'code': 'tool_unavailable', 'tool': args['tool_name']})
    mapping = config.get('tool_evidence', {}).get(args['tool_name'])
    if mapping != {'plan_path': path}:
        missing.append({'code': 'tool_evidence_mapping_missing', 'tool': args['tool_name'], 'plan_path': path})
    result = {**copy.deepcopy(args), 'version': 1, 'status': 'unexecutable',
        'input_state': current['state']['id'], 'baseline_state': task['state_id'],
        'plan': {'path': path, 'sha256': manifest.get(path, {}).get('hash')}, 'checks': [],
        'tool': {'name': args['tool_name'], 'available': tool is not None,
                 'recipe_hash': digest(tool) if tool is not None else None},
        'missing': missing, 'execution': {'performed': False}, 'formal_adoption': False,
        'limitations': ['Planned does not mean executed, safe, verified or adopted.',
            'Purpose, assumptions and next steps are Bot hypotheses, not new authority.',
            'Run the chosen owner-approved tool separately; inspect its bound evidence before choosing a next step.']}
    if path not in manifest or not (workspace/path).exists():
        missing.append({'code': 'plan_missing', 'path': path}); return result
    raw = read(workspace, path, 1024**2); plan_hash = hashlib.sha256(raw).hexdigest()
    require(plan_hash == manifest[path]['hash'] == baseline['manifest'].get(path, {}).get('hash'),
            'stale_basis', 'Verification acceptance must match the task baseline and saved current state')
    try: plan = json.loads(raw)
    except (ValueError, UnicodeError):
        require(False, 'invalid_input', 'Verification plan must be valid JSON')
    require(isinstance(plan, dict) and set(plan) == {'version', 'components', 'checks'}
            and plan['version'] == 1 and isinstance(plan['components'], list)
            and isinstance(plan['checks'], list) and 1 <= len(plan['checks']) <= 100,
            'invalid_input', 'Bounded frozen physical plan v1 required')
    require(all(isinstance(c, dict) and isinstance(c.get('id'), str) for c in plan['checks']),
            'invalid_input', 'Every check needs an ID')
    checks = {c['id']: c for c in plan['checks']}
    require(len(checks) == len(plan['checks']) and set(args['check_ids']) <= set(checks),
            'invalid_input', 'Select existing unique check IDs from the frozen plan')
    selected = [checks[ident] for ident in args['check_ids']]
    reports = [c.get('report') for c in selected]
    require(all(isinstance(p, str) for p in reports) and set(reports) == set(args['expected_outputs']),
            'invalid_input', 'Expected outputs must be exactly the selected frozen reports')
    hashes = {}; total = len(raw)
    for check in selected:
        inputs = check.get('inputs')
        require(isinstance(inputs, list) and 1 <= len(inputs) <= 100
                and all(isinstance(p, str) for p in inputs) and len(set(inputs)) == len(inputs),
                'invalid_input', 'Check inputs must be distinct saved paths')
        for name in inputs:
            Store.safe_name(name)
            if name in hashes: continue
            require(len(hashes) < 100, 'invalid_input', 'Select at most 100 distinct input files')
            hashes[name] = None
            if name not in manifest or not (workspace/name).exists():
                missing.append({'code': 'input_missing', 'path': name}); continue
            data = read(workspace, name); total += len(data)
            require(total <= 256*1024**2, 'invalid_input', 'Verification input acquisition exceeds 256 MiB')
            hashes[name] = hashlib.sha256(data).hexdigest()
            if hashes[name] != manifest[name]['hash']:
                missing.append({'code': 'input_changed', 'path': name})
        # Validates finite thresholds, units and evaluator contract without inventing a result.
        evaluate(check, None, {name: hashes[name] for name in inputs})
        Store.safe_name(check['report'])
        require(check['report'] not in [path, *inputs], 'invalid_input', 'Reports cannot overwrite frozen inputs')
        if not in_scope(check['report'], task['write_scope']):
            missing.append({'code': 'report_outside_scope', 'path': check['report']})
        observed = next((c for c in current.get('engineering', {}).get('checks', [])
            if c['id'] == check['id'] and c.get('physical_plan') == {'path': path, 'sha256': plan_hash}), None)
        recorded = None if observed is None else {'status': observed['status'],
            'effective_status': observed['effective_status'],
            'comparisons': observed.get('physical_result', {}).get('comparisons', []),
            'reasons': observed.get('physical_result', {}).get('reasons', [])}
        result['checks'].append({**copy.deepcopy(check), 'input_hashes': {p: hashes[p] for p in inputs},
                                 'recorded_result': copy.deepcopy(recorded)})
    result['status'] = 'unexecutable' if missing or args['missing_inputs'] else 'planned'
    require(len(canonical(result).encode()) <= 128000, 'invalid_input', 'Verification plan too large; select fewer checks')
    return result
