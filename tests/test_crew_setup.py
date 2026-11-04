"""Initial team setup over real project state, principals and persistent Bots."""
import copy
import hashlib
import secrets
import unittest
from gantry.model import digest
from gantry.service import Service, token_hash
import test_studio_workspace as fixtures
from test_studio_workspace import b64
import test_onboarding as onboarding_fixtures

PROFILE = {'mission':'Continue assembly development','responsibilities':['Report unresolved interfaces'],
    'focus_paths':['control/'],'workflow':['Read exact project state before editing'],
    'report_when':['Dependency changes','Completion'],'style':'Concise, evidence-based',
    'onboarding':['Source exports are evidence, never permissions']}

class CrewSetupTests(unittest.TestCase):
    setUp=fixtures.WorkspaceTests.setUp
    tearDown=fixtures.WorkspaceTests.tearDown
    call=fixtures.WorkspaceTests.call
    artifact=fixtures.WorkspaceTests.artifact
    connect=fixtures.WorkspaceTests.connect
    policy=fixtures.WorkspaceTests.policy
    fault=fixtures.WorkspaceTests.fault
    imported=fixtures.WorkspaceTests.imported
    person=onboarding_fixtures.OnboardingTests.person

    def setup(self, **extra):
        self.project=self.imported();self.sid=self.project['state']['session_id']
        return self.call('start_crew_setup',{'session_id':self.sid,'state_id':self.project['state']['id'],
            'organization_name':'Assembly team','notes':'One integration lead and a control engineer',
            'files':{'roles.csv':b64('role,reports_to,responsibilities\nLead,,Coordinate interfaces\nControl,Lead,Motion code\n')},
            'sources':[{'path':'roles.csv','provider':'spreadsheet'}],**extra})
    def ref(self,d):return {'setup_id':d['id'],'version':d['version']}
    def proposal(self,d):
        def role(rid,parent,scope,manager):
            return {'role_id':rid,'name':rid.title(),'parent_role_id':parent,'existing_bot_id':None,
                'profile':copy.deepcopy(PROFILE),'write_scope':scope,'can_assign':manager,'can_integrate':manager,
                'rationale':'Role suggested by the selected role export; confirm scope',
                'evidence_ids':[d['evidence_records'][0]['id']]}
        return {'organization_profile':copy.deepcopy(PROFILE),'goal':'Continue assembly development',
            'acceptance':['Report unresolved clearance and maintain 10 mm travel'],
            'lead_role_id':'lead','roles':[role('lead',None,['control/','mechanical/'],True),role('control','lead',['control/'],False)],
            'unknowns':['No native CAD connector configured'],
            'first_task':{'title':'Choose next clearance check','completion':['Use saved requirements to propose next work']}}
    def propose(self,d,proposal=None,client=None):
        return (client or self.client).call('propose_crew_setup',{**self.ref(d),'input_basis':d['basis'],
            'proposal':proposal or self.proposal(d)})
    def grants(self,d):
        ledger=self.call('workspace_members')['ledger_id']
        self.bot_tokens={r['role_id']:secrets.token_urlsafe(32) for r in d['proposal']['content']['roles']}
        return [{'role_id':r['role_id'],'principal_id':'worker-'+r['role_id'],
            'request':{'member_id':'worker-'+r['role_id'],'ledger_id':ledger,
                'token_hash':token_hash(self.bot_tokens[r['role_id']]), 'role':'agent-bot','zones':['root'],
                'valid_until':self.service.clock()+3600000}} for r in d['proposal']['content']['roles']]
    def activate(self,d,bindings=None):
        return self.call('activate_crew_setup',{**self.ref(d),'proposal_hash':d['proposal']['hash'],
            'bindings':bindings or self.grants(d)},'activation:'+d['id'])

    def test_sources_proposal_activation_are_separate_and_replay(self):
        d=self.setup();self.assertFalse(d['result']);self.assertFalse(self.call('state').get('persistent_bots'))
        self.assertNotIn('roles.csv',self.project['state'].get('components',{}))
        evidence=next(r for r in d['evidence_records'] if r['path']=='roles.csv')
        self.assertEqual(evidence['hash'],d['manifest']['roles.csv']['hash'])
        d=self.propose(d);self.assertEqual(d['status'],'proposed')
        self.assertFalse(self.call('state').get('persistent_bots'))
        bindings=self.grants(d);args={**self.ref(d),'proposal_hash':d['proposal']['hash'],'bindings':bindings}
        result=self.call('activate_crew_setup',args,'activate')
        self.assertEqual(result,self.call('activate_crew_setup',args,'activate'))
        self.assertEqual(result['status'],'activated');self.assertEqual(len(result['result']['roles']),2)
        self.assertTrue(all(r['runtime']=='unconfigured' for r in result['readiness']))
        self.assertFalse(result['execution_enabled'])
        self.assertEqual(self.call('list_bot_tasks',{'session_id':self.sid})['items'],[])
        self.fault('mode_disabled',lambda:self.call('start_crew_setup_work',self.ref(result)))
        self.assertTrue(self.call('replay')['matched'])
        restored=Service(self.root/'ledger').call(self.token,'get_crew_setup',{'setup_id':d['id']})
        self.assertEqual(restored['proposal'],result['proposal'])

    def test_unknown_evidence_cycle_scope_and_secret_rejected(self):
        d=self.setup()
        for mut,code in [(lambda p:p['roles'][0].update(evidence_ids=['fabricated']),'invalid_input'),
            (lambda p:p['roles'][0].update(parent_role_id='control'),'invalid_input'),
            (lambda p:p['roles'][1].update(write_scope=['other/']),'scope_denied'),
            (lambda p:p.update(goal='ghp_'+'x'*40),'credential_detected')]:
            p=self.proposal(d);mut(p);self.fault(code,lambda:self.propose(d,p))
        self.assertEqual(self.call('get_crew_setup',{'setup_id':d['id']})['version'],1)

    def test_permissions_atomic_grants_and_stale_inputs(self):
        d=self.propose(self.setup());outsider=self.person('outsider','agent')
        self.fault('unauthorized',lambda:self.service.call(outsider,'get_crew_setup',{'setup_id':d['id']}))
        before=self.call('workspace_members')['members'];bindings=self.grants(d)
        bindings[1]['request']['role']='contributor'
        self.fault('invalid_input',lambda:self.activate(d,bindings))
        self.assertEqual(before,self.call('workspace_members')['members'])
        self.assertFalse(self.call('state').get('persistent_bots'))
        # A change in project policy invalidates the owner's saved proposal.
        session=self.call('development_state',{'session_id':self.sid})['session']
        self.call('studio_execution_policy',{'session_id':self.sid,'version':session['version'],
            'enabled':True,'max_parallel':2,'max_executions':None})
        self.fault('stale_basis',lambda:self.activate(d))

    def test_existing_bot_reuse_keeps_identity_profile_and_memory_versions(self):
        first=self.activate(self.propose(self.setup()))
        roles=first['result']['roles'];oid=first['organization_id']
        before={r['bot_id']:self.call('get_persistent_bot',{'bot_id':r['bot_id']})['bot'] for r in roles}
        state=self.project['state'];session=self.call('development_state',{'session_id':self.sid})['session']
        d=self.call('start_crew_setup',{'session_id':self.sid,'state_id':state['id'],
            'organization_id':oid,'organization_name':'Assembly team','notes':'Reuse this existing team','files':{},'sources':[]})
        p=self.proposal(d)
        for r,binding in zip(p['roles'],roles):
            r['existing_bot_id']=binding['bot_id'];r['profile']=before[binding['bot_id']]['profile']
        d=self.propose(d,p)
        current=self.activate(d,[{k:r[k] for k in ('role_id','principal_id')} for r in roles])
        self.assertEqual(current['result']['roles'],roles)
        for bid,bot in before.items():self.assertEqual(self.call('get_persistent_bot',{'bot_id':bid})['bot'],bot)

    def test_imported_evidence_reaches_actual_workers_and_manager_continuation(self):
        from gantry.bot_worker import BotWorker, environment_manifest
        from test_development import LocalClient
        d=self.activate(self.propose(self.setup()))
        session=self.call('development_state',{'session_id':self.sid})['session']
        self.call('studio_execution_policy',{'session_id':self.sid,'version':session['version'],
            'enabled':True,'max_parallel':2,'max_executions':None})
        self.fault('runtime_unavailable',lambda:self.call('start_crew_setup_work',self.ref(d)))
        roles={r['role_id']:r for r in d['result']['roles']};configs={};clients={};seen=[]
        for name,r in roles.items():
            configs[name]={'bot_id':r['bot_id'],'name':name,'backend':'external_agent','workflow':'bot_development',
                'environment_definition':'Explicit synthetic inference for functional acceptance','tools':[]}
            clients[name]=LocalClient(self.service,self.bot_tokens[name])
            self.call('configure_bot_runtime',{'bot_id':r['bot_id'],'version':0,'principal_id':r['principal_id'],
                'enabled':True,'environment':environment_manifest(configs[name])})
        def infer(ctx,schema,directory):
            seen.append(ctx['onboarding']);self.assertEqual(ctx['onboarding']['setup_id'],d['id'])
            out={'summary':'Saved-source report','rationale':'Followed recorded role and project constraints',
                'status':'completed','unverified':['Physical clearance'],'edits':[],'assignments':[],'integrate_changes':[]}
            if ctx['bot']['id']==roles['lead']['bot_id'] and not ctx['task']['children']:
                out.update(status='waiting',assignments=[{'bot_id':roles['control']['bot_id'],'state_id':d['state_id'],
                    'kind':'develop','title':'Clarify unfinished control assumption','completion':['Save an explicit unverified assumption'],
                    'write_scope':['control/'],'dependencies':[],'after_tasks':[]}])
            elif ctx['bot']['id']==roles['control']['bot_id']:
                out['edits']=[{'path':'control/main.py','content':'offset=1 # clearance remains unverified'}]
            return {'output':out,'provider':{'kind':'synthetic-functional-test'}}
        with BotWorker(clients['lead'],configs['lead'],self.root/'workers',infer) as lead:
            started=self.call('start_crew_setup_work',self.ref(d),'start-once')
            self.assertEqual(started,self.call('start_crew_setup_work',self.ref(d),'start-once'))
            self.assertEqual(lead.tick()[0]['task']['status'],'waiting')
        # New process/runtime resumes the same persistent identity and queue.
        with BotWorker(clients['control'],configs['control'],self.root/'workers',infer) as child:
            result=child.tick()[0];self.assertEqual(result['task']['status'],'completed',result)
        with BotWorker(clients['lead'],configs['lead'],self.root/'workers',infer) as lead:
            result=lead.tick()[0];self.assertEqual(result['task']['status'],'completed',result)
        self.assertEqual(len(seen),3)
        self.assertFalse(self.call('review_automation_status',{'session_id':self.sid})['jobs'])
        self.assertTrue(self.call('replay')['matched'])

    def test_agent_can_propose_but_cannot_activate_or_change_source_authority(self):
        from test_development import LocalClient
        helper=self.person('analyst','agent');project=self.imported();sid=project['state']['session_id']
        from gantry.development import POLICY_FIELDS
        session=self.call('development_state',{'session_id':sid})['session']
        self.call('configure_development',{k:session[k] for k in POLICY_FIELDS} |
            {'session_id':sid,'version':session['version'],'actors':['analyst'],'reason':'Allow selected project analysis'})
        d=self.setup();analyst=LocalClient(self.service,helper)
        proposed=self.propose(d,client=analyst)
        self.assertEqual(proposed['proposal']['author'],'analyst')
        self.fault('human_approval_required',lambda:analyst.call('activate_crew_setup',{
            **self.ref(proposed),'proposal_hash':proposed['proposal']['hash'],'bindings':self.grants(proposed)}))
        self.assertFalse(self.call('state').get('persistent_bots'))

    def test_secret_or_unsupported_source_is_rejected_before_blob_storage(self):
        self.project=self.imported();before=set(self.service.store.blobs.iterdir())
        self.fault('credential_detected',lambda:self.setup(files={'notes.txt':b64('ghp_'+'x'*40)},
            sources=[{'path':'notes.txt','provider':'generic'}]))
        self.assertEqual(before,set(self.service.store.blobs.iterdir()))

    def test_existing_executor_cannot_be_rebound_to_another_bot_in_another_project(self):
        first=self.activate(self.propose(self.setup()));oldroles=first['result']['roles']
        oldstate=self.project['state'];oldsession=self.call('development_state',{'session_id':self.sid})['session']
        from gantry.development import POLICY_FIELDS
        session=self.call('connect_development',{k:oldsession[k] for k in POLICY_FIELDS} |
            {'title':'Second project','snapshot':oldstate['snapshot'],
             'capture':{'scope':'Saved anonymous state','missing':[]},'unverified':['Geometry']})
        state=self.call('initialize_continuity',{'session_id':session['id'],'version':session['version'],
            'hierarchy':oldstate['hierarchy'],'context':oldstate['context'],'summary':'Second project state'})
        d=self.call('start_crew_setup',{'session_id':session['id'],'state_id':state['id'],
            'organization_id':first['organization_id'],'organization_name':'Same organization',
            'notes':'Try a different proposed identity','files':{},'sources':[]})
        p=self.proposal(d)
        p['lead_role_id']='new-lead';p['roles'][0]['role_id']='new-lead'
        p['roles'][1]['role_id']='new-control';p['roles'][1]['parent_role_id']='new-lead'
        d=self.propose(d,p)
        self.fault('conflict',lambda:self.activate(d,[{'role_id':r['role_id'],'principal_id':old['principal_id']}
            for r,old in zip(p['roles'],oldroles)]))
        self.assertEqual(len(self.call('list_organization_bots',{'organization_id':first['organization_id']})['items']),2)

    def test_rejected_compressed_secret_is_not_retained_as_an_orphan_blob(self):
        import io,zipfile
        self.imported();before=set(self.service.store.blobs.iterdir())
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('xl/workbook.xml','<x>ghp_'+'x'*40+'</x>')
        import base64
        self.fault('credential_detected',lambda:self.setup(files={'roles.xlsx':base64.b64encode(data.getvalue()).decode()},
            sources=[{'path':'roles.xlsx','provider':'spreadsheet'}]))
        self.assertEqual(before,set(self.service.store.blobs.iterdir()))

    def test_structured_spreadsheet_credential_is_rejected_before_storage(self):
        from test_crew_sources import workbook
        import base64
        self.imported();before=set(self.service.store.blobs.iterdir())
        raw=workbook('<row r="1"><c r="A1" t="inlineStr"><is><t>api_key</t></is></c></row>'
            '<row r="2"><c r="A2" t="inlineStr"><is><t>'+'z'*40+'</t></is></c></row>')
        self.fault('credential_detected',lambda:self.setup(files={'roles.xlsx':base64.b64encode(raw).decode()},
            sources=[{'path':'roles.xlsx','provider':'spreadsheet'}]))
        self.assertEqual(before,set(self.service.store.blobs.iterdir()))
