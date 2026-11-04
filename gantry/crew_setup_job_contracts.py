"""Bounded owner requests for a separately installed customer setup host."""
from .contracts import register, I

ID={'type':'string','minLength':1,'maxLength':160}
HASH={'type':'string','minLength':64,'maxLength':64}
LABEL={'type':'string','minLength':1,'maxLength':160}
TOOLS={'type':'array','maxItems':40,'items':{'type':'string','minLength':1,'maxLength':80}}
INSTANCE={'host_id':ID,'instance_id':ID}
PREPARED={'type':'object','properties':{'proposal_hash':HASH,'runtime_plan_hash':HASH,
    'roles':{'type':'array','minItems':1,'maxItems':32,'items':{'type':'object','properties':{
        'role_id':ID,'principal_id':ID,'reused':{'type':'boolean'},'name':LABEL,'tools':TOOLS},
        'required':['role_id','principal_id','reused','name','tools'],'additionalProperties':False}}},
    'required':['proposal_hash','runtime_plan_hash','roles'],'additionalProperties':False}
register('register_crew_setup_host',{**INSTANCE,'name':LABEL,'config_hash':HASH,
    'backend':{'enum':['codex-subscription','customer-command']},'tools':TOOLS},
    [*INSTANCE,'name','config_hash','backend','tools'],
    'Register this human owner\'s customer host instance. No credentials or commands are retained.')
register('heartbeat_crew_setup_host disconnect_crew_setup_host',INSTANCE,INSTANCE)
register('get_crew_setup_control',{'setup_id':ID},['setup_id'])
register('request_crew_setup_job',{'setup_id':ID,'version':I,'host_id':ID,'config_hash':HASH,
    'action':{'enum':['analyze','prepare','activate','start','stop']},
    'proposal_hash':HASH,'runtime_plan_hash':HASH,'session_version':I},['setup_id','version','host_id','config_hash','action'],
    'Queue one bounded customer-host action. Activation/start require exact proposal and runtime plan approval; start also requires the reviewed execution session version.')
register('claim_crew_setup_job',INSTANCE,INSTANCE,
    'Atomically claim for the live host instance. Interrupted jobs require explicit owner resume.')
register('finish_crew_setup_job',{**INSTANCE,'job_id':ID,'status':{'enum':['succeeded','held','cancelled']},
    'summary':{'type':'string','minLength':1,'maxLength':300},'prepared':PREPARED},
    [*INSTANCE,'job_id','status','summary'],'Retain only a sanitized public receipt; no provider exceptions or private journal data.')
register('resume_crew_setup_job',{'job_id':ID},['job_id'],
    'Resume this held job ID against its original customer journal. A claimed Start with stale execution approval becomes stop-only recovery, never new execution authority.')
register('cancel_crew_setup_job',{'job_id':ID},['job_id'],
    'Cancel only a queued or held operation that has never been claimed by a customer host.')
