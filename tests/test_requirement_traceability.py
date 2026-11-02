import copy
import unittest
from gantry.requirement_traceability import assess, validate_refs
from gantry.model import Fault

class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.ref={'requirement_id':'motion','revision_id':'rev_motion'}
        req={'id':'motion','revision_id':'rev_motion','type':'requirement','zone':'root',
             'previous_revision':None,'data':{'description':'Reach target','verification_checks':['travel','load']}}
        self.s={'entries':{'motion':req},'revisions':{'rev_motion':req}}
        self.context={'requirement_refs':[self.ref]}
        self.checks=[{'id':i,'effective_status':'pass','requirement_refs':[self.ref]} for i in ['travel','load']]
    def view(self): return assess(self.s,self.context,{'checks':self.checks})['items'][0]
    def test_all_checks_required_and_explicit_bindings(self):
        self.assertEqual(self.view()['status'],'met')
        self.checks.pop()
        self.assertEqual(self.view()['status'],'unverified')
        self.checks[0]['effective_status']='fail'
        self.assertEqual(self.view()['status'],'unmet')
        self.checks[0]['requirement_refs']=[]
        self.assertEqual(self.view()['status'],'unverified')
    def test_changed_requirement_keeps_pinned_result(self):
        self.s['entries']['motion']={**self.s['entries']['motion'],'revision_id':'rev_new','previous_revision':'rev_motion'}
        self.s['revisions']['rev_new']=self.s['entries']['motion']
        self.assertEqual(self.view()['status'],'needs_review')
        self.assertEqual(self.view()['pinned_status'],'met')
    def test_draft_revision_and_mismatched_id_rejected(self):
        self.s['revisions']['rev_draft']={**self.s['entries']['motion'],'revision_id':'rev_draft'}
        with self.assertRaises(Fault): validate_refs(self.s,[{**self.ref,'revision_id':'rev_draft'}])
        with self.assertRaises(Fault): validate_refs(self.s,[{**self.ref,'requirement_id':'other'}])
    def test_empty_plan_and_legacy_never_pass(self):
        self.s['entries']['motion']['data']['verification_checks']=[]
        self.assertEqual(self.view()['status'],'unverified')
        result=assess(self.s,{'requirements':['legacy text']},{'checks':[]})
        self.assertFalse(result['configured'])
        self.assertEqual(result['unlinked_requirements'],['legacy text'])

import test_continuity as fixtures

class TraceabilityIntegrationTests(unittest.TestCase):
    setUp=fixtures.ContinuityTests.setUp
    tearDown=fixtures.ContinuityTests.tearDown
    call=fixtures.ContinuityTests.call
    artifact=fixtures.ContinuityTests.artifact
    policy=fixtures.ContinuityTests.policy
    connect=fixtures.ContinuityTests.connect
    detail=fixtures.ContinuityTests.detail
    initialize=fixtures.ContinuityTests.initialize
    begin=fixtures.ContinuityTests.begin
    checkpoint=fixtures.ContinuityTests.checkpoint
    contract=fixtures.ContinuityTests.contract
    fault=fixtures.ContinuityTests.fault
    def requirement(self, previous=None):
        p=self.call('propose',{'title':'Motion requirement','changes':[{'id':'motion','type':'requirement','zone':'root',
            'expected_revision':previous,'data':{'description':'Travel under load','verification_checks':['travel','load']}}]})
        args={'proposal_id':p['id'],'version':p['version']}
        self.call('submit',args);self.call('endorse',{**args,'reason':'Required scope'})
        self.call('review_adoption',{**args,'verdict':'approve','reason':'Approve requirement definition'})
        self.call('commit',args)
        return {'requirement_id':'motion','revision_id':p['changes'][0]['revision_id']}
    def linked(self):
        self.ref=self.requirement(); base=self.initialize()
        ctx=copy.deepcopy(base['context']);ctx['requirement_refs']=[self.ref]
        manifest=self.call('get_development_state',{'state_id':base['id']})['manifest']
        h=manifest['input.txt']['hash']
        ctx['environment']['engineering']={'version':1,'components':[{'id':'arm','role':'motion','assembly':'robot','inputs':{'input.txt':h}}],
            'checks':[{'id':i,'scope':'motion','components':['arm'],'required':True,'status':'pass',
                       'inputs':{'input.txt':h},'evidence':{'input.txt':h},'requirement_refs':[self.ref]} for i in ['travel','load']]}
        return self.checkpoint(self.begin(base),files={'input.txt':'initial'},context=ctx)['state']
    def test_full_path_stale_files_requirements_and_replay(self):
        state=self.linked()
        view=lambda sid:self.call('get_development_state',{'state_id':sid})
        self.assertEqual(view(state['id'])['requirement_coverage']['items'][0]['status'],'met')
        self.assertEqual(view(state['id'])['status']['adoption'],'unadopted')
        change=self.begin(state);self.assertEqual(change['requirement_refs'],[self.ref])
        changed=self.checkpoint(change)['state']
        self.assertEqual(view(changed['id'])['requirement_coverage']['items'][0]['status'],'unverified')
        self.requirement(self.ref['revision_id'])
        item=view(state['id'])['requirement_coverage']['items'][0]
        self.assertEqual((item['status'],item['pinned_status']),('needs_review','met'))
        self.assertTrue(self.call('replay')['matched'])
    def test_integrating_new_links_into_legacy_state(self):
        ref=self.requirement(); base=self.initialize()
        change=self.begin(base)
        cp=self.checkpoint(change,files={'input.txt':'initial'},context={**base['context'],'requirement_refs':[ref]})
        shared=self.call('share_change',{'change_id':change['id'],'version':cp['change']['version']})['change']
        result=self.call('integrate_changes',{'state_id':base['id'],
            'changes':[{'id':shared['id'],'version':shared['version']}],'summary':'Integrate linked scope'})
        self.assertTrue(result['integrated'])
        self.assertEqual(result['state']['context']['requirement_refs'],[ref])
        self.assertTrue(self.call('replay')['matched'])

    def test_explicit_exploration_and_mentor_execution_hold(self):
        state=self.linked()
        change=self.call('begin_change',{'state_id':state['id'],'title':'Explore','purpose':'Research',
            'write_scope':['input.txt'],'dependencies':[],'assignee':'admin','requirement_refs':[]})
        self.assertEqual(change['requirement_refs'],[])
        self.call('select_development_state',{'state_id':state['id'],'version':self.detail()['session']['version'],'reason':'Continue'})
        ctx=self.call('mentor_context',{'session_id':self.session['id']})
        self.assertEqual(ctx['development']['requirement_coverage']['items'][0]['status'],'met')
        c=self.call('mentor_propose',{'session_id':self.session['id'],'milestone_id':next(m['id'] for m in ctx['milestones'] if m['generation']==ctx['session']['generation'] and m['status']=='pending'),
            'input_state':state['id'],'evidence':[state['id']],'contract':{**self.contract(),'input_snapshot':state['snapshot']}})
        self.assertEqual(c['requirement_refs'],[self.ref])
        self.requirement(self.ref['revision_id'])
        self.assertIn('stale_requirements',self.call('check_execution',{'contract_id':c['id']})['reasons'])

import test_bot_development as bots

class CrewRequirementTests(unittest.TestCase):
    setUp=bots.BotDevelopmentTests.setUp
    tearDown=bots.BotDevelopmentTests.tearDown
    scope=bots.BotDevelopmentTests.scope
    artifact=bots.BotDevelopmentTests.artifact
    assignment=bots.BotDevelopmentTests.assignment
    task=bots.BotDevelopmentTests.task
    worker=bots.BotDevelopmentTests.worker
    answer=bots.BotDevelopmentTests.answer
    infer=bots.BotDevelopmentTests.infer
    fault=bots.BotDevelopmentTests.fault
    requirement=TraceabilityIntegrationTests.requirement
    def call(self,*a,**kw): return self.owner.call(*a,**kw)
    def test_crew_receives_requirement_and_holds_stale_task(self):
        ref=self.requirement()
        change=self.call('begin_change',{'state_id':self.base['id'],'title':'Link','purpose':'Link requirement',
            'write_scope':['mechanical.txt'],'dependencies':[],'assignee':'admin'})
        ctx={**self.base['context'],'requirement_refs':[ref]}
        self.base=self.call('checkpoint_change',{'change_id':change['id'],'version':change['version'],
            'snapshot':self.base['snapshot'],'summary':'Linked','rationale':'Explicit requirement',
            'unfinished':[],'work_status':'working','capture':{'scope':'files','missing':[]},'context':ctx})['state']
        task=self.task('designer')
        self.assertEqual(task['requirement_refs'],[ref])
        detail=self.clients['designer'].call('get_bot_task',{'task_id':task['id']})
        self.assertEqual(detail['development']['requirement_coverage']['items'][0]['status'],'unverified')
        with self.worker('designer') as worker:
            args={'task_id':task['id'],'version':task['version'],'runtime_fence':worker.runtime['fence']}
            claim=self.clients['designer'].call('claim_bot_task',args)
            self.requirement(ref['revision_id'])
            self.fault('stale_basis',lambda:self.clients['designer'].call('check_bot_task',
                {'task_id':task['id'],'fence':claim['task']['fence']}))
    def test_bot_cannot_read_requirement_outside_delegated_zone(self):
        for change in [
            {'id':'restricted','type':'zone','zone':'root','data':{'owner':'admin','participation':'participating'}},
            {'id':'private_requirement','type':'requirement','zone':'restricted','data':{'description':'Restricted design criterion','verification_checks':[]}}]:
            p=self.call('propose',{'title':'Scoped fixture','changes':[change]})
            a={'proposal_id':p['id'],'version':p['version']}
            self.call('submit',a);self.call('endorse',{**a,'reason':'Fixture'})
            self.call('review_adoption',{**a,'verdict':'approve','reason':'Fixture'})
            self.call('commit',a)
        ref={'requirement_id':'private_requirement','revision_id':p['changes'][0]['revision_id']}
        c=self.call('begin_change',{'state_id':self.base['id'],'title':'Link','purpose':'Scoped',
            'write_scope':['mechanical.txt'],'dependencies':[],'assignee':'admin'})
        self.base=self.call('checkpoint_change',{'change_id':c['id'],'version':c['version'],
            'snapshot':self.base['snapshot'],'summary':'Scoped state','rationale':'Fixture','unfinished':[],
            'work_status':'working','capture':{'scope':'files','missing':[]},
            'context':{**self.base['context'],'requirement_refs':[ref]}})['state']
        task=self.task('designer')
        self.fault('unauthorized',lambda:self.clients['designer'].call('get_bot_task',{'task_id':task['id']}))
