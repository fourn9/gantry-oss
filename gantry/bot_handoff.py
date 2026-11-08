"""Acknowledged assignment transfer; navigation never changes execution ownership."""
import copy
from .contracts import register, S, I, A
from .model import require, uid
from .development import in_scope
from .bot_development import TERMINAL, PAGE
from .requirement_traceability import stale_refs

register('request_bot_handoff', {'task_id':S,'version':I,'to_bot_id':S,'reason':S,'requested_by_bot':S},
    ['task_id','version','to_bot_id','reason'])
register('acknowledge_bot_handoff', {'handoff_id':S,'version':I,'confirm_stopped':S,'summary':S,'unfinished':A},
    ['handoff_id','version','confirm_stopped','summary','unfinished'])
register('accept_bot_handoff', {'handoff_id':S,'version':I,'runtime_fence':S}, ['handoff_id','version','runtime_fence'])
register('list_bot_handoffs', {'bot_id':S,**PAGE}, ['bot_id'])


class BotHandoffMixin:
    def _handoff_authority(self,s,actor,task,requested_by=None):
        p,d=self._bd_project(s,actor,task['session_id'])
        if self._bd_owner(actor,p): return
        if task.get('studio_request_id'):
            request=s['studio_bot_requests'][task['studio_request_id']]
            change=self._dev_get(s,'dev_changes',request['work_id']) if request['work_id'] else {
                'session_id':d['id'],'assignee':d['owner'],'author':d['owner']}
            if actor['kind']=='human' and actor['id']==request['requester']:
                self._studio_task_authority(s,actor,change,request['mode']); return
        binding,_,_,_=self._bd_actor(s,actor,d['id'],requested_by)
        require(binding['can_assign'] and self._bd_subordinate(s,binding['bot_id'],task['bot_id']),
                'unauthorized','Assignment manager authority required')

    def _handoff_target(self,s,task,bid):
        binding=self._bd_binding(s,task['session_id'],bid); bot,org=self._persistent_identity(s,bid)
        if task.get('studio_request_id'):
            require(s['principals'][binding['principal_id']]['kind']=='agent','unauthorized','Studio handoff requires a dedicated agent identity')
        require(binding['enabled'] and bot['enabled'] and org['enabled'],'mode_disabled','Target Bot disabled')
        require(all(in_scope(path,binding['write_scope']) for path in task['write_scope']),
                'scope_denied','Target lacks the assigned write scope')
        if task.get('parent_task_id'):
            parent=s['bot_tasks'][task['parent_task_id']]
            require(self._bd_subordinate(s,parent['bot_id'],bid),'scope_denied','Target is outside the assigning manager subtree')
        return binding

    def cmd_request_bot_handoff(self,s,actor,a,fx,n,con):
        task=self._dev_get(s,'bot_tasks',a['task_id'])
        self._handoff_authority(s,actor,task,a.get('requested_by_bot'))
        require(task['version']==a['version'] and task['status'] not in TERMINAL | {'handoff_requested'},
                'conflict','Task ended, changed or already has a handoff')
        self._handoff_target(s,task,a['to_bot_id'])
        require(all(s['bot_tasks'][i]['status'] in TERMINAL for i in task['children']),
                'dependency_pending','Reconcile active child work before transferring the manager')
        require(not any(s['bot_task_messages'][i]['status']!='resolved' for i in task.get('consultations',[])),
                'dependency_pending','Resolve outstanding peer consultations before transfer')
        h=dict(a,id=uid('handoff'),subject_id=a['to_bot_id'],session_id=task['session_id'],
            from_bot_id=task['bot_id'],source_principal=task['principal_id'],author=actor['id'],
            phase='requested',version=1,created_seq=s['seq']+1)
        # Fence acceptance immediately; this does NOT claim the customer process has stopped.
        task.update(status='handoff_requested',version=task['version']+1,handoff_id=h['id'])
        task.pop('fence',None)
        self._dev_save(s,fx,'bot_tasks',task)
        return self._dev_save(s,fx,'bot_handoffs',h)

    def cmd_acknowledge_bot_handoff(self,s,actor,a,fx,n,con):
        h=self._dev_get(s,'bot_handoffs',a['handoff_id']); p,d=self._bd_project(s,actor,h['session_id'])
        require(actor['id']==h['source_principal'] or self._bd_owner(actor,p),
                'unauthorized','Source executor or project owner must confirm the process stopped')
        require(h['version']==a['version'] and h['phase']=='requested','invalid_state','Handoff is not awaiting stop acknowledgement')
        task=s['bot_tasks'][h['task_id']]
        require(task['status']=='handoff_requested','invalid_state','Source task is no longer transferring')
        require(a['confirm_stopped'].strip() and a['summary'].strip(),'invalid_input','Explicit stopped-process confirmation required')
        h.update(phase='ready',version=h['version']+1,state_id=task.get('output_state',task['state_id']),
            summary=a['summary'],unfinished=a['unfinished'],stopped_by=actor['id'],confirm_stopped=a['confirm_stopped'])
        return self._dev_save(s,fx,'bot_handoffs',h)

    def _handoff_accept_authority(self,s,actor,h):
        task=s['bot_tasks'][h['task_id']]; principal=s['principals'].get(h['author'])
        require(principal and principal.get('enabled',True),'unauthorized','Original delegator revoked')
        self._handoff_authority(s,principal,task,h.get('requested_by_bot'))
        binding=self._handoff_target(s,task,h['to_bot_id'])
        require(binding['principal_id']==actor['id'],'unauthorized','Only target executor can accept')
        d=self._dev_session(s,actor,h['session_id'])
        require(task['generation']==d['generation'] and not stale_refs(s,task.get('requirement_refs',[])),
                'stale_basis','Project or requirements changed; reassess before a new assignment')

    def cmd_accept_bot_handoff(self,s,actor,a,fx,n,con):
        h=self._dev_get(s,'bot_handoffs',a['handoff_id']); self._dev_session(s,actor,h['session_id'])
        require(h['version']==a['version'] and h['phase']=='ready','invalid_state','Source must acknowledge stopping first')
        self._handoff_accept_authority(s,actor,h)
        self._runtime_fence(s,actor,h['to_bot_id'],a['runtime_fence'],con)
        old=s['bot_tasks'][h['task_id']]
        require(old['status']=='handoff_requested','invalid_state','Source task changed')
        data={k:copy.deepcopy(old[k]) for k in ('session_id','kind','title','completion','write_scope','dependencies','after_tasks','requirement_refs')}
        data.update(bot_id=h['to_bot_id'],state_id=h['state_id'], issue_ids=copy.deepcopy(old.get('issue_ids', [])))
        if old.get('candidate_id'): data['candidate_id']=old['candidate_id']
        new=self._bd_assign(s,actor,data,fx,n,con,handoff=h)
        successor=s['bot_tasks'][new['id']]
        successor['handoff_from']=h['id']
        for k in ('studio_request_id','studio_mode','parent_task_id','reply_request_id'):
            if k in old: successor[k]=old[k]
        successor['children']=copy.deepcopy(old['children'])
        successor['predecessor_task_ids']=old.get('predecessor_task_ids',[])+[old['id']]
        self._handoff_candidate(s,actor,old,successor,h,fx,n,con)
        self._inherit_continuation(old,successor)
        self._dev_save(s,fx,'bot_tasks',successor)
        if old.get('parent_task_id'):
            parent=s['bot_tasks'][old['parent_task_id']]
            parent['children']=[new['id'] if i==old['id'] else i for i in parent['children']]
            self._dev_save(s,fx,'bot_tasks',parent)
        if old.get('reply_request_id'):
            question=s['bot_task_messages'][old['reply_request_id']]; question['response_task_id']=new['id']
            self._dev_save(s,fx,'bot_task_messages',question)
        if old.get('studio_request_id'):
            request=s['studio_bot_requests'][old['studio_request_id']]
            request['task_id']=new['id']; request['task_ids'].append(new['id'])
            self._dev_save(s,fx,'studio_bot_requests',request)
        old.update(status='cancelled',cancellation='Acknowledged handoff',version=old['version']+1,successor_task_id=new['id'])
        self._dev_save(s,fx,'bot_tasks',old)
        h.update(phase='accepted',version=h['version']+1,accepted_by=actor['id'],successor_task_id=new['id'])
        return self._dev_save(s,fx,'bot_handoffs',h)

    def _handoff_candidate(self,s,actor,old,successor,h,fx,n,con):
        if not old.get('output_state'): return
        source=s['dev_states'][old['output_state']]
        original=s['dev_changes'][old['change_id']]['base_state'] if old.get('change_id') else old['state_id']
        candidate=self.cmd_begin_change(s,actor,{'state_id':original,'title':old['title'],
            'purpose':'Continue acknowledged handoff '+h['id'],'write_scope':old['write_scope'],
            'dependencies':old['dependencies'],'assignee':actor['id'],'requirement_refs':old.get('requirement_refs',[])},fx,n,con)
        saved=self.cmd_checkpoint_change(s,actor,{'change_id':candidate['id'],'version':candidate['version'],
            'snapshot':source['snapshot'],'context':source['context'],'summary':h['summary'],
            'rationale':'Preserves saved candidate from '+old['id']+' at '+source['id'],
            'unfinished':h['unfinished'],'capture':{'scope':'Acknowledged saved checkpoint',
            'missing':['Unsaved source-process edits are not transferred']},'work_status':'working'},fx,n,con)
        successor.update(change_id=candidate['id'],output_state=saved['state']['id'])

    def cmd_list_bot_handoffs(self,s,actor,a,fx,n,con):
        self._persistent_access(s,actor,a['bot_id'],con)
        rows=[]
        for h in s.get('bot_handoffs',{}).values():
            if a['bot_id'] not in (h['from_bot_id'],h['to_bot_id']): continue
            from .model import Fault
            try: self._dev_session(s,actor,h['session_id'])
            except Fault: continue
            if h['id']>a.get('after',''): rows.append(copy.deepcopy(h))
        rows.sort(key=lambda h:h['id']); limit=a.get('limit',30)
        return {'items':rows[:limit],'next_cursor':rows[limit-1]['id'] if len(rows)>limit else None}
