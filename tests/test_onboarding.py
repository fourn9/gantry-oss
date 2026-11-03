"""Anonymous fixtures: onboarding never executes the project or certifies it."""
import base64
import copy
import secrets
import unittest
from gantry.service import Service, token_hash
from gantry.model import digest
import test_studio_workspace as fixtures

b64=lambda x:base64.b64encode(x.encode()).decode()
class OnboardingTests(fixtures.WorkspaceTests):
    def start(self, **kw):
        args={'name':'Bench carriage','goal':'Share unfinished routing',
            'files':{'cad/base.step':b64('source A'),'cad/alternative.step':b64('source B'),
                     'control/motion.py':b64('offset=1'),'README.md':b64('Travel remains unverified')},
            'actors':[], 'missing':['Unsaved editor buffers'], **kw}
        if args.get('files') is None:args.pop('files',None)
        return self.call('start_onboarding',args)
    def ref(self,d): return {'onboarding_id':d['id'],'version':d['version']}
    def test_discovery_resume_complete_and_share_are_separate(self):
        d=self.start(); self.assertEqual(d['status'],'draft')
        self.assertTrue(d['questions']);self.assertEqual(d['discovery']['method'],'file-inventory-v1')
        self.assertEqual(self.call('studio_overview')['projects'],[])
        restored=Service(self.root/'ledger').call(self.token,'get_onboarding',{'onboarding_id':d['id']})
        self.assertEqual(restored['snapshot'],d['snapshot'])
        d=self.call('answer_onboarding',{**self.ref(d),'question_id':d['questions'][0]['id'],'answer':'Both have different uses'})
        d=self.call('complete_onboarding',{**self.ref(d),'title':'Share routing progress','purpose':'Allow teammate continuation'})
        again=self.call('complete_onboarding',{**self.ref(d),'title':'Share routing progress','purpose':'Allow teammate continuation'})
        self.assertEqual(d['result'],again['result'])
        v=self.call('studio_work',{'work_id':d['result']['change']['id']})
        self.assertEqual(v['selected']['status']['verification'],'unverified')
        self.assertEqual(v['selected']['status']['adoption'],'unadopted')
        self.assertEqual(v['selected']['status']['sharing'],'local')
        self.assertIn('Both have different uses',str(v['selected']['state']['context']))
        self.assertEqual(v['selected']['manifest']['cad/base.step']['hash'],d['manifest']['cad/base.step']['hash'])
        self.assertTrue(self.call('replay')['matched'])
    def test_answers_survive_same_evidence_and_become_stale_on_change(self):
        d=self.start();q=d['questions'][0]
        d=self.call('answer_onboarding',{**self.ref(d),'question_id':q['id'],'answer':'Use base.step'})
        original=copy.deepcopy(d)
        d=self.call('refresh_onboarding',{**self.ref(d),'snapshot':d['snapshot']})
        self.assertEqual(d['questions'][0]['answer']['status'],'current')
        snap=self.artifact({'cad/base.step':'changed','cad/alternative.step':'source B','control/motion.py':'offset=1','README.md':'Travel remains unverified'})
        d=self.call('refresh_onboarding',{**self.ref(d),'snapshot':snap})
        self.assertEqual(d['questions'][0]['answer']['status'],'stale')
        self.assertEqual(d['answers'][q['id']]['text'],'Use base.step')
        self.fault('stale_basis',lambda:self.call('answer_onboarding',{**self.ref(original),'question_id':q['id'],'answer':'outdated'}))
    def test_proposals_are_attributed_and_do_not_override_corrections(self):
        d=self.start();node=d['hierarchy'][1]
        d=self.call('correct_onboarding',{**self.ref(d),'node_id':node['id'],'title':'Cleaning assembly','reason':'Team name'})
        proposal={'nodes':[{**node,'title':'Guessed name'}], 'findings':[{'text':'Control may actuate this mechanism',
           'kind':'inferred','evidence':[{'path':'control/motion.py','hash':d['manifest']['control/motion.py']['hash']}]}],
           'questions':[], 'next_work':{'title':'Inspect routing','purpose':'Check unknown clearance'},'limitations':['CAD features not parsed']}
        d=self.call('propose_onboarding',{**self.ref(d),'snapshot':d['snapshot'],'proposal':proposal})
        self.assertEqual(next(n for n in d['hierarchy'] if n['id']==node['id'])['title'],'Cleaning assembly')
        self.assertEqual(d['proposal']['author'],'admin')
        bad=copy.deepcopy(proposal);bad['findings'][0]['evidence'][0]['hash']='0'*64
        self.fault('stale_basis',lambda:self.call('propose_onboarding',{**self.ref(d),'snapshot':d['snapshot'],'proposal':bad}))
        bad=copy.deepcopy(proposal);bad['nodes'][0]['paths']=['../../outside']
        self.fault('scope_denied',lambda:self.call('propose_onboarding',{**self.ref(d),'snapshot':d['snapshot'],'proposal':bad}))
    def test_scope_secrets_and_failed_completion_are_atomic(self):
        for path,value,code in [('../out.txt','text','scope_denied'),('.env','text','scope_denied'),('main.py','ghp_'+'x'*40,'credential_detected')]:
            self.fault(code,lambda:self.start(files={path:b64(value)}))
        self.assertEqual(self.call('list_onboardings')['items'],[])
        d=self.start()
        self.fault('invalid_input',lambda:self.call('complete_onboarding',{**self.ref(d),'title':' ','purpose':'x'}))
        self.assertEqual(self.call('studio_overview')['projects'],[])
    def person(self,name,kind='human'):
        token=secrets.token_urlsafe(32)
        p=self.call('propose',{'title':'Add fixture participant','changes':[{'id':name,'type':'principal',
            'data':{'kind':kind,'permissions':['read','record','work'],'token_hash':token_hash(token)}}]})
        ref={'proposal_id':p['id'],'version':p['version']}
        for cmd,args in [('submit',ref),('endorse',{**ref,'reason':'fixture'}),('review_adoption',{**ref,'reason':'fixture','verdict':'approve'}),('commit',ref)]:self.call(cmd,args)
        return token
    def test_collaborator_can_propose_but_not_grant_access_or_complete(self):
        token=self.person('helper','agent');outsider=self.person('outsider')
        d=self.start(actors=['helper']);args={'onboarding_id':d['id']}
        self.fault('unauthorized',lambda:self.service.call(outsider,'get_onboarding',args))
        self.assertEqual(self.service.call(outsider,'list_onboardings',{})['items'],[])
        self.assertEqual(self.service.call(token,'get_onboarding',args)['id'],d['id'])
        self.fault('human_approval_required',lambda:self.service.call(token,'complete_onboarding',{**self.ref(d),'title':'No','purpose':'No'},'finish'))
    def test_saved_snapshot_onboarding_does_not_require_reupload(self):
        d=self.start();snap=d['snapshot']
        other=self.start(files=None,snapshot=snap)
        self.assertEqual(other['manifest'],d['manifest'])

    def test_customer_analysis_is_bounded_recoverable_and_does_not_execute(self):
        from gantry.onboarding_agent import analyze
        d=self.start();calls=[]
        def infer(context,schema,directory):
            calls.append(context)
            self.assertIn('cad/base.step',context['metadata_only_paths'])
            return {'output':{'nodes':[], 'findings':[{'text':'Travel is not yet verified','kind':'observed',
                'evidence':[{'path':'README.md','hash':d['manifest']['README.md']['hash']}]}],
                'questions':[],'next_work':{'title':'Share routing','purpose':'Compare saved variants'},
                'limitations':['Native CAD requires its own tool']}, 'provider':{'kind':'synthetic-test'}}
        first=analyze(self.client,d['id'],self.root/'analysis',infer)
        self.assertEqual(first,analyze(self.client,d['id'],self.root/'analysis',infer))
        self.assertEqual(len(calls),1);self.assertFalse(first['project_executed'])
        self.assertEqual(self.call('get_onboarding',{'onboarding_id':d['id']})['proposal']['content']['findings'][0]['text'],'Travel is not yet verified')

    def test_first_work_can_be_shared_and_continued_by_another_identity(self):
        from test_development import LocalClient
        from gantry.workspace import continue_workspace
        token=self.person('teammate');d=self.start(actors=['teammate'])
        d=self.call('complete_onboarding',{**self.ref(d),'title':'Share progress','purpose':'Independent continuation'})
        work=d['result']['change'];cp=self.call('studio_sync_update',{'work_id':work['id'],'version':work['version'],
            'expected_state':work['head'],'files':{'control/motion.py':b64('offset=2')},'deleted':[],
            'summary':'Unfinished edit','rationale':'Prepare review','unfinished':['Clearance not checked'],'missing':[]})
        self.call('studio_share_update',{'work_id':work['id'],'version':cp['change']['version'],'state_id':cp['state']['id'],'note':'Continue this version'})
        other=LocalClient(Service(self.root/'ledger'),token)
        continued=continue_workspace(other,work['id'],cp['state']['id'],self.root/'continued','Review saved routing')
        self.assertEqual((self.root/'continued'/'workspace'/'control'/'motion.py').read_text(),'offset=2')
        self.assertEqual(other.call('studio_work',{'work_id':continued['work_id']})['selected']['status']['verification'],'unverified')

    def test_analysis_lost_response_retries_saved_submission_without_inference(self):
        from gantry.onboarding_agent import analyze
        d=self.start();client=self.client;calls=[]
        class LostResponse:
            lost=False
            def call(inner,cmd,args=None,key=None):
                result=client.call(cmd,args or {},key)
                if cmd=='propose_onboarding' and not inner.lost:
                    inner.lost=True;raise OSError('response lost after commit')
                return result
        def infer(*args):
            calls.append(True)
            return {'output':{'nodes':[], 'findings':[], 'questions':[],
                'next_work':{'title':'Share saved work','purpose':'Inspect unresolved geometry'},
                'limitations':['Native geometry not interpreted']}}
        connection=LostResponse()
        with self.assertRaises(OSError):analyze(connection,d['id'],self.root/'lost',infer)
        result=analyze(connection,d['id'],self.root/'lost',infer)
        self.assertEqual(len(calls),1);self.assertEqual(result['status'],'proposal_saved')
        self.assertEqual(self.call('get_onboarding',{'onboarding_id':d['id']})['version'],2)

    def test_cli_preview_is_local_and_apply_is_idempotent(self):
        from types import SimpleNamespace
        from gantry.onboarding_cli import run
        root=self.root/'source';root.mkdir();(root/'part.py').write_text('position = 1')
        args=SimpleNamespace(action='start',root=str(root),paths=['part.py'],name='Fixture',goal='',actor=[],
            apply=False,onboarding_id=None)
        class Offline:
            def call(*args):raise AssertionError('Preview contacted the service')
        preview=run(Offline(),args)
        self.assertFalse(preview['sent']);self.assertFalse((root/'.gantry').exists())
        args.apply=True
        result=run(self.client,args)
        self.assertEqual(run(self.client,args),result)
        self.assertEqual(len(self.call('list_onboardings')['items']),1)

    def test_revoked_collaborator_and_cycles_are_rejected(self):
        token=self.person('helper','agent');d=self.start(actors=['helper'])
        root=d['hierarchy'][0];child=d['hierarchy'][1]
        self.fault('invalid_input',lambda:self.call('correct_onboarding',{**self.ref(d),
            'node_id':root['id'],'title':root['title'],'parent':child['id'],'reason':'Invalid fixture'}))
        d=self.call('set_onboarding_collaborators',{**self.ref(d),'actors':[]})
        self.fault('unauthorized',lambda:self.service.call(token,'get_onboarding',{'onboarding_id':d['id']}))

    def test_large_directory_inventory_is_bounded_without_losing_files(self):
        from gantry.onboarding_discovery import discover
        manifest={f'dir{i}/part.step':{'hash':'a'*64,'size':1} for i in range(1000)}
        found=discover(manifest,'Fixture')
        self.assertEqual(len(found['hierarchy']),100)
        self.assertEqual(len(found['hierarchy'][0]['paths']),1000)
        self.assertIn('first 99 folders',found['limitations'][-1])

    def test_agent_reproposal_reuses_answers_until_the_source_changes(self):
        d=self.start()
        q={'id':'routing-intent','text':'Which motion is intended?','why':'Code value alone does not establish intent',
           'options':[], 'evidence':[{'path':'control/motion.py','hash':d['manifest']['control/motion.py']['hash']}]}
        proposal={'nodes':[], 'findings':[], 'questions':[q], 'next_work':{'title':'Share work','purpose':'Clarify routing'}, 'limitations':[]}
        d=self.call('propose_onboarding',{**self.ref(d),'snapshot':d['snapshot'],'proposal':proposal})
        d=self.call('answer_onboarding',{**self.ref(d),'question_id':q['id'],'answer':'Bench travel only'})
        d=self.call('propose_onboarding',{**self.ref(d),'snapshot':d['snapshot'],'proposal':proposal})
        question=next(item for item in d['questions'] if item['id']==q['id'])
        self.assertEqual(question['answer']['status'],'current')
        self.assertEqual(question['answer']['text'],'Bench travel only')
