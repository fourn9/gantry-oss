import copy
import json
from gantry.hardware import publish
from gantry.physical_evidence import evaluate
from test_hardware_publish import HardwarePublishTests
from test_requirement_traceability import TraceabilityIntegrationTests

class HardwareTraceTests(HardwarePublishTests):
    requirement=TraceabilityIntegrationTests.requirement
    def linked(self):
        base,change,root=self.prepare()
        self.ref=self.requirement()
        self.check['requirement_refs']=[self.ref]
        (root/'physical-plan.json').write_text(json.dumps(self.plan))
        self.snapshot=self.artifact({p.name:p.read_text() for p in root.iterdir() if p.name!='stress.json'})
        self.session=self.connect(); base=self.initialize()
        cp=self.checkpoint(self.begin(base,['physical-plan.json']),
            files={p.name:p.read_text() for p in root.iterdir() if p.name!='stress.json'},
            context={**base['context'],'requirement_refs':[self.ref]})
        base=cp['state']; change=self.begin(base,['bracket.step','stress.json'])
        report=json.loads((root/'stress.json').read_text());report['requirement_refs']=[self.ref]
        (root/'stress.json').write_text(json.dumps(report))
        return base,change,root
    def test_publish_preserves_bindings_and_retry(self):
        base,c,root=self.linked()
        cp=publish(self.client,base['id'],c['id'],c['version'],root,'physical-plan.json','linked')
        v=self.call('get_development_state',{'state_id':cp['state']['id']})
        self.assertEqual(v['engineering']['checks'][0]['requirement_refs'],[self.ref])
        # The independent travel check is absent: load alone cannot fulfill motion.
        self.assertEqual(v['requirement_coverage']['items'][0]['status'],'unverified')
        self.assertEqual(v['engineering']['checks'][0]['effective_status'],'pass')
        again=publish(self.client,cp['state']['id'],c['id'],cp['change']['version'],root,'physical-plan.json','retry')
        self.assertEqual(again['state']['context']['environment']['engineering']['checks'][0]['requirement_refs'],[self.ref])
    def test_old_report_cannot_satisfy_new_requirement(self):
        base,c,root=self.linked()
        report=json.loads((root/'stress.json').read_text());report.pop('requirement_refs')
        (root/'stress.json').write_text(json.dumps(report))
        cp=publish(self.client,base['id'],c['id'],c['version'],root,'physical-plan.json','old-report')
        check=cp['state']['context']['environment']['engineering']['checks'][0]
        self.assertEqual(check['status'],'unknown')
        self.assertIn('requirement_refs_mismatch',check['physical_result']['reasons'])


    def test_inferred_check_requires_explicit_source_and_preserves_origin(self):
        from gantry.engineering_proposals import bind_plan, candidate_context
        base,c,root=self.linked()
        proposal={'components':[{'id':'bracket','role':'load_support','assembly':'frame',
                    'paths':['bracket.step','material.json'],'evidence':[base['id']],'rationale':'Support'}],
            'checks':[{'id':'load','scope':'structural','components':['bracket'],'paths':['bracket.step','material.json'],
                'required':True,'method':'Measure stress','acceptance':'stress <=50 MPa','rationale':'Load',
                'evidence':[base['id']],'finding_id':'f1','requirement_refs':[self.ref]}],'limitations':['Test inference']}
        v=self.call('get_development_state',{'state_id':base['id']})
        bound=bind_plan(proposal,base['context'],v['manifest'],'review-fixture',base['id'],{'f1'},lambda refs:None)
        context=candidate_context(base['context'],bound,v['manifest'])
        # Save the plan's explicit correspondence before attempting publication.
        self.plan['checks'][0]['source_check']={'submission_id':'review-fixture','state_id':base['id']}
        (root/'physical-plan.json').write_text(json.dumps(self.plan))
        prep=self.begin(base,['physical-plan.json'])
        cp=self.checkpoint(prep,files={p.name:p.read_text() for p in root.iterdir() if p.name!='stress.json'},context=context)
        target=self.begin(cp['state'],['stress.json'])
        result=publish(self.client,cp['state']['id'],target['id'],target['version'],root,'physical-plan.json','inferred')
        check=result['state']['context']['environment']['engineering']['checks'][0]
        self.assertEqual(check['status'],'pass');self.assertEqual(check['source_submission'],'review-fixture')
        self.assertEqual(check['requirement_refs'],[self.ref])


import test_change_review as reviews
import test_development as dev
import test_requirement_traceability as trace

class MentorHandoffTests(reviews.ChangeReviewTests):
    requirement=trace.TraceabilityIntegrationTests.requirement
    contract=dev.DevelopmentTests.contract
    def test_review_work_retains_subset_and_requirement_change_holds_execution(self):
        self.setup_review(); ref=self.requirement()
        cp=self.checkpoint(self.cp['change'],context={**self.cp['state']['context'],'requirement_refs':[ref]})
        # New change scopes work explicitly; old change remains unlinked.
        c=self.begin(cp['state'],['result.json']);r=self.submit(c)
        self.report(r);self.complete(r,self.claim(r))
        contract={**self.contract(),'input_snapshot':cp['state']['snapshot']}
        work=self.mentor.call('propose_review_work',{'submission_id':r['id'],'finding_ids':['f1'],'contract':contract})
        self.assertEqual(work['requirement_refs'],[ref])
        self.assertTrue(self.call('check_execution',{'contract_id':work['id']})['allowed'])
        e=self.call('start_execution',{'contract_id':work['id'],'version':work['version']})['execution']
        self.requirement(ref['revision_id'])
        live=next(x for x in self.detail()['executions'] if x['id']==e['id'])
        self.assertFalse(live['continuation_allowed'])
        result=dev.DevelopmentTests.finish(self,e,output_snapshot=self.artifact({'input.txt':'modified','result.json':'{"verdict":"pass"}'}))
        self.assertFalse(result['valid']);self.assertIn('stale_requirements',result['reasons'])
        self.assertFalse(self.call('get_change_review',{'submission_id':r['id']})['applicable'])
    def test_pending_review_holds_and_reassessed_submission_resumes(self):
        self.setup_review();old=self.requirement()
        cp=self.checkpoint(self.cp['change'],context={**self.cp['state']['context'],'requirement_refs':[old]})
        r=self.submit(cp['change']);new=self.requirement(old['revision_id'])
        self.assertFalse(self.call('get_change_review',{'submission_id':r['id']})['applicable'])
        self.fault('stale_basis',lambda:self.claim(r))
        cp=self.checkpoint(cp['change'],context={**cp['state']['context'],'requirement_refs':[new]})
        fresh=self.submit(cp['change']);self.report(fresh)
        self.assertEqual(self.complete(fresh,self.claim(fresh))['status'],'completed')

    def test_exploratory_review_does_not_gain_all_state_requirements(self):
        self.setup_review(); ref=self.requirement()
        cp=self.checkpoint(self.cp['change'],context={**self.cp['state']['context'],'requirement_refs':[ref]})
        c=self.call('begin_change',{'state_id':cp['state']['id'],'title':'Explore','purpose':'Research','write_scope':['result.json'],
            'dependencies':[],'assignee':'admin','requirement_refs':[]})
        r=self.submit(c);self.report(r);self.complete(r,self.claim(r))
        work=self.mentor.call('propose_review_work',{'submission_id':r['id'],'finding_ids':['f1'],
            'contract':{**self.contract(),'input_snapshot':cp['state']['snapshot']}})
        self.assertEqual(work['requirement_refs'],[])

import hashlib
import importlib.util
import unittest
from gantry.hardware import screen_report

class NativeCADHandoffTests(HardwareTraceTests):
    @unittest.skipUnless(importlib.util.find_spec('OCP'),'Optional CAD runtime unavailable')
    def test_native_cad_measurement_publish_requirement_context(self):
        from gantry import cad_kernel as cq
        ref=self.requirement(); root=self.root/'native';root.mkdir()
        for name,x in [('a',0),('b',4)]:
            cq.export_step(cq.box(1,1,1).translate((x,0,0)),str(root/(name+'.step')))
        parts=[{'id':name,'path':name+'.step','sha256':hashlib.sha256((root/(name+'.step')).read_bytes()).hexdigest()} for name in ['a','b']]
        request={'parts':parts,'pairs':[['a','b']],'clearance':.1,'overlap_tolerance':1e-6,'unit':'mm','frame':'assembly'}
        check={'id':'travel','scope':'placement','components':['assembly'],'required':True,
            'inputs':['a.step','b.step'],'report':'clearance.json','requirement_refs':[ref],
            'conditions':{'unit':'mm','frame':'assembly','clearance':.1,'overlap_tolerance':1e-6,'pairs':[['a','b']],
                          'parts':{'a':'a.step','b':'b.step'}},
            'evaluator':{'name':'gantry.cad-screen','version':'1'},'environment':{'cad_backend':cq.BACKEND},
            'criteria':[{'metric':'violating_pairs','unit':'count','max':0}]}
        plan={'version':1,'components':[{'id':'assembly','role':'motion','assembly':'robot','paths':['a.step','b.step']}],'checks':[check]}
        (root/'physical-plan.json').write_text(json.dumps(plan));(root/'input.txt').write_text('initial')
        from gantry.continuity_adapter import capture_workspace
        artifact,_=capture_workspace(self.client,root,'native-baseline','root')
        self.snapshot=artifact['revision_id'];self.session=self.connect();base=self.initialize()
        c=self.begin(base,['clearance.json']);cp=self.call('checkpoint_change',{'change_id':c['id'],'version':c['version'],
            'snapshot':self.snapshot,'summary':'Linked CAD','rationale':'Static clearance','unfinished':['load'],
            'work_status':'working','capture':{'scope':'files','missing':[]},'context':{**base['context'],'requirement_refs':[ref]}})
        report=screen_report(root,request,check)
        self.assertEqual(report['requirement_refs'],[ref])
        self.assertEqual(report['measurements']['violating_pairs']['value'],0)
        (root/'clearance.json').write_text(json.dumps(report))
        done=publish(self.client,cp['state']['id'],c['id'],cp['change']['version'],root,'physical-plan.json','native-publish')
        self.call('select_development_state',{'state_id':done['state']['id'],'version':self.detail()['session']['version'],'reason':'Review measured result'})
        ctx=self.call('mentor_context',{'session_id':self.session['id']})
        self.assertEqual(ctx['development']['engineering']['checks'][0]['effective_status'],'pass')
        item=ctx['development']['requirement_coverage']['items'][0]
        self.assertEqual(item['status'],'unverified');self.assertEqual(item['gaps'],['load'])
        self.assertTrue(self.call('replay')['matched'])

class CrewHandoffTests(trace.CrewRequirementTests):
    def linked_state(self,ref):
        c=self.call('begin_change',{'state_id':self.base['id'],'title':'Reassess','purpose':'Updated requirement',
            'write_scope':['mechanical.txt'],'dependencies':[],'assignee':'admin'})
        self.base=self.call('checkpoint_change',{'change_id':c['id'],'version':c['version'],'snapshot':self.base['snapshot'],
            'summary':'Reassessed','rationale':'New baseline','unfinished':[],'work_status':'working',
            'capture':{'scope':'files','missing':[]},'context':{**self.base['context'],'requirement_refs':[ref]}})['state']
    def test_changed_requirement_new_assignment_resumes(self):
        ref=self.requirement();self.linked_state(ref)
        old=self.task('designer')
        with self.worker('designer') as worker:
            client=self.clients['designer']
            claim=client.call('claim_bot_task',{'task_id':old['id'],'version':old['version'],'runtime_fence':worker.runtime['fence']})
            new=self.requirement(ref['revision_id'])
            self.fault('stale_basis',lambda:client.call('check_bot_task',{'task_id':old['id'],'fence':claim['task']['fence']}))
            self.call('cancel_bot_task',{'task_id':old['id'],'version':claim['task']['version'],'reason':'Reassess requirement'})
            self.linked_state(new);task=self.task('designer')
            claim=client.call('claim_bot_task',{'task_id':task['id'],'version':task['version'],'runtime_fence':worker.runtime['fence']})
            self.assertEqual(claim['context']['task']['requirement_refs'],[new])
            done=client.call('finish_bot_task',{'task_id':task['id'],'fence':claim['task']['fence'],
                'report':{k:v for k,v in self.answer().items() if k!='edits'}})
            self.assertEqual(done['task']['status'],'completed');self.assertFalse(done['formal_adoption'])
        self.assertTrue(self.call('replay')['matched'])
    def test_consultation_and_child_inherit_exploration_subset(self):
        self.linked_state(self.requirement());task=self.task('lead',requirement_refs=[])
        with self.worker('lead') as worker:
            client=self.clients['lead']
            claim=client.call('claim_bot_task',{'task_id':task['id'],'version':task['version'],'runtime_fence':worker.runtime['fence']})
            asked=client.call('ask_bot',{'task_id':task['id'],'fence':claim['task']['fence'],'to_bot_id':'control',
                'question':'Explore alternatives','evidence':[self.base['id']]})
            self.assertEqual(asked['response_task']['requirement_refs'],[])
            done=client.call('finish_bot_task',{'task_id':task['id'],'fence':claim['task']['fence'],
                'report':{k:v for k,v in self.answer(status='waiting',assignments=[self.assignment('mechanical')]).items() if k!='edits'}})
            children=self.call('get_bot_task',{'task_id':task['id']})['children']
            self.assertTrue(children);self.assertEqual(children[0]['requirement_refs'],[])
    def test_scoped_bot_can_publish_physical_evidence_without_admin_api(self):
        ref=self.requirement();root=self.root/'physical';root.mkdir()
        check={'id':'load','scope':'structural','components':['part'],'required':True,'inputs':['mechanical.txt'],
            'report':'control.txt','conditions':{'force':1},'evaluator':{'name':'fixture','version':'1'},
            'environment':{'kind':'fixture'},'criteria':[{'metric':'stress','unit':'MPa','max':50}],'requirement_refs':[ref]}
        plan={'version':1,'components':[{'id':'part','role':'support','assembly':'robot','paths':['mechanical.txt']}],'checks':[check]}
        files={'mechanical.txt':'1','control.txt':'1','physical-plan.json':json.dumps(plan)}
        c=self.call('begin_change',{'state_id':self.base['id'],'title':'Prepare','purpose':'Pinned plan',
            'write_scope':['physical-plan.json'],'dependencies':[],'assignee':'admin'})
        self.base=self.call('checkpoint_change',{'change_id':c['id'],'version':c['version'],'snapshot':self.artifact(files),
            'summary':'Plan','rationale':'Fixture','unfinished':[],'work_status':'working','capture':{'scope':'files','missing':[]},
            'context':{**self.base['context'],'requirement_refs':[ref]}})['state']
        for name,value in files.items():(root/name).write_text(value)
        (root/'control.txt').write_text(json.dumps({'status':'completed','inputs':{'mechanical.txt':hashlib.sha256(b'1').hexdigest()},
            'conditions':check['conditions'],'evaluator':check['evaluator'],'environment':check['environment'],
            'requirement_refs':[ref],'measurements':{'stress':{'value':40,'unit':'MPa'}},'limitations':['Fixture only']}))
        task=self.task('lead')
        from gantry.crew_runtime import _execute
        with self.worker('lead') as worker:
            client=self.clients['lead']
            claim=client.call('claim_bot_task',{'task_id':task['id'],'version':task['version'],'runtime_fence':worker.runtime['fence']})
            lease={'task_id':task['id'],'fence':claim['task']['fence']}
            result=_execute(client,claim['context'],lease,{},'publish_physical',{'plan_path':'physical-plan.json'},root,root,'bot-physical')
            check=result['state']['context']['environment']['engineering']['checks'][0]
            self.assertEqual(check['status'],'pass');self.assertEqual(check['requirement_refs'],[ref])
            self.assertEqual(result['change']['requirement_refs'],[ref])
            changed=copy.deepcopy(result['state']['context']);changed['constraints']=[]
            self.fault('scope_denied',lambda:client.call('checkpoint_bot_task',{**lease,
                'snapshot':result['state']['snapshot'],'summary':'Invalid','rationale':'Invalid','unfinished':[],
                'capture':{'scope':'files','missing':[]},'context':changed}))
            self.requirement(ref['revision_id'])
            self.fault('stale_basis',lambda:_execute(client,claim['context'],lease,{},'publish_physical',
                {'plan_path':'physical-plan.json'},root,root,'stale-bot'))

class RunnerRequirementTests(trace.TraceabilityIntegrationTests):
    def test_real_process_is_cancelled_when_requirement_changes(self):
        import sys,time
        from concurrent.futures import ThreadPoolExecutor
        from gantry.runner import run_contract
        from gantry.model import digest
        state=self.linked()
        self.call('select_development_state',{'state_id':state['id'],'version':self.detail()['session']['version'],'reason':'Run linked state'})
        self.recipe={'argv':[sys.executable,'-c','import pathlib,time; pathlib.Path("result.json").write_text(\'{"verdict":"pass"}\'); time.sleep(10)'], 'timeout_seconds':20}
        d=self.detail()['session']
        self.call('configure_development',{'session_id':d['id'],'version':d['version'],'reason':'Local cancellation test',**self.policy()})
        ctx=self.call('mentor_context',{'session_id':d['id']})
        m=next(m for m in ctx['milestones'] if m['status']=='pending' and m['generation']==ctx['session']['generation'])
        contract=self.call('mentor_propose',{'session_id':d['id'],'milestone_id':m['id'],'input_state':state['id'],
            'evidence':[state['id']],'contract':{**self.contract(),'input_snapshot':state['snapshot']}})
        with ThreadPoolExecutor(max_workers=1) as pool:
            job=pool.submit(run_contract,self.client,contract['id'],{'test':self.recipe},self.root/'running',.1)
            deadline=time.monotonic()+8
            while not list((self.root/'running').glob('**/workspace/result.json')) and time.monotonic()<deadline:
                time.sleep(.05)
            self.assertTrue(list((self.root/'running').glob('**/workspace/result.json')))
            self.requirement(self.ref['revision_id'])
            result=job.result(timeout=12)
        self.assertEqual(result['status'],'cancelled')
        self.assertFalse(result['valid']);self.assertIn('stale_requirements',result['reasons'])
        self.assertTrue(self.call('replay')['matched'])
