"""One exact-state target contract for browsing, conversations and agent retrieval."""
from .contracts import S
from .model import require, Fault

ANCHOR = {'type':'object','properties':{'kind':{'enum':['work','project','component','file','cad','code','requirement']},
    'path':S,'hash':S,'part':S,'line':{'type':'integer','minimum':1},'component_id':S,
    'requirement_id':S,'revision_id':S},'required':['kind'],'additionalProperties':False}


class StudioTargetsMixin:
    def _studio_cad_part_supported(self,path,info):
        """Adapters may extend preview support while retaining exact source hashes."""
        return path.lower().endswith(('.stl','.obj'))

    def _studio_project_state(self,s,actor,pid,sid=None):
        project=self._project(s,actor,pid)
        sid=sid or project.get('baseline_state')
        require(sid,'invalid_state','No saved project state; import a workspace first')
        state=self._continuity_state(s,actor,sid)
        link=s.get('product_sessions',{}).get(state['session_id'],{})
        require(link.get('project_id')==pid or project.get('baseline_state')==sid,
                'scope_denied','State does not belong to this project')
        return project,state

    def _studio_target(self,s,actor,a):
        change=None
        if a.get('work_id'):
            change,session=self._studio_work(s,actor,a['work_id'])
            state=self._studio_state(s,actor,change,a['state_id'])
            pid=s.get('product_sessions',{}).get(session['id'],{}).get('project_id')
            require(not a.get('project_id') or a['project_id']==pid,'scope_denied','Work belongs to another project')
        else:
            require(a.get('project_id'),'invalid_input','Work or project target required')
            project,state=self._studio_project_state(s,actor,a['project_id'],a['state_id'])
            pid=project['id'];session=self._dev_session(s,actor,state['session_id'])
        anchor=a['anchor'];kind=anchor['kind']
        fields={'work':{'kind'},'project':{'kind'},'component':{'kind','component_id'},
            'requirement':{'kind','requirement_id','revision_id'},'file':{'kind','path','hash'},
            'cad':{'kind','path','hash','part'},'code':{'kind','path','hash','line'}}
        require(set(anchor)==fields[kind],'invalid_input','Anchor fields do not match target')
        if kind=='work': require(change,'invalid_input','Work anchor requires work')
        if kind=='component':
            require(any(h['id']==anchor['component_id'] for h in state['hierarchy']),'invalid_input','Component absent from this state')
        if kind=='requirement':
            ref={k:anchor[k] for k in ('requirement_id','revision_id')}
            require(ref in state['context'].get('requirement_refs',[]),'invalid_input','Requirement revision absent from state')
        if kind in {'file','cad','code'}:
            path=anchor['path'];info=self._manifest(s,state['snapshot']).get(path)
            require(info and info['hash']==anchor['hash'],'invalid_input','Anchor does not match saved file and version')
            if kind=='code':
                require(info['size']<=262144,'invalid_input','File too large for line anchoring')
                try: text=b''.join(self.store.verified_parts(info)).decode('utf-8')
                except UnicodeDecodeError: raise Fault('invalid_input','Code line requires UTF-8 text')
                require('\x00' not in text and 1<=anchor['line']<=len(text.splitlines()),'invalid_input','Line does not exist')
            if kind=='cad':
                require(anchor['part']==path and self._studio_cad_part_supported(path,info),'invalid_input','Select a supported saved part')
        return change,session,state,pid

    def _studio_participants(self,s,actor,session,state):
        rows=[]
        for pid in sorted(set(session['actors']+[session['owner']])):
            person=s['principals'].get(pid,{})
            if not person.get('enabled',True): continue
            try: self._continuity_state(s,person,state['id'])
            except (Fault,KeyError): continue
            bots=[s['persistent_bots'][b['bot_id']] for b in s.get('bot_bindings',{}).values()
                if b['session_id']==session['id'] and b['principal_id']==pid and b.get('enabled')
                and b.get('workflow')=='bot_development' and s['persistent_bots'][b['bot_id']]['enabled']]
            rows.append({'id':pid,'kind':person.get('kind','unknown'),
                'name':' / '.join(b['name'] for b in bots) or person.get('name',pid),
                'role':' / '.join(b['profile']['mission'] for b in bots) or 'Project member',
                'team':session['title'],'bot_ids':[b['id'] for b in bots]})
        return rows
