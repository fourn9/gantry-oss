"""Transactional control records only; all inference and processes run on the host."""
import copy
import re
from . import crew_setup_job_contracts  # register the strict public boundary
from .connection_policy import clean_bytes
from .model import Fault, canonical, digest, identifier, require, uid

LEASE_MS=60000
NONTERMINAL={'queued','running','held'}
HOST_FIELDS=('id','name','backend','tools','config_hash','instance_id','lease_until')
JOB_FIELDS=('id','setup_id','host_id','config_hash','action','status','version','summary',
            'proposal_hash','runtime_plan_hash','session_version','prepared','instance_id','claim_count','created_at','recovery_only')
PRIVATE_TEXT=re.compile(r'(?i)traceback|authorization\s*:|\bbearer\s+\S+|'
    r'\b(?:password|secret|token|api[_-]?key)\s*[:=]|/(?:Users|home|private|tmp)/|[a-z]:[\\/]')


def public_text(value):
    clean_bytes(value.encode())
    require(value.strip() and not PRIVATE_TEXT.search(value) and not any(ord(c)<32 for c in value),
            'credential_detected','Only a public setup summary or label may be retained')


def hash_value(value):
    require(isinstance(value,str) and re.fullmatch('[a-f0-9]{64}',value),
            'invalid_input','A SHA-256 digest is required')


class CrewSetupJobsMixin:
    def _setup_owner(self,s,actor,setup_id):
        setup,session=self._crew_setup(s,actor,{'setup_id':setup_id})
        require(actor['kind']=='human' and actor['id']==session['owner']==setup['owner'],
                'unauthorized','Setup control belongs to its human owner')
        self.allowed(actor,'work')
        return setup,session

    def _setup_host(self,s,actor,host_id,instance_id=None,online=False):
        host=self._dev_get(s,'crew_setup_hosts',host_id)
        require(actor['kind']=='human' and host['owner']==actor['id'],
                'unauthorized','Customer host belongs to another owner')
        self.allowed(actor,'work')
        if instance_id is not None:
            require(host['instance_id']==instance_id,'unauthorized','Customer host instance was replaced')
        if online:require(host['lease_until']>self.clock(),'runtime_unavailable','Customer host is offline')
        return host

    def _host_view(self,host):
        return {**{k:copy.deepcopy(host[k]) for k in HOST_FIELDS},'online':host['lease_until']>self.clock()}

    @staticmethod
    def _job_view(job):
        return {k:copy.deepcopy(job[k]) for k in JOB_FIELDS if k in job}

    def _save_setup_job(self,s,fx,job):
        self._dev_save(s,fx,'crew_setup_jobs',job)
        return self._job_view(job)

    @staticmethod
    def _setup_jobs(s,setup_id=None,host_id=None):
        return [copy.deepcopy(j) for j in s.get('crew_setup_jobs',{}).values()
                if (setup_id is None or j['setup_id']==setup_id) and (host_id is None or j['host_id']==host_id)]

    def cmd_register_crew_setup_host(self,s,actor,a,fx,n,con):
        self._dev_human(actor);self.allowed(actor,'record')
        identifier(a['host_id']);identifier(a['instance_id']);hash_value(a['config_hash']);public_text(a['name'])
        public_text(a['host_id']);public_text(a['instance_id'])
        for tool in a['tools']:identifier(tool);public_text(tool)
        require(len(set(a['tools']))==len(a['tools']),'invalid_input','Duplicate tool label')
        old=s.get('crew_setup_hosts',{}).get(a['host_id'])
        if old:
            old=self._setup_host(s,actor,a['host_id'])
            require(old['instance_id']==a['instance_id'] or old['lease_until']<=self.clock(),
                    'conflict','Another customer host instance still has a live lease')
            require(old['config_hash']!=a['config_hash'] or all(old[k]==a[k] for k in ('backend','tools')),
                    'conflict','A configuration digest cannot describe different customer capabilities')
            active=[j for j in self._setup_jobs(s,host_id=old['id']) if j['status'] in NONTERMINAL]
            require(not active or all(old[k]==a[k] for k in ('config_hash','backend','tools')),
                    'conflict','Preserve the host configuration while setup work is unresolved')
            if old['instance_id']!=a['instance_id']:
                for job in active:
                    if job['status']=='running':
                        job.update(status='held',summary='Customer host restarted. Resume to reconcile the saved local journal.')
                        self._save_setup_job(s,fx,job)
        else:
            require(sum(h['owner']==actor['id'] for h in s.get('crew_setup_hosts',{}).values())<32,
                    'resource_unavailable','Customer host registration limit reached')
        host={'id':a['host_id'],'owner':actor['id'],**{k:copy.deepcopy(a[k]) for k in
              ('instance_id','name','config_hash','backend','tools')},'lease_until':self.clock()+LEASE_MS}
        self._dev_save(s,fx,'crew_setup_hosts',host)
        return self._host_view(host)

    def cmd_heartbeat_crew_setup_host(self,s,actor,a,fx,n,con):
        host=self._setup_host(s,actor,a['host_id'],a['instance_id'])
        host['lease_until']=self.clock()+LEASE_MS
        self._dev_save(s,fx,'crew_setup_hosts',host)
        return self._host_view(host)

    def cmd_disconnect_crew_setup_host(self,s,actor,a,fx,n,con):
        host=self._setup_host(s,actor,a['host_id'],a['instance_id'])
        host['lease_until']=0
        self._dev_save(s,fx,'crew_setup_hosts',host)
        return self._host_view(host)

    def _prepared_setup(self,s,setup,host=None):
        if not setup['result']:
            session=s['dev_sessions'][setup['session_id']];state=s['dev_states'][setup['state_id']]
            if setup['inputs']!=self._crew_setup_inputs(s,session,state,setup['organization_id']):return None
        candidates=[j for j in self._setup_jobs(s,setup['id']) if j['status']=='succeeded' and j.get('prepared')
                    and setup.get('proposal') and j['prepared']['proposal_hash']==setup['proposal']['hash']
                    and (setup['result'] or j['result_version']==setup['version'])]
        candidates.sort(key=lambda j:j['created_seq'],reverse=True)
        for job in candidates:
            if setup['result']:
                expected=job['result_version']+1+bool(setup['result'].get('first_task_id'))
                if setup['version']!=expected:continue
                if {r['role_id']:r['principal_id'] for r in setup['result']['roles']}!={
                        r['role_id']:r['principal_id'] for r in job['prepared']['roles']}:continue
            h=s.get('crew_setup_hosts',{}).get(job['host_id'])
            if h and h['config_hash']==job['config_hash'] and (not host or host['id']==h['id']):
                return copy.deepcopy(job['prepared'])
        return None

    def cmd_get_crew_setup_control(self,s,actor,a,fx,n,con):
        setup,_=self._setup_owner(s,actor,a['setup_id'])
        hosts=[self._host_view(h) for h in s.get('crew_setup_hosts',{}).values() if h['owner']==actor['id']]
        jobs=sorted(self._setup_jobs(s,setup['id']),key=lambda j:j['created_seq'],reverse=True)
        return {'hosts':hosts,'jobs':[self._job_view(j) for j in jobs[:20]],'prepared':self._prepared_setup(s,setup)}

    def _check_setup_job(self,s,actor,job,after_started=False):
        setup,session=self._setup_owner(s,actor,job['setup_id'])
        host=self._setup_host(s,actor,job['host_id'])
        require(host['config_hash']==job['config_hash'],'stale_basis','Customer host configuration changed')
        if job.get('recovery_only'):
            require(job['action']=='start' and job['claim_count']>0 and setup['status']=='activated'
                    and setup['result'] and setup['session_id']==job['session_id'],
                    'scope_denied','Stop-only recovery must preserve the activated setup identity')
            return setup,session,host
        versions={job['version']}
        if after_started and job['action'] in {'analyze','activate','start'}:versions.add(job['version']+1)
        require(setup['version'] in versions and setup['basis']==job['input_basis'],
                'stale_basis','Setup changed; review its current state')
        if not setup['result']:self._check_crew_setup_basis(s,setup,session)
        if job.get('proposal_hash'):
            require(setup.get('proposal') and setup['proposal']['hash']==job['proposal_hash'],
                    'stale_basis','Reviewed proposal changed')
        action=job['action']
        if action=='start':
            require('session_version' in job,'invalid_input','Approve the exact execution session version')
            require(session['version']==job['session_version'],'stale_basis','Project execution delegation changed')
        if action=='analyze':
            require(not setup['result'],'invalid_state','Team is already activated')
            require(setup['status']=='draft' or (after_started and setup['version']==job['version']+1),
                    'stale_basis','Analysis must begin from the saved draft setup')
        elif action=='prepare':
            require(setup['status']=='proposed','invalid_state','Prepare a reviewed proposal before activation')
        elif action in {'activate','start'}:
            prepared=self._prepared_setup(s,setup,host)
            require(prepared and prepared['runtime_plan_hash']==job['runtime_plan_hash'],
                    'stale_basis','Reviewed runtime preparation changed')
            if action=='activate':
                require(setup['status']=='proposed' or (after_started and setup['status']=='activated'),
                        'invalid_state','Review the team before activation')
            else:
                require(setup['status']=='activated','invalid_state','Activate the team before starting workers')
                require(session['mode']=='execute','mode_disabled','Enable project execution before starting workers')
        elif action=='stop':require(setup['result'],'invalid_state','No activated team to stop')
        return setup,session,host

    def cmd_request_crew_setup_job(self,s,actor,a,fx,n,con):
        setup,_=self._setup_owner(s,actor,a['setup_id']);self.allowed(actor,'record')
        host=self._setup_host(s,actor,a['host_id'])
        require(host['config_hash']==a['config_hash'],'stale_basis','Customer host configuration changed')
        for key in ('config_hash','proposal_hash','runtime_plan_hash'):
            if key in a:hash_value(a[key])
        intent={k:a[k] for k in ('setup_id','version','host_id','config_hash','action','proposal_hash','runtime_plan_hash','session_version') if k in a}
        if a['action'] in {'start','stop'}:intent['requested_instance_id']=host['instance_id']
        fingerprint=digest(intent);jobs=sorted(self._setup_jobs(s,setup['id']),key=lambda j:j['created_seq'])
        active=[copy.deepcopy(j) for j in s.get('crew_setup_jobs',{}).values() if j['status'] in NONTERMINAL
                and (j['setup_id']==setup['id'] or j['host_id']==host['id'])]
        for job in active:
            if job['request_hash']==fingerprint:return self._job_view(job)
        require(not active,'conflict','Resolve the existing setup operation before requesting another')
        # Restart after Stop or a host-instance replacement is a new bounded
        # worker lifecycle. Old request keys still replay exactly in Service.
        opposite={'start':'stop','stop':'start'}.get(a['action'])
        last_opposite=max((j['created_seq'] for j in jobs if j['action']==opposite and j['status']=='succeeded'),default=-1)
        offline_workers=a['action']=='start' and setup['result'] and any(
            self._studio_presence(s,r['bot_id'])['presence']=='offline' for r in setup['result']['roles'])
        for job in reversed(jobs):
            if not offline_workers and job['status']=='succeeded' and job['request_hash']==fingerprint and job['created_seq']>last_opposite:
                return self._job_view(job)
        require(setup['version']==a['version'],'stale_basis','Team setup changed; review the current proposal')
        require(host['lease_until']>self.clock(),'runtime_unavailable','Customer host is offline')
        if a['action'] in {'activate','start'}:
            require('proposal_hash' in a and 'runtime_plan_hash' in a,'invalid_input','Approve both exact preparation hashes')
        job={'id':uid('crewjob'),'owner':actor['id'],'session_id':setup['session_id'],**intent,
             'request_hash':fingerprint,'input_basis':setup['basis'],'status':'queued','summary':'Waiting for customer host.',
             'claim_count':0,'created_at':self.clock(),'created_seq':s['seq']+1}
        if a['action']=='prepare' and setup.get('proposal'):job.setdefault('proposal_hash',setup['proposal']['hash'])
        self._check_setup_job(s,actor,job)
        require(sum(j['owner']==actor['id'] and j['status'] in NONTERMINAL for j in s.get('crew_setup_jobs',{}).values())<32,
                'resource_unavailable','Resolve existing setup jobs before queuing more')
        return self._save_setup_job(s,fx,job)

    def cmd_claim_crew_setup_job(self,s,actor,a,fx,n,con):
        host=self._setup_host(s,actor,a['host_id'],a['instance_id'],online=True)
        jobs=sorted(self._setup_jobs(s,host_id=host['id']),key=lambda j:j['created_seq'])
        for job in jobs:
            if job['status']=='running':
                require(job['instance_id']==a['instance_id'],'conflict','Interrupted work requires explicit resume')
                return {'job':self._job_view(job)}
        for job in jobs:
            if job['status']!='queued':continue
            try:self._check_setup_job(s,actor,job,after_started=job['claim_count']>0)
            except Fault:
                job.update(status='held',summary='Setup inputs changed. Review the saved setup before continuing.')
                self._save_setup_job(s,fx,job)
                continue
            job.update(status='running',instance_id=a['instance_id'],claim_count=job['claim_count']+1,
                       summary='Customer host is processing this setup operation.')
            return {'job':self._save_setup_job(s,fx,job)}
        return {'job':None}

    def _setup_prepared_receipt(self,s,setup,host,job,prepared):
        for name in ('proposal_hash','runtime_plan_hash'):hash_value(prepared[name])
        require(setup.get('proposal') and prepared['proposal_hash']==setup['proposal']['hash'],
                'stale_basis','Preparation differs from the current proposal')
        roles={r['role_id']:r for r in setup['proposal']['content']['roles']}
        received=prepared['roles']
        require(len(received)==len(roles) and {r['role_id'] for r in received}==set(roles)
                and len({r['principal_id'] for r in received})==len(received),
                'invalid_input','Preparation must map every role to one distinct principal')
        for role in received:
            original=roles[role['role_id']];identifier(role['principal_id']);public_text(role['name'])
            principal=s['principals'].get(role['principal_id'])
            require(not principal or (principal.get('enabled',True) and principal['kind']=='agent'
                    and 'admin' not in principal['permissions']),
                    'scope_denied','Prepared workers require dedicated enabled agent principals')
            require(role['reused']==bool(original['existing_bot_id']),
                    'stale_basis','Preparation role differs from the reviewed proposal')
            for tool in role['tools']:identifier(tool);public_text(tool)
            require(len(set(role['tools']))==len(role['tools']) and set(role['tools'])<=set(host['tools']),
                    'scope_denied','Preparation tools exceed the registered customer configuration')
        clean_bytes(canonical(prepared).encode())
        return {**copy.deepcopy(prepared),'job_id':job['id'],'host_id':host['id'],'config_hash':host['config_hash']}

    def cmd_finish_crew_setup_job(self,s,actor,a,fx,n,con):
        host=self._setup_host(s,actor,a['host_id'],a['instance_id'],online=True)
        job=self._dev_get(s,'crew_setup_jobs',a['job_id'])
        require(job['owner']==actor['id'] and job['host_id']==host['id'] and job.get('instance_id')==a['instance_id'],
                'unauthorized','Setup job belongs to another host instance')
        self._setup_owner(s,actor,job['setup_id']);public_text(a['summary'])
        require(job['status']=='running','conflict','Only a claimed setup operation can finish')
        require(not job.get('recovery_only') or a['status'] in {'held','cancelled'},
                'invalid_input','Stop-only recovery cannot report successful execution')
        if a['status']=='cancelled':
            require(job.get('recovery_only') and job['action']=='start','invalid_input',
                    'Only stop-only Start recovery may cancel a claimed operation')
            setup,_,_=self._check_setup_job(s,actor,job,after_started=True)
            require(all(s.get('bot_runtimes',{}).get(role['bot_id'],{}).get('lease_until',0)<=self.clock()
                        for role in setup['result']['roles']),
                    'runtime_unavailable','Stop or fence every activated runtime before closing recovery')
        require('prepared' not in a or (a['status']=='succeeded' and job['action'] in {'analyze','prepare'}),
                'invalid_input','Preparation receipts belong only to successful analysis or preparation')
        if a['status']=='succeeded':
            setup,_,_=self._check_setup_job(s,actor,job,after_started=True)
            if job['action'] in {'analyze','prepare'}:
                require('prepared' in a,'invalid_input','Successful preparation needs its public receipt')
                job['prepared']=self._setup_prepared_receipt(s,setup,host,job,a['prepared'])
                job['result_version']=setup['version']
            if job['action'] in {'activate','start'}:
                require(setup['result'],'invalid_state','Activation has not been recorded')
                prepared=self._prepared_setup(s,setup,host)
                require({r['role_id']:r['principal_id'] for r in setup['result']['roles']}==
                        {r['role_id']:r['principal_id'] for r in prepared['roles']},
                        'stale_basis','Activated principals differ from the approved preparation')
                if job['action']=='start':require(setup['result'].get('first_task_id'),'invalid_state','First task has not been recorded')
        job.update(status=a['status'],summary=a['summary'])
        return self._save_setup_job(s,fx,job)

    def cmd_resume_crew_setup_job(self,s,actor,a,fx,n,con):
        job=self._dev_get(s,'crew_setup_jobs',a['job_id'])
        _,session=self._setup_owner(s,actor,job['setup_id'])
        require(job['status']=='held','conflict','Only a held operation can be resumed')
        if job['action']=='start' and job['claim_count']>0 and session['version']!=job.get('session_version'):
            job['recovery_only']=True
        self._check_setup_job(s,actor,job,after_started=job['claim_count']>0)
        self._setup_host(s,actor,job['host_id'],online=True)
        job.update(status='queued',summary=('Waiting to stop and reconcile the previous customer workers.'
                   if job.get('recovery_only') else 'Waiting to reconcile the saved customer journal.'))
        return self._save_setup_job(s,fx,job)

    def cmd_cancel_crew_setup_job(self,s,actor,a,fx,n,con):
        job=self._dev_get(s,'crew_setup_jobs',a['job_id'])
        self._setup_owner(s,actor,job['setup_id'])
        if job['status']=='cancelled':return self._job_view(job)
        require(job['claim_count']==0 and job['status'] in {'queued','held'},
                'conflict','Claimed customer work must be reconciled through its original journal')
        job.update(status='cancelled',summary='Owner cancelled this operation before the customer host claimed it.')
        return self._save_setup_job(s,fx,job)
