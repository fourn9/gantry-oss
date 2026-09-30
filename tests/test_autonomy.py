import base64
import copy
import json
import secrets
import sys
import tempfile
import time
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch, MagicMock
from gantry.service import Service, token_hash
from gantry.model import Fault, digest
from gantry.backup import restore_backup
from gantry.autonomy_worker import analyst_once
from gantry.runner import run_contract, persist
from gantry.inference import infer
from test_development import LocalClient


class AutonomyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.now=time.time_ns()//1000000
        self.service=Service(self.root/'ledger',clock=lambda:self.now)
        self.admin=LocalClient(self.service,self.service.bootstrap()['token'])
        self.agents=[]
        for name in ('analyst-a','analyst-b','runner'):
            token=secrets.token_urlsafe(32)
            p=self.admin.call('propose',{'title':'Delegate '+name,'changes':[{'id':name,'type':'principal','data':{
                'kind':'agent','permissions':['read','record','propose','work'],'token_hash':token_hash(token),'zones':['root']}}]})
            args={'proposal_id':p['id'],'version':p['version']}
            self.admin.call('submit',args);self.admin.call('endorse',{**args,'reason':'test'})
            self.admin.call('review_adoption',{**args,'reason':'test','verdict':'approve'});self.admin.call('commit',args)
            self.agents.append(LocalClient(self.service,token))
        self.project=self.admin.call('save_project',{'name':'Robot test','description':'Hardware and software'})
        self.snapshot=self.admin.call('capture_artifact',{'files':{'control.py':base64.b64encode(b'gain=1').decode(),
            'head.step':base64.b64encode(b'fixture CAD').decode()}})['revision_id']
        seed=self.admin.call('create_product_session',{'project_id':self.project['id'],'title':'Imported state','goal':'Continue', 'snapshot':self.snapshot})
        self.admin.call('set_session_outcome',{'session_id':seed['session']['id'],'version':1,'outcome':'closed','reason':'Baseline only'})
        self.project=self.admin.call('save_project',{**{k:self.project[k] for k in ('name','description','version')},
            'project_id':self.project['id'],'baseline_state':seed['state']['id']})
        self.integration=self.admin.call('configure_integration',{'project_id':self.project['id'],'provider':'monitoring','name':'Observed robot','enabled':True})
        self.recipe={'argv':[sys.executable,'-c','open("result.json","w").write(\'{"verdict":"pass"}\')'],'timeout_seconds':10}
        self.config={'project_id':self.project['id'],'version':0,'enabled':True,'analysts':['analyst-a','analyst-b'],
            'provider':{'kind':'fixture','model':'test-fixture','max_input_tokens':150000,'max_output_tokens':2000,'timeout_seconds':5,
                'input_microusd_per_million':0,'output_microusd_per_million':0},
            'session_template':{'mode':'execute','actors':['analyst-a','analyst-b','runner'],'write_scope':['result.json'],
                'recipes':{'check':digest(self.recipe)},'max_executions':4,'timeout_seconds':30,'max_parallel':2},
            'max_daily_calls':30,'max_daily_microusd':0,'max_monthly_microusd':0,'max_active_sessions':4,'max_sessions_per_day':4,
            'max_replans_per_session':8,'max_daily_executions':8,'cooldown_seconds':1,'max_attempts_per_trigger':3,'reason':'Isolated zero-cost test'}
        self.admin.call('configure_automation',self.config)
    def tearDown(self):self.tmp.cleanup()
    def signal(self,name='head',body='A simulated physical observation'):
        return self.admin.call('ingest_signal',{'integration_id':self.integration['id'],'source_event_id':name,'title':name,'body':body,
            'occurred_at':'2026-09-23T00:00:00Z','observed_configuration':{'hardware':'h1','software':'s1','electrical':'unknown'}})
    def claim(self,kind='triage',client=None):
        return (client or self.agents[0]).call('claim_analysis',{'project_id':self.project['id'],'worker_id':'worker','kind':kind})
    def triage(self,run,action='start'):
        return {'decisions':[{'action':action,'signal_ids':list(run['basis']['signals']),'title':'Investigate observed motion',
            'goal':'Reproduce joint hardware and software issue','rationale':'Related observed configuration',
            'evidence':list(run['basis']['signals'].values()),'priority':'high','session_id':None}]}
    def complete(self,run,output,client=None,**extra):
        return (client or self.agents[0]).call('complete_analysis',{'analysis_id':run['id'],'fence':run['fence'],'output':output,
            'usage':{'input_tokens':0,'output_tokens':0},**extra})
    def begin(self):
        self.signal();r=self.claim()['run'];result=self.complete(r,self.triage(r))
        self.assertEqual(result['status'],'completed',result)
        return result['result']['decisions'][0]['session_id']
    def proposal(self,run,action='propose'):
        d=run['context']['session'];refs=[d['active_state'],run['milestone_ids'][-1]]
        return {'action':action,'rationale':'Test explicit evidence','evidence':refs,'proposal':None if action!='propose' else {
            'input_state':d['active_state'],'evidence':refs,'alternatives':['Wait for bench data'],'selection_reason':'First reproduce in bounded simulation',
            'contract':{'title':'Check recorded configuration','input_snapshot':d['snapshot'],'write_scope':['result.json'],
                'recipe':'check','recipe_hash':digest(self.recipe),'expected_outputs':['result.json'],
                'completion':{'description':'Pass the simulated check','require_exit_zero':True,'required_files':['result.json'],'verdict_file':'result.json'},
                'dependencies':[],'hypothesis':'Recorded combination can be reproduced','rationale':'Evidence-linked bounded check'}}}
    def contract(self):
        run=self.claim('mentor')['run'];result=self.complete(run,self.proposal(run));self.assertEqual(result['status'],'completed',result)
        return result['result']['contract_id']
    def reconfigure(self,**overrides):
        self.config={**self.config,**overrides,'version':self.config['version']+1}
        return self.admin.call('configure_automation',self.config)

    def test_group_sources_auto_session_real_execution_and_no_adoption(self):
        a=self.signal('hose');b=self.signal('controller')
        run=self.claim()['run'];self.assertEqual(len(run['context']['signals']),2)
        result=self.complete(run,self.triage(run));sid=result['result']['decisions'][0]['session_id']
        detail=self.admin.call('session_details',{'session_id':sid})
        self.assertEqual(set(detail['link']['signal_ids']),{a['id'],b['id']})
        self.assertEqual(detail['session']['owner'],'admin')
        contract=self.contract()
        executed=run_contract(self.agents[2],contract,{'check':self.recipe},self.root/'runner')
        self.assertEqual(executed['engineering_verdict'],'pass')
        self.now+=2000
        run=self.claim('mentor')['run'];out=self.complete(run,self.proposal(run,'no_action'))
        self.assertEqual(out['status'],'completed')
        self.assertEqual(self.claim('mentor')['status'],'idle')
        self.assertEqual(self.admin.call('session_details',{'session_id':sid})['state']['status']['adoption'],'unadopted')
        self.assertTrue(self.admin.call('replay')['matched'])

    def test_external_analyst_has_truthful_provenance_without_paid_dispatch(self):
        self.reconfigure(provider={**self.config['provider'],'kind':'external','model':'subscription-analyst'})
        self.signal();run=self.claim()['run']
        with patch('gantry.inference.build_opener') as http, patch('gantry.inference.subprocess.Popen') as process:
            with self.assertRaises(Fault) as exc:infer(run,{'kind':'external'})
            self.assertEqual(exc.exception.code,'external_submission_required')
            http.assert_not_called();process.assert_not_called()
        result=self.agents[0].call('complete_analysis',{'analysis_id':run['id'],'fence':run['fence'],
            'output':self.triage(run),'provider_response_id':'external-submission'})
        self.assertEqual(result['status'],'completed')
        saved=self.agents[0].call('get_analysis',{'analysis_id':run['id']})
        self.assertEqual(saved['provider']['kind'],'external')
        self.assertEqual(saved['usage_status'],'unknown')
        self.assertNotIn('usage',saved)
        self.assertEqual(saved['charged_microusd'],0)

    def test_large_cad_manifest_is_retrievable_without_blocking_analysis(self):
        sid=self.begin();session=self.admin.call('development_state',{'session_id':sid})['session']
        files={'control.py':base64.b64encode(b'gain=1').decode(),'head.step':base64.b64encode(b'fixture CAD').decode()}
        files.update({'assets/long_component_name_mesh_'+str(i)+'.stl':base64.b64encode(b'mesh fixture').decode() for i in range(600)})
        snapshot=self.admin.call('capture_artifact',{'files':files})['revision_id']
        change=self.admin.call('begin_change',{'state_id':session['active_state'],'title':'Import full CAD assembly',
            'purpose':'Preserve all assets','write_scope':['assets/'],'dependencies':[],'assignee':'admin'})
        saved=self.admin.call('checkpoint_change',{'change_id':change['id'],'version':change['version'],'snapshot':snapshot,
            'summary':'600 separate meshes','rationale':'Actual multi-file restoration inputs','unfinished':[],
            'work_status':'working','capture':{'scope':'saved files','missing':[]}})
        self.admin.call('select_development_state',{'state_id':saved['state']['id'],'version':session['version'],'reason':'Review new assembly'})
        full=self.admin.call('mentor_context',{'session_id':sid})
        self.assertGreater(len(json.dumps(full)),200000)
        run=self.claim('mentor')['run'];ctx=run['context']
        self.assertLess(len(json.dumps(ctx)),100000)
        self.assertEqual(ctx['development']['manifest']['file_count'],602)
        self.assertTrue(ctx['context_capture']['omitted'])
        detail=self.admin.call('get_development_state',{'state_id':saved['state']['id']})
        self.assertEqual(len(detail['manifest']),602)
        self.assertEqual(self.complete(run,self.proposal(run,'no_action'))['status'],'completed')

    def test_large_failed_output_inventory_keeps_failure_and_allows_replan(self):
        self.reconfigure(session_template={**self.config['session_template'], 'write_scope':['result.json','results/']})
        sid=self.begin();run=self.claim('mentor')['run'];proposal=self.proposal(run)
        proposal['proposal']['contract']['write_scope']=['result.json','results/']
        result=self.complete(run,proposal);cid=result['result']['contract_id']
        e=self.agents[2].call('start_execution',{'contract_id':cid,'version':1})['execution']
        files={'control.py':base64.b64encode(b'gain=1').decode(),'head.step':base64.b64encode(b'fixture CAD').decode(),
               'result.json':base64.b64encode(b'{"verdict":"fail"}').decode()}
        files.update({'results/copied_component_with_long_stable_name_'+str(i)+'.stl':base64.b64encode(b'mesh').decode() for i in range(3000)})
        refs={}; names=list(files)
        for start in range(0,len(names),1000):
            batch={name:files[name] for name in names[start:start+1000]}
            part=self.admin.call('capture_artifact',{'files':batch})['revision_id']
            refs.update({name:[{'revision_id':part,'path':name}] for name in batch})
        snapshot=self.admin.call('capture_artifact',{'files':{},'assembled_files':refs})['revision_id']
        ended=self.agents[2].call('finish_execution',{'execution_id':e['id'],'output_snapshot':snapshot,'exit_code':2,
            'capture':{'scope':'saved output files','missing':[]},'unverified':['real hardware'],'summary':'Observed contact failure',
            'hypothesis':'Check latest combination','rationale':'Do not discard failed evidence','execution_status':'failed'})
        self.assertTrue(ended['valid']);self.assertEqual(ended['engineering_verdict'],'fail')
        session=self.admin.call('development_state',{'session_id':sid})['session']
        change=self.admin.call('begin_change',{'state_id':session['active_state'],'title':'Continue from failed output',
            'purpose':'Keep evidence and restore in a second context','write_scope':['result.json','results/'],
            'dependencies':[],'assignee':'admin'})
        state=self.admin.call('checkpoint_change',{'change_id':change['id'],'version':change['version'],'snapshot':snapshot,
            'summary':'Failed artifacts retained','rationale':'Diagnose before another physical run','unfinished':['contact diagnosis'],
            'work_status':'working','capture':{'scope':'saved outputs','missing':[]}})['state']
        self.admin.call('select_development_state',{'state_id':state['id'],'version':session['version'],'reason':'Continue diagnosis'})
        manifest=self.admin.call('restore_artifact',{'revision_id':snapshot,'metadata_only':True})['manifest']['files']
        self.admin.call('record_state_restore',{'state_id':state['id'],
            'hashes':{p:v['hash'] for p,v in manifest.items()},'limitations':['unit-test adapter receipt']})
        self.now+=2000;run=self.claim('mentor')['run'];item=run['context']['executions'][0]
        self.assertEqual(item['engineering_verdict'],'fail');self.assertEqual(item['output_snapshot'],snapshot)
        self.assertEqual(item['changed_path_count'],3001);self.assertGreater(item['omitted_changed_path_count'],0)
        receipt=run['context']['development']['restores'][0]
        self.assertEqual(receipt['file_count'],3003);self.assertTrue(receipt['hashes_omitted'])
        self.assertNotIn('hashes',receipt)
        restored=self.admin.call('get_development_state',{'state_id':state['id']})['restores'][0]
        self.assertEqual(len(restored['hashes']),3003)
        full=self.admin.call('development_state',{'session_id':sid})
        self.assertEqual(len(full['executions'][0]['changed_paths']),3001)
        self.assertEqual(len(self.admin.call('restore_artifact',{'revision_id':snapshot,'metadata_only':True})['manifest']['files']),3003)
        self.assertEqual(self.complete(run,self.proposal(run))['status'],'completed')

    def test_two_distinct_analysts_only_one_triage_claim_and_lease_fence(self):
        self.signal()
        with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda c:self.claim(client=c),self.agents[:2]))
        self.assertEqual(sum(r['status']=='claimed' for r in results),1)
        claimed=next(r['run'] for r in results if r['status']=='claimed')
        owner=self.agents[0] if claimed['actor']=='analyst-a' else self.agents[1]
        self.now=claimed['lease_until']+1
        new=self.claim()['run']
        with self.assertRaises(Fault):self.complete(claimed,self.triage(claimed),owner)
        self.assertEqual(self.complete(new,self.triage(new))['status'],'completed')
        self.assertEqual(len([s for s in self.admin.call('product_overview')['sessions'] if s['outcome']=='open']),1)

    def test_stale_evidence_rejected_then_updated_signal_reuses_session(self):
        self.signal();run=self.claim()['run'];self.signal(body='Updated evidence')
        self.assertEqual(self.complete(run,self.triage(run))['reason'],'stale_context')
        self.now+=2000;run=self.claim()['run'];first=self.complete(run,self.triage(run))['result']['decisions'][0]['session_id']
        self.signal(body='Another observation');self.now+=2000;run=self.claim()['run']
        result=self.complete(run,self.triage(run))
        self.assertEqual(result['result']['decisions'][0]['session_id'],first)
        self.assertEqual(result['result']['decisions'][0]['disposition'],'attach')

    def test_failure_and_dependency_change_trigger_new_contracts(self):
        sid=self.begin();cid=self.contract();c=self.admin.call('development_state',{'session_id':sid})['contracts'][0]
        e=self.agents[2].call('start_execution',{'contract_id':cid,'version':c['version']})['execution']
        self.agents[2].call('finish_execution',{'execution_id':e['id'],'output_snapshot':self.snapshot,'exit_code':1,
            'capture':{'scope':'test','missing':[]},'unverified':['physical behavior'],'summary':'Actual failed attempt',
            'hypothesis':'h','rationale':'Missing result','execution_status':'failed'})
        self.now+=2000;run=self.claim('mentor')['run']
        self.assertEqual(run['context']['trigger']['kind'],'failure')
        second=self.complete(run,self.proposal(run));self.assertEqual(second['status'],'completed')
        d=self.admin.call('development_state',{'session_id':sid})['session']
        revised=self.admin.call('capture_artifact',{'files':{'control.py':base64.b64encode(b'gain=2').decode(),
            'head.step':base64.b64encode(b'fixture CAD').decode()}})['revision_id']
        change=self.agents[0].call('begin_change',{'state_id':d['active_state'],'title':'Change controller gain',
            'purpose':'Updated physical constraint','write_scope':['control.py'],'dependencies':['head.step'],'assignee':'analyst-a'})
        checkpoint=self.agents[0].call('checkpoint_change',{'change_id':change['id'],'version':change['version'],
            'snapshot':revised,'summary':'New controller','rationale':'Physical constraint changed','unfinished':['physical test'],
            'work_status':'working','capture':{'scope':'test','missing':[]}})
        self.agents[0].call('select_development_state',{'state_id':checkpoint['state']['id'],'version':d['version'],'reason':'Dependency revised'})
        self.now+=2000;run=self.claim('mentor')['run']
        self.assertEqual(run['context']['trigger']['kind'],'dependency_changed')
        self.assertFalse(self.agents[2].call('check_execution',{'contract_id':second['result']['contract_id']})['allowed'])
        self.assertEqual(run['context']['session']['snapshot'],revised)
        self.assertEqual(self.complete(run,self.proposal(run))['status'],'completed')

    def test_invalid_model_output_has_no_partial_effects_and_no_shell_authority(self):
        self.signal();r=self.claim()['run'];out=self.triage(r)
        out['decisions'].append(dict(out['decisions'][0],signal_ids=['not-in-context']))
        result=self.complete(r,out);self.assertEqual(result['status'],'failed')
        self.assertEqual(len(self.admin.call('product_overview')['sessions']),1)
        self.now+=2000;r=self.claim()['run'];self.complete(r,self.triage(r))
        r=self.claim('mentor')['run'];out=self.proposal(r);out['proposal']['contract']['argv']=['rm','-rf','/']
        self.assertEqual(self.complete(r,out)['status'],'failed')
        self.assertEqual(self.admin.call('development_state',{'session_id':r['session_id']})['contracts'],[])

    def test_shared_inference_budget_and_disabled_paid_provider(self):
        provider={**self.config['provider'],'kind':'openai','model':'operator-selected-model',
            'input_microusd_per_million':1000000,'output_microusd_per_million':1000000}
        self.reconfigure(provider=provider,max_daily_microusd=152000,max_monthly_microusd=152000,max_daily_calls=1)
        self.signal();r=self.claim()['run']
        with self.assertRaises(Fault) as exc:infer(r,{'kind':'openai','allow_paid':False})
        self.assertEqual(exc.exception.code,'provider_disabled')
        self.agents[0].call('fail_analysis',{'analysis_id':r['id'],'fence':r['fence'],'code':'request_outcome_unknown'})
        self.now+=2000;self.assertEqual(self.claim(client=self.agents[1])['reason'],'inference_budget')
        status=self.admin.call('automation_status')['projects'][0]
        self.assertEqual(status['usage']['monthly_microusd'],152000)
        self.assertEqual(status['runs'][0]['usage_status'],'unknown')

    def test_disabled_and_stale_policy_fence_execution_and_inference(self):
        sid=self.begin();r=self.claim('mentor')['run'];self.reconfigure(enabled=False)
        self.assertEqual(self.complete(r,self.proposal(r))['reason'],'delegation_changed')
        self.assertEqual(self.claim()['status'],'disabled')
        self.reconfigure(enabled=True);self.now+=2000;cid=self.contract()
        self.reconfigure(enabled=False)
        reasons=self.agents[2].call('check_execution',{'contract_id':cid})['reasons']
        self.assertIn('automation_disabled',reasons)

    def test_nonhuman_cannot_delegate_and_legacy_mentor_cannot_bypass_lease(self):
        with self.assertRaises(Fault):self.agents[0].call('configure_automation',{**self.config,'version':1})
        sid=self.begin();r=self.claim('mentor')['run'];proposal=self.proposal(r)['proposal']
        with self.assertRaises(Fault) as exc:
            self.agents[0].call('mentor_propose',dict(proposal,session_id=sid,milestone_id=r['milestone_ids'][-1]))
        self.assertEqual(exc.exception.code,'analysis_required')

    def test_independent_mentor_claims_and_project_path_conflicts(self):
        self.signal('a');r=self.claim()['run'];self.complete(r,self.triage(r))
        self.signal('b');self.now+=2000;r=self.claim()['run'];self.complete(r,self.triage(r))
        r1=self.claim('mentor')['run'];r2=self.claim('mentor',self.agents[1])['run']
        self.assertNotEqual(r1['session_id'],r2['session_id'])
        c1=self.complete(r1,self.proposal(r1))['result']['contract_id']
        c2=self.complete(r2,self.proposal(r2),self.agents[1])['result']['contract_id']
        self.assertTrue(self.agents[2].call('start_execution',{'contract_id':c1,'version':1})['allowed'])
        blocked=self.agents[1].call('start_execution',{'contract_id':c2,'version':1})
        self.assertFalse(blocked['allowed']);self.assertIn('project_write_conflict',blocked['reasons'])

    def test_crash_after_inference_replays_saved_response_without_second_model_call(self):
        self.signal();r=self.claim()['run'];journal=self.root/'analyst'
        persist(journal/'active.json',{'worker_id':'worker','run':r,'phase':'response_saved',
            'receipt':{'output':self.triage(r),'usage':{'input_tokens':0,'output_tokens':0}}})
        with patch('gantry.autonomy_worker.infer') as model:
            result=analyst_once(self.agents[0],{'project_ids':[self.project['id']]},journal,'worker')
        self.assertEqual(result['status'],'completed');model.assert_not_called()
        restored=self.root/'restored';restore_backup(restored,self.admin.call('export'))
        replay=Service(restored,clock=lambda:self.now)
        self.assertEqual(replay.call(self.admin.token,'automation_status'),self.admin.call('automation_status'))

    def test_uncertain_process_does_not_retry_model_and_wait_does_not_spin(self):
        self.signal();r=self.claim()['run'];journal=self.root/'uncertain'
        persist(journal/'active.json',{'worker_id':'worker','run':r,'phase':'request_started'})
        with patch('gantry.autonomy_worker.infer') as model:
            result=analyst_once(self.agents[0],{'project_ids':[self.project['id']]},journal,'worker')
        self.assertEqual(result['reason'],'request_outcome_unknown');model.assert_not_called()
        self.now+=2000;r=self.claim()['run'];self.complete(r,self.triage(r,'defer'))
        self.now+=2000;self.assertEqual(self.claim()['status'],'idle')

    def test_circuit_breaker_stops_repeated_provider_failures(self):
        self.signal()
        for i in range(3):
            r=self.claim()['run']
            self.agents[0].call('fail_analysis',{'analysis_id':r['id'],'fence':r['fence'],'code':'provider_unavailable'})
            self.now+=2000
        self.assertEqual(self.claim()['reason'],'circuit_open')
        self.reconfigure(reason='Operator reviewed provider configuration')
        self.assertEqual(self.claim()['status'],'claimed')

    def test_session_capacity_replan_limit_and_project_execution_budget(self):
        self.reconfigure(max_active_sessions=1,max_replans_per_session=1,max_daily_executions=0)
        sid=self.begin();cid=self.contract()
        self.assertIn('project_execution_budget',self.agents[2].call('check_execution',{'contract_id':cid})['reasons'])
        self.signal('other');self.now+=2000;r=self.claim()['run']
        held=self.complete(r,self.triage(r))
        self.assertEqual(held['result']['decisions'][0]['disposition'],'held_capacity')
        self.agents[0].call('signal_development',{'session_id':sid,'kind':'dependency_changed','summary':'New physical constraint',
            'references':[self.snapshot]})
        self.assertIn('automation_review_pending',self.agents[2].call('check_execution',{'contract_id':cid})['reasons'])
        self.assertEqual(self.claim('mentor')['reason'],'replan_limit')

    def test_new_dependency_evidence_retires_old_runnable_proposal(self):
        sid=self.begin();cid=self.contract()
        self.agents[0].call('signal_development',{'session_id':sid,'kind':'dependency_changed','summary':'New harness limit',
            'references':[self.snapshot]})
        self.now+=2000;r=self.claim('mentor')['run']
        result=self.complete(r,self.proposal(r,'wait'));self.assertEqual(result['status'],'completed')
        old=next(c for c in self.admin.call('development_state',{'session_id':sid})['contracts'] if c['id']==cid)
        self.assertEqual(old['status'],'superseded')
        self.assertFalse(self.agents[2].call('check_execution',{'contract_id':cid})['allowed'])

    def test_analysis_foreign_principal_and_cross_workspace_are_denied(self):
        self.signal();r=self.claim()['run']
        with self.assertRaises(Fault):self.complete(r,self.triage(r),self.agents[1])
        with self.assertRaises(Fault):self.agents[2].call('claim_analysis',{'project_id':self.project['id'],'worker_id':'x','kind':'triage'})
        other=Service(self.root/'other');token=other.bootstrap()['token']
        with self.assertRaises(Fault):other.call(token,'get_analysis',{'analysis_id':r['id']})

    def test_idle_poll_does_not_append_development_events(self):
        before=self.admin.call('verify')
        self.assertEqual(self.claim()['status'],'idle')
        self.assertEqual(self.claim('mentor')['status'],'idle')
        self.assertEqual(before,self.admin.call('verify'))

    def test_openai_request_envelope_and_usage_with_mock_transport(self):
        self.signal();r=self.claim()['run'];r['provider']={**r['provider'],'kind':'openai','model':'operator-model'}
        response=MagicMock();response.__enter__.return_value=response
        response.read.return_value=json.dumps({'id':'response-fixture','status':'completed','usage':{'input_tokens':100,'output_tokens':80},
            'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(self.triage(r))}]}]}).encode()
        opener=MagicMock();opener.open.return_value=response
        with patch.dict('os.environ',{'GANTRY_MODEL_API_KEY':'test-only'}),patch('gantry.inference.build_opener',return_value=opener):
            receipt=infer(r,{'kind':'openai','allow_paid':True})
        request=opener.open.call_args.args[0];body=json.loads(request.data)
        self.assertFalse(body['store']);self.assertNotIn('tools',body)
        self.assertEqual(body['model'],'operator-model');self.assertEqual(receipt['usage']['input_tokens'],100)
        self.assertTrue(body['text']['format']['strict'])
        self.assertNotIn('test-only',json.dumps(self.admin.call('export')))

if __name__=='__main__':unittest.main()
