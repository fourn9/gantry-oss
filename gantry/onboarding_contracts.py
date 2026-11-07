"""Agent and UI share the same bounded, evidence-bound onboarding contract."""
from .contracts import register,S,I,A
from .continuity_contracts import NODE
from .requirement_mapping import LINKS
TEXT={'type':'string','minLength':1,'maxLength':2000}
SHORT={'type':'string','minLength':1,'maxLength':240}
FILES={'type':'object','maxProperties':1000,'additionalProperties':{'type':'string'}}
REF={'type':'object','properties':{'path':S,'hash':S},'required':['path','hash'],'additionalProperties':False}
EVIDENCE={'type':'array','minItems':1,'maxItems':1000,'items':REF}
FINDING={'type':'object','properties':{'text':TEXT,'kind':{'enum':['inferred','observed']},'evidence':EVIDENCE},
         'required':['text','kind','evidence'],'additionalProperties':False}
QUESTION={'type':'object','properties':{'id':SHORT,'text':TEXT,'why':TEXT,'options':{'type':'array','maxItems':5,'items':SHORT},'evidence':EVIDENCE},
          'required':['id','text','why','options','evidence'],'additionalProperties':False}
NEXT={'type':'object','properties':{'title':SHORT,'purpose':TEXT},'required':['title','purpose'],'additionalProperties':False}
PROPOSAL={'type':'object','properties':{
    'requirement_links': LINKS,
    'nodes':{'type':'array','maxItems':100,'items':NODE},
    'findings':{'type':'array','maxItems':50,'items':FINDING},
    'questions':{'type':'array','maxItems':10,'items':QUESTION},
    'next_work':NEXT,'limitations':{'type':'array','maxItems':30,'items':TEXT}},
    'required':['nodes','findings','questions','next_work','limitations'],'additionalProperties':False}
R={'onboarding_id':S,'version':I}
register('start_onboarding',{'name':SHORT,'goal':{'type':'string','maxLength':2000},'files':FILES,'snapshot':S,
    'actors':{'type':'array','maxItems':30,'items':S},'missing':{'type':'array','maxItems':100,'items':TEXT},'zone':S},['name','actors','missing'],
    'Owner chooses saved source scope. Store a resumable draft, never execute source or infer approved requirements.')
register('get_onboarding',{'onboarding_id':S},['onboarding_id'],'Read bounded discovery, exact source manifest, prior answers and the customer-agent contract.')
register('list_onboardings',{'after':S})
register('refresh_onboarding',{**R,'files':FILES,'snapshot':S},[*R], 'Reinspect an exact saved snapshot. Preserve corrections; mark answers to changed evidence stale.')
register('propose_onboarding',{**R,'snapshot':S,'proposal':PROPOSAL},[*R,'snapshot','proposal'],
    'Customer agent submits a sourced interpretation and next-work suggestion. Cannot change permissions, formal requirements or tests.')
register('answer_onboarding',{**R,'question_id':S,'answer':TEXT},[*R,'question_id','answer'])
register('correct_onboarding',{**R,'node_id':S,'title':SHORT,'parent':S,'paths':A,'reason':TEXT},[*R,'node_id','title','reason'])
register('complete_onboarding',{**R,'title':SHORT,'purpose':TEXT},[*R,'title','purpose'],
    'Owner confirms first work. Reuse existing continuity; no external edits, sharing, verification or formal adoption.')
register('set_onboarding_collaborators',{**R,'actors':{'type':'array','maxItems':30,'items':S}},[*R,'actors'],
    'Owner updates which existing identities can help with this setup. Does not grant execution or change principal permissions.')
