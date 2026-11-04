"""Evidence-driven initial Crew setup; inference never grants authority."""
from .contracts import register, S, I, A
from .onboarding_contracts import FILES, TEXT, SHORT
from .review_contracts import BOT_PROFILE
from .membership import REQUEST

ROLE = {'type':'object','properties':{
    'role_id':SHORT,'name':SHORT,'parent_role_id':{'type':['string','null']},
    'existing_bot_id':{'type':['string','null']},'profile':BOT_PROFILE,
    'write_scope':A,'can_assign':{'type':'boolean'},'can_integrate':{'type':'boolean'},
    'rationale':TEXT,'evidence_ids':{'type':'array','minItems':1,'maxItems':30,'items':S}},
    'required':['role_id','name','parent_role_id','existing_bot_id','profile','write_scope','can_assign','can_integrate','rationale','evidence_ids'],
    'additionalProperties':False}
PROPOSAL = {'type':'object','properties':{
    'organization_profile':BOT_PROFILE,'goal':TEXT,'acceptance':{'type':'array','minItems':1,'maxItems':30,'items':TEXT},
    'lead_role_id':SHORT,'roles':{'type':'array','minItems':1,'maxItems':32,'items':ROLE},
    'unknowns':{'type':'array','maxItems':30,'items':TEXT},
    'first_task':{'type':'object','properties':{'title':SHORT,'completion':{'type':'array','minItems':1,'maxItems':30,'items':TEXT}},
                  'required':['title','completion'],'additionalProperties':False}},
    'required':['organization_profile','goal','acceptance','lead_role_id','roles','unknowns','first_task'],
    'additionalProperties':False}
SOURCE = {'type':'object','properties':{'path':S,'provider':{'enum':['generic','notion','linear','jira','spreadsheet']}},
          'required':['path','provider'],'additionalProperties':False}
BINDING = {'type':'object','properties':{'role_id':S,'principal_id':S,'request':REQUEST},
           'required':['role_id','principal_id'],'additionalProperties':False}
REF = {'setup_id':S,'version':I}
register('start_crew_setup',{'session_id':S,'state_id':S,'organization_id':S,'organization_name':SHORT,
    'notes':{'type':'string','maxLength':12000},'files':FILES,
    'sources':{'type':'array','maxItems':30,'items':SOURCE}},
    ['session_id','state_id','organization_name','notes','files','sources'],
    'Owner selects organizational exports; preserve originals separately from project files. Never execute or grant authority.')
register('get_crew_setup',{'setup_id':S},['setup_id'])
register('list_crew_setups',{'session_id':S},['session_id'])
register('propose_crew_setup',{**REF,'input_basis':S,'proposal':PROPOSAL},[*REF,'input_basis','proposal'],
    'Propose sourced organization/roles using the frozen project and organization evidence. No permission grants.')
register('activate_crew_setup',{**REF,'proposal_hash':S,'bindings':{'type':'array','minItems':1,'maxItems':32,'items':BINDING}},
    [*REF,'proposal_hash','bindings'], 'Owner approves exact hierarchy and scopes. Atomically reuse membership and persistent Bot contracts; runtimes remain offline.')
register('start_crew_setup_work',{**REF},[*REF],
    'Owner explicitly queues first planning task; requires existing execution delegation and a ready runtime. Never triggered by import.')
