"""Artifact-first views over existing projects, changes, states and shares.

Studio never adopts or certifies a design. All writes use the same Core transaction.
"""
import copy
from .contracts import register, S, I
from .development import in_scope
from .model import Fault, require, uid, digest
from .studio_discussion import StudioDiscussionMixin
from .studio_workspace import StudioWorkspaceMixin

LIMIT = {'type':'integer','minimum':1,'maximum':100}
register('studio_overview', {'after':S, 'limit':LIMIT})
register('studio_work', {'work_id':S,'state_id':S,'activity_only':{'type':'boolean'}}, ['work_id'])
register('studio_import_update', {'work_id':S,'version':I,'files':{'type':'object','additionalProperties':{'type':'string'}},
    'summary':{'type':'string','minLength':1,'maxLength':1000}}, ['work_id','version','files','summary'])
register('studio_share_update', {'work_id':S,'version':I,'state_id':S,'note':{'type':'string','maxLength':1000}},
    ['work_id','version','state_id','note'])


class StudioMixin(StudioDiscussionMixin, StudioWorkspaceMixin):
    def _studio_work(self, s, actor, wid):
        change = self._dev_get(s, 'dev_changes', wid)
        session = self._dev_session(s, actor, change['session_id'])
        return change, session

    def _studio_states(self, s, change):
        return [change['base_state']] + change['checkpoints']

    def _studio_state(self, s, actor, change, sid):
        require(sid in self._studio_states(s, change), 'invalid_input', 'State does not belong to this work')
        return self._continuity_state(s, actor, sid)

    def _studio_summary(self, s, change, project_id, task=None):
        state = s['dev_states'][change['head']]
        owner = s['principals'].get(change['assignee'], {})
        return {**{k:change[k] for k in ('id','title','purpose','session_id','version','base_state','head','status','sharing','assignee')},
            'project_id':project_id,'owner':{'id':change['assignee'],'kind':owner.get('kind','unknown')},
            'components':[{'id':h['id'],'title':h['title'],'parent':h.get('parent')} for h in state['hierarchy']
                if any(in_scope(p,change['write_scope']) for p in h['paths']) or
                   any(in_scope(p,h['paths']) for p in change['write_scope'])],
            'task_status':task['status'] if task else None, 'updated_at':state['created_at']}

    def cmd_studio_overview(self, s, actor, a, fx, n, con):
        overview = self.cmd_product_overview(s, actor, {}, fx, n, con)
        sessions = {d['id']:d for d in overview['sessions']}
        projects = []
        for p in overview['projects']:
            own = [d for d in sessions.values() if d['project_id'] == p['id']]
            sid = p.get('baseline_state') or next((d['active_state'] for d in own if d.get('active_state')), None)
            state = None
            if sid:
                try: state = self._continuity_state(s, actor, sid)
                except Fault: pass
            projects.append({**p,'hierarchy':state['hierarchy'] if state else [],
                'structure_state':state['id'] if state else None,
                'sessions':[{'id':d['id'],'title':d['title'],'active_state':d.get('active_state')} for d in own]})
        tasks={t.get('change_id'):t for t in s.get('bot_tasks',{}).values()}
        works=[]
        for c in s.get('dev_changes', {}).values():
            if c['session_id'] not in sessions: continue
            try: self._continuity_state(s,actor,c['head'])
            except Fault: continue
            works.append(self._studio_summary(s,c,sessions[c['session_id']]['project_id'],tasks.get(c['id'])))
        works.sort(key=lambda w:w['id'])
        after=a.get('after',''); eligible=[w for w in works if w['id']>after]; limit=a.get('limit',100)
        return {'projects':projects,'works':eligible[:limit], 'next':eligible[limit-1]['id'] if len(eligible)>limit else None,
            'total':len(works),'seq':s['seq'],
            'can_import':actor['kind']=='human' and ('admin' in actor['permissions'] or {'work','record'} <= set(actor['permissions'])) and
                ('allowed_commands' not in actor or 'studio_import_project' in actor['allowed_commands'])}

    def cmd_studio_work(self, s, actor, a, fx, n, con):
        c,d=self._studio_work(s,actor,a['work_id']); sid=a.get('state_id',c['head'])
        state=self._studio_state(s,actor,c,sid)
        discussions=self._studio_discussion_index(s,actor,c)
        state_ids=set(self._studio_states(s,c))
        activity=digest({'work':c,'discussions':discussions,
            'shares':[x for x in s.get('dev_shares',{}).values() if x['change_id']==c['id']],
            'execution_context':{table:[x for x in s.get(table,{}).values() if x.get('session_id')==d['id']]
                for table in ('dev_executions','dev_evaluations','dev_contracts','bot_tasks')},
            'adoptions':[e for e in s['entries'].values() if e['type']=='design_document'
                and e['data'].get('development_state') in state_ids]})
        if a.get('activity_only'): return {'activity_token':activity}
        project=s.get('product_sessions',{}).get(d['id'],{}).get('project_id')
        shares=[x for x in s.get('dev_shares',{}).values() if x['change_id']==c['id']]
        versions=[]
        for index, ref in enumerate(self._studio_states(s,c)):
            st=self._continuity_state(s,actor,ref)
            receipts=[x for x in shares if x['state_id']==ref]
            versions.append({'id':ref,'number':index,'summary':st['summary'],'created_at':st['created_at'],
                'sharing':'shared' if receipts else 'baseline' if index==0 else 'unshared',
                'notes':[x['note'] for x in receipts if x.get('note')]})
        participants=[]
        for pid in sorted(set(d['actors']+[d['owner']])):
            person=s['principals'].get(pid,{})
            if person.get('enabled',True): participants.append({'id':pid,'kind':person.get('kind','unknown')})
        task=next((t for t in s.get('bot_tasks',{}).values() if t.get('change_id')==c['id']),None)
        source=self._dev_artifact(s,state['snapshot'])['data'].get('source') or {}
        permitted=lambda command: 'allowed_commands' not in actor or command in actor['allowed_commands']
        return {'work':{**self._studio_summary(s,c,project,task),'write_scope':c['write_scope'],'dependencies':c['dependencies']},
            'source':{k:source[k] for k in ('repository','commit') if isinstance(source.get(k),str)},
            'activity':[{'id':x['id'],'status':x['status']} for x in s.get('dev_executions',{}).values()
                if x.get('input_state')==sid and x['status'] in ('running','waiting')],
            'selected':self.cmd_get_development_state(s,actor,{'state_id':sid},fx,n,con),
            'versions':versions,'participants':participants,
            'threads':self._studio_threads(s,c['id'],sid),
            'discussion_index':discussions,'activity_token':activity,
            'can_update':permitted('studio_import_update') and permitted('studio_share_update') and ('admin' in actor['permissions'] or (actor['id'] in {c['assignee'],c['author']} and {'work','record'} <= set(actor['permissions']))) and c['sharing']!='integrated',
            'can_comment':permitted('studio_comment') and ('record' in actor['permissions'] or 'admin' in actor['permissions']),
            'capture':state['capture']}

    def cmd_studio_import_update(self, s, actor, a, fx, n, con):
        c=self._change(s,actor,{'change_id':a['work_id'],'version':a['version']})
        d=self._dev_session(s,actor,c['session_id']); self.allowed(actor,'record')
        pid=s.get('product_sessions',{}).get(d['id'],{}).get('project_id')
        require(pid, 'invalid_state', 'Link this development to a project before browser import')
        # Reuse credential screening, upload limits, immutable artifact storage.
        upload=self.cmd_upload_project_files(s,actor,{'project_id':pid,'session_id':d['id'],
            'files':a['files'],'category':'other','summary':a['summary']},fx,n,con)
        require(all(in_scope(p,c['write_scope']) for p in a['files']), 'scope_denied', 'Files outside this work scope')
        previous=self._continuity_state(s,actor,c['head'])
        files=copy.deepcopy(dict(self._manifest(s,previous['snapshot'])))
        files.update(self._manifest(s,upload['snapshot']))
        artifact=self._entry(uid('artifact'),'artifact_snapshot',d['zone'],{'files':files,
            'capture_scope':'saved files uploaded over prior checkpoint','missing_dependencies':previous['capture']['missing'],
            'source':{**(self._dev_artifact(s,previous['snapshot'])['data'].get('source') or {}),
                'previous_state':previous['id'],'upload':upload['id']},'restorable':True},None)
        self._save_entry(s,fx,artifact)
        return self.cmd_checkpoint_change(s,actor,{'change_id':c['id'],'version':c['version'],
            'snapshot':artifact['revision_id'],'summary':a['summary'],'rationale':'User imported saved external edits',
            'unfinished':previous['unfinished'],'work_status':'working',
            'capture':{'scope':'uploaded saved files over previous checkpoint',
                'missing':sorted(set(previous['capture']['missing']+['unsaved external edits','files not selected for import']))}},fx,n,con)

    def cmd_studio_share_update(self, s, actor, a, fx, n, con):
        c=self._change(s,actor,{'change_id':a['work_id'],'version':a['version']})
        require(c['head']==a['state_id'],'stale_basis','Work advanced; inspect the new version before sharing')
        require(c['sharing']!='shared','invalid_state','This checkpoint is already shared')
        result=self.cmd_share_change(s,actor,{'change_id':c['id'],'version':c['version']},fx,n,con)
        result['share']['note']=a['note']; self._dev_save(s,fx,'dev_shares',result['share'])
        return result
