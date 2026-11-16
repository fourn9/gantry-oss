"""Explicit human feedback with scope and revocation; never authority."""
import copy
from .contracts import register, S, I
from .model import digest, require

register('set_bot_preference', {
    'session_id':S, 'bot_id':S, 'key':{**S,'maxLength':128}, 'version':{'type':'integer','minimum':0},
    'scope':{'enum':['task','project']}, 'task_id':{'type':['string','null']},
    'text':{**S,'maxLength':2000}, 'reason':{**S,'maxLength':2000},
    'enabled':{'type':'boolean'}},
    ['session_id','bot_id','key','version','scope','task_id','text','reason','enabled'])


class BotPreferencesMixin:
    def cmd_set_bot_preference(self,s,actor,a,fx,n,con):
        require(actor['kind']=='human','human_approval_required','Only a human owner declares preferences')
        project,_=self._bd_project(s,actor,a['session_id'])
        require(self._bd_owner(actor,project),'unauthorized','Project owner required')
        binding=self._bd_binding(s,a['session_id'],a['bot_id'])
        require(binding['enabled'],'unauthorized','Bot binding disabled')
        require((a['scope']=='task') == bool(a['task_id']),'invalid_input','Task scope needs a target task; project scope uses null')
        if a['task_id']:
            task=self._dev_get(s,'bot_tasks',a['task_id'])
            require(task['session_id']==a['session_id'] and task['bot_id']==a['bot_id'] and
                task['principal_id']==binding['principal_id'],'scope_denied','Feedback targets this bound Bot task')
        ident=digest([a['session_id'],a['bot_id'],a['key']])
        old=s.get('bot_preferences',{}).get(ident)
        require(a['version']==(old or {}).get('version',0),'stale_basis','Preference changed')
        row=dict(copy.deepcopy(a),id=ident,subject_id=a['bot_id'],author_id=actor['id'],
            principal_id=binding['principal_id'],version=a['version']+1,created_seq=s['seq']+1,
            evidence_status='explicit_human_preference_not_requirement')
        return self._dev_save(s,fx,'bot_preferences',row)

    def _preference_context(self,s,actor,task,con):
        project=s['bot_projects'][task['session_id']]
        binding=self._bd_binding(s,task['session_id'],task['bot_id'])
        own=actor['id']==task['principal_id'] and self._binding_access(s,actor,binding)
        if not own and not self._bd_owner(actor,project):return None
        rows=con.execute("SELECT id FROM records WHERE collection='bot_preferences' AND subject_id=? AND session_id=? ORDER BY id",
            (task['bot_id'],task['session_id']))
        items=[]
        for row in rows:
            p=self._dev_get(s,'bot_preferences',row[0])
            if not p['enabled'] or p['principal_id']!=binding['principal_id']:continue
            if p['scope']=='task' and p['task_id']!=task['id']:continue
            items.append(copy.deepcopy(p))
            require(len(items)<=40,'context_limit','Consolidate explicit preferences before continuing')
        return {'items':items,'basis':digest(items),
            'interpretation':'Owner-attributed preferences, subordinate to requirements and authority. Task-scoped feedback must not become a lasting preference. Inferred preferences remain hypotheses until the owner declares them.'}
