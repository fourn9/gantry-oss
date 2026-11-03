"""Descriptive paired results. Failed and unstarted trials stay in the denominator."""
import json
from pathlib import Path

from .runner import persist

ARMS = ('without_experience', 'with_experience')


def summarize(settings, rows):
    arms = {}
    for arm in ARMS:
        items = [r for r in rows if r['arm'] == arm]
        accepted = [r for r in items if r['status'] == 'accepted']
        arms[arm] = {'planned': settings['repetitions'], 'accepted': len(accepted),
            'success_rate': len(accepted) / settings['repetitions'],
            'statuses': {s: sum(r['status'] == s for r in items) for s in sorted({r['status'] for r in items})},
            'accepted_seconds': [r['total_seconds'] for r in accepted]}
    ratios = []
    for pair in range(settings['repetitions']):
        matched = {r['arm']: r for r in rows if r['pair'] == pair}
        if all(a in matched and matched[a]['status'] == 'accepted' for a in ARMS):
            denominator = matched[ARMS[1]]['total_seconds']
            if denominator > 0: ratios.append(matched[ARMS[0]]['total_seconds'] / denominator)
    return {'arms': arms, 'matched_successful_pairs': len(ratios), 'time_ratios_without_over_with': ratios,
        'incomplete_trials': sum(r['status'] in {'running', 'pending', 'interrupted', 'incomplete'} for r in rows),
        'interpretation': 'Descriptive paired observations only; no causal, statistical or physical-validity claim.'}


def write_report(root, report):
    root = Path(root)
    report['summary'] = summarize(report['settings'], report['trials'])
    persist(root/'report.json', report)
    lines = ['# Bot experience comparison', '', report['summary']['interpretation'], '',
        '| Pair | Arm | Status | Total seconds | Setup seconds | Calls |',
        '| --- | --- | --- | --- | --- | --- |']
    for row in report['trials']:
        lines.append(f"| {row['pair']+1} | {row['arm']} | {row['status']} | {row.get('total_seconds', 'unknown')} | "
                     f"{row.get('setup_seconds', 'unknown')} | {len(row.get('calls', []))} |")
    lines += ['', 'Only accepted/accepted pairs produce time ratios (without / with):',
              str(report['summary']['time_ratios_without_over_with']), '',
              'Timing includes planning, edits, tools, recording, independent verification and reflection. '
              'Setup is separate. Failed or interrupted trials are not successful completion times.', '',
              'Unknown token usage and human intervention time are not zero. Model receipts, ledger and files '
              'are private; do not publish this directory. Imported experience is declared, not verified history.']
    (root/'report.md').write_text('\n'.join(lines)+'\n'); (root/'report.md').chmod(0o600)
    return report


def regenerate(root):
    root = Path(root)
    return write_report(root, json.loads((root/'report.json').read_text()))
