"""Experience plans and durable outcome reflection, authored by customer Bots."""
import copy

from . import bot_learning_contracts  # Registers API contracts.
from .bot_learning_recall import recall, context_basis
from .model import digest, require, uid


class BotLearningMixin:
    def _learning_source(self, s, actor, task, memory_id):
        memory = self._dev_get(s, 'bot_memories', memory_id)
        self._dev_session(s, actor, memory['session_id'])
        binding = self._persistent_binding(s, memory['session_id'], memory['role'])
        bot, org = self._persistent_identity(s, task['bot_id'])
        require(binding and binding['enabled'] and binding['bot_id'] == memory.get('bot_id')
            and binding['principal_id'] == memory['principal_id']
            and s['persistent_bots'][binding['bot_id']]['enabled'],
            'unauthorized', 'Memory source binding revoked or reassigned')
        own = memory.get('bot_id') == bot['id'] and self._binding_access(s, actor, binding)
        shared = digest([org['id'], memory_id]) in s.get('organization_memories', {})
        require(own or shared, 'unauthorized', 'Memory is not shared with this Bot')
        return memory

    def cmd_prepare_bot_learning(self, s, actor, a, fx, n, con):
        task = self._bd_checked(s, actor, a, con)
        limit = min(a.get('limit', 20), 40)
        packet = dict(id=uid('bplan'), subject_id=task['bot_id'], task_id=task['id'],
            session_id=task['session_id'], bot_id=task['bot_id'], principal_id=actor['id'],
            attempt=task['attempt'], status='pending', stamp=copy.deepcopy(task['stamp']),
            state_id=task.get('output_state', task['state_id']),
            environment_hash=s['bot_runtimes'][task['bot_id']]['environment_hash'],
            requirement_refs=copy.deepcopy(task.get('requirement_refs', [])),
            working_state=copy.deepcopy(self._working_note(s, task['session_id'], task['bot_id'])),
            query={'after': a.get('after', ''), 'limit': limit},
            recall=recall(self, s, actor, task, con, a.get('after', ''), limit), created_seq=s['seq']+1)
        return self._dev_save(s, fx, 'bot_learning_plans', packet)

    def cmd_submit_bot_learning_plan(self, s, actor, a, fx, n, con):
        task = self._bd_checked(s, actor, a, con)
        packet = self._dev_get(s, 'bot_learning_plans', a['plan_id'])
        require(packet['task_id'] == task['id'] and packet['attempt'] == task['attempt'] and
            packet['principal_id'] == actor['id'], 'unauthorized', 'Plan belongs to another executor or attempt')
        require(packet['status'] == 'pending', 'stale_basis', 'Plan is already immutable')
        require(packet['stamp'] == task['stamp'] and packet['state_id'] == task.get('output_state', task['state_id']),
                'stale_basis', 'Planning inputs changed')
        require(packet.get('working_state') == self._working_note(s, task['session_id'], task['bot_id']),
                'stale_basis', 'Working commitments changed; prepare a new plan')
        current = recall(self, s, actor, task, con, **packet['query'])
        require(current == packet['recall'], 'stale_basis', 'Experience or source access changed; prepare a new plan')
        available = {m['id']: m for m in current['items']}
        seen = set()
        for decision in a['output']['decisions']:
            mid = decision['memory_id']
            require(mid in available and mid not in seen, 'invalid_input', 'Use a unique recalled memory ID')
            seen.add(mid); self._learning_source(s, actor, task, mid)
            require(decision['use'] != 'apply' or not available[mid]['applicability_flags'],
                    'stale_basis', 'Changed, incomplete or contradicted experience must be rechecked or rejected')
        require(seen == set(available), 'invalid_input', 'Record apply/recheck/reject for every recalled item')
        for bid in a['output']['consult_bot_ids']:
            binding = self._bd_binding(s, task['session_id'], bid)
            require(binding['enabled'] and bid != task['bot_id'], 'invalid_input', 'Consult an active peer')
        packet.update(status='completed', output=copy.deepcopy(a['output']), completed_seq=s['seq']+1)
        self._dev_save(s, fx, 'bot_learning_plans', packet)
        task['learning_plan_id'] = packet['id']; self._dev_save(s, fx, 'bot_tasks', task)
        return packet

    def cmd_get_bot_learning_plan(self, s, actor, a, fx, n, con):
        plan = self._dev_get(s, 'bot_learning_plans', a['plan_id'])
        task = self._dev_get(s, 'bot_tasks', plan['task_id'])
        project, _ = self._bd_project(s, actor, task['session_id'], active=False)
        if not self._bd_owner(actor, project):
            self._bd_actor(s, actor, task['session_id'], task['bot_id'])
            require(plan['principal_id'] == actor['id'], 'unauthorized', 'Plan belongs to the original executor')
        for memory in plan['recall']['items']: self._learning_source(s, actor, task, memory['id'])
        return plan

    def _learning_context(self, s, actor, task):
        if not task.get('learning_plan_id'): return None
        plan = self._dev_get(s, 'bot_learning_plans', task['learning_plan_id'])
        for memory in plan['recall']['items']: self._learning_source(s, actor, task, memory['id'])
        return copy.deepcopy(plan)

    def _learning_enqueue(self, s, actor, task, fx):
        if not task.get('learning_plan_id'): return
        plan = self._dev_get(s, 'bot_learning_plans', task['learning_plan_id'])
        if plan['attempt'] != task['attempt'] or plan['status'] != 'completed': return
        report = task['reports'][-1]
        reflection = dict(id='breflect_' + digest([task['id'], task['attempt'], report['seq']])[:32],
            subject_id=task['bot_id'], bot_id=task['bot_id'], principal_id=actor['id'],
            session_id=task['session_id'], task_id=task['id'], plan_id=plan['id'],
            status='pending', version=1, report=copy.deepcopy(report['report']),
            report_record=copy.deepcopy(report), context_basis=context_basis(s, task, report['state_id']), requirement_refs=copy.deepcopy(task.get('requirement_refs', [])),
            environment_hash=s['bot_runtimes'][task['bot_id']]['environment_hash'],
            created_seq=s['seq']+1, evidence_status='executor_report_not_independent_verification')
        self._dev_save(s, fx, 'bot_reflections', reflection)

    def _learning_reflection_access(self, s, actor, ident, writing=False):
        record = self._dev_get(s, 'bot_reflections', ident)
        project, _ = self._bd_project(s, actor, record['session_id'], active=False)
        if writing or not self._bd_owner(actor, project):
            self._bd_actor(s, actor, record['session_id'], record['bot_id'])
            require(record['principal_id'] == actor['id'], 'unauthorized', 'Reflection belongs to the original executor')
        task = self._dev_get(s, 'bot_tasks', record['task_id'])
        plan = self._dev_get(s, 'bot_learning_plans', record['plan_id'])
        for memory in plan['recall']['items']: self._learning_source(s, actor, task, memory['id'])
        return record, task, plan

    def cmd_list_bot_reflections(self, s, actor, a, fx, n, con):
        bot, _ = self._persistent_access(s, actor, a['bot_id'], con)
        limit = a.get('limit', 20)
        rows = con.execute('SELECT id FROM records WHERE collection=? AND subject_id=? AND id>? ORDER BY id LIMIT ?',
            ('bot_reflections', bot['id'], a.get('after', ''), limit+1)).fetchall()
        items = []
        from .model import Fault
        for row in rows[:limit]:
            try: record, _, _ = self._learning_reflection_access(s, actor, row[0])
            except Fault: continue
            if record['status'] == 'pending': items.append(copy.deepcopy(record))
        return {'items': items, 'next_cursor': rows[limit-1][0] if len(rows)>limit else None}

    def cmd_get_bot_reflection(self, s, actor, a, fx, n, con):
        record, task, plan = self._learning_reflection_access(s, actor, a['reflection_id'])
        return {**copy.deepcopy(record), 'plan': copy.deepcopy(plan),
            'task': {'id': task['id'], 'title': task['title'], 'completion': task['completion']},
            'evidence_rules': {'planning_intent_id': plan['id'], 'executor_report_task_id': task['id'],
                'saved_state_id': record['report_record']['state_id'],
                'observations': 'Same-attempt action, decision and experience-use IDs before this report; output_artifact IDs linked by those tool receipts',
                'limits': 'Plans are intent; states are saved bytes; reports and use links are executor claims. None establishes physical correctness.'},
            'observations': self._learning_observations(s, record, con),
            'experience_actions': self._learning_observations(s, record, con, 'bot_learning_uses'),
            'observations_coverage': 'At most 20 action and 20 experience-use receipts from this attempt before its report; get_bot_records pages full history'}

    def _learning_observations(self, s, record, con, table='bot_actions'):
        rows = con.execute('SELECT id FROM records WHERE collection=? AND subject_id=? AND created_seq<=? '
            'ORDER BY created_seq DESC,id DESC LIMIT 20', (table, record['task_id'], record['created_seq']))
        values = [self._dev_get(s, table, r[0]) for r in rows]
        return [v for v in values if v['attempt'] == record['report_record']['attempt']]

    def cmd_complete_bot_reflection(self, s, actor, a, fx, n, con):
        record, task, plan = self._learning_reflection_access(s, actor, a['reflection_id'], writing=True)
        require(record['status'] == 'pending' and record['version'] == a['version'], 'stale_basis', 'Reflection already completed')
        allowed = {m['id'] for m in plan['recall']['items']}
        seen = set(); memory_ids = []
        b = self._bd_binding(s, task['session_id'], task['bot_id'])
        org = s['organizations'][s['persistent_bots'][task['bot_id']]['organization_id']]
        team = {'session_id': task['session_id'], 'version': s['bot_projects'][task['session_id']]['version']}
        lesson_keys = [digest(v) for v in a['output']['lessons']]
        require(len(lesson_keys) == len(set(lesson_keys)), 'invalid_input', 'Do not duplicate a lesson in one reflection')
        for lesson in a['output']['lessons']:
            self._learning_evidence(s, task, record, lesson['evidence'], con)
            for relation in ('supersedes', 'contradicts'):
                for mid in lesson[relation]:
                    require(mid in allowed, 'invalid_input', 'Link only a recalled source')
                    old = self._learning_source(s, actor, task, mid)
                    if relation == 'supersedes':
                        require(old.get('bot_id') == task['bot_id'], 'unauthorized', 'Cannot supersede another Bot memory')
            memory = self._save_bot_memory(s, fx, team, actor, dict(session_id=task['session_id'], role=b['role'],
                state_id=record['report_record']['state_id'], visibility='role', observation=lesson['observation'],
                applicability=lesson['when_to_use'], limitations=lesson['when_not_to_use'] + a['output']['unknowns'],
                evidence=lesson['evidence'], paths=lesson['paths'], assessment='inconclusive', source='experience_reflection',
                lesson=copy.deepcopy(lesson), reflection_id=record['id'], requirement_refs=record['requirement_refs'],
                environment_hash=record['environment_hash'], context_basis=record['context_basis'],
                self_assessment=copy.deepcopy(a['output'].get('self_assessment')),
                evidence_status='bot_inferred_hypothesis'))
            memory_ids.append(memory['id'])
            if org.get('share_reflections'): self._bd_share_memory(s, actor, org, memory, fx)
        used = {d['memory_id'] for d in plan['output']['decisions'] if d['use'] != 'reject'}
        for feedback in a['output']['feedback']:
            mid = feedback['memory_id']
            require(mid in used and mid not in seen, 'invalid_input', 'Feedback requires unique non-rejected plan memory')
            self._learning_evidence(s, task, record, feedback['evidence'], con); seen.add(mid)
            self._dev_save(s, fx, 'bot_experience_feedback', dict(copy.deepcopy(feedback),
                id=digest([record['id'], mid]), subject_id=mid, reflection_id=record['id'],
                session_id=record['session_id'], bot_id=record['bot_id'], principal_id=actor['id'],
                created_seq=s['seq']+1, evidence_status='reported_utility_not_causal_proof'))
        record.update(status='completed', version=record['version']+1, output=copy.deepcopy(a['output']),
            memory_ids=memory_ids, completed_seq=s['seq']+1)
        return self._dev_save(s, fx, 'bot_reflections', record)

    def _learning_evidence(self, s, task, record, refs, con):
        # Citations must be this attempt's saved objects, not unrelated successful work.
        for ref in refs:
            if ref in {task['id'], record['report_record']['state_id'], record['plan_id']}:
                continue
            if ref.startswith('rev_'):
                # Only a tool receipt from this attempt can establish this link.
                linked = con.execute("SELECT id FROM records WHERE collection='bot_actions' AND subject_id=? AND created_seq<=? "
                    "AND COALESCE(json_extract(body,'$.value.attempt'),json_extract(body,'$.attempt'))=? "
                    "AND COALESCE(json_extract(body,'$.value.kind'),json_extract(body,'$.kind'))='tool' "
                    "AND COALESCE(json_extract(body,'$.value.details.result.output_artifact'),"
                    "json_extract(body,'$.details.result.output_artifact'))=? LIMIT 1",
                    (task['id'], record['created_seq'], record['report_record']['attempt'], ref)).fetchone()
                require(linked, 'invalid_input', 'Tool output must belong to this attempt')
                self._dev_artifact(s, ref)
                continue
            action = s.get('bot_actions', {}).get(ref) or s.get('bot_decisions', {}).get(ref) or s.get('bot_learning_uses', {}).get(ref)
            require(action and action['task_id'] == task['id'] and action.get('attempt') == record['report_record']['attempt']
                and action['created_seq'] <= record['created_seq'], 'invalid_input', 'Cite actual observations from this attempt')
