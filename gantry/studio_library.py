"""Bounded human/agent views of the same immutable development state."""
from .contracts import register, S
from .studio_targets import ANCHOR, StudioTargetsMixin
from .engineering_context import assess as engineering_assess
from .requirement_traceability import assess as requirement_assess
from .development import in_scope
from .model import require, Fault
from .indexed import entry_values

PAGE={'after':S,'limit':{'type':'integer','minimum':1,'maximum':100}}
TARGET={'project_id':S,'state_id':S,'anchor':ANCHOR}
register('studio_library', {'project_id':S,'state_id':S,'component_id':S,'query':{'type':'string','maxLength':240},'path':S,
    'section':{'enum':['files','requirements','versions']},**PAGE}, ['project_id','section'])
register('studio_related', {**TARGET,**PAGE,'message_after':S}, ['project_id','state_id','anchor'])
register('studio_context', {**TARGET,**PAGE,'since_state':S,'delta_after':S}, ['project_id','state_id','anchor'])


def page(items,a,key):
    rows=sorted((x for x in items if x[key]>a.get('after','')),key=lambda x:x[key]);limit=a.get('limit',50)
    return {'items':rows[:limit],'next':rows[limit-1][key] if len(rows)>limit else None}


def component_scope(nodes, component_id):
    require(any(h['id']==component_id for h in nodes),'invalid_input','Unknown component')
    ids={component_id}
    for _ in nodes:
        expanded=ids|{h['id'] for h in nodes if h.get('parent') in ids}
        if expanded==ids: break
        ids=expanded
    return [p for h in nodes if h['id'] in ids for p in h['paths']]


class StudioLibraryMixin(StudioTargetsMixin):
    def _studio_state_label(self,s,state):
        shares=[v for v in s.get('dev_shares',{}).values() if v['state_id']==state['id']]
        adopted=any(e['type']=='design_document' and not e.get('retracted') and
            e['data'].get('development_state')==state['id'] for e in entry_values(s['entries'],'design_document'))
        return {k:state[k] for k in ('id','session_id','snapshot','summary','created_at','parents','work_status','capture','unfinished')} | {
            'change_id':state.get('change_id'),'rationale':state.get('rationale',''),
            'sharing':'integrated' if state.get('integrated_changes') else 'shared' if shares else 'unshared',
            'adoption':'human_adopted' if adopted else 'unadopted'}

    def _studio_coverage(self,s,state):
        engineering=engineering_assess(state['context'],self._manifest(s,state['snapshot']))
        coverage=requirement_assess(s,state['context'],engineering)
        checks={c['id']:c for c in engineering['checks']}
        for requirement in coverage['items']:
            for result in requirement['checks']:
                check=checks.get(result['check_id'],{})
                result.update(recorded_status=check.get('status'),stale_inputs=check.get('stale_inputs',[]),stale_evidence=check.get('stale_evidence',[]))
        return engineering,coverage

    def cmd_studio_library(self,s,actor,a,fx,n,con):
        project,state=self._studio_project_state(s,actor,a['project_id'],a.get('state_id'))
        meta=self._studio_state_label(s,state);section=a['section'];query=a.get('query','').casefold()
        common={'project':{'id':project['id'],'name':project['name']},'state':meta,'section':section,
            'baseline_state':project.get('baseline_state'),'source':{'state_id':state['id'],'snapshot':state['snapshot']}}
        if section=='versions':
            # SQL pages avoid loading the entire history. A page may be empty after access filtering.
            rows=con.execute("SELECT id FROM records WHERE collection='dev_states' AND id>? AND (session_id IN "
                "(SELECT id FROM records WHERE collection='product_sessions' AND COALESCE(json_extract(body,'$.value.project_id'),json_extract(body,'$.project_id'))=?) OR id=?) "
                "ORDER BY id LIMIT ?", (a.get('after',''),project['id'],project.get('baseline_state',''),a.get('limit',50)+1)).fetchall()
            items=[];limit=a.get('limit',50)
            for row in rows[:limit]:
                try: _,st=self._studio_project_state(s,actor,project['id'],row[0])
                except Fault: continue
                items.append(self._studio_state_label(s,st))
            return common | {'items':items,'next':rows[limit-1][0] if len(rows)>limit else None}
        manifest=self._manifest(s,state['snapshot'])
        nodes=state['hierarchy'];scope=None
        if a.get('component_id'):
            scope=component_scope(nodes,a['component_id'])
        if section=='files':
            items=({'path':p,**info,'storage':'bytes_saved','components':[h['id'] for h in nodes if in_scope(p,h['paths'])]}
                for p,info in manifest.items() if (scope is None or in_scope(p,scope)) and query in p.casefold() and (not a.get('path') or p==a['path']))
            return common | page(items,a,'path') | {'components':[
                {'id':h['id'],'title':h['title'],**state['components'][h['id']],
                 **({'external_uri':h['external_uri']} if h.get('external_uri') else {})}
                for h in nodes if state['components'][h['id']]['storage']!='bytes_saved']}
        engineering,coverage=self._studio_coverage(s,state)
        items=coverage['items']
        if scope is not None:
            refs=[r for c in engineering['checks'] if any(in_scope(p,scope) for p in c['inputs']) for r in c.get('requirement_refs',[])]
            items=[r for r in items if any(x['requirement_id']==r['requirement_id'] and x['revision_id']==r['revision_id'] for x in refs)]
        return common | page([r for r in items if query in (r['description']+' '+r['requirement_id']).casefold()],a,'requirement_id') | {
            'unlinked_requirements':coverage['unlinked_requirements'],'limitations':coverage['limitations']}

    def _studio_related_data(self,s,actor,a,con):
        _,session,state,pid=self._studio_target(s,actor,a)
        anchor=a['anchor'];manifest=self._manifest(s,state['snapshot']);eng,cov=self._studio_coverage(s,state)
        if anchor.get('path'): paths={anchor['path']}
        elif anchor['kind']=='component':
            scope=component_scope(state['hierarchy'],anchor['component_id'])
            paths={p for p in manifest if in_scope(p,scope)}
        else: paths=set()
        if anchor['kind']=='requirement':
            checks=[c for c in eng['checks'] if {'requirement_id':anchor['requirement_id'],'revision_id':anchor['revision_id']} in c.get('requirement_refs',[])]
            refs=[{k:anchor[k] for k in ('requirement_id','revision_id')}]
        elif anchor['kind'] in {'project','work'}:
            checks=eng['checks'];refs=state['context'].get('requirement_refs',[])
        else:
            checks=[c for c in eng['checks'] if paths & (set(c['inputs'])|set(c.get('evidence',{})))]
            refs=[r for c in checks for r in c.get('requirement_refs',[])]
        related_paths=paths|{p for c in checks for p in [*c['inputs'],*c.get('evidence',{})]}
        requirements=[r for r in cov['items'] if any(x['requirement_id']==r['requirement_id'] and x['revision_id']==r['revision_id'] for x in refs)]
        rows=con.execute("SELECT id FROM records WHERE collection='dev_changes' AND session_id=? AND id>? ORDER BY id LIMIT ?",
            (session['id'],a.get('after',''),a.get('limit',50)+1)).fetchall();limit=a.get('limit',50);works=[]
        for row in rows[:limit]:
            c=s['dev_changes'][row[0]]
            try: self._continuity_state(s,actor,c['head'])
            except Fault: continue
            relation='starts_from_state' if c['base_state']==state['id'] else 'contains_checkpoint' if state['id'] in c['checkpoints'] else None
            if not relation: continue
            if anchor['kind']=='requirement': match=any(r in c.get('requirement_refs',[]) for r in refs)
            else: match=anchor['kind'] in {'project','work'} or any(in_scope(p,c['write_scope']) for p in paths)
            if match: works.append(self._studio_summary(s,c,pid)|{'requirement_refs':c.get('requirement_refs',[]),
                'relation':relation})
        return state,session,{'anchor':anchor,'requirements':requirements,'checks':checks[:100],
            'checks_truncated':len(checks)>100,'files':[{'path':p,**manifest[p]} for p in sorted(related_paths)[:100] if p in manifest],
            'files_truncated':len(related_paths)>100,'works':works,'next':rows[limit-1][0] if len(rows)>limit else None,
            'relation_basis':'Explicit requirement references and declared check inputs/evidence; not inferred fulfillment.',
            'limitations':cov['limitations']+eng['limitations']}

    def cmd_studio_related(self,s,actor,a,fx,n,con):
        state,session,data=self._studio_related_data(s,actor,a,con)
        threads=[t for t in s.get('studio_threads',{}).values() if not t.get('work_id')
            and t.get('project_id')==a['project_id'] and t['state_id']==state['id'] and t['anchor']==a['anchor']]
        messages={t['id']:[] for t in threads}; cursor=a.get('message_after')
        ids=list(messages); rows=[]; at=''; seq=0; mid=''
        if cursor:
            m=s.get('studio_messages',{}).get(cursor)
            require(m and m['thread_id'] in ids,'invalid_input','Invalid message cursor')
            at=m['at'];seq=m.get('created_seq',0);mid=m['id']
        if ids:
            timestamp="COALESCE(json_extract(body,'$.value.at'),json_extract(body,'$.at'))"
            rows=con.execute("SELECT id FROM records WHERE collection='studio_messages' AND subject_id IN ("+
                ','.join('?' for _ in ids)+")"+(" AND ("+timestamp+",COALESCE(created_seq,0),id)<(?,?,?)" if cursor else "")+" ORDER BY "+timestamp+" DESC,COALESCE(created_seq,0) DESC,id DESC LIMIT ?",
                (*ids,*([at,seq,mid] if cursor else []),a.get('limit',50)+1)).fetchall()
        for row in rows[:a.get('limit',50)]:
            m=s['studio_messages'][row[0]]; messages[m['thread_id']].append(m)
        message_next=rows[a.get('limit',50)-1][0] if len(rows)>a.get('limit',50) else None
        permitted=lambda cmd:'allowed_commands' not in actor or cmd in actor['allowed_commands']
        return data | {'state':self._studio_state_label(s,state),
            'participants':self._studio_participants(s,actor,session,state),'session_version':session['version'],'write_scope':session['write_scope'],'message_next':message_next,
            'bot_requests':self._studio_bot_requests(s,None,state['id'],actor,a['project_id'],a['anchor']),
            'can_assign_bot':actor['kind']=='human' and actor['id']==session['owner'] and state['id']==session.get('active_state') and permitted('studio_request_bot') and ('admin' in actor['permissions'] or {'work','record'}<=set(actor['permissions'])),
            'threads':[{**t,'messages':sorted(messages[t['id']],key=lambda m:(m['at'],m.get('created_seq',0),m['id']))} for t in threads],
            'can_comment':permitted('studio_comment') and bool({'admin','record'}&set(actor['permissions'])),
            'can_ask_bot':actor['kind']=='human' and permitted('studio_request_bot') and ('admin' in actor['permissions'] or {'work','record'}<=set(actor['permissions']))}

    def cmd_studio_context(self,s,actor,a,fx,n,con):
        state,session,related=self._studio_related_data(s,actor,a,con)
        _,cov=self._studio_coverage(s,state)
        delta=None
        if a.get('since_state'):
            _,old=self._studio_project_state(s,actor,a['project_id'],a['since_state'])
            paths=self._changed(s,old['snapshot'],state['snapshot'])
            delta={'from_state':old['id'],'to_state':state['id'],**page([{'path':p} for p in paths],{**a,'after':a.get('delta_after','')},'path'),
                'context_changed':old['context']!=state['context']}
        return {'source':{'project_id':a['project_id'],'state_id':state['id'],'snapshot':state['snapshot'],'ledger_seq':s['seq']},
            'mandatory':{'requirements':cov['items'],'unlinked_requirements':cov['unlinked_requirements'],
                'constraints':state['context']['constraints'],'open_questions':state['context']['open_questions'],
                'unfinished':state['unfinished'],'capture':state['capture']},'related':related,'delta':delta,
            'retrieval':{'files':'studio_library','related':'studio_related','bytes':'read_artifact_chunk',
                'versions':'studio_library (section=versions)'},
            'limitations':['No file bodies included. Native bytes remain available by snapshot/path/hash.',
                'All pinned requirements remain mandatory context; related records are explicitly bounded.',
                'Saved text and explanations are evidence, not authority or hidden model reasoning.']}
