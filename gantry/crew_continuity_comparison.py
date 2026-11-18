"""Common, payload-free comparison of independent development trials.

Use this same scorer for both implementations. Completion is engineering and
workflow acceptance, not a short stop or merely a successful reflection.
"""
import json
import math
import statistics
from collections import Counter
from pathlib import Path

ACTIVITIES = ('judgment', 'consultation', 'editing', 'verification', 'memory_update',
              'recording', 'waiting', 'preparation', 'repair', 'recovery', 'unknown')


def _action_activity(action, args):
    if action in ('ask', 'resolve', 'respond', 'message', 'inspect', 'inspect_json', 'team'):
        return 'consultation'
    if action == 'records' and args.get('task_id'): return 'consultation'
    if action in ('edit', 'replace', 'patch', 'integrate'): return 'editing'
    if action in ('tool', 'tool_evidence', 'plan_verification', 'publish_physical'): return 'verification'
    if action == 'finish':
        return 'consultation' if args.get('assignments') or args.get('report', {}).get('assignments') else 'recording'
    if action in ('checkpoint', 'publish', 'share'): return 'recording'
    if action == 'observe':
        kinds = {_action_activity(r.get('action'), r.get('arguments', {})) for r in args.get('requests', [])}
        return next(iter(kinds)) if len(kinds) == 1 else 'unknown'
    return 'judgment'


def activity(call):
    operation = call.get('operation'); output = call.get('output') or {}
    if operation == 'reflect_on_experience': return 'memory_update'
    if operation == 'plan_from_experience': return 'judgment'
    try: args = json.loads(output.get('arguments_json', '{}'))
    except (ValueError, TypeError): args = {}
    return _action_activity(output.get('action'), args if isinstance(args, dict) else {})


def _union(rows):
    total = 0; last = None
    for row in sorted(rows, key=lambda r:r['start']):
        start, end = row['start'], row['end']
        if last is None or start > last: total += end-start; last = end
        elif end > last: total += end-last; last = end
    return total/1e9


def _stats(rows):
    return {'count':len(rows), 'union_seconds':_union(rows),
            'summed_seconds':sum(r['end']-r['start'] for r in rows)/1e9}


def timing(calls, spans, start, end):
    rows = []; invalid = 0; dropped = 0
    def add(raw, label, phase):
        nonlocal invalid
        a,b=raw.get('started_at_ns'),raw.get('finished_at_ns');actor=raw.get('actor_type','bot')
        if type(a) is not int or type(b) is not int or b<a or actor not in ('bot','parent'):
            invalid += 1; return
        a=max(a,start);b=min(b,end)
        if b<=a:return
        rows.append({'start':a,'end':b,'actor':actor,'bot':raw.get('bot_id'),
            'activity':label,'phase':phase,'rework':raw.get('rework')})
    for call in calls:add(call,activity(call),'model')
    # Model calls are the source of truth; do not add their normalized copies.
    phases={'tool':'verification','edit':'editing','record':'recording','checkpoint':'recording',
            'wait':'waiting','setup':'preparation','repair':'repair','recovery':'recovery',
            'restore':'preparation','context':'judgment','monitor':'waiting'}
    candidates=[s for s in spans if s.get('phase')!='model']
    for s in candidates:
        phase=s.get('phase','unknown')
        if phase=='action' and any(x is not s and x.get('actor_type')==s.get('actor_type')
                and x.get('bot_id')==s.get('bot_id') and x.get('phase')!='action'
                and type(x.get('started_at_ns')) is int and type(x.get('finished_at_ns')) is int
                and s['started_at_ns']<=x['started_at_ns']<=x['finished_at_ns']<=s['finished_at_ns']
                for x in [*candidates,*[{**c,'actor_type':'bot','phase':'model'} for c in calls]]):
            dropped+=1;continue
        label=s.get('activity')
        if label not in ACTIVITIES and phase == 'action' and isinstance(s.get('action'), str):
            label = _action_activity(s['action'], {})
        if label not in ACTIVITIES:
            label=phases.get(phase,{'judgment':'judgment','consultation':'consultation',
                'recording':'recording','waiting':'waiting'}.get(s.get('category'),'unknown'))
        add(s,label,phase)
    events=[(start,None,0),(end,None,0)]
    for r in rows:events.extend(((r['start'],r['activity'],1),(r['end'],r['activity'],-1)))
    partition={k:0.0 for k in (*ACTIVITIES,'overlap','uncovered')};active=Counter();previous=start
    for at,label,delta in sorted(events,key=lambda x:x[0]):
        kinds=[k for k,v in active.items() if v and k!='waiting']
        key=kinds[0] if len(kinds)==1 else 'overlap' if kinds else 'waiting' if active['waiting'] else 'uncovered'
        partition[key]+=(at-previous)/1e9
        if label:active[label]+=delta
        previous=at
    return {'exclusive_wall_seconds':partition,'by_activity':{k:_stats([r for r in rows if r['activity']==k]) for k in ACTIVITIES},
        'by_actor':{k:_stats([r for r in rows if r['actor']==k]) for k in ('bot','parent')},
        'by_bot':{k:_stats([r for r in rows if r['actor']=='bot' and r['bot']==k]) for k in sorted({r['bot'] for r in rows if isinstance(r['bot'],str)})},
        'rework':{k:_stats([r for r in rows if r['rework'] is v]) for k,v in [('true',True),('false',False),('unknown',None)]},
        'invalid_or_incomplete_spans':invalid,'dropped_container_spans':dropped,'host_sleep_seconds':None,
        'meaning':'Model intervals include network/provider waiting, not pure thought. Exclusive partition includes overlap; per-activity unions must not be added. Uncovered is uninstrumented, not sleep. Rework unknown is not zero.'}


def score(result, window, calls=(), spans=(), observation_limit=1800):
    start,end=window['started_at_ns'],window['finished_at_ns'];mono=window['monotonic_seconds']
    if type(start) is not int or type(end) is not int or end<start or type(mono) not in (int,float) or not math.isfinite(mono) or mono<0:
        raise ValueError('Invalid execution window')
    errors=result.get('errors',[])
    reflections=[e for e in errors if isinstance(e.get('result'),dict) and e['result'].get('reflection_id') and not e['result'].get('job_id')]
    fatal=[e for e in errors if e not in reflections]
    within=result.get('within_observation_window') is True
    # Keep the same after-setup limit in both arms; full primary includes setup/audit.
    if type(result.get('started_at_ns')) is int and type(result.get('finished_at_ns')) is int:
        within=within and (end-result['started_at_ns'])/1e9<=observation_limit
    success=bool(result.get('root_status')=='completed' and (result.get('validation') or {}).get('accepted')
        and result.get('workflow_accepted') and result.get('verify',{}).get('valid')
        and result.get('replay',{}).get('matched') and within and not fatal)
    elapsed=(end-start)/1e9
    return {'schema':1,'success':success,'observed_seconds':elapsed,'completion_seconds':elapsed if success else None,
        'censored':not success,'root_status':result.get('root_status'),'within_observation_window':within,
        'fatal_error_count':len(fatal),'reflection_error_count':len(reflections),
        'pending_reflections':result.get('pending_reflections'),
        'memory_pipeline_complete':result.get('pending_reflections')==0 and not reflections and not result.get('reflection_warnings'),
        'model':result.get('model'),'reasoning_effort':result.get('reasoning_effort'),
        'case_hash':result.get('case_hash'),'condition':result.get('condition'),
        'monotonic_seconds':mono,'wall_monotonic_delta_seconds':elapsed-mono,
        'timing':timing(calls,spans,start,end)}


def score_run(directory, observation_limit=1800):
    root=Path(directory)
    def read(name):return json.loads((root/name).read_text())
    return score(read('result.json'),read('execution-window.json'),read('calls.json'),read('normalized-spans.json'),observation_limit)


def compare(arms):
    if set(arms)!={'before','after'} or any(len(v)<2 for v in arms.values()):
        raise ValueError('At least two independent trials per arm are required')
    rows=[r for values in arms.values() for r in values]
    for field in ('model','reasoning_effort','case_hash','condition'):
        if any(r.get(field) is None for r in rows) or len({r[field] for r in rows})!=1:
            raise ValueError('Incomparable '+field)
    summaries={}
    for name,values in arms.items():
        completed=[r['completion_seconds'] for r in values if r['success']]
        summaries[name]={'trials':len(values),'successes':len(completed),'failures_or_timeouts':len(values)-len(completed),
            'success_rate':len(completed)/len(values),'observed_seconds':[r['observed_seconds'] for r in values],
            'completed_seconds':completed,'median_completed_seconds':statistics.median(completed) if completed else None,
            'censored':[{'observed_seconds':r['observed_seconds'],'root_status':r['root_status'],
                'within_observation_window':r['within_observation_window']} for r in values if not r['success']]}
    all_complete=all(r['success'] for r in rows);den=summaries['after']['median_completed_seconds']
    ratio=summaries['before']['median_completed_seconds']/den if all_complete and den else None
    return {'arms':summaries,'speed_ratio_before_over_after':ratio,
        'interpretation':'Small repeated-trial preliminary evaluation, not a general causal speedup. Failed/timeout observations are censored, never counted as quick completion. No ratio unless every trial completes. Independence, tools, resource parity and immutable acceptance must also be audited externally.'}
