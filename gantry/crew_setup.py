"""Initial organization proposals over existing state, identity and Bot contracts."""
import copy
import base64
from . import crew_setup_contracts
from .connection_policy import clean_bytes, decode_files
from .development import in_scope
from .model import require, uid, digest, canonical, identifier


def bot_id_for(organization_id, role):
    return role['existing_bot_id'] or 'crew-'+digest([organization_id,role['role_id']])[:24]


class CrewSetupMixin:
    def _crew_setup(self,s,actor,a,owner=False,write=False):
        setup=self._dev_get(s,'crew_setups',a['setup_id'])
        session=self._dev_session(s,actor,setup['session_id'])
        self._continuity_state(s,actor,setup['state_id'])
        if setup['snapshot']: self.zone_write(actor,self._dev_artifact(s,setup['snapshot'])['zone'])
        if owner:self._dev_human(actor,session)
        if write:
            self.allowed(actor,'record')
            require(setup['version']==a['version'],'stale_basis','Team setup changed; review the current proposal')
        return setup,session

    def _crew_setup_inputs(self,s,session,state,oid):
        org=s.get('organizations',{}).get(oid)
        return {'session_version':session['version'],'active_state':session.get('active_state'),
            'work_heads':{w['id']:[w['head'],w['version']] for w in s.get('dev_changes',{}).values()
                          if w['session_id']==session['id']},
            'organization_version':org['version'] if org else 0,
            'bots':{b['id']:b['version'] for b in s.get('persistent_bots',{}).values() if b['organization_id']==oid},
            'project_version':s.get('bot_projects',{}).get(session['id'],{}).get('version',0),
            'bindings':{b['id']:b['version'] for b in s.get('bot_bindings',{}).values() if b['session_id']==session['id']},
            'requirements':{r['requirement_id']:s['entries'].get(r['requirement_id'],{}).get('revision_id')
                            for r in state['context'].get('requirement_refs',[])}}

    def _crew_setup_view(self,s,actor,setup,session):
        value=copy.deepcopy(setup)
        state=self._continuity_state(s,actor,setup['state_id'])
        value['stale']=setup['inputs']!=self._crew_setup_inputs(s,session,state,setup['organization_id']) if not setup['result'] else False
        value['can_confirm']=actor['kind']=='human' and actor['id']==session['owner']
        value['execution_enabled']=session['mode']=='execute'
        value['readiness']=[]
        if setup['result']:
            for role in setup['result']['roles']:
                presence=self._studio_presence(s,role['bot_id'])
                value['readiness'].append({**role,'runtime':{'not_configured':'unconfigured'}.get(presence['presence'],presence['presence']),
                    'configured':presence['presence']!='not_configured','runtime_version':presence.get('version',0)})
        return value

    def _save_crew_setup(self,s,actor,setup,session,fx):
        clean_bytes(canonical(setup).encode())
        self._dev_save(s,fx,'crew_setups',setup)
        return self._crew_setup_view(s,actor,setup,session)

    def cmd_start_crew_setup(self,s,actor,a,fx,n,con):
        from .crew_sources import parse_source
        session=self._dev_session(s,actor,a['session_id']);self._dev_human(actor,session)
        self.allowed(actor,'record');state=self._continuity_state(s,actor,a['state_id'])
        require(state['session_id']==session['id'],'scope_denied','Project state belongs to another session')
        require(a['organization_name'].strip(),'invalid_input','Organization name required')
        require(len(a['files'])<=30,'invalid_input','Select at most 30 organizational source files')
        labels={x['path']:x['provider'] for x in a['sources']}
        require(len(labels)==len(a['sources']) and set(labels)==set(a['files']),
                'invalid_input','Each selected source needs one provider label')
        existing=s.get('bot_projects',{}).get(session['id'])
        oid=a.get('organization_id') or (existing['organization_id'] if existing else uid('organization'))
        if 'organization_id' in a or existing:
            org=self._organization_owner(s,actor,oid)
            require(org['owner']==session['owner'],'scope_denied','Project and organization owners must match')
            require(not existing or existing['organization_id']==oid,'scope_denied','Project already belongs to another organization')
        else:org=None
        # Preflight expanded content before writing any blob. Raw-byte screening
        # alone cannot detect credentials or active content inside a spreadsheet.
        if a['files']:decode_files(a['files'],list(a['files']))
        parsed_sources={path:parse_source(path,base64.b64decode(raw,validate=True),labels[path])
                        for path,raw in a['files'].items()}
        clean_bytes(a['notes'].encode())
        snapshot,manifest=(self._onboarding_source(s,actor,{'files':a['files']},fx,n,con,session['zone'])
                           if a['files'] else (None,{}))
        records=[];limitations=[];budget=160000
        state_text=canonical({k:state[k] for k in ('summary','context','unfinished','hierarchy','capture')})
        for path,text,locator in [('@project-state',state_text,state['id']),('@owner-notes',a['notes'],'owner statement')]:
            h=digest(text);records.append({'id':digest([path,h,locator]),'path':path,'hash':h,'locator':locator,
                'text':text[:24000],'kind':'observed'})
            if len(text)>24000:limitations.append(path+': context preview truncated; fetch exact state separately')
            budget-=len(text[:24000])
        for path,info in sorted(manifest.items()):
            parsed=parsed_sources[path];limitations.extend(parsed['limitations'])
            omitted=0
            for record in parsed['records']:
                clean_bytes(record['text'].encode())
                if len(record['text'])>budget:omitted+=1;continue
                records.append(record);budget-=len(record['text'])
            if omitted:limitations.append(f'{path}: {omitted} records omitted from bounded context; original remains saved')
        bots=[{k:copy.deepcopy(b[k]) for k in ('id','name','profile','parent_bot_id','version','enabled')}
              for b in s.get('persistent_bots',{}).values() if b['organization_id']==oid]
        inputs=self._crew_setup_inputs(s,session,state,oid)
        setup={'id':uid('crewsetup'),'version':1,'session_id':session['id'],'state_id':state['id'],
            'owner':session['owner'],'organization_id':oid,'organization_name':org['name'] if org else a['organization_name'],
            'notes':a['notes'],'snapshot':snapshot,'manifest':manifest,'sources':a['sources'],
            'evidence_records':records,'source_limitations':limitations,'inputs':inputs,
            'basis':digest([inputs,state['id'],snapshot,a['notes']]),'status':'draft','proposal':None,'result':None,
            'context':{'state':{'id':state['id'],'snapshot':state['snapshot'],'summary':state['summary'],
                               'manifest':dict(self._manifest(s,state['snapshot']))},
                       'organization':({k:copy.deepcopy(org[k]) for k in ('id','name','profile','version')} if org else None),
                       'existing_bots':bots,'scope':list(session['write_scope'])},'created_at':self.clock()}
        return self._save_crew_setup(s,actor,setup,session,fx)

    def cmd_get_crew_setup(self,s,actor,a,fx,n,con):
        setup,session=self._crew_setup(s,actor,a)
        return self._crew_setup_view(s,actor,setup,session)

    def cmd_list_crew_setups(self,s,actor,a,fx,n,con):
        session=self._dev_session(s,actor,a['session_id'])
        return {'items':[self._crew_setup_view(s,actor,x,session) for x in s.get('crew_setups',{}).values()
                         if x['session_id']==session['id']]}

    def _check_crew_setup_basis(self,s,setup,session):
        state=self._dev_get(s,'dev_states',setup['state_id'])
        require(setup['inputs']==self._crew_setup_inputs(s,session,state,setup['organization_id']),
            'stale_basis','Project or organization changed; start a fresh setup from the saved sources')

    def _check_crew_setup_proposal(self,s,setup,session,p):
        roles={r['role_id']:r for r in p['roles']};evidence={r['id'] for r in setup['evidence_records']}
        require(len(roles)==len(p['roles']) and p['lead_role_id'] in roles,'invalid_input','Unique roles and a lead required')
        require(roles[p['lead_role_id']]['parent_role_id'] is None,'invalid_input','Lead must be the root')
        ids=[bot_id_for(setup['organization_id'],r) for r in p['roles']]
        require(len(set(ids))==len(ids),'invalid_input','Each role needs a distinct persistent Bot')
        for role in roles.values():
            identifier(role['role_id']);require(role['name'].strip(),'invalid_input','Role name required')
            require(set(role['evidence_ids'])<=evidence,'invalid_input','Role evidence is not in this saved context')
            self._dev_paths(role['write_scope'],True)
            require(all(in_scope(path,session['write_scope']) for path in role['write_scope']),
                    'scope_denied','Proposed role scope exceeds project delegation')
            seen=set();current=role['role_id']
            while current:
                require(current in roles and current not in seen,'invalid_input','Hierarchy must be complete and acyclic')
                seen.add(current);current=roles[current]['parent_role_id']
            require(p['lead_role_id'] in seen,'invalid_input','Every role must report to the lead')
            parent=roles.get(role['parent_role_id'])
            if parent:
                require(parent['can_assign'],'invalid_input','A reporting manager needs assignment delegation')
                require(all(in_scope(path,parent['write_scope']) for path in role['write_scope']),
                    'scope_denied','Child scope must fit its reporting manager delegation')
            bid=bot_id_for(setup['organization_id'],role);old=s.get('persistent_bots',{}).get(bid)
            if role['existing_bot_id']:
                require(old and old['organization_id']==setup['organization_id'],'scope_denied','Existing Bot is not in the selected organization')
                expected_parent=bot_id_for(setup['organization_id'],parent) if parent else None
                require(old['enabled'] and old['name']==role['name'] and old['profile']==role['profile'] and old['parent_bot_id']==expected_parent,
                    'conflict','Reuse preserves existing Bot profile and hierarchy; change them through a separate reviewed organization update')
            else:require(not old,'conflict','Bot already exists; explicitly reuse its identity')
        org=s.get('organizations',{}).get(setup['organization_id'])
        require(not org or p['organization_profile']==org['profile'],'conflict','Existing organization profile must be preserved')
        clean_bytes(canonical(p).encode())

    def cmd_propose_crew_setup(self,s,actor,a,fx,n,con):
        setup,session=self._crew_setup(s,actor,a,write=True)
        require(not setup['result'],'invalid_state','Team is already activated')
        require(a['input_basis']==setup['basis'],'stale_basis','Wrong source context')
        self._check_crew_setup_basis(s,setup,session)
        self._check_crew_setup_proposal(s,setup,session,a['proposal'])
        setup['proposal']={'content':copy.deepcopy(a['proposal']),'hash':digest(a['proposal']),'author':actor['id']}
        setup['status']='proposed';setup['version']+=1
        return self._save_crew_setup(s,actor,setup,session,fx)

    def cmd_activate_crew_setup(self,s,actor,a,fx,n,con):
        setup,session=self._crew_setup(s,actor,a,owner=True,write=True)
        require(setup['status']=='proposed' and setup['proposal'],'invalid_state','Review an organization proposal first')
        require(setup['proposal']['hash']==a['proposal_hash'],'stale_basis','Proposal differs from reviewed content')
        self._check_crew_setup_basis(s,setup,session)
        p=setup['proposal']['content'];self._check_crew_setup_proposal(s,setup,session,p)
        require(not any(t['status'] in {'running','waiting','held','handoff_requested'} for t in self._bd_task_rows(s,session['id'],con)),
                'conflict','Stop active work before changing the team')
        bindings={b['role_id']:b for b in a['bindings']}
        require(len(bindings)==len(a['bindings']) and set(bindings)=={r['role_id'] for r in p['roles']},'invalid_input','Map every proposed role exactly once')
        require(len({b['principal_id'] for b in bindings.values()})==len(bindings),'invalid_input','Each Bot needs a dedicated principal')
        role_bots={r['role_id']:bot_id_for(setup['organization_id'],r) for r in p['roles']}
        active_bindings=[b for b in s.get('bot_bindings',{}).values() if b['enabled']]
        require(all(b['bot_id'] in role_bots.values() for b in active_bindings if b['session_id']==session['id']),
            'conflict','Existing project Bots must be explicitly reused; disabling a prior role requires a separate delegation change')
        for b in bindings.values():
            bid=role_bots[b['role_id']]
            require(all(old['bot_id']==bid for old in active_bindings if old['principal_id']==b['principal_id'])
                    and all(rt['bot_id']==bid for rt in s.get('bot_runtimes',{}).values()
                            if rt['principal_id']==b['principal_id'] and rt['enabled']),
                    'conflict','This principal already belongs to another persistent Bot; use a dedicated identity')
            if 'request' in b:
                r=b['request'];require(r['member_id']==b['principal_id'] and r['role']=='agent-bot' and r['zones']==[session['zone']],
                    'invalid_input','New Bot credentials must be scoped to this project zone and the agent-bot role')
                self.cmd_grant_workspace_member(s,actor,{'request':r,'fingerprint':digest(r),
                    'sessions':[{'session_id':session['id'],'version':session['version']}],
                    'reason':'Owner activated sourced organization proposal '+setup['id']},fx,n,con)
                session=self._dev_session(s,actor,session['id'])
            principal=s['principals'].get(b['principal_id'],{})
            require(principal.get('kind')=='agent' and principal.get('enabled',True) and b['principal_id'] in session['actors'],
                'unauthorized','Use an existing delegated agent or a new scoped access request')
            require(principal.get('expires_at',self.clock()+1)>self.clock(),'expired','Agent credential has expired')
        oid=setup['organization_id']
        if oid not in s.get('organizations',{}):
            self.cmd_configure_organization(s,actor,{'organization_id':oid,'version':0,'name':setup['organization_name'],
                'profile':p['organization_profile'],'enabled':True},fx,n,con)
        roles={r['role_id']:r for r in p['roles']};members=[]
        for role in p['roles']:
            members.append({k:copy.deepcopy(role[k]) for k in ('name','profile','write_scope','can_assign','can_integrate')} |
                {'bot_id':bot_id_for(oid,role),'principal_id':bindings[role['role_id']]['principal_id'],
                 'parent_bot_id':bot_id_for(oid,roles[role['parent_role_id']]) if role['parent_role_id'] else None})
        proposed=self.cmd_propose_bot_team(s,actor,{'session_id':session['id'],'organization_id':oid,
            'lead_bot_id':bot_id_for(oid,roles[p['lead_role_id']]),'goal':p['goal'],'acceptance':p['acceptance'],
            'members':members,'rationale':'Owner confirmed evidence-bound setup '+setup['id']},fx,n,con)
        self.cmd_activate_bot_team(s,actor,{'proposal_id':proposed['id']},fx,n,con)
        setup['status']='activated';setup['version']+=1
        setup['result']={'organization_id':oid,'lead_bot_id':proposed['configuration']['lead_bot_id'],
            'roles':[{'role_id':r['role_id'],'bot_id':bot_id_for(oid,r),'principal_id':bindings[r['role_id']]['principal_id']} for r in p['roles']],
            'team_proposal_id':proposed['id'],'activated_by':actor['id']}
        return self._save_crew_setup(s,actor,setup,session,fx)

    def _crew_setup_context(self,s,actor,task):
        # A role's onboarding evidence reaches actual work, not only the setup UI.
        # No cross-project memories or source exports are selected implicitly.
        setups=[x for x in s.get('crew_setups',{}).values() if x['session_id']==task['session_id'] and x['result']
                and any(r['bot_id']==task['bot_id'] for r in x['result']['roles'])]
        if not setups:return None
        setup=max(setups,key=lambda x:(x['created_at'],x['id']))
        self._crew_setup(s,actor,{'setup_id':setup['id']})
        mapped=next(r for r in setup['result']['roles'] if r['bot_id']==task['bot_id'])
        role=next(r for r in setup['proposal']['content']['roles'] if r['role_id']==mapped['role_id'])
        ids=set(role['evidence_ids']);remaining=12000;records=[];omitted=0
        for record in setup['evidence_records']:
            if record['id'] not in ids:continue
            if len(record['text'])>remaining:omitted+=1;continue
            records.append(copy.deepcopy(record));remaining-=len(record['text'])
        return {'setup_id':setup['id'],'proposal_hash':setup['proposal']['hash'],
            'role_rationale':role['rationale'],'evidence':records,'omitted_records':omitted,
            'unknowns':setup['proposal']['content']['unknowns'],
            'source_limitations':setup['source_limitations'],
            'retrieval':'get_crew_setup','authority':'Selected organizational evidence; not execution authority or verified engineering results'}

    def cmd_start_crew_setup_work(self,s,actor,a,fx,n,con):
        setup,session=self._crew_setup(s,actor,a,owner=True,write=True)
        require(setup['status']=='activated','invalid_state','Activate the team first')
        if setup['result'].get('first_task_id'):return self._crew_setup_view(s,actor,setup,session)
        require(session['mode']=='execute','mode_disabled','Owner must enable execution separately')
        lead=setup['result']['lead_bot_id']
        require(self._studio_presence(s,lead)['presence']=='online','runtime_unavailable','Start the approved customer runtime first')
        require(session.get('active_state')==setup['inputs']['active_state'],'stale_basis','Project baseline changed; assign from the current state')
        current=self._crew_setup_inputs(s,session,s['dev_states'][setup['state_id']],setup['organization_id'])
        require(current['work_heads']==setup['inputs']['work_heads'],'stale_basis','Work advanced since onboarding; assign from its current state')
        p=setup['proposal']['content'];role=next(r for r in p['roles'] if r['role_id']==p['lead_role_id'])
        task=self.cmd_assign_bot_task(s,actor,{'session_id':session['id'],'bot_id':lead,'state_id':setup['state_id'],
            'kind':'plan','title':p['first_task']['title'],'completion':p['first_task']['completion'],
            'write_scope':role['write_scope'],'dependencies':[],'after_tasks':[]},fx,n,con)
        setup['result']['first_task_id']=task['id'];setup['version']+=1
        return self._save_crew_setup(s,actor,setup,session,fx)
