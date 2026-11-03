"""Version-anchored Studio requests over the existing persistent Bot task queue."""
import copy
from .contracts import register, S, I, A
from .model import require, uid, digest
from .development import in_scope
from .studio_discussion import ANCHOR

register('studio_team', {'project_id': S}, ['project_id'])
register('studio_request_bot', {'work_id':S, 'version':I, 'state_id':S, 'anchor':ANCHOR,
    'mode':{'enum':['ask','assign']}, 'bot_id':S, 'body':{'type':'string','minLength':1,'maxLength':4000},
    'completion':A, 'write_scope':A},
    ['work_id','version','state_id','anchor','mode','bot_id','body','completion','write_scope'])


class StudioBotsMixin:
    def _studio_ask_guard(self,s,actor,command,args):
        # A Bot MCP credential is reusable, not a task-scoped capability. While
        # answering Ask, reserve this executor identity for read-only work so a
        # direct API call cannot escape the worker's action restrictions.
        if actor['kind']!='agent' or command in self.READS: return
        active=[t for t in s.get('bot_tasks',{}).values() if t['principal_id']==actor['id']
            and t.get('studio_mode')=='ask' and t['status'] in {'running','held','handoff_requested'}]
        if not active: return
        task_ids={t['id'] for t in active}; bot_ids={t['bot_id'] for t in active}
        task_commands={'finish_bot_task','hold_bot_task','recover_bot_task','refresh_bot_task',
            'record_bot_action','record_bot_experience','update_bot_working_state',
            'record_bot_learning_use'}
        if command in task_commands and args.get('task_id') in task_ids: return
        if command in {'start_bot_runtime','heartbeat_bot_runtime','stop_bot_runtime'} and args.get('bot_id') in bot_ids: return
        if command in {'acknowledge_bot_handoff','accept_bot_handoff'}:
            h=s.get('bot_handoffs',{}).get(args.get('handoff_id'),{})
            if h.get('task_id') in task_ids: return
        require(False,'scope_denied','This executor is answering a read-only Ask; finish or hand it off before performing other writes')

    def _studio_task_authority(self, s, actor, change, mode):
        self.allowed(actor, 'record'); self.allowed(actor, 'work')
        session = self._dev_session(s, actor, change['session_id'])
        # A request is not an admin grant. A human may delegate only work they own.
        require(actor['kind'] == 'human', 'unauthorized', 'Bots delegate through their fenced task reports')
        if mode == 'assign':
            require(actor['id'] in {change['assignee'], change['author'], session['owner']},
                    'unauthorized', 'Only this work owner or project owner may assign editing')
        return session

    def _studio_presence(self, s, bot_id):
        rt = s.get('bot_runtimes', {}).get(bot_id)
        if not rt: return {'presence':'not_configured', 'host':'customer-managed'}
        return {'presence':'online' if rt['enabled'] and rt.get('lease_until',0)>self.clock() else 'offline',
            'host':'customer-managed', 'version':rt['version'], 'environment':copy.deepcopy(rt['environment']),
            'principal_id':rt['principal_id'], 'enabled':rt['enabled']}

    def _studio_team_session(self, s, actor, d):
        p = s.get('bot_projects',{}).get(d['id'])
        bindings = [b for b in s.get('bot_bindings',{}).values()
            if b['session_id']==d['id'] and b.get('workflow')=='bot_development']
        bots = []
        for binding in sorted(bindings,key=lambda b:b['bot_id']):
            bot = s['persistent_bots'][binding['bot_id']]
            bots.append({'bot':copy.deepcopy(bot), 'binding':copy.deepcopy(binding),
                'runtime':self._studio_presence(s,bot['id'])})
        principals = [{'id':pid,'kind':s['principals'][pid]['kind']}
            for pid in sorted(set(d['actors'])) if pid in s['principals'] and s['principals'][pid]['kind']=='agent' and s['principals'][pid].get('enabled',True)
            and ('work' in s['principals'][pid]['permissions'] or 'admin' in s['principals'][pid]['permissions'])]
        config = {'project':p,'bots':[{k:v for k,v in row.items() if k!='runtime'} for row in bots],
            'session_version':d['version']}
        return {'id':d['id'],'title':d['title'],'mode':d['mode'],'write_scope':d['write_scope'],
            'requirements':d['requirements'],'constraints':d['constraints'],'owner':d['owner'],
            'version':d['version'],'max_parallel':d['max_parallel'],'max_executions':d['max_executions'],
            'project':p,'bots':bots,'principals':principals,'configuration_token':digest(config),
            'can_configure':actor['kind']=='human' and actor['id']==d['owner'] and
                ('allowed_commands' not in actor or 'studio_setup_team' in actor['allowed_commands'])}

    def cmd_studio_team(self, s, actor, a, fx, n, con):
        overview=self.cmd_product_overview(s,actor,{},fx,n,con)
        project=next((p for p in overview['projects'] if p['id']==a['project_id']),None)
        require(project,'unauthorized','Project is not accessible')
        return {'project':project,'sessions':[self._studio_team_session(s,actor,self._dev_session(s,actor,d['id'])) for d in overview['sessions']
            if d['project_id']==project['id']], 'mentor_required':False}

    def cmd_studio_request_bot(self, s, actor, a, fx, n, con):
        change, d = self._studio_work(s,actor,a['work_id'])
        self._studio_task_authority(s,actor,change,a['mode'])
        target=self._bd_binding(s,d['id'],a['bot_id'])
        require(s['principals'][target['principal_id']]['kind']=='agent','unauthorized','Studio Bots require a dedicated agent identity')
        state = self._studio_state(s,actor,change,a['state_id'])
        require(a['version']==change['version'],'stale_basis','Work changed; refresh before sending')
        require(a['mode']=='ask' or state['id']==change['head'],'stale_basis','Assign from the latest work checkpoint')
        require(a['body'].strip() and a['completion'],'invalid_input','Question/purpose and completion conditions required')
        require(a['mode']!='ask' or not a['write_scope'],'invalid_input','Ask is read-only; use Assign work for editing')
        require(a['mode']!='assign' or a['write_scope'],'invalid_input','Assign an explicit editable scope')
        require(all(in_scope(path,change['write_scope']) for path in a['write_scope']),
                'scope_denied','Assignment exceeds the originating work scope')
        # Reuse selection validation, recipient access and exact-version thread handling.
        message=self.cmd_studio_comment(s,actor,{k:a[k] for k in ('work_id','state_id','anchor')} |
            {'body':a['body'],'mentions':[]},fx,n,con)
        request_id=uid('brequest')
        manifest=self._manifest(s,state['snapshot'])
        dependencies=sorted(set(change['dependencies']+[a['anchor']['path']] if a['anchor'].get('path') else change['dependencies']))
        task=self._bd_assign(s,actor,{'session_id':d['id'],'bot_id':a['bot_id'],'state_id':state['id'],
            'kind':'report' if a['mode']=='ask' else 'develop','title':a['body'][:200],
            'completion':a['completion'],'write_scope':a['write_scope'],
            'dependencies':[p for p in dependencies if p in manifest],'after_tasks':[],
            'requirement_refs':change.get('requirement_refs',[])},fx,n,con,studio={'change':change,'mode':a['mode']})
        saved=s['bot_tasks'][task['id']]
        saved.update(studio_request_id=request_id,studio_mode=a['mode'])
        self._dev_save(s,fx,'bot_tasks',saved)
        record=dict(a,id=request_id,subject_id=change['id'],session_id=d['id'],task_id=task['id'],
            task_ids=[task['id']],thread_id=message['thread_id'],requester=actor['id'],created_seq=s['seq']+1)
        self._dev_save(s,fx,'studio_bot_requests',record)
        return {'request_id':request_id,'task_id':task['id'],'thread_id':message['thread_id'],
            'status':'pending','runtime':self._studio_presence(s,a['bot_id'])}

    def _studio_bot_requests(self,s,work_id,state_id=None,actor=None):
        rows=[]
        for r in s.get('studio_bot_requests',{}).values():
            if r['work_id']!=work_id or (state_id and r['state_id']!=state_id): continue
            task=s['bot_tasks'][r['task_id']]
            owner=s['bot_projects'][task['session_id']]['owner']
            handoff=s.get('bot_handoffs',{}).get(task.get('handoff_id'))
            rows.append({**copy.deepcopy(r),'status':task['status'],'task_version':task['version'],
                'can_handoff':bool(actor and actor['kind']=='human' and actor['id'] in {owner,r['requester']}),
                'can_acknowledge':bool(actor and handoff and (actor['id']==handoff['source_principal'] or actor['kind']=='human' and actor['id']==owner)),
                'bot_id':task['bot_id'],'bot_name':s['persistent_bots'][task['bot_id']]['name'],
                'handoff':copy.deepcopy(s.get('bot_handoffs',{}).get(task.get('handoff_id'))),
                'runtime':self._studio_presence(s,task['bot_id']), 'hold_reason':task.get('hold_reason'),
                'result_work_id':task.get('change_id'),'result_state_id':task.get('output_state'),
                'children':[{k:c.get(k) for k in ('id','bot_id','candidate_id','status','change_id','output_state')}
                    for c in (s['bot_tasks'][i] for i in task['children'])]})
        return sorted(rows,key=lambda r:r['created_seq'])

    def _studio_bot_context(self,s,task):
        if not task.get('studio_request_id'): return {}
        record=s['studio_bot_requests'][task['studio_request_id']]
        return {'studio_request':{k:copy.deepcopy(record[k]) for k in
            ('id','work_id','state_id','anchor','body','mode','requester','thread_id')}}

    def _studio_return_bot_report(self,s,actor,task,fx,n,con):
        if not task.get('studio_request_id') or task['status'] not in {'completed','failed','blocked','cancelled'}: return
        r=s['studio_bot_requests'][task['studio_request_id']]
        if task.get('output_state') and not task.get('change_id'):
            integrated=s['dev_states'][task['output_state']]
            change=self.cmd_begin_change(s,actor,{'state_id':task['state_id'],'title':task['title']+' · Candidate',
                'purpose':'Integrated Bot candidate; not formally adopted','write_scope':task['write_scope'],
                'dependencies':task['dependencies'],'assignee':actor['id'],'requirement_refs':task.get('requirement_refs',[])},fx,n,con)
            saved=self.cmd_checkpoint_change(s,actor,{'change_id':change['id'],'version':change['version'],
                'snapshot':integrated['snapshot'],'context':integrated['context'],'summary':integrated['summary'],
                'rationale':'Candidate from integration '+integrated['id'],'unfinished':integrated['unfinished'],
                'capture':integrated['capture'],'work_status':'completed'},fx,n,con)
            self.cmd_share_change(s,actor,{'change_id':change['id'],'version':saved['change']['version']},fx,n,con)
            task.update(change_id=change['id'],integrated_state=integrated['id'],output_state=saved['state']['id'])
            self._dev_save(s,fx,'bot_tasks',task)
        report=task['reports'][-1]['report'] if task['reports'] else {'summary':task.get('cancellation','Task stopped'),'rationale':'','unverified':[]}
        body=report['summary']+'\n\n'+report['rationale']
        if report['unverified']: body+='\n\nUnverified: '+'; '.join(report['unverified'])
        message=self.cmd_studio_comment(s,actor,{'work_id':r['work_id'],'state_id':r['state_id'],
            'anchor':r['anchor'],'thread_id':r['thread_id'],'body':body[:4000] or 'Task ended','mentions':[]},fx,n,con)
        message.update(bot_id=task['bot_id'],task_id=task['id'],result_work_id=task.get('change_id'),result_state_id=task.get('output_state'))
        self._dev_save(s,fx,'studio_messages',message)
        self._dev_save(s,fx,'studio_notifications',dict(id=uid('mention'),session_id=task['session_id'],
            subject_id=r['requester'],work_id=r['work_id'],state_id=r['state_id'],thread_id=r['thread_id'],
            message_id=message['id'],at=self.clock(),read=False))
