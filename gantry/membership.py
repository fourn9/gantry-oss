"""Human-reviewed workspace membership over existing principal/decision events."""
import copy
import re
from .contracts import register,S,I,A
from .model import require,identifier,digest

ROLES=['reader','contributor','agent-developer','agent-reviewer','agent-bot']
REQUEST={'type':'object','properties':{'member_id':S,'ledger_id':S,'token_hash':S,
    'role':{'enum':ROLES},'zones':{'type':'array','minItems':1,'maxItems':32,'items':S},'valid_until':I},
    'required':['member_id','ledger_id','token_hash','role','zones','valid_until'],'additionalProperties':False}
SESSIONS={'type':'array','maxItems':100,'items':{'type':'object','properties':{'session_id':S,'version':I},
    'required':['session_id','version'],'additionalProperties':False}}
register('workspace_members',{})
register('grant_workspace_member',{'request':REQUEST,'fingerprint':S,'sessions':SESSIONS,'reason':S,'expires_at':I},
    ['request','fingerprint','sessions','reason'])
register('revoke_workspace_member',{'member_id':S,'expected_revision':S,'reason':S},['member_id','expected_revision','reason'])

class MembershipMixin:
    def _membership_owner(self,actor):
        self._dev_human(actor);self.allowed(actor,'admin')

    def cmd_workspace_members(self,s,actor,a,fx,n,con):
        self._membership_owner(actor)
        return {'ledger_id':s['ledger_id'],'members':[{
            **{k:v for k,v in p.items() if k in {'id','kind','permissions','zones','enabled','expires_at'}},
            'revision_id':s['entries'][p['id']]['revision_id']}
            for p in sorted(s['principals'].values(),key=lambda x:x['id'])],
            'sessions':[{'id':d['id'],'title':d['title'],'version':d['version'],'zone':d['zone'],'actors':d['actors']}
                for d in s.get('dev_sessions',{}).values()],
            'boundary':'Zones share artifact access; use separate workspaces for mutually untrusted teams.'}

    def _membership_decision(self,s,actor,change,reason,fx,n,con):
        # This is the owner's explicit grant/revoke action, not model approval.
        proposal=self.cmd_propose(s,actor,{'title':'Membership: '+change['id'],'changes':[change],'rationale':reason},fx,n,con)
        ref={'proposal_id':proposal['id'],'version':proposal['version']}
        self.cmd_submit(s,actor,ref,fx,n,con)
        self.cmd_endorse(s,actor,{**ref,'reason':reason},fx,n,con)
        self.cmd_review_adoption(s,actor,{**ref,'reason':reason,'verdict':'approve'},fx,n,con)
        self.cmd_commit(s,actor,ref,fx,n,con)
        return proposal['id']

    def cmd_grant_workspace_member(self,s,actor,a,fx,n,con):
        self._membership_owner(actor);r=a['request'];identifier(r['member_id'])
        require(digest(r)==a['fingerprint'],'stale_basis','Access request differs from reviewed fingerprint')
        require(r['ledger_id']==s['ledger_id'],'scope_denied','Request belongs to another workspace')
        require(self.clock()<r['valid_until']<=self.clock()+7*86400000,'expired','Access request expired or exceeds seven days')
        require(re.fullmatch('[a-f0-9]{64}',r['token_hash']),'invalid_input','SHA-256 credential hash required')
        require(not any(p['token_hash']==r['token_hash'] for p in s['principals'].values()),
                'conflict','Credential hash already belongs to an identity; generate a new credential')
        require(r['member_id'] not in s['entries'],'conflict','Member ID already exists; use reviewed rotation or revoke')
        require(len(set(r['zones']))==len(r['zones']),'invalid_input','Duplicate zones')
        require(all(s['entries'].get(z,{}).get('type')=='zone' for z in r['zones']),'invalid_input','Unknown zone')
        require(len({ref['session_id'] for ref in a['sessions']})==len(a['sessions']),'invalid_input','Duplicate sessions')
        sessions=[]
        for ref in a['sessions']:
            d=self._dev_session(s,actor,ref['session_id'])
            require(d['version']==ref['version'],'stale_basis','Session delegation changed; review it again')
            require(d['zone'] in r['zones'],'scope_denied','Session outside member zones')
            sessions.append(d)
        agent=r['role'].startswith('agent-')
        data={'kind':'agent' if agent else 'human','permissions':['read'] if r['role']=='reader' else ['read','record','propose','work'],
            'token_hash':r['token_hash'],'zones':r['zones'],'enabled':True}
        if agent:
            from .agent_connection import PROFILES
            data['allowed_commands']=sorted(PROFILES[r['role'].removeprefix('agent-')])
        if 'expires_at' in a:
            require(a['expires_at']>self.clock(),'expired','Credential expiry must be in the future')
            data['expires_at']=a['expires_at']
        proposal=self._membership_decision(s,actor,{'id':r['member_id'],'type':'principal','zone':'root','data':data},a['reason'],fx,n,con)
        for d in sessions:
            # An additive participant grant does not alter existing workers' recipes,
            # scopes or running jobs. Their existing checks remain in force.
            d['actors']=sorted(set(d['actors']+[r['member_id']]))
            d['version']+=1;d['reason']=a['reason'];self._dev_save(s,fx,'dev_sessions',d)
        return {'member_id':r['member_id'],'revision_id':s['entries'][r['member_id']]['revision_id'],
            'proposal_id':proposal,'sessions':[d['id'] for d in sessions],'credential_shared':False}

    def cmd_revoke_workspace_member(self,s,actor,a,fx,n,con):
        self._membership_owner(actor)
        e=self._get(s,'entries',a['member_id'])
        require(e['type']=='principal' and 'admin' not in e['data']['permissions'],'scope_denied','Owner/admin changes require the full policy review path')
        require(e['revision_id']==a['expected_revision'],'stale_basis','Member changed')
        data=copy.deepcopy(e['data']);data['enabled']=False
        proposal=self._membership_decision(s,actor,{'id':e['id'],'type':'principal','zone':e['zone'],
            'expected_revision':e['revision_id'],'data':data},a['reason'],fx,n,con)
        return {'member_id':e['id'],'enabled':False,'proposal_id':proposal,
                'note':'New API calls are denied. Local tools stop when their runner observes revocation.'}
