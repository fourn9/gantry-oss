"""Failure-to-lesson-to-held-out-work experiment, not automatic lesson validation."""
import copy
import json
from pathlib import Path

from .learning_evaluation import run_trial, run_frozen_evaluation
from .learning_evaluation_case import freeze_case
from .learning_evaluation_setup import LocalClient
from .model import digest, require, uid
from .monthly_codex import infer_monthly
from .runner import persist
from .service import Service


def generated_lessons(root, row):
    """Read only lessons from this actual completed training reflection."""
    if not row.get('reflections'): return []
    credentials = json.loads((root/'credentials.json').read_text())
    client = LocalClient(Service(root/'ledger'), credentials['owner'])
    eligible = {r['id'] for r in row['reflections'] if r['status'] == 'completed'}
    lessons = []; cursor = None
    while True:
        page = client.call('list_persistent_memories', {'bot_id': 'evaluation-bot', 'limit': 100,
            **({'after': cursor} if cursor else {})})
        lessons.extend(m for m in page['items'] if m.get('reflection_id') in eligible and m.get('lesson'))
        cursor = page['next_cursor']
        if not cursor: return sorted(lessons, key=lambda m: (m['created_seq'], m['id']))


def transfer_note(memory, training_hash):
    lesson = memory['lesson']
    # Preserve the actual generated strategy, conditions and provenance; never
    # import training solutions, full reports or manually rewrite a lesson.
    return {'observation': 'Generated training reflection: '+json.dumps(lesson, ensure_ascii=False),
        'applicability': lesson['when_to_use'],
        'limitations': memory['limitations'] + ['Generated hypothesis, not independently validated; recheck new conditions'],
        'source': 'training_case='+training_hash+'; memory='+memory['id']+'; sha256='+digest(memory)}


def run_transfer_evaluation(training_case, cases, output, *, model, reasoning_effort,
                            max_calls, seconds, repetitions=1, seed=0, infer_fn=None):
    require(isinstance(model, str) and model.strip() and '\x00' not in model, 'invalid_input', 'Pin model')
    require(reasoning_effort in {'minimal','low','medium','high','xhigh'}, 'invalid_input', 'Pin reasoning effort')
    require(all(type(n) is int and n > 0 for n in (max_calls, seconds, repetitions)) and type(seed) is int,
        'invalid_input', 'Positive experimental bounds and integer seed required')
    require(isinstance(cases, (list, tuple)) and 0 < len(cases) <= 20, 'invalid_input', 'Select 1–20 held-out cases')
    paths = [training_case, *cases]
    frozen = [freeze_case(p) for p in paths]  # Freeze all inputs BEFORE training.
    require(all(not c['experiences'] for c in frozen), 'invalid_input', 'Transfer study starts without supplied lessons')
    require(all(c['environment']['sandbox'] != 'unavailable' for c in frozen), 'sandbox_unavailable', 'OS sandbox required')
    root = Path(output).resolve()
    for path in paths:
        source = (Path(path).resolve().parent/json.loads(Path(path).read_text())['project_root']).resolve()
        require(not root.is_relative_to(source), 'scope_denied', 'Keep outputs outside every source project')
    require(not root.exists() and not root.is_symlink(), 'invalid_input', 'Use a new private output directory')
    root.mkdir(parents=True, mode=0o700)
    settings = dict(model=model, reasoning_effort=reasoning_effort, max_calls=max_calls, seconds=seconds,
        repetitions=repetitions, seed=seed, backend='codex_subscription' if infer_fn is None else 'test_override')
    persist(root/'frozen-inputs.json', frozen)
    row = {'trial_id': uid('trial'), 'status': 'pending', 'calls': [], 'verification': []}
    result = {'status': 'training', 'settings': settings, 'training': row, 'generated_lessons': [],
        'evaluations': [], 'planned_cases': [{'case_hash': f['case_hash'], 'status': 'pending'} for f in frozen[1:]],
        'limitations': ['Generated lessons are imported hypotheses, not validated rules',
            'Same model can repeat or rationalize mistakes; peer review is not physical certification',
            'Training is charged separately and must be included in any claimed amortized benefit',
            'Operator must ensure held-out tasks differ; freezing does not guarantee task quality']}
    save = lambda: persist(root/'transfer.json', result)
    save()
    try:
        run_trial(root, frozen[0], settings, row, infer_fn or infer_monthly, save, False)
        # A pre-satisfied baseline or absent outcome cannot establish this chain.
        if not row['verification'] or row['verification'][0]['accepted']:
            result['status'] = 'inconclusive_no_initial_failure'; return result
        lessons = generated_lessons(root/row['trial_id'], row)
        result['generated_lessons'] = lessons
        if not lessons:
            result['status'] = 'inconclusive_no_generated_lessons'; return result
        notes = [transfer_note(m, frozen[0]['case_hash']) for m in lessons]
        require(len(notes) <= 20, 'context_limit', 'Too many generated lessons; retain experiment for inspection')
        persist(root/'transferred-lessons.json', notes)
        result['status'] = 'evaluating'; save()
        for i, target in enumerate(frozen[1:]):
            target = copy.deepcopy(target); target['experiences'] = notes
            target['unseeded_case_hash'] = target.pop('case_hash'); target['case_hash'] = digest(target)
            directory = root/('case-'+str(i+1)); directory.mkdir(mode=0o700)
            persist(directory/'frozen-case.json', target)
            result['planned_cases'][i]['status'] = 'running'; save()
            report = run_frozen_evaluation(target, directory, settings, infer_fn)
            result['evaluations'].append(report)
            interrupted = any(t['status'] == 'interrupted' for t in report['trials'])
            result['planned_cases'][i]['status'] = 'interrupted' if interrupted else 'recorded'
            save()
            if interrupted: result['status'] = 'interrupted'; return result
        result['status'] = 'recorded'
        return result
    except KeyboardInterrupt:
        result['status'] = 'interrupted'; return result
    finally:
        save()
