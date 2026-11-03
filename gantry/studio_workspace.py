"""Atomic saved-workspace import and delta checkpoints over continuity, not a second ledger."""
import copy
from .contracts import register, S, I, A
from .continuity_contracts import NODE, CONTEXT
from .connection_policy import decode_files, safe_path
from .development import in_scope
from .model import require, uid

FILES = {'type':'object','maxProperties':1000,'additionalProperties':{'type':'string'}}
register('studio_import_project', {'name':S,'description':S,'files':FILES,
    'hierarchy':{'type':'array','minItems':1,'maxItems':1000,'items':NODE},'context':CONTEXT,
    'title':S,'purpose':S,'write_scope':A,'dependencies':A,'actors':A,'missing':A,'zone':S},
    ['name','description','files','hierarchy','context','title','purpose','write_scope','dependencies','actors','missing'])
register('studio_sync_update', {'work_id':S,'version':I,'expected_state':S,'files':FILES,'deleted':A,
    'summary':S,'rationale':S,'unfinished':A,'missing':A,'context':CONTEXT},
    ['work_id','version','expected_state','files','deleted','summary','rationale','unfinished','missing'])


class StudioWorkspaceMixin:
    def cmd_studio_import_project(self, s, actor, a, fx, n, con):
        self._dev_human(actor); self.allowed(actor,'record')
        decode_files(a['files'], list(a['files']))
        for node in a['hierarchy']:
            for path in node['paths']: safe_path(path, True)
        for path in a['write_scope']: safe_path(path, True)
        project=self.cmd_save_project(s,actor,{'name':a['name'],'description':a['description'],
            'zone':a.get('zone','root')},fx,n,con)
        missing=sorted(set(a['missing']+['unsaved edits','earlier tool operations','environment not verified']))
        artifact=self.cmd_capture_artifact(s,actor,{'files':a['files'],'zone':project['zone'],
            'source':{'adapter':'saved-workspace','project_id':project['id']},
            'capture_scope':'explicit saved workspace scope','missing_dependencies':missing},fx,n,con)
        d=self.cmd_connect_development(s,actor,{'title':a['title'],'zone':project['zone'],
            'snapshot':artifact['revision_id'],'requirements':a['context']['requirements'],
            'constraints':a['context']['constraints'],'capture':{'scope':'saved workspace','missing':missing},
            'unverified':a['context']['open_questions'],'mode':'suggest','actors':a['actors'],
            'write_scope':a['write_scope'],'recipes':{},'max_executions':0,'timeout_seconds':300,'max_parallel':1},fx,n,con)
        state=self.cmd_initialize_continuity(s,actor,{'session_id':d['id'],'version':d['version'],
            'hierarchy':a['hierarchy'],'context':a['context'],'summary':'Imported existing saved development'},fx,n,con)
        project=self.cmd_save_project(s,actor,{'project_id':project['id'],'version':project['version'],
            'name':project['name'],'description':project['description'],'baseline_state':state['id']},fx,n,con)
        self.cmd_link_product_session(s,actor,{'project_id':project['id'],'session_id':d['id']},fx,n,con)
        change=self.cmd_begin_change(s,actor,{'state_id':state['id'],'title':a['title'],'purpose':a['purpose'],
            'write_scope':a['write_scope'],'dependencies':a['dependencies'],'assignee':actor['id']},fx,n,con)
        return {'project':project,'state':state,'change':change}

    def cmd_studio_sync_update(self, s, actor, a, fx, n, con):
        c=self._change(s,actor,{'change_id':a['work_id'],'version':a['version']}); self.allowed(actor,'record')
        require(c['head']==a['expected_state'],'stale_basis','Work advanced; inspect before synchronization')
        previous=self._continuity_state(s,actor,c['head'])
        require(not set(a['deleted']) & set(a['files']),'invalid_input','Cannot update and delete the same path')
        paths=set(a['deleted']) | set(a['files'])
        require(paths or ('context' in a and a['context'] != previous['context']), 'invalid_input','No update')
        for path in paths:
            safe_path(path)
            require(in_scope(path,c['write_scope']),'scope_denied','Path outside this work scope')
        files=copy.deepcopy(dict(self._manifest(s,previous['snapshot'])))
        for path in a['deleted']:
            require(path in files,'invalid_input','Deleted path absent from baseline')
            del files[path]
        if a['files']:
            decode_files(a['files'],c['write_scope'])
            upload=self.cmd_capture_artifact(s,actor,{'files':a['files'],'zone':s['dev_sessions'][c['session_id']]['zone'],
                'capture_scope':'saved file delta'},fx,n,con)
            files.update(self._manifest(s,upload['revision_id']))
        require(files,'invalid_input','Workspace must retain at least one file')
        missing=sorted(set(previous['capture']['missing']+a['missing']))
        artifact=self._entry(uid('artifact'),'artifact_snapshot',s['dev_sessions'][c['session_id']]['zone'],
            {'files':files,'capture_scope':'saved workspace checkpoint','missing_dependencies':missing,
             'source':{**(self._dev_artifact(s,previous['snapshot'])['data'].get('source') or {}),
                       'adapter':'saved-workspace','previous_state':previous['id']},'restorable':True},None)
        self._save_entry(s,fx,artifact)
        return self.cmd_checkpoint_change(s,actor,{'change_id':c['id'],'version':c['version'],
            'snapshot':artifact['revision_id'],'summary':a['summary'],'rationale':a['rationale'],
            'unfinished':a['unfinished'],'work_status':'working',
            **({'context':a['context']} if 'context' in a else {}),
            'capture':{'scope':'saved files; no unsaved edits or native tool operations','missing':missing}},fx,n,con)
