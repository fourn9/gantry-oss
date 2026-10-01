"""Explicit-PR job orchestration. No inference or customer process inside Core."""
import copy
from .model import require, uid, Fault
from .development import in_scope
from .contracts import register, S, A, O, validate
from .review_contracts import obj, REVIEW_OUTPUT

POLICY = {'session_id': S, 'version': {'type':'integer','minimum':0}, 'enabled': {'type':'boolean'},
          'max_rounds': {'type':'integer','minimum':1,'maximum':10},
          'max_jobs': {'type':'integer','minimum':1,'maximum':100}, 'developer_principal': S}
register('configure_review_automation', POLICY, list(POLICY))
register('get_review_team', {'session_id': S}, ['session_id'])
register('review_automation_status', {'session_id': S}, ['session_id'])
register('claim_mentor_job', {'job_id': S, 'lease_seconds': {'type':'integer','minimum':10,'maximum':1800}, 'verification_hash':S}, ['job_id','lease_seconds'])
register('check_mentor_job', {'job_id':S,'fence':S}, ['job_id','fence'])
register('finish_mentor_job', {'job_id':S,'fence':S,'output':O,'provider':O}, ['job_id','fence','output','provider'])
register('fail_mentor_job', {'job_id':S,'fence':S,'reason':S}, ['job_id','fence','reason'])
register('recover_mentor_job', {'job_id': S, 'fence': S, 'reason': S,
    'checkpoint_hash': S, 'confirmed_stopped': {'type': 'boolean', 'enum': [True]},
    'retry_inference': {'type': 'boolean'},
    'lease_seconds': {'type': 'integer', 'minimum': 10, 'maximum': 900}},
    ['job_id', 'fence', 'reason', 'checkpoint_hash', 'confirmed_stopped', 'retry_inference', 'lease_seconds'])
SPECIALIST = obj({'summary':S,'evidence':A,'unresolved':A})
DEVELOPER = obj({'edits': {'type':'array','maxItems':100,'items':obj({'path':S,'content':{'type':'string'}})},
                 'summary':S,'hypothesis':S,'rationale':S,'unverified':A})
REFLECTION = obj({'assessment':{'enum':['supported','contradicted','inconclusive']}, 'observation':S,'applicability':S,'limitations':A})
JOB_SCHEMAS = {'specialist':SPECIALIST, 'coordinator':REVIEW_OUTPUT, 'developer':DEVELOPER, 'reflection':REFLECTION}

class MentorJobsMixin:
    def cmd_get_review_team(self,s,actor,a,fx,n,con):
        d=self._dev_session(s,actor,a['session_id'])
        return {'team':copy.deepcopy(s.get('review_teams',{}).get(d['id'])), 'session':d}

    def cmd_configure_review_automation(self,s,actor,a,fx,n,con):
        d=self._dev_session(s,actor,a['session_id']);self._dev_human(actor,d)
        team=self._review_team(s,actor,d['id'])
        old=s.get('review_automation',{}).get(d['id'],{})
        require(a['version']==old.get('version',0),'stale_basis','Automation policy changed')
        require(any(m['principal_id']==a['developer_principal'] and m['side']=='user' for m in team['members']),
                'unauthorized','Developer must be a delegated user-side agent')
        policy=dict(a,id=d['id'],version=a['version']+1,team_version=team['version'],used_jobs=old.get('used_jobs',0))
        self._dev_save(s,fx,'review_automation',policy)
        # Opt-in also picks up already submitted, still-current pending PRs.
        if policy['enabled']:
            for r in list(s.get('change_reviews',{}).values()):
                if r['session_id']==d['id'] and r['status']=='pending':
                    try:self._review_current(s,r,team)
                    except Fault:continue
                    self._enqueue_review_jobs(s,fx,r)
        return policy

    def _job(self,s,fx,r,kind,role,principal,round_number):
        key=r['id']+':'+kind+':'+role
        if key in s.get('mentor_jobs',{}):return
        self._dev_save(s,fx,'mentor_jobs',dict(id=key,session_id=r['session_id'],submission_id=r['id'],
            kind=kind,role=role,principal_id=principal,status='pending',round=round_number,created_at=self.clock()))

    def _enqueue_review_jobs(self,s,fx,r):
        p=s.get('review_automation',{}).get(r['session_id'])
        if not p or not p['enabled']:return
        t=s['review_teams'][r['session_id']]; round_number=r.get('automation_round',0)
        for role in r['required_roles']:
            self._job(s,fx,r,'specialist',role,next(m['principal_id'] for m in t['members'] if m['role']==role),round_number)
        self._job(s,fx,r,'coordinator',t['coordinator'],next(m['principal_id'] for m in t['members'] if m['role']==t['coordinator']),round_number)

    def cmd_review_automation_status(self,s,actor,a,fx,n,con):
        self._dev_session(s,actor,a['session_id'])
        rows=con.execute('SELECT id FROM records WHERE collection=? AND session_id=? ORDER BY id LIMIT 501',('mentor_jobs',a['session_id'])).fetchall()
        jobs=[]
        for row in rows[:500]:
            j=self._dev_get(s,'mentor_jobs',row[0]);j.pop('fence',None);j.pop('review_fence',None);j.pop('context',None)
            now=self.clock()
            j['timing_ms']={'queue':max(0,j.get('started_at',now)-j['created_at']),
                'execution':max(0,j.get('finished_at',now)-j['started_at']) if 'started_at' in j else None,
                'total':max(0,j.get('finished_at',now)-j['created_at'])}
            if j['status']=='running' and j.get('lease_until',0)<=now:
                j['status']='interrupted';j['error']='Lease expired; inspect saved output before resuming'
            jobs.append(j)
        return {'policy':copy.deepcopy(s.get('review_automation',{}).get(a['session_id'])), 'jobs':jobs,'truncated':len(rows)>500}

    def _job_current(self,s,actor,j):
        r,t=self._review_access(s,actor,j['submission_id']);p=s.get('review_automation',{}).get(j['session_id'],{})
        require(p.get('enabled') and p['team_version']==t['version'],'mode_disabled','Automation disabled or team changed')
        require(actor['id']==j['principal_id'],'unauthorized','Job belongs to another principal')
        d=self._dev_session(s,actor,j['session_id'])
        require(d['mode']!='record','mode_disabled','Record-only session')
        if j['kind']!='reflection': self._review_current(s,r,t)
        if j['kind']=='developer':
            self._member(t,actor,'user');self.allowed(actor,'work');self.allowed(actor,'record')
            require(d['mode']=='execute' and p['developer_principal']==actor['id'],'mode_disabled','Developer execution not delegated')
            require(s['dev_changes'][r['change_id']]['assignee']==actor['id'],'unauthorized','Wrong change assignee')
        else:self._member(t,actor,'gantry',j['role']);self.allowed(actor,'propose')
        return r,t,p,d

    def cmd_claim_mentor_job(self,s,actor,a,fx,n,con):
        j=self._dev_get(s,'mentor_jobs',a['job_id']);r,t,p,d=self._job_current(s,actor,j)
        require(j['status']=='pending','conflict','Job is already claimed or terminal; uncertain jobs are not automatically rerun')
        require(p['used_jobs']<p['max_jobs'],'budget_exhausted','Subscription job limit reached')
        if j['kind']=='developer':
            require(not self._engineering_check(s,r)['input_mismatches'], 'stale_basis', 'Engineering input bindings need reconciliation')
            require(d['used_executions']<d['max_executions'],'budget_exhausted','Execution limit reached')
            active=[x for x in s.get('mentor_jobs',{}).values() if x['session_id']==d['id'] and x['kind']=='developer' and x['status']=='running']
            active += [x for x in s.get('dev_executions',{}).values() if x['session_id']==d['id'] and x['status'] in {'running','cancelling'}]
            require(len(active)<d['max_parallel'],'resource_unavailable','Execution slots occupied')
            scope=s['dev_changes'][r['change_id']]['write_scope']
            for x in active:
                other=x.get('write_scope', s.get('dev_contracts',{}).get(x.get('contract_id'),{}).get('write_scope',[]))
                require(not any(in_scope(path,other) or in_scope(q,scope) for path in scope for q in other),'conflict','Active write scope overlap')
            reasons=self._automation_execution_reasons(s,actor,d,{'review_submission':r['id'],'write_scope':scope})
            require(not reasons,'execution_blocked','Project execution conditions not satisfied', reasons=reasons)
            if a.get('verification_hash'):
                require(a['verification_hash'] in d['recipes'].values(),'recipe_not_allowed','Verification command not delegated')
            j.update(write_scope=scope,verification_hash=a.get('verification_hash'),execution_policy_version=d['version'])
            d['used_executions']+=1;self._dev_save(s,fx,'dev_sessions',d)
        if j['kind']=='specialist':
            children={m['role'] for m in t['members'] if m.get('parent_role')==j['role']} & set(r['required_roles'])
            require(children<=set(r['specialists']),'review_pending','Waiting for subordinate reports')
        if j['kind']=='coordinator':
            require(set(r['required_roles'])<=set(r['specialists']),'review_pending','Waiting for specialist reports')
            claimed=self.cmd_claim_change_review(s,actor,{'submission_id':r['id'],'lease_seconds':min(a['lease_seconds'],900)},fx,n,con)
            j['review_fence']=claimed['fence']
        context=self.cmd_get_change_review(s,actor,{'submission_id':r['id']},fx,n,con)
        context['change']=self._dev_get(s,'dev_changes',r['change_id'])
        context['write_scope']=d['write_scope']
        if hasattr(self,'cmd_related_review_context'):
            context['related']=self.cmd_related_review_context(s,actor,{'submission_id':r['id']},fx,n,con)
        if j['kind']=='reflection':
            context['response']=self._dev_get(s,'review_responses',j['response_id'])
            context['returned_development']=self.cmd_get_development_state(s,actor,{'state_id':context['response']['state_id']},fx,n,con)
            context['returned_observations']=[{'job_id':x['id'],'provider':x.get('provider',{})} for x in s.get('mentor_jobs',{}).values()
                if x['kind']=='developer' and x['status']=='completed' and x.get('result',{}).get('response_id')==j['response_id']]
        j.update(status='running',fence=uid('joblease'),lease_until=self.clock()+a['lease_seconds']*1000,
                 policy_version=p['version'],context=context,started_at=self.clock())
        p=copy.deepcopy(p);p['used_jobs']+=1;self._dev_save(s,fx,'review_automation',p)
        return self._dev_save(s,fx,'mentor_jobs',j)

    def _owned_job(self,s,actor,a):
        j=self._dev_get(s,'mentor_jobs',a['job_id'])
        require(j['principal_id']==actor['id'] and j.get('fence')==a['fence'],'unauthorized','Job fence mismatch')
        require(j['status']=='running','conflict','Job already terminal')
        return j

    def cmd_check_mentor_job(self,s,actor,a,fx,n,con):
        j=self._owned_job(s,actor,a);r,t,p,d=self._job_current(s,actor,j)
        require(self.clock()<j['lease_until'] and p['version']==j['policy_version'],'stale_basis','Job lease/policy changed')
        if j['kind']=='developer':
            require(d['version']==j['execution_policy_version'],'stale_basis','Execution policy changed')
            if j.get('verification_hash'):require(j['verification_hash'] in d['recipes'].values(),'recipe_not_allowed','Verification permission revoked')
        return {'allowed':True,'job_id':j['id']}

    def cmd_recover_mentor_job(self, s, actor, a, fx, n, con):
        """Fence an explicitly stopped worker; retain context, reports and prior attempts.

        Local process/receipt reconciliation precedes this command. A new model
        attempt consumes allowance; returning already saved output does not.
        No new identity, scope, execution recipe or acceptance is authorized here.
        """
        j = self._dev_get(s, 'mentor_jobs', a['job_id'])
        require(j['principal_id'] == actor['id'] and j.get('fence') == a['fence'],
                'unauthorized', 'Recovery belongs to the original worker identity and fence')
        require(j['status'] in {'running', 'failed'}, 'conflict', 'Job is not recoverable')
        r, t, p, d = self._job_current(s, actor, j)
        require(p['version'] == j['policy_version'], 'stale_basis', 'Automation policy changed; resubmit')
        require(len(a['checkpoint_hash']) == 64 and all(c in '0123456789abcdef' for c in a['checkpoint_hash']),
                'invalid_input', 'Checkpoint SHA-256 required')
        require(j['context']['context_fingerprint'] == self._review_fingerprint(s, r),
                'stale_basis', 'Review evidence changed; resubmit instead of reusing an old answer')
        if j['kind'] == 'developer':
            require(d['version'] == j['execution_policy_version'], 'stale_basis', 'Execution delegation changed')
            require(not self._engineering_check(s, r)['input_mismatches'], 'stale_basis', 'Engineering inputs changed')
            if j.get('verification_hash'):
                require(j['verification_hash'] in d['recipes'].values(), 'recipe_not_allowed', 'Verification revoked')
            active = [x for x in s.get('mentor_jobs', {}).values() if x['id'] != j['id']
                      and x['session_id'] == d['id'] and x['kind'] == 'developer' and x['status'] == 'running']
            active += [x for x in s.get('dev_executions', {}).values()
                       if x['session_id'] == d['id'] and x['status'] in {'running', 'cancelling'}]
            require(len(active) < d['max_parallel'], 'resource_unavailable', 'Execution slots occupied')
            for x in active:
                other = x.get('write_scope', s.get('dev_contracts', {}).get(x.get('contract_id'), {}).get('write_scope', []))
                require(not any(in_scope(path, other) or in_scope(q, j['write_scope'])
                        for path in j['write_scope'] for q in other), 'conflict', 'Active write scope overlap')
            reasons = self._automation_execution_reasons(s, actor, d,
                {'review_submission': r['id'], 'write_scope': j['write_scope']})
            # Resuming the same reserved execution does not create another run.
            reasons = [reason for reason in reasons if reason != 'project_execution_budget']
            require(not reasons, 'execution_blocked', 'Project conditions changed', reasons=reasons)
        if a['retry_inference']:
            require(p['used_jobs'] < p['max_jobs'], 'budget_exhausted', 'No inference retry allowance')
            p = copy.deepcopy(p); p['used_jobs'] += 1
            self._dev_save(s, fx, 'review_automation', p)
        if j['kind'] == 'coordinator':
            require(r['status'] != 'completed', 'conflict', 'Review already completed')
            require(not r.get('fence') or r['fence'] == j.get('review_fence'),
                    'conflict', 'Another coordinator owns the review')
            r.update(status='running', reviewer=actor['id'], fence=uid('fence'),
                     lease_until=self.clock() + a['lease_seconds'] * 1000)
            r.pop('error', None)
            j['review_fence'] = r['fence']
            self._dev_save(s, fx, 'change_reviews', r)
        j.setdefault('recoveries', []).append({'at': self.clock(), 'actor_id': actor['id'],
            'previous_status': j['status'], 'previous_error': j.get('error'),
            'checkpoint_hash': a['checkpoint_hash'], 'reason': a['reason'],
            'retry_inference': a['retry_inference']})
        j.update(status='running', fence=uid('joblease'), lease_until=self.clock() + a['lease_seconds'] * 1000)
        j.pop('error', None); j.pop('finished_at', None)
        return self._dev_save(s, fx, 'mentor_jobs', j)

    def cmd_fail_mentor_job(self,s,actor,a,fx,n,con):
        j=self._owned_job(s,actor,a);self._dev_session(s,actor,j['session_id'])
        j.update(status='failed',error=a['reason'][:1000],finished_at=self.clock())
        if j['kind']=='coordinator':
            r=self._dev_get(s,'change_reviews',j['submission_id'])
            if r.get('fence')==j.get('review_fence') and r['status']=='running':
                r.update(status='failed',error=j['error'],failed_at=self.clock(),lease_until=0)
                r.pop('fence',None)
                self._dev_save(s,fx,'change_reviews',r)
        return self._dev_save(s,fx,'mentor_jobs',j)

    def cmd_finish_mentor_job(self,s,actor,a,fx,n,con):
        self.cmd_check_mentor_job(s,actor,{'job_id':a['job_id'],'fence':a['fence']},fx,n,con)
        j=self._owned_job(s,actor,a);r,t,p,d=self._job_current(s,actor,j)
        require(self.clock()<j['lease_until'] and p['version']==j['policy_version'],'stale_basis','Job lease or policy changed')
        output=copy.deepcopy(a['output'])
        schema=JOB_SCHEMAS[j['kind']]
        if j['kind']=='developer':
            # Customer worker applies edits to isolated restored state and returns captured bytes.
            schema=obj({'snapshot':S,'summary':S,'hypothesis':S,'rationale':S,'unverified':A,'capture':O})
        validate(output,schema)
        if j['kind']=='specialist':
            result=self.cmd_submit_specialist_review(s,actor,{'submission_id':r['id'],'role':j['role'],**output},fx,n,con)
        elif j['kind']=='coordinator':
            result=self.cmd_complete_change_review(s,actor,{'submission_id':r['id'],'fence':j['review_fence'],
                'context_fingerprint':j['context']['context_fingerprint'],'output':output},fx,n,con)
            if output['verdict']=='changes_requested' and j['round']<p['max_rounds']:
                self._job(s,fx,r,'developer','developer',p['developer_principal'],j['round'])
        elif j['kind']=='developer':
            change=self._dev_get(s,'dev_changes',r['change_id'])
            changed=self._changed(s,s['dev_states'][r['state_id']]['snapshot'],output['snapshot'])
            require(all(in_scope(path,d['write_scope']) and in_scope(path,change['write_scope']) for path in changed),
                    'scope_denied','Output exceeds delegated edit scope')
            checkpoint=self.cmd_checkpoint_change(s,actor,{'change_id':change['id'],'version':change['version'],
                'snapshot':output['snapshot'],'summary':output['summary'],'rationale':output['rationale'],
                'unfinished':output['unverified'],'work_status':'paused','capture':output['capture'],
                'engineering_review':r['id']},fx,n,con)
            response=self.cmd_respond_to_change_review(s,actor,{'submission_id':r['id'],'candidate_state':checkpoint['state']['id'],
                'responses':[{'finding_id':f['id'],'explanation':output['summary']} for f in r['output']['findings']]},fx,n,con)
            new=self.cmd_submit_change_review(s,actor,{'change_id':change['id'],'version':checkpoint['change']['version'],
                'question':r['question'],'stage':r['stage'],'acceptance':r['acceptance'],'required_roles':r['required_roles']},fx,n,con)
            new['automation_round']=j['round']+1;self._dev_save(s,fx,'change_reviews',new)
            # Submit hook already inserted jobs; correct their round in this same transaction.
            for job in list(s.get('mentor_jobs',{}).values()):
                if job['submission_id']==new['id']:
                    job=copy.deepcopy(job);job['round']=new['automation_round'];self._dev_save(s,fx,'mentor_jobs',job)
            coordinator=next(m['principal_id'] for m in t['members'] if m['role']==t['coordinator'])
            self._job(s,fx,r,'reflection',t['coordinator'],coordinator,j['round'])
            reflection=copy.deepcopy(s['mentor_jobs'][r['id']+':reflection:'+t['coordinator']]);reflection['response_id']=response['id']
            self._dev_save(s,fx,'mentor_jobs',reflection)
            result={'candidate':checkpoint['state']['id'],'response_id':response['id'],'resubmission_id':new['id']}
        else:
            result=self.cmd_reflect_change_review(s,actor,{'submission_id':r['id'],'response_id':j['response_id'],**output},fx,n,con)
        j.update(status='completed',output=output,provider=a['provider'],result=result,finished_at=self.clock())
        self._dev_save(s,fx,'mentor_jobs',j)
        return {'job_id':j['id'],'status':'completed','result':result}
