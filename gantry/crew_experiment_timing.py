"""Summarize normalized experiment spans without equating concurrent time to elapsed.

Input labels describe observed operation intent, not hidden model thought. Model
intervals include CLI, network and provider wait. Use leaf spans when summed work
is wanted; union measurements also tolerate nested/parallel records. Rework must
be tagged from explicit evidence, never inferred here from a failure or repetition.
"""
import math
from collections import Counter

CATEGORIES = ('judgment', 'consultation', 'work', 'recording', 'waiting', 'unknown')
PHASES = {'model', 'action', 'tool', 'edit', 'record', 'context', 'checkpoint',
          'recovery', 'restore', 'wait', 'setup', 'repair', 'monitor', 'unknown'}


def _union(rows):
    total = 0; last = None
    for start, end in sorted((r['start'], r['end']) for r in rows):
        if last is None or start > last:
            total += end-start; last = end
        elif end > last:
            total += end-last; last = end
    return total/1e9


def _stats(rows):
    return {'count': len(rows), 'summed_span_seconds': sum(r['end']-r['start'] for r in rows)/1e9,
            'union_seconds': _union(rows),
            'active_union_seconds': _union([r for r in rows if r['category'] != 'waiting'])}


def _partition(rows, start, end):
    # Exclusive categories count concurrent equal-intent spans once. Different
    # active intents get an explicit overlap bucket, with no arbitrary priority.
    events = [(start, None, 0), (end, None, 0)]
    for row in rows:
        events.extend([(row['start'], row['category'], 1), (row['end'], row['category'], -1)])
    result = {key: 0 for key in (*CATEGORIES, 'overlap', 'uncovered')}
    active = Counter(); previous = start
    for at, category, delta in sorted(events, key=lambda x: x[0]):
        labels = [key for key, count in active.items() if count and key != 'waiting']
        label = labels[0] if len(labels) == 1 else 'overlap' if labels else 'waiting' if active['waiting'] else 'uncovered'
        result[label] += (at-previous)/1e9
        if category: active[category] += delta
        previous = at
    return result


def summarize(spans, started_at_ns, finished_at_ns):
    """Return payload-free aggregates within a specified wall-clock window.

    Span fields: id, actor_type (bot/parent), bot_id (required for bot), category,
    phase, started_at_ns, finished_at_ns (None if incomplete), rework (bool/None),
    optional monotonic_seconds. task_id/action_key may exist for callers' joins;
    arbitrary metadata is ignored and not copied into the summary. IDs must be
    unique: exact repeats are deduplicated; conflicting identities are excluded.
    """
    if type(started_at_ns) is not int or type(finished_at_ns) is not int or finished_at_ns < started_at_ns:
        raise ValueError('Use an ordered integer nanosecond measurement window')
    counters = {k: 0 for k in ('invalid', 'incomplete', 'duplicates', 'conflicting_ids', 'outside_window', 'clipped')}
    grouped = {}; conflicts = set(); clock_deltas = []
    for source in spans:
        try:
            key = source['id']; actor = source['actor_type']; bot = source.get('bot_id')
            category = source['category']; phase = source['phase']
            start = source['started_at_ns']; end = source['finished_at_ns']; rework = source.get('rework')
            mono = source.get('monotonic_seconds')
            if not isinstance(key, str) or not key or actor not in ('bot', 'parent') or category not in CATEGORIES:
                raise ValueError()
            if actor == 'bot' and (not isinstance(bot, str) or not bot): raise ValueError()
            if actor == 'parent' and bot is not None and not isinstance(bot, str): raise ValueError()
            if not isinstance(phase, str) or not phase or type(start) is not int: raise ValueError()
            if end is not None and (type(end) is not int or end < start): raise ValueError()
            if rework is not None and type(rework) is not bool: raise ValueError()
            if mono is not None and (type(mono) not in (int, float) or not math.isfinite(mono) or mono < 0): raise ValueError()
            row = {'actor_type': actor, 'bot_id': bot, 'category': category,
                   'phase': phase if phase in PHASES else 'unknown', 'start': start, 'end': end,
                   'rework': rework, 'monotonic_seconds': mono}
            if key in grouped:
                if grouped[key] == row: counters['duplicates'] += 1
                else: conflicts.add(key)
            else: grouped[key] = row
        except (KeyError, ValueError, TypeError): counters['invalid'] += 1
    counters['conflicting_ids'] = len(conflicts)
    rows = []
    for key, row in grouped.items():
        if key in conflicts: continue
        if row['end'] is None:
            counters['incomplete'] += 1; continue
        start, end = row['start'], row['end']
        if end <= started_at_ns or start >= finished_at_ns:
            counters['outside_window'] += 1; continue
        if start < started_at_ns or end > finished_at_ns: counters['clipped'] += 1
        elif row['monotonic_seconds'] is not None:
            clock_deltas.append(abs((end-start)/1e9-row['monotonic_seconds']))
        rows.append({**row, 'start': max(start, started_at_ns), 'end': min(end, finished_at_ns)})
    elapsed = (finished_at_ns-started_at_ns)/1e9
    total = _stats(rows)
    return {'schema': 1, 'elapsed_seconds': elapsed, **counters,
        'records_complete': not (counters['invalid'] or counters['incomplete'] or conflicts),
        'summed_span_seconds': total['summed_span_seconds'],
        'active_union_seconds': total['active_union_seconds'],
        'accounted_union_seconds': total['union_seconds'],
        'uncovered_seconds': max(0, elapsed-total['union_seconds']),
        'exclusive_wall_seconds': _partition(rows, started_at_ns, finished_at_ns),
        'per_category': {k: _stats([r for r in rows if r['category'] == k]) for k in CATEGORIES},
        'per_phase': {k: _stats([r for r in rows if r['phase'] == k]) for k in sorted({r['phase'] for r in rows})},
        'per_bot': {k: _stats([r for r in rows if r['actor_type'] == 'bot' and r['bot_id'] == k])
                    for k in sorted({r['bot_id'] for r in rows if r['actor_type'] == 'bot'})},
        'bot': _stats([r for r in rows if r['actor_type'] == 'bot']),
        'parent': _stats([r for r in rows if r['actor_type'] == 'parent']),
        'rework': {label: _stats([r for r in rows if r['rework'] is value])
                   for label, value in [('true', True), ('false', False), ('unknown', None)]},
        'clock_comparison': {'complete_unclipped_samples': len(clock_deltas),
            'max_absolute_wall_monotonic_delta_seconds': max(clock_deltas) if clock_deltas else None},
        'host_sleep_seconds': None,
        'meaning': 'Intent categories and execution phases are separate. Model time includes provider/network waiting, not pure thinking. '
            'Summed spans and category unions may overlap; only the exclusive partition sums to elapsed. Waiting is excluded from active union. '
            'Uncovered time is uninstrumented, not proven idle or sleep. Rework is a non-additive evidence-tagged subset; unknown is not zero. '
            'Parent spans measure recorded intervention windows, not unobserved human effort. Clock deltas do not prove host suspension.'}
