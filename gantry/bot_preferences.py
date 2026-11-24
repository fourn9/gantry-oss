"""Explicit human feedback with scope and revocation; never authority."""
import copy
from .contracts import register, S
from .model import digest, require

register('set_bot_preference', {
    'session_id':S, 'bot_id':S, 'key':{**S,'maxLength':128}, 'version':{'type':'integer','minimum':0},
    'scope':{'enum':['task','phase','project']}, 'task_id':{'type':['string','null']},
    'phase':{**S,'maxLength':128}, 'memory_id':S,
    'text':{**S,'maxLength':2000}, 'reason':{**S,'maxLength':2000},
    'enabled':{'type':'boolean'}},
    ['session_id','bot_id','key','version','scope','task_id','text','reason','enabled'])


def effective_preferences(rows, task_id, phase):
    """Resolve each topic independently; specificity applies only within human guidance."""
    ranks = {'project': 0, 'phase': 1, 'task': 2}
    selected = {}
    for row in rows:
        scope = row['scope']
        if not row['enabled'] or (scope == 'task' and row['task_id'] != task_id):
            continue
        if scope == 'phase' and row['phase'] != phase:
            continue
        old = selected.get(row['key'])
        if old is None or ranks[scope] > ranks[old['scope']]:
            selected[row['key']] = row
    # Stable order preserves existing basis hashes for unchanged rules.
    return sorted(selected.values(), key=lambda row: row['id'])


def preference_rows(core, s, binding, con):
    rows = con.execute("SELECT id FROM records WHERE collection='bot_preferences' AND subject_id=? AND session_id=?",
                       (binding['bot_id'], binding['session_id']))
    for (ident,) in rows:
        pref = core._dev_get(s, 'bot_preferences', ident)
        if pref['principal_id'] == binding['principal_id']:
            yield pref


class BotPreferencesMixin:
    def cmd_set_bot_preference(self,s,actor,a,fx,n,con):
        require(actor['kind']=='human','human_approval_required','Only a human owner declares preferences')
        project,_=self._bd_project(s,actor,a['session_id'])
        require(self._bd_owner(actor,project),'unauthorized','Project owner required')
        binding=self._bd_binding(s,a['session_id'],a['bot_id'])
        require(binding['enabled'],'unauthorized','Bot binding disabled')
        require(bool(a['task_id'] and a['task_id'].strip()) if a['scope']=='task' else a['task_id'] is None,
                'invalid_input','Task scope needs a target task; other scopes use null')
        if a['task_id']:
            task=self._dev_get(s,'bot_tasks',a['task_id'])
            require(task['session_id']==a['session_id'] and task['bot_id']==a['bot_id'] and
                task['principal_id']==binding['principal_id'],'scope_denied','Feedback targets this bound Bot task')
        require((a['scope'] == 'phase') == ('phase' in a), 'invalid_input', 'Specify a phase only for phase guidance')
        require(all(a[k].strip() for k in ('text', 'reason', 'key')) and
                ('phase' not in a or a['phase'].strip()), 'invalid_input', 'Supply a topic, guidance and reason')
        legacy_key = [a['session_id'], a['bot_id'], a['key']]
        legacy_id = digest(legacy_key)
        legacy = s.get('bot_preferences', {}).get(legacy_id)
        if legacy and legacy['principal_id'] == binding['principal_id'] and legacy['scope'] == a['scope'] and legacy['task_id'] == a['task_id']:
            ident = legacy_id
        else:
            ident = digest([*legacy_key, binding['principal_id'], a['scope'], a['task_id'], a.get('phase')])
        old=s.get('bot_preferences',{}).get(ident)
        require(a['version']==(old or {}).get('version',0),'stale_basis','Preference changed')
        memory_id = a.get('memory_id') or (old or {}).get('memory_id')
        if memory_id:
            memory = self._dev_get(s, 'bot_memories', memory_id)
            require(memory['session_id']==a['session_id'] and memory.get('bot_id')==a['bot_id'] and
                    memory['principal_id']==binding['principal_id'], 'scope_denied', 'Select a lesson of this bound Bot')
            self._learning_source(s, actor, a, memory_id)
            require(memory.get('source')=='experience_reflection' and a['key']=='lesson-'+memory_id,
                    'invalid_input','Use the topic of the original lesson')
        row=dict(copy.deepcopy(a),id=ident,subject_id=a['bot_id'],author_id=actor['id'],
            principal_id=binding['principal_id'],version=a['version']+1,created_seq=s['seq']+1,
            evidence_status='explicit_human_preference_not_requirement')
        if memory_id: row['memory_id'] = memory_id
        return self._dev_save(s,fx,'bot_preferences',row)

    def _preference_context(self,s,actor,task,con):
        project=s['bot_projects'][task['session_id']]
        binding=self._bd_binding(s,task['session_id'],task['bot_id'])
        own=actor['id']==task['principal_id'] and self._binding_access(s,actor,binding)
        if not own and not self._bd_owner(actor,project):return None
        state_id = task.get('state_id') or s['dev_sessions'][binding['session_id']]['active_state']
        phase = s['dev_states'][state_id]['context']['environment'].get('development_phase')
        items = effective_preferences(preference_rows(self, s, binding, con), task['id'], phase)
        require(len(items) <= 40, 'context_limit', 'Consolidate explicit preferences before continuing')
        return {'items':items,'basis':digest(items),
            'interpretation':'Owner-attributed preferences, subordinate to requirements and authority. Task-scoped feedback must not become a lasting preference. Inferred preferences remain hypotheses until the owner declares them.'}
