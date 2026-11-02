"""Bot working hypotheses with canonical project references, never new authority."""
import copy
from . import bot_continuity_contracts
from .model import digest, require, uid


class BotContinuityMixin:
    def _working_note(self, s, sid, bid):
        return s.get('bot_working_states', {}).get(digest([sid, bid]))

    def _working_context(self, s, actor, task):
        project, session = self._bd_project(s, actor, task['session_id'], active=False)
        if not self._bd_owner(actor, project):
            if actor['id'] != task['principal_id']: return None
            self._bd_actor(s, actor, task['session_id'], task['bot_id'])
        note = self._working_note(s, task['session_id'], task['bot_id'])
        require(not note or self._bd_owner(actor, project) or note['principal_id'] == actor['id'],
                'unauthorized', 'Working context belongs to a previous principal')
        return {'note': copy.deepcopy(note), 'project': copy.deepcopy(project),
                'active_state_id': session.get('active_state'),
                'interpretation': 'Bot-authored working hypotheses; canonical project/state requirements prevail'}

    def cmd_get_bot_working_state(self, s, actor, a, fx, n, con):
        b = self._bd_binding(s, a['session_id'], a['bot_id'])
        result = self._working_context(s, actor, {**a, 'principal_id':b['principal_id']})
        require(result is not None, 'unauthorized', 'Working notes are private to their Bot and owner')
        return result

    def cmd_update_bot_working_state(self, s, actor, a, fx, n, con):
        task = self._bd_checked(s, actor, a, con)
        old = self._working_note(s, task['session_id'], task['bot_id'])
        require(a['version'] == (old or {}).get('version', 0), 'stale_basis', 'Working note changed')
        require(not old or old['principal_id'] == actor['id'], 'unauthorized', 'Working note belongs to a previous principal')
        state_id = task.get('output_state', task['state_id'])
        manifest = self._manifest(s, s['dev_states'][state_id]['snapshot'])
        require(set(a['watch_paths']) <= set(manifest), 'invalid_input', 'Watch saved paths only')
        observed_state_id = s['dev_sessions'][task['session_id']]['active_state']
        shared_manifest = self._manifest(s, s['dev_states'][observed_state_id]['snapshot'])
        tasks = {}
        for tid in a['watch_tasks']:
            watched = self._dev_get(s, 'bot_tasks', tid)
            require(watched['session_id'] == task['session_id'] and tid != task['id'],
                    'scope_denied', 'Watch another task in this project')
            from .bot_wake import task_signal
            tasks[tid] = task_signal(watched)
        note = dict(old or {}, id=digest([task['session_id'], task['bot_id']]),
            subject_id=task['bot_id'], bot_id=task['bot_id'], session_id=task['session_id'],
            principal_id=actor['id'], version=a['version']+1, source_task_id=task['id'], state_id=state_id,
            content={k:copy.deepcopy(a[k]) for k in bot_continuity_contracts.CONTENT},
            watch_basis={'state_id':observed_state_id,
                         'paths':{p:shared_manifest.get(p, {}).get('hash') for p in a['watch_paths']}, 'tasks':tasks},
            created_seq=s['seq']+1, evidence_status='bot_working_hypothesis')
        return self._dev_save(s, fx, 'bot_working_states', note)

    def _working_report(self, s, actor, task, fx):
        # Completion of one task does not close ongoing commitments.
        note = self._working_note(s, task['session_id'], task['bot_id'])
        if note and note['principal_id'] != actor['id']: return
        note = copy.deepcopy(note) if note else dict(id=digest([task['session_id'],task['bot_id']]),
            subject_id=task['bot_id'], bot_id=task['bot_id'], session_id=task['session_id'],
            principal_id=actor['id'], version=0, source_task_id=task['id'], state_id=task.get('output_state',task['state_id']),
            content={'focus':task['title'], 'next_steps':[], 'commitments':[],
                     'unknowns':[], 'watch_paths':[], 'watch_tasks':[], 'due_at':None},
            watch_basis={'paths':{},'tasks':{}}, evidence_status='bot_working_hypothesis')
        note.update(version=note['version']+1, last_report_task=task['id'],
                    last_report_seq=task['reports'][-1]['seq'], last_report_state_id=task.get('output_state',task['state_id']),
                    created_seq=s['seq']+1)
        self._dev_save(s, fx, 'bot_working_states', note)

    def cmd_record_bot_learning_use(self, s, actor, a, fx, n, con):
        task = self._bd_checked(s, actor, a, con)
        plan = self._learning_context(s, actor, task)
        require(plan and plan['attempt'] == task['attempt'] and plan['status'] == 'completed',
                'invalid_input', 'Complete this attempt learning plan first')
        require(any(d['memory_id']==a['memory_id'] and d['use']!='reject' for d in plan['output']['decisions']),
                'invalid_input', 'Link a non-rejected planned memory')
        self._learning_source(s, actor, task, a['memory_id'])
        require(len(a['action_ids']) == len(set(a['action_ids'])), 'invalid_input', 'Duplicate action')
        for ident in a['action_ids']:
            action = s.get('bot_actions',{}).get(ident)
            require(action and action['task_id']==task['id'] and action['attempt']==task['attempt'],
                    'invalid_input', 'Link actual actions from this attempt')
        record = dict({k:copy.deepcopy(v) for k,v in a.items() if k!='fence'},
            id=uid('buse'), subject_id=task['id'], session_id=task['session_id'], bot_id=task['bot_id'],
            attempt=task['attempt'], plan_id=plan['id'], created_seq=s['seq']+1,
            evidence_status='reported_link_to_recorded_actions')
        return self._dev_save(s, fx, 'bot_learning_uses', record)
