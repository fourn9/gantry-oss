"""Paired local model experiments on the normal Crew Worker. Run from a source checkout."""
import argparse
import hashlib
import itertools
import json
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

from personal_guidance_trial import BotLearningTests, LocalClient, LocalModel, Service, seed
from gantry.bot_worker import BotWorker, environment_manifest
from gantry.project_sandbox import backend, runtime_roots

CASES = [('yoke', 'amber', 'amber'), ('retainer', 'blue', 'blue'),
         ('sled', 'amber and blue; current signatures disagree', 'blue')]
PREPARED = [('collar', 'amber', 'amber'), ('spacer', 'blue', 'blue'),
            ('link', 'amber and blue; current signatures disagree', 'blue')]
SMOKE = ('smoke', 'amber and blue; current signatures disagree', 'amber')
CHECK = ("from pathlib import Path; import json,sys; "
         "ok=Path('mechanical.txt').read_text()==json.loads(Path('control.txt').read_text())['release']; "
         "print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)")
# Exact (truncated) model-generated lesson used by the prior source-checkout experiment.
LESSON = """**Conditional Procedure:**

**When to Apply:**
- When the assembly drawing shows the blue guide, design copied it, and the release check failed.

**When to Ask:**
- When the fixture register identifies the amber guide for station T17, and Manufacturing states the drawing persists across fixture replacements.

**Action:**
1. **Review the Assembly Drawing:**
   - Ensure that the blue guide is no longer present in the current assembly"""
READ = 'Look up the current signed register'
ASK = 'Ask manufacturing which guide this revision releases'
INSPECT = 'Read the exact manufacturing response report'
RESOLVE = 'Resolve the consultation citing the received answer'
CHECK_ACTION = 'Run the release check on the current saved candidate'
SUBMIT = 'Submit the candidate'
BLUE, AMBER = ('Save blue guide', 'Save amber guide')
PEEK = 'Read the manufacturing release for this revision'
REPORTS = ['Report release: blue', 'Report release: amber', 'Report release: unknown']


class FrozenLesson:
    def text(self, _):
        return LESSON


def checkpoint(f, case):
    part, register, release = case
    change = f.owner.call('begin_change', {'state_id': f.base['id'], 'title': part, 'purpose': 'Select guide',
        'dependencies': [], 'write_scope': ['mechanical.txt', 'control.txt'], 'assignee': 'admin'})
    snapshot = f.artifact({'mechanical.txt': 'undecided',
                           'control.txt': json.dumps({'register': register, 'release': release})})
    result = f.owner.call('checkpoint_change', {'change_id': change['id'], 'version': change['version'],
        'snapshot': snapshot, 'summary': 'New fixture register', 'rationale': 'Independent exercise',
        'unfinished': ['Select and test the guide'], 'capture': {'scope': 'saved fixtures', 'missing': []},
        'work_status': 'paused'})
    return result['state']['id']


def actions(client, task_id):
    return client.call('get_bot_records', {'task_id': task_id, 'kind': 'actions', 'limit': 100})['items']


def score(owner, view, case, final_state, task_actions):
    expected = case[2]
    verified = [a['id'] for a in task_actions if a['kind'] == 'tool' and a['input_state'] == final_state
                and a['details']['result'].get('exit_code') == 0 and a['details']['result'].get('output_artifact')
                and not a['details']['result'].get('error')]
    actual = view['development']['manifest']['mechanical.txt']['hash']
    consultations = []
    for question in view['consultations']:
        report = question.get('response_report') or {}
        peer_id = report.get('request', {}).get('task_id')
        if not peer_id:
            continue
        peer = owner.call('get_bot_task', {'task_id': peer_id})
        read = any(a['kind'] == 'inspect_json' and a['details']['result'].get('pointer') == '/release'
                   and a['details']['result'].get('value') == expected for a in actions(owner, peer_id))
        inspected = any(a['kind'] == 'inspect' and json.loads(a['details']['arguments']) == report['request']
                        and a['details']['result'].get('value', {}).get('summary') == 'Report release: '+expected
                        for a in task_actions)
        cited = any(a['kind'] == 'resolve' and question.get('answer_id') in json.loads(a['details']['arguments']).get('evidence', [])
                    and not a['details']['result'].get('error') for a in task_actions)
        consultations.append({'peer_task': peer_id, 'peer_checked_source': read, 'read_exact_report': inspected,
            'cited': cited, 'status': question['status'], 'peer_status': peer['task']['status']})
    consulted = any(c['cited'] and c['read_exact_report'] and c['peer_checked_source']
                    and c['status'] == 'resolved' and c['peer_status'] == 'completed' for c in consultations)
    right = actual == hashlib.sha256(expected.encode()).hexdigest()
    accepted = view['task']['status'] == 'completed' and right and bool(verified) and ('disagree' not in case[1] or consulted)
    return {'passed': accepted, 'status': view['task']['status'], 'correct_file': right,
            'check_receipts': verified, 'consultations': consultations, 'expected_digest': hashlib.sha256(expected.encode()).hexdigest(),
            'actual_digest': actual}


def run(f, model, home, case, state_id, past, mid, memory, feedback, rotation, smoke=False, prefix=()):
    setup = time.perf_counter()
    shutil.copytree(f.root/'ledger', home/'ledger')
    service = Service(home/'ledger')
    owner = LocalClient(service, f.token)
    clients = {k: LocalClient(service, f.tokens[k]) for k in ('designer', 'control')}
    history = next(a['details']['rationale'] for a in actions(clients['designer'], past) if a['kind'] == 'review_feedback')
    decisions = {'designer': [], 'control': []}
    receipts = []
    snapshot_seconds = time.perf_counter()-setup

    def infer(ctx, schema, directory):
        role = ctx['bot']['id']
        peer = role == 'control'
        log = decisions[role]
        last = ctx.get('last_result') or {}
        if last and log:
            if 'exit_code' in last:
                outcome = 'Check exit code '+str(last['exit_code'])+' '+last.get('output', '').strip()
            elif 'changed' in last:
                outcome = 'Saved digest '+last['hash'][:12]
                if feedback:
                    assert last['saved_state_id'] == ctx['development']['state']['id']
                    outcome += (' (content changed)' if last['changed'] else ' (unchanged; same saved state)')
                    outcome += '; recorded evaluation: '+last['recorded_verification']
            elif 'value' in last:
                value = last['value']
                outcome = str(value.get('summary', value) if isinstance(value, dict) else value)
            else:
                outcome = str(last.get('error') or ('Acknowledged' if not last.get('reason') else last['reason']))
            log[-1]['result'] = outcome
        q = next(iter(ctx.get('consultations', [])), {})
        if not peer and q.get('status') == 'open':
            kind, args = 'finish', f.answer(status='waiting', summary='Await manufacturing')
        elif len(log) >= (4 if peer else 8+len(prefix)):
            kind, args = 'finish', f.answer(status='failed', summary='Decision budget exhausted')
        else:
            if peer:
                options = [PEEK, *REPORTS]
                prompt = 'Manufacturing reviewer. Identify the effective released guide for this revision. Report your finding to the requester.'
            else:
                prompt = (ctx['task']['title']+'. Drawing shows blue. Deliver the correct saved guide after a passing release check. '
                    'If signatures disagree, obtain the effective release from manufacturing, read the report and resolve with evidence. '
                    'A saved design still needs a check. Submit when done. Historical record: '+history)
                if memory:
                    lesson = next(m for m in ctx['memory']['items'] if m['id'] == mid)
                    prompt += '\nRecalled conditional lesson (one source): '+lesson['lesson']['strategy']
                prompt += '\nCurrent guide file: '+ctx['files']['mechanical.txt']+'; consultation: '+q.get('status', 'none')
                options = [READ]
                if not q: options.append(ASK)
                if q.get('status') == 'answered': options.extend([INSPECT, RESOLVE])
                options.extend([BLUE, AMBER, CHECK_ACTION, SUBMIT])
            options = options[rotation:]+options[:rotation]
            prompt += '\nYour previous actions and observations: '+json.dumps([(row['choice'], row.get('result')) for row in log])
            stamp = time.perf_counter()
            primed = not peer and len(log) < len(prefix)
            if primed:
                choice = prefix[len(log)]
                assert choice in options
            elif smoke:
                order = [PEEK, REPORTS[1]] if peer else [READ, ASK, INSPECT, RESOLVE, AMBER, CHECK_ACTION, SUBMIT]
                choice = order[len(log)]
                assert choice in options, (choice, options, q)
            else:
                choice = model.choose(prompt, options)
            log.append({'choice': choice, 'source': 'fixture' if smoke or primed else 'model', 'decision_seconds': time.perf_counter()-stamp,
                        'input_state': ctx['development']['state']['id']})
            if choice in (READ, PEEK):
                kind, args = 'inspect_json', {'path': 'control.txt', 'pointer': '/release' if peer else '/register'}
            elif choice == ASK:
                kind, args = 'ask', {'to_bot_id': 'control', 'question': 'Which guide is effective for this fixture revision?',
                                     'evidence': [ctx['development']['state']['id']]}
            elif choice == INSPECT:
                kind, args = 'inspect', q['response_report']['request']
            elif choice == RESOLVE:
                kind, args = 'resolve', {'message_id': q['id'], 'reason': 'Reviewed this fixture question', 'evidence': [q['answer_id']]}
            elif choice in (AMBER, BLUE):
                kind, args = 'edit', {'path': 'mechanical.txt', 'content': choice.split()[1],
                                      'expected_hash': hashlib.sha256(ctx['files']['mechanical.txt'].encode()).hexdigest()}
            elif choice == CHECK_ACTION:
                kind, args = 'tool', {'name': 'release_check'}
            else:
                kind, args = 'finish', f.answer(summary=choice)
        return {'output': {'action': kind, 'arguments_json': json.dumps(args), 'rationale': args.get('summary', kind)},
                'provider': {'kind': 'instrument_smoke' if smoke else 'local_model_constrained_choice'}}

    start = time.perf_counter()
    task = owner.call('assign_bot_task', {**f.assignment('designer', title='Select fixture guide for '+case[0], state_id=state_id),
                                          'session_id': f.sid})
    with BotWorker(clients['designer'], f.configs['designer'], home/'runtime', infer) as designer, \
            BotWorker(clients['control'], f.configs['control'], home/'runtime', infer) as control:
        for worker in (designer, control, designer):
            results = worker.tick()
            receipts.extend([{'task_id': r.get('task', {}).get('id'), 'status': r.get('status') or r.get('task', {}).get('status'),
                              'reason': r.get('reason')} for r in results])
            view = owner.call('get_bot_task', {'task_id': task['id']})
            if view['task']['status'] in {'completed','failed','blocked'}: break
    task_actions = actions(owner, task['id'])
    final_state = view['development']['state']['id']
    result = score(owner, view, case, final_state, task_actions)
    elapsed = time.perf_counter()-start
    if smoke:
        assert not score(owner, view, case, 'different-state', task_actions)['passed']
        assert not score(owner, view, case, final_state, [a for a in task_actions if a['kind'] != 'inspect'])['passed']
        assert not score(owner, view, (case[0], case[1], 'blue'), final_state, task_actions)['passed']
    edits = [a for a in task_actions if a['kind'] == 'edit']
    return {**result, 'case': case[0], 'memory': memory, 'feedback': feedback, 'rotation': rotation, 'task_id': task['id'],
        'base_state': state_id, 'final_state': final_state, 'seconds': elapsed, 'clone_seconds': snapshot_seconds,
        'duplicate_saves': sum(a['details']['result'].get('changed') is False for a in edits),
        'checks': sum(a['kind']=='tool' for a in task_actions), 'receipts': receipts, 'decisions': decisions,
        'parent_interventions': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--smoke', action='store_true')
    modes.add_argument('--prepared-start', action='store_true', help='Separate diagnostic with a recorded, fixture-driven prefix')
    args = parser.parse_args()
    root = args.output.resolve()
    if root.exists() or root.is_relative_to(Path(__file__).resolve().parents[1]):
        parser.error('Specify a new private output directory outside the checkout')
    root.mkdir(mode=0o700, parents=True)
    if not args.smoke and not args.model: parser.error('Specify local model directory')
    t = time.perf_counter()
    model = None if args.smoke else LocalModel(args.model.resolve())
    model_load = time.perf_counter()-t
    t = time.perf_counter()
    f = BotLearningTests()
    f.setUp()
    try:
        past, mid, _ = seed(f, FrozenLesson())
        for role in ('designer','control'):
            config = f.configs[role]
            config.update(agent_loop=True)
            if role == 'designer':
                config.update(local_tools={'release_check': {'argv': [str(Path(sys.base_prefix)/'bin'/'python3'), '-c', CHECK],
                    'timeout_seconds': 10}}, sandbox=backend(), tool_runtime=runtime_roots())
            f.owner.call('configure_bot_runtime', {'bot_id': role,'version': 1, 'principal_id': role,
                'enabled': True, 'environment': environment_manifest(config)})
        cases = [SMOKE] if args.smoke else PREPARED if args.prepared_start else CASES
        states = {case[0]: checkpoint(f, case) for case in cases}
        groups = [(SMOKE, True, True, 0)] if args.smoke else list(itertools.product(cases, [False,True], [False,True], range(2)))
        random.Random(9091).shuffle(groups)
        freeze = {'commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=Path(__file__).parent,text=True).strip(),
                  'model_load_seconds': model_load, 'fixture_seconds': time.perf_counter()-t, 'states':states,
                  'groups':groups, 'smoke':args.smoke, 'prepared_start':args.prepared_start}
        (root/'manifest.json').write_text(json.dumps(freeze,indent=2))
        for i, (case, memory, feedback, rotation) in enumerate(groups):
            n = len(model.transcript) if model else 0
            prefix = ()
            if args.prepared_start:
                prefix = (READ, ASK) if 'disagree' in case[1] else (READ, AMBER, AMBER)
            row = run(f, model, root/str(i), case, states[case[0]], past, mid, memory, feedback, rotation, args.smoke, prefix)
            row['fixture_prefix'] = prefix
            with (root/'runs.jsonl').open('a') as out: print(json.dumps(row),file=out)
            if model: (root/str(i)/'inference.json').write_text(json.dumps(model.transcript[n:]))
            print(i, row['case'], row['passed'], row['status'], round(row['seconds'],2),flush=True)
            if args.smoke:
                assert row['passed'], row
    finally:
        f.tearDown()


if __name__ == '__main__':
    main()
