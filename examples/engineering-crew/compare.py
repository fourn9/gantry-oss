"""Opt-in held-out file-loop / Gantry comparison; private outputs, real tools/model.

No model is invoked by importing this module or with --prepare-only.
"""
import argparse
import base64
import copy
import hashlib
import json
import resource
import shutil
import sys
import tempfile
import time
from pathlib import Path

from gantry.adapters import restore_files
from gantry.bot_worker import BotWorker, environment_manifest
from gantry.contracts import validate
from gantry.crew_runtime import GUIDE, SCHEMA, action_schemas
from gantry.crew_timing import summarize
from gantry.hardware import publish
from gantry.learning_evaluation import usage
from gantry.learning_evaluation_case import environment
from gantry.learning_evaluation_setup import setup, assignment
from gantry.model import Fault, canonical, digest, require
from gantry.monthly_codex import infer_monthly
from gantry.project_files import read_file, write_file
from gantry.project_sandbox import backend, runtime_roots, execute
from gantry.runner import persist

WINDOW = 1800
SCOPE = ['design.json', 'control.json', 'fixed.step', 'carrier.step', 'report.json', 'trace.json']
GOAL = 'Resolve the recorded nominal CAD and executable control acceptance gaps. Inspect inputs, choose corrections, test them and report the result and limitations.'
ACCEPTANCE = ['All frozen interface criteria pass on the final saved combination using fresh build/verify tool evidence.',
              'Do not edit the evaluator, controller implementation, calibration or acceptance plan.',
              'No physical feasibility, safety or formal adoption claim.']
LIMITATIONS = [
    'One held-out parameter case per arm, not a causal benchmark or a development-wide speedup claim.',
    'Same accessible input files and tool recipes; prompts/action menus/context packaging differ by treatment.',
    'B is one Bot with Core evidence and planning; no Mentor, delegation, prior memories or learning-loop treatment.',
    'Model=None uses the CLI default; the provider receipt does not prove the resolved model remained identical.',
    'Model duration includes provider/CLI/network wait; internal thinking time and host sleep are not separately observed.',
    'Nominal static CAD and a software filter only; no dynamics, loads, electrical, tolerance or hardware validation.',
    'Tool process CPU time and peak RSS are process-tree observations, not remote inference resource use.',
]


def sha(raw): return hashlib.sha256(raw).hexdigest()


def files_at(workspace):
    return {p.name: read_file(workspace, p.name) for p in sorted(workspace.iterdir()) if p.is_file()}


class Measurement:
    def __init__(self, root):
        self.root = root; self.start = None; self.rows = []; self.calls = []; self.tools = []
        self.phase = 'setup'; self.resources = None; self.wall_start_ns = None

    def event(self, kind, **values):
        row = {'timestamp_ns': time.time_ns(), 'elapsed': time.monotonic()-self.start if self.start else None,
               'phase': self.phase, 'kind': kind, **values}
        self.rows.append(row)
        with (self.root/'timeline.jsonl').open('a') as stream: stream.write(canonical(row)+'\n')

    def begin(self):
        self.start = time.monotonic(); self.wall_start_ns = time.time_ns(); self.phase = 'measurement'
        self.resources = resource.getrusage(resource.RUSAGE_CHILDREN); self.event('measurement_start')

    def elapsed(self):
        return max(time.monotonic()-self.start, (time.time_ns()-self.wall_start_ns)/1e9)

    def active(self):
        if self.start is not None:
            require(self.elapsed() < WINDOW, 'observation_timeout', 'The equal 1800-second observation window ended')

    def infer(self, context, schema, directory):
        self.active(); started = time.monotonic()
        call = {'attempt': len(self.calls)+1, 'started_at_ns': time.time_ns(), 'status': 'started', 'usage': None}
        self.calls.append(call); self.event('inference_start', attempt=call['attempt'])
        try:
            receipt = infer_monthly(context, schema, directory,
                timeout_seconds=max(.1, min(180, WINDOW-self.elapsed())),
                model=None, reasoning_effort='low')
            call.update(status='completed', provider=receipt['provider'], usage=receipt['provider'].get('usage'),
                        action=receipt['output'].get('action'))
            self.active(); return receipt
        except Exception as exc:
            call.update(status='failed', error=exc.code if isinstance(exc, Fault) else type(exc).__name__)
            raise
        finally:
            call.update(finished_at_ns=time.time_ns(), seconds=time.monotonic()-started)
            persist(self.root/'model-calls.json', self.calls); self.event('inference_end', **call)

    def before_api(self, name):
        if name in {'claim_bot_task', 'refresh_bot_task', 'check_bot_task', 'checkpoint_bot_task'}: self.active()


def tool(workspace, name, tools, metrics, *, scope=SCOPE, phase='tool'):
    started = time.monotonic(); stamp = time.time_ns()
    try: return _tool(workspace, name, tools, metrics, scope=scope, phase=phase)
    except Exception as exc:
        row = {'name': name, 'phase': phase, 'started_at_ns': stamp, 'finished_at_ns': time.time_ns(),
               'seconds': time.monotonic()-started, 'exit_code': None,
               'reason': exc.code if isinstance(exc, Fault) else type(exc).__name__}
        metrics.tools.append(row); metrics.event('tool_error', **row); raise


def _tool(workspace, name, tools, metrics, *, scope, phase):
    """Same approved argv and sandbox as Crew; validate all outputs before copyback."""
    require(name in tools, 'scope_denied', 'Only build and verify are installed')
    before = files_at(workspace); started = time.monotonic(); stamp = time.time_ns()
    metrics.event('tool_start', name=name, tool_phase=phase)
    with tempfile.TemporaryDirectory(dir=metrics.root) as temp:
        scratch = Path(temp)
        for path, raw in before.items(): (scratch/path).write_bytes(raw)
        result = execute(tools[name], scratch, runtime_roots(), backend(), metrics.active)
        changed = []
        for path in before:
            require((scratch/path).is_file(), 'scope_denied', 'Tool deleted a source')
        for path in scratch.iterdir():
            if path.name in {'.test-output', 'home', 'tmp'}: continue
            require(path.is_file() and not path.is_symlink(), 'scope_denied', 'Unexpected tool output')
            raw = read_file(scratch, path.name)
            if raw != before.get(path.name):
                require(path.name in scope, 'scope_denied', 'Tool changed frozen input')
                changed.append((path.name, raw))
        for path, raw in changed:
            write_file(workspace, path, raw, sha(before[path]) if path in before else 'absent')
    row = {'name': name, 'phase': phase, 'started_at_ns': stamp, 'finished_at_ns': time.time_ns(),
           'seconds': time.monotonic()-started, 'sandbox_seconds': result['seconds'],
           'exit_code': result['exit_code'], 'reason': result['reason'],
           'input_hashes': {p: sha(raw) for p, raw in before.items()},
           'output_hashes': {p: sha(raw) for p, raw in files_at(workspace).items()}}
    metrics.tools.append(row); metrics.event('tool_end', **row)
    return result


def physical_plan(cad_backend):
    inputs = ['design.json', 'control.json', 'calibration.json', 'build.py', 'verify.py', 'controller.py', 'fixed.step', 'carrier.step']
    plan = {'version': 1, 'components': [
        {'id': 'carrier', 'role': 'moving carrier', 'assembly': 'assembly', 'paths': ['design.json', 'carrier.step', 'fixed.step']},
        {'id': 'control', 'role': 'position command', 'assembly': 'assembly', 'paths': ['control.json', 'calibration.json', 'controller.py']}],
        'checks': [{'id': 'interface', 'scope': 'placement', 'components': ['carrier', 'control'], 'required': True,
            'inputs': inputs, 'report': 'report.json', 'conditions': {'unit': 'mm', 'frame': 'assembly', 'steps': 80},
            'evaluator': {'name': 'native-cad-control', 'version': '1'}, 'environment': {'cad_backend': cad_backend},
            'requirement_refs': [], 'criteria': [
                {'metric': 'overlap', 'unit': 'mm3', 'max': .001}, {'metric': 'clearance', 'unit': 'mm', 'min': 1},
                {'metric': 'carrier_x', 'unit': 'mm', 'min': 11, 'max': 20},
                {'metric': 'cad_source_error', 'unit': 'mm', 'max': .01}, {'metric': 'control_error', 'unit': 'mm', 'max': .01}]}]}
    return plan


def prepare(root, metrics):
    from gantry import cad_kernel as cad
    require(backend() != 'unavailable', 'sandbox_unavailable', 'A supported OS sandbox is required')
    generation_start = time.monotonic()
    workspace = root/'initial'; workspace.mkdir(mode=0o700)
    for name in ('build.py', 'verify.py', 'controller.py'):
        (workspace/name).write_bytes(Path(__file__).with_name(name).read_bytes())
    for path, values in {'design.json': {'carrier_x_mm': -4}, 'control.json': {'target_mm': 0},
                         'calibration.json': {'offset_mm': -3}}.items():
        (workspace/path).write_text(canonical(values))
    plan = physical_plan(cad.BACKEND)
    (workspace/'physical-plan.json').write_text(canonical(plan))
    tools = {name: {'argv': [sys.executable, '-B', name+'.py'], 'timeout_seconds': 60} for name in ['build', 'verify']}
    for name in tools:
        result = tool(workspace, name, tools, metrics, phase='baseline')
        require(result['exit_code'] == 0 and not result['reason'], 'fixture_failed', 'Native baseline tool failed', result=result)
    files = files_at(workspace)
    frozen = {'name': 'Held-out nominal engineering comparison', 'goal': GOAL, 'acceptance': ACCEPTANCE,
        'baseline_generation_seconds': time.monotonic()-generation_start,
        'write_scope': SCOPE, 'files': {p: base64.b64encode(raw).decode() for p, raw in files.items()},
        'manifest': {p: sha(raw) for p, raw in files.items()}, 'experiences': [],
        'environment': {**environment(), 'executable': sys.executable, 'cad_backend': cad.BACKEND},
        'verifier': {'script': 'verify.py', 'timeout_seconds': 60}, 'plan': plan,
        'acceptance_hash': digest({'goal': GOAL, 'acceptance': ACCEPTANCE, 'plan': plan,
            'immutable': {p: sha(raw) for p, raw in files.items() if p not in SCOPE}})}
    persist(root/'frozen.json', frozen); return frozen, tools


def setup_b(root, frozen, tools, metrics):
    owner, client, config, sid, state_id = setup(root/'core', frozen,
        {'model': None, 'reasoning_effort': 'low', 'seconds': WINDOW}, [])
    config.update(experience_learning=False, local_tools=tools,
                  tool_evidence={'verify': {'plan_path': 'physical-plan.json'}})
    owner.call('configure_bot_runtime', {'bot_id': config['bot_id'], 'version': 1,
        'principal_id': config['bot_id'], 'enabled': True, 'environment': environment_manifest(config)})
    change = owner.call('begin_change', {'state_id': state_id, 'title': 'Import identical baseline measurements',
        'purpose': 'Record real tool output', 'write_scope': SCOPE, 'dependencies': [], 'assignee': 'admin'})
    state = publish(owner, state_id, change['id'], change['version'], root/'initial', 'physical-plan.json', 'baseline')['state']
    for path, field in [('design.json', 'carrier_x_mm'), ('control.json', 'target_mm'), ('calibration.json', 'offset_mm')]:
        owner.call('extract_json_evidence', {'state_id': state['id'], 'subject_id': 'assembly', 'path': path,
            'profile': 'configuration.v1', 'fields': [{'name': field, 'pointer': '/'+field, 'unit': 'mm', 'frame': 'assembly', 'time_basis': 'configuration'}]})
    task = owner.call('assign_bot_task', assignment(sid, state['id'], frozen))
    client.before = metrics.before_api
    persist(root/'treatment.json', {'session_id': sid, 'state_id': state['id'], 'task_id': task['id'], 'config': config})
    return owner, client, config, task


def load_fixture(root, source):
    """Reuse only immutable setup bytes, never the source arm's model history."""
    from gantry import cad_kernel as cad
    source = source.resolve(); frozen = json.loads(read_file(source, 'frozen.json'))
    names = {'build.py', 'verify.py', 'controller.py', 'design.json', 'control.json', 'calibration.json',
             'physical-plan.json', 'fixed.step', 'carrier.step', 'report.json', 'trace.json'}
    require(set(frozen['files']) == names and set(frozen['manifest']) == names,
            'invalid_fixture', 'Fixture contains unexpected or missing files')
    files = {p: base64.b64decode(frozen['files'][p], validate=True) for p in names}
    require(all(sha(raw) == frozen['manifest'][p] for p, raw in files.items()), 'invalid_fixture', 'Fixture hash mismatch')
    for name in ['build.py', 'verify.py', 'controller.py']:
        require(files[name] == Path(__file__).with_name(name).read_bytes(), 'stale_fixture', 'Fixture scripts differ from this source version')
    for name, value in {'design.json': {'carrier_x_mm': -4}, 'control.json': {'target_mm': 0}, 'calibration.json': {'offset_mm': -3}}.items():
        require(json.loads(files[name]) == value, 'invalid_fixture', 'Only the unchanged held-out initial parameters may be shared')
    plan = physical_plan(cad.BACKEND)
    require(json.loads(files['physical-plan.json']) == plan and frozen['plan'] == plan,
            'invalid_fixture', 'Fixture acceptance differs from the frozen protocol')
    expected = digest({'goal': GOAL, 'acceptance': ACCEPTANCE, 'plan': plan,
        'immutable': {p: sha(raw) for p, raw in files.items() if p not in SCOPE}})
    require(frozen['acceptance_hash'] == expected and frozen['goal'] == GOAL and frozen['acceptance'] == ACCEPTANCE
            and frozen['write_scope'] == SCOPE, 'invalid_fixture', 'Fixture contract mismatch')
    current = {**environment(), 'executable': sys.executable, 'cad_backend': cad.BACKEND}
    require(all(digest(current[k]) == digest(frozen['environment'][k]) for k in ['python', 'executable', 'packages', 'sandbox', 'runtime', 'cad_backend']),
            'stale_fixture', 'Use the same installed runtime as the shared fixture')
    workspace = root/'initial'; workspace.mkdir(mode=0o700)
    for path, raw in files.items(): (workspace/path).write_bytes(raw)
    frozen['environment'] = current
    frozen['fixture_manifest_hash'] = digest(frozen['manifest'])
    persist(root/'frozen.json', frozen)
    tools = {name: {'argv': [sys.executable, '-B', name+'.py'], 'timeout_seconds': 60} for name in ['build', 'verify']}
    return frozen, tools


def plain(root, frozen, tools, metrics):
    workspace = root/'workspace'; shutil.copytree(root/'initial', workspace)
    schema = copy.deepcopy(SCHEMA); schema['properties']['action']['enum'] = ['read', 'edit', 'tool', 'finish']
    schemas = {k: v for k, v in action_schemas().items() if k in schema['properties']['action']['enum']}
    history = []; last = None
    while True:
        metrics.active(); number = len(history); directory = root/'journals'/str(number)
        files = files_at(workspace)
        previews = {}
        for path, raw in files.items():
            try: previews[path] = {'hash': sha(raw), 'size': len(raw), 'text': raw[:6000].decode()}
            except UnicodeError: previews[path] = {'hash': sha(raw), 'size': len(raw), 'binary': True}
        context = {'goal': GOAL, 'acceptance': ACCEPTANCE, 'write_scope': SCOPE, 'files': previews,
            'available_tools': tools, 'action_schemas': schemas, 'action_guide': {k: GUIDE[k] for k in schemas},
            'instruction': 'Choose one action. Only local files and logs are available; no ledger. '
                'Read action-log.json to retrieve earlier receipts. Finish uses edits=[], assignments=[], integrate_changes=[]. '
                'No physical operations or adoption. Use actual tool evidence; do not invent results.',
            'recent_history': history[-12:], 'last_result': last, 'round': number}
        receipt = metrics.infer(context, schema, directory/'model'); output = receipt['output']
        action = output['action']; started = time.monotonic(); stamp = time.time_ns()
        try:
            args = json.loads(output['arguments_json']); validate(args, schemas[action])
            if action == 'read':
                require(args['path'] in files or args['path'] == 'action-log.json', 'scope_denied', 'Read a known project file')
                raw = canonical(history).encode() if args['path'] == 'action-log.json' else read_file(workspace, args['path'])
                offset = args.get('offset', 0); chunk = raw[offset:offset+min(args.get('length', 6000), 6000)]
                try: payload = {'text': chunk.decode()}
                except UnicodeError: payload = {'base64': base64.b64encode(chunk).decode()}
                last = {**payload, 'hash': sha(raw), 'size': len(raw), 'next_offset': offset+len(chunk) if offset+len(chunk)<len(raw) else None}
            elif action == 'edit':
                require(args['path'] in SCOPE, 'scope_denied', 'Frozen file is read-only')
                write_file(workspace, args['path'], args['content'].encode(), args['expected_hash'])
                last = {'path': args['path'], 'hash': sha(args['content'].encode())}
            elif action == 'tool': last = tool(workspace, args['name'], tools, metrics)
            else:
                require(not args['edits'] and not args['assignments'] and not args['integrate_changes'], 'scope_denied', 'Finish cannot perform edits or delegation')
                persist(root/'model-report.json', args); last = {'report': args}
        except (Fault, ValueError, KeyError, OSError) as exc:
            last = {'error': exc.code if isinstance(exc, Fault) else type(exc).__name__, 'message': str(exc)[:1000]}
        row = {'attempt': number+1, 'started_at_ns': stamp, 'finished_at_ns': time.time_ns(), 'action': action,
               'rationale': output['rationale'], 'arguments': output['arguments_json'], 'result': last, 'seconds': time.monotonic()-started}
        history.append(row); persist(root/'actions.json', history); metrics.event('action', action=action, error=last.get('error'))
        if action == 'finish' and 'report' in last: return workspace, last['report']['status']


def gantry(root, frozen, tools, metrics, prepared):
    owner, client, config, task = prepared
    with BotWorker(client, config, root/'journals', metrics.infer) as worker:
        results = worker.tick(); persist(root/'worker-results.json', results)
    final = owner.call('get_bot_task', {'task_id': task['id']}); persist(root/'task.json', final)
    state_id = final['task'].get('output_state', final['task']['state_id'])
    detail = owner.call('get_development_state', {'state_id': state_id}); persist(root/'linked-final.json', detail)
    workspace = root/'workspace'; restore_files(owner, detail['state']['snapshot'], workspace)
    actions = []; after = None
    while True:
        page = owner.call('get_bot_records', {'task_id': task['id'], 'kind': 'actions', 'limit': 100, **({'after': after} if after else {})})
        actions.extend(page['items']); after = page['next_cursor']
        if not after: break
    persist(root/'actions.json', actions); persist(root/'core-integrity.json', {'verify': owner.call('verify'), 'replay': owner.call('replay')})
    return workspace, final['task']['status']


def final_check(root, workspace, frozen, tools, metrics):
    metrics.active(); files = files_at(workspace)
    immutable = {p: files.get(p) is not None and sha(files[p]) == expected for p, expected in frozen['manifest'].items() if p not in SCOPE}
    require(all(immutable.values()), 'evaluation_tampered', 'Read-only evaluation or input changed', immutable=immutable)
    # Never build here: this must not fix absent/stale CAD on the model's behalf.
    audit = root/'final-audit'; shutil.copytree(workspace, audit)
    submitted_report = json.loads((audit/'report.json').read_text())
    required = frozen['plan']['checks'][0]['inputs']
    submitted_fresh = submitted_report.get('inputs') == {p: sha(read_file(audit, p)) for p in required}
    # A file report is evidence only if an actual approved tool produced it at
    # the submitted inputs. B's fenced linkage is checked separately below.
    if (root/'linked-final.json').exists():
        linked = json.loads((root/'linked-final.json').read_text())
        check = next((c for c in linked['engineering']['checks'] if c['id'] == 'interface'), {})
        physical = check.get('physical_result', {}); execution = physical.get('execution', {})
        actions = json.loads((root/'actions.json').read_text())
        tool_receipt = any(a['kind'] == 'tool' and a['input_state'] == execution.get('input_state')
            and json.loads(a['details'].get('arguments', '{}')).get('name') == 'verify'
            and a['details'].get('result', {}).get('exit_code') == 0
            and not a['details'].get('result', {}).get('reason')
            and a['details'].get('result', {}).get('output_artifact') == execution.get('output_artifact') for a in actions)
        raw_check = next((c for c in linked['state']['context']['environment']['engineering']['checks'] if c['id'] == 'interface'), {})
        publication = any(a['kind'] == 'tool_evidence' and a['details'].get('result', {}).get('exit_code') == 0
            and 'report.json' in a['details'].get('result', {}).get('refreshed_paths', [])
            and a['details'].get('result', {}).get('evidence_publication', {}).get('state_id') == linked['state']['id']
            and raw_check in a['details'].get('result', {}).get('evidence_publication', {}).get('checks', []) for a in actions)
        linked_fresh = bool(check.get('effective_status') == 'pass' and physical.get('status') == 'pass'
            and execution.get('exit_code') == 0 and execution.get('action_key') and tool_receipt and publication
            and check.get('evidence', {}).get('report.json') == sha(read_file(audit, 'report.json'))
            and all(check.get('inputs', {}).get(p) == sha(read_file(audit, p)) for p in required))
    else:
        executions = [t for t in metrics.tools if t['phase'] == 'tool' and t['name'] == 'verify']
        linked_fresh = any(t['exit_code'] == 0 and not t['reason']
            and all(t['input_hashes'].get(p) == sha(read_file(audit, p)) for p in required)
            and t['output_hashes'].get('report.json') == sha(read_file(audit, 'report.json')) for t in executions)
    result = tool(audit, 'verify', tools, metrics, scope=['report.json', 'trace.json'], phase='final_audit')
    require(result['exit_code'] == 0 and not result['reason'], 'evaluation_failed', 'Independent verify failed', result=result)
    report = json.loads((audit/'report.json').read_text()); comparisons = []
    for criterion in frozen['plan']['checks'][0]['criteria']:
        value = report['measurements'].get(criterion['metric'], {}); measured = value.get('value')
        passed = type(measured) in {float, int} and value.get('unit') == criterion['unit']
        passed = passed and ('min' not in criterion or measured >= criterion['min']) and ('max' not in criterion or measured <= criterion['max'])
        comparisons.append({'criterion': criterion, 'observed': value, 'passed': bool(passed)})
    return {'accepted': submitted_fresh and linked_fresh and all(x['passed'] for x in comparisons),
            'submitted_report_fresh': submitted_fresh, 'actual_tool_evidence_linked': linked_fresh,
            'immutable': immutable, 'comparisons': comparisons, 'tool': result, 'formal_adoption': False}


def metrics_summary(root, metrics, total):
    tools = [x for x in metrics.tools if x['phase'] != 'baseline']
    # Crew's real execution receipts retain sandbox duration even on capture failure.
    for path in (root/'journals').rglob('tool-execution.json') if (root/'journals').exists() else []:
        r = json.loads(path.read_text())
        spans = [json.loads(p.read_text()) for p in (path.parent/'timing').glob('*.json')]
        action_span = next((s for s in spans if s['phase'] == 'action'), {})
        tools.append({'phase': 'crew_tool', 'seconds': r['seconds'],
            'action_started_at_ns': action_span.get('started_at_ns'), 'action_finished_at_ns': action_span.get('finished_at_ns'),
            'exit_code': r['exit_code'], 'reason': r['reason'], 'receipt': str(path.relative_to(root))})
    actions_path = root/'actions.json'; actions = json.loads(actions_path.read_text()) if actions_path.exists() else []
    action_errors = sum(bool(x.get('result', {}).get('error') or x.get('details', {}).get('result', {}).get('error')) for x in actions)
    model_seconds = sum(x['seconds'] for x in metrics.calls); tool_seconds = sum(x['seconds'] for x in tools)
    r = resource.getrusage(resource.RUSAGE_CHILDREN); initial = metrics.resources
    return {'total_wall_seconds': total, 'total_monotonic_seconds': time.monotonic()-metrics.start,
        'model_seconds': model_seconds, 'tool_seconds': tool_seconds,
        'other_harness_record_restore_wait_seconds': max(0, total-model_seconds-tool_seconds),
        'deliberate_sleep_seconds': 0, 'host_sleep_seconds': None, 'provider_wait_seconds': None,
        'model_attempts': len(metrics.calls), 'tool_attempts': len(tools), 'action_count': len(actions),
        'action_errors': action_errors, 'model_errors': sum(c['status'] != 'completed' for c in metrics.calls),
        'tool_errors': sum(t['exit_code'] != 0 or bool(t['reason']) for t in tools),
        'usage': usage(metrics.calls), 'tools': tools,
        'child_user_cpu_seconds': r.ru_utime-initial.ru_utime, 'child_system_cpu_seconds': r.ru_stime-initial.ru_stime,
        'child_peak_rss_native_units_includes_setup': r.ru_maxrss,
        'crew_phases': summarize(root/'journals'), 'parent_interventions': [],
        'human_active_seconds': None, 'human_interventions_during_run': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--condition', choices=['A', 'B'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--fixture', type=Path, help='Prepared setup directory; reuse only frozen initial files, never its journals')
    parser.add_argument('--prepare-only', action='store_true', help='Run actual native setup, never invoke inference')
    args = parser.parse_args(); root = args.output.resolve()
    require(not root.exists() and not root.is_relative_to(Path(__file__).resolve().parents[2]), 'scope_denied', 'Use a new private output directory outside the source repository')
    root.mkdir(parents=True, mode=0o700); metrics = Measurement(root); setup_start = time.monotonic()
    try:
        frozen, tools = load_fixture(root, args.fixture) if args.fixture else prepare(root, metrics)
        frozen['fixture_manifest_hash'] = digest(frozen['manifest']); persist(root/'frozen.json', frozen)
        prepared = setup_b(root, frozen, tools, metrics) if args.condition == 'B' else None
        setup_seconds = time.monotonic()-setup_start
        protocol = {'condition': args.condition, 'model': None, 'reasoning_effort': 'low', 'window_seconds': WINDOW,
            'acceptance_hash': frozen['acceptance_hash'], 'fixture_manifest_hash': frozen['fixture_manifest_hash'],
            'setup_seconds': setup_seconds, 'shared_fixture': bool(args.fixture),
            'baseline_generation_seconds': frozen.get('baseline_generation_seconds'), 'limitations': LIMITATIONS,
            'parent_setup': 'Harness, anonymous held-out baseline, frozen criteria, authority and tools; no proposed solution or model outputs.',
            'source_hashes': {p.name: sha(p.read_bytes()) for p in [Path(__file__), Path(__file__).with_name('build.py'), Path(__file__).with_name('verify.py'), Path(__file__).with_name('controller.py')]}}
        persist(root/'protocol.json', protocol)
        if args.prepare_only:
            persist(root/'result.json', {'status': 'prepared_not_executed', **protocol}); print(canonical({'status': 'prepared_not_executed', 'output': str(root)})); return
        metrics.begin(); status = 'error'; validation = None; error = None
        try:
            workspace, status = plain(root, frozen, tools, metrics) if args.condition == 'A' else gantry(root, frozen, tools, metrics, prepared)
            validation = final_check(root, workspace, frozen, tools, metrics)
        except Exception as exc:
            error = {'code': exc.code if isinstance(exc, Fault) else type(exc).__name__, 'message': str(exc)}
            metrics.event('run_error', **error)
        total = (time.time_ns()-metrics.wall_start_ns)/1e9
        accepted = bool(status == 'completed' and validation and validation['accepted'] and total <= WINDOW)
        result = {'status': 'accepted' if accepted else 'not_accepted', 'task_status': status, 'validation': validation,
            'error': error, 'setup_seconds': setup_seconds, 'condition': args.condition, 'acceptance_hash': frozen['acceptance_hash'],
            'fixture_manifest_hash': frozen['fixture_manifest_hash'],
            'metrics': metrics_summary(root, metrics, total), 'limitations': LIMITATIONS}
        persist(root/'result.json', result); print(canonical({'status': result['status'], 'seconds': total, 'output': str(root)}))
    except Exception as exc:
        persist(root/'setup-error.json', {'type': type(exc).__name__, 'message': str(exc), 'seconds': time.monotonic()-setup_start})
        raise


if __name__ == '__main__': main()
