"""Opt-in paired experiment through real Core/BotWorker, using isolated ledgers."""
import base64
import hashlib
import json
import random
import time
from pathlib import Path

from . import project_sandbox
from .adapters import restore_files
from .bot_worker import BotWorker
from .learning_evaluation_case import freeze_case, environment
from .learning_evaluation_report import ARMS, write_report
from .learning_evaluation_setup import setup, assignment
from .model import Fault, canonical, digest, require, uid
from .monthly_codex import infer_monthly
from .runner import persist


class Measurements:
    def __init__(self, root, frozen, row, settings, infer_fn, save):
        self.root, self.frozen, self.row, self.settings = root, frozen, row, settings
        self.infer_fn, self.save = infer_fn, save
        self.start = time.monotonic()
        self.owner = None

    def active(self):
        require(time.monotonic()-self.start < self.settings['seconds'],
            'evaluation_timeout', 'Experimental wall-clock limit reached')

    def inference(self, context, schema, directory):
        self.active()
        require(len(self.row['calls']) < self.settings['max_calls'],
            'evaluation_call_limit', 'Experimental inference call limit reached')
        call = {'phase': context.get('operation', 'action'), 'status': 'started',
            'elapsed_start': time.monotonic()-self.start, 'usage': None}
        self.row['calls'].append(call); self.save()
        start = time.monotonic()
        try:
            receipt = self.infer_fn(context, schema, directory, timeout_seconds=max(0.1,
                min(180, self.settings['seconds']-(time.monotonic()-self.start))),
                model=self.settings['model'], reasoning_effort=self.settings['reasoning_effort'])
            call.update(status='completed', usage=receipt['provider'].get('usage'), provider=receipt['provider'].get('kind'))
            self.active()
            return receipt
        except Exception as exc:
            call.update(status='failed', error=exc.code if isinstance(exc, Fault) else type(exc).__name__)
            raise
        finally:
            call['seconds'] = time.monotonic()-start; self.save()

    def before(self, name):
        if name in {'check_bot_task', 'refresh_bot_task', 'claim_bot_task', 'checkpoint_bot_task'}: self.active()

    def after(self, name, args, result):
        if name == 'checkpoint_bot_task': self.verify(result['state']['id'])
        if name == 'complete_bot_reflection':
            self.row.setdefault('reflections', []).append({'id': result['id'], 'status': result['status']})

    def verify(self, state_id):
        self.active()
        detail = self.owner.call('get_development_state', {'state_id': state_id})
        snapshot = detail['state']['snapshot']
        directory = self.root/'verification'/str(len(self.row['verification']))
        directory.mkdir(parents=True, mode=0o700)
        workspace = directory/'workspace'
        restore_files(self.owner, snapshot, workspace)
        for name, expected in self.frozen['manifest'].items():
            if name not in self.frozen['write_scope']:
                path = workspace/name
                require(path.is_file() and not path.is_symlink() and
                    hashlib.sha256(path.read_bytes()).hexdigest() == expected,
                    'evaluation_tampered', 'Frozen read-only verifier/input was changed')
        result = project_sandbox.execute({'argv': [self.frozen['environment']['executable'], '-B',
            self.frozen['verifier']['script']], 'timeout_seconds': self.frozen['verifier']['timeout_seconds']},
            workspace, self.frozen['environment']['runtime'], self.frozen['environment']['sandbox'], self.active)
        result.update(state_id=state_id, snapshot=snapshot, evaluator_hash=self.frozen['manifest'][self.frozen['verifier']['script']],
            accepted=result['exit_code'] == 0 and result['reason'] is None, elapsed=time.monotonic()-self.start,
            scope='Frozen Python acceptance; no physical certification or adoption')
        persist(directory/'result.json', result)
        artifact = self.owner.call('capture_artifact', {'files': {'evaluation.json': base64.b64encode(canonical(result).encode()).decode()}})
        evidence = self.owner.call('record', {'type': 'eval_result', 'data': {**result,
            'run_id': 'comparison:'+digest([state_id, snapshot]), 'verdict': 'pass' if result['accepted'] else 'fail',
            'artifact': artifact['revision_id']}})
        result['evidence_revision'] = evidence['revision_id']
        self.row['verification'].append(result); self.save()
        return result


def usage(calls):
    keys = ('input_tokens', 'cached_input_tokens', 'output_tokens')
    complete = bool(calls) and all(isinstance(c.get('usage'), dict) and c['status'] == 'completed' for c in calls)
    result = {'complete': complete, 'monetary_cost': None, 'cost_reason': 'Subscription usage; per-call money not reported'}
    for key in keys:
        known = [c['usage'][key] for c in calls if isinstance(c.get('usage'), dict) and type(c['usage'].get(key)) is int]
        result[key] = sum(known) if complete and len(known) == len(calls) else None
        result['observed_'+key] = sum(known) if known else None
    return result


def _actions(owner, task_id):
    result = []; cursor = None
    while True:
        page = owner.call('get_bot_records', {'task_id': task_id, 'kind': 'actions', 'limit': 100,
            **({'after': cursor} if cursor else {})})
        result.extend(page['items']); cursor = page['next_cursor']
        if not cursor: return sorted(result, key=lambda a: a['created_seq'])


def collect_actions(owner, row, root):
    actions = _actions(owner, row['task_id']); persist(root/'actions.json', actions)
    row['action_order'] = [a['kind'] for a in actions]
    tools = [a for a in actions if a['kind'] == 'tool']
    def signature(action):
        args = action['details']['arguments']
        try: args = {'parsed': json.loads(args)}
        except ValueError: args = {'malformed': args}  # Retain malformed calls as failures.
        return digest([args, action['details'].get('workspace_before')])
    signatures = [signature(a) for a in tools]
    row['repeated_identical_tool_checks'] = len(signatures)-len(set(signatures))
    detail = owner.call('get_bot_task', {'task_id':row['task_id']})
    plan = detail.get('learning_plan')
    row['learning_plan'] = {k:plan[k] for k in ('id','status','output','selection_method') if k in plan} if plan else None
    links=[]; cursor=None
    while True:
        page=owner.call('get_bot_records', {'task_id':row['task_id'], 'kind':'learning_uses', 'limit':100, **({'after':cursor} if cursor else {})})
        links.extend(page['items']); cursor=page['next_cursor']
        if not cursor: break
    row['experience_use_count']=len(links); persist(root/'experience-uses.json',links)
    row['failed_tool_checks'] = sum(bool(a['details'].get('result', {}).get('error')) or
        a['details'].get('result', {}).get('exit_code') not in (None, 0) or
        bool(a['details'].get('result', {}).get('reason')) for a in tools)


def run_evaluation(case_path, output, *, model, reasoning_effort, max_calls, seconds,
                   repetitions=1, seed=0, infer_fn=None, learning_mode="always"):
    require(isinstance(model, str) and model.strip() and '\x00' not in model, 'invalid_input', 'Pin an explicit model')
    require(reasoning_effort in {'minimal','low','medium','high','xhigh'}, 'invalid_input', 'Pin a supported reasoning effort')
    for value in (max_calls, seconds, repetitions):
        require(type(value) is int and value > 0, 'invalid_input', 'Positive experimental limits required')
    require(type(seed) is int, 'invalid_input', 'Integer randomization seed required')
    require(learning_mode in {"always","selective"}, "invalid_input", "Unknown learning mode")
    frozen = freeze_case(case_path)
    require(frozen['environment']['sandbox'] != 'unavailable', 'sandbox_unavailable', 'A supported OS sandbox is required')
    root = Path(output).resolve()
    source = (Path(case_path).resolve().parent / json.loads(Path(case_path).read_text())['project_root']).resolve()
    require(not root.is_relative_to(source), 'scope_denied', 'Keep experiment output outside the source project')
    require(not root.exists() and not root.is_symlink(), 'invalid_input', 'Use a new private output directory')
    root.mkdir(parents=True, mode=0o700)
    persist(root/'frozen-case.json', frozen)
    settings = dict(model=model, reasoning_effort=reasoning_effort, max_calls=max_calls, seconds=seconds,
                    repetitions=repetitions, seed=seed, learning_mode=learning_mode, backend='codex_subscription' if infer_fn is None else 'test_override')
    return run_frozen_evaluation(frozen, root, settings, infer_fn)


def run_frozen_evaluation(frozen, root, settings, infer_fn=None):
    first = random.Random(settings['seed']).randrange(2)
    trials = [{'pair': p, 'arm': ARMS[(first+p+i)%2], 'trial_id': uid('trial'),
               'status': 'pending', 'calls': [], 'verification': []}
              for p in range(settings['repetitions']) for i in range(2)]
    report = {'schema_version': 1, 'case_hash': frozen['case_hash'], 'settings': settings, 'trials': trials,
              'human_seconds': None, 'human_interventions': None,
              'limitations': ['Small opt-in comparison, no population-level effect claim',
                'Fixed Python verifier only; operator must ensure it measures the claimed acceptance',
                'Same requested model/effort, not guaranteed identical provider infrastructure',
                'Both arms use Crew; this measures experience availability, not Gantry versus no Gantry']}
    save = lambda: write_report(root, report)
    save()
    for row in trials:
        try: run_trial(root, frozen, settings, row, infer_fn or infer_monthly, save, row['arm'] == 'with_experience')
        except KeyboardInterrupt: break
    return save()


def run_trial(root, frozen, settings, row, infer_fn, save, supplied):
    started = time.monotonic(); row['status'] = 'running'; save()
    metrics = None; owner = None; arm_root = root/row['trial_id']
    try:
        require(digest(environment()) == digest(frozen['environment']), 'stale_basis', 'Runtime environment changed between arms')
        # No arm label in paths sent to the model; only the report knows the assignment.
        owner, client, config, sid, state = setup(arm_root, frozen, settings, supplied)
        row.update(setup_seconds=time.monotonic()-started, session_id=sid, initial_state=state)
        metrics = Measurements(arm_root, frozen, row, settings, infer_fn or infer_monthly, save)
        metrics.owner = owner
        baseline = metrics.verify(state)
        if baseline['accepted']:
            row['status'] = 'pre_satisfied'
            return
        task = owner.call('assign_bot_task', assignment(sid, state, frozen)); row['task_id'] = task['id']
        client.before, client.after = metrics.before, metrics.after
        with BotWorker(client, config, arm_root/'journals', infer_fn=metrics.inference) as worker:
            row['worker_results'] = worker.tick()
        final = owner.call('get_bot_task', {'task_id': task['id']})['task']
        row.update(task_status=final['status'], final_state=final.get('output_state', state))
        checked = metrics.verify(row['final_state'])
        pending = owner.call('list_bot_reflections', {'bot_id': 'evaluation-bot'})['items']
        reflections = row.get('reflections', []) + [{'id': r['id'], 'status': r['status']} for r in pending]
        row['reflections'] = reflections
        finished = final['status'] == 'completed' and bool(reflections) and all(r['status'] == 'completed' for r in reflections)
        row['status'] = 'accepted' if finished and checked['accepted'] else 'not_accepted' if finished else 'held'
    except (Exception, KeyboardInterrupt) as exc:
        code = exc.code if isinstance(exc, Fault) else type(exc).__name__
        row.update(status='timeout' if code in {'evaluation_timeout','provider_timeout'} else
            'interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed', error=code)
        if isinstance(exc, KeyboardInterrupt): raise
    finally:
        if owner and row.get('task_id'):
            try: collect_actions(owner, row, arm_root)
            except Exception as exc:
                row['metrics_error'] = exc.code if isinstance(exc, Fault) else type(exc).__name__
                if row['status'] == 'accepted': row['status'] = 'incomplete'
        if metrics:
            row['total_seconds'] = time.monotonic()-metrics.start
            if row['status'] == 'accepted' and row['total_seconds'] >= settings['seconds']:
                row.update(status='timeout', error='evaluation_timeout')
        else:
            row['setup_seconds'] = time.monotonic()-started
        row['usage'] = usage(row['calls']); save()
