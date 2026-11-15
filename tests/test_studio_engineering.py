import unittest
import test_studio as fixtures


class StudioEngineeringTests(unittest.TestCase):
    def setUp(self):
        self.c=fixtures.StudioTests();self.c.setUp();self.addCleanup(self.c.tearDown)

    def test_assessment_stays_bound_to_selected_work_state_and_refreshes_on_new_evidence(self):
        c=self.c; _,base,work=c.setup_work(); cp=c.checkpoint(work)
        current=c.call('studio_work',{'work_id':work['id']})
        self.assertEqual(current['design_assessment']['state_id'],cp['state']['id'])
        old=c.call('studio_work',{'work_id':work['id'],'state_id':base['id']})
        self.assertEqual(old['design_assessment']['baseline_state_id'],base['id'])
        self.assertEqual(old['design_assessment']['state_id'],base['id'])
        self.assertEqual(old['design_assessment']['changes'],[])
        view=current['selected']; c.call('record_evidence_view',{'state_id':cp['state']['id'],'subject_id':'robot',
            'profile':'fixture','extractor':'fixture','sources':[{'revision_id':view['state']['snapshot'],
                'path':'input.txt','sha256':view['manifest']['input.txt']['hash'],'locator':'text'}],
            'fields':[{'name':'note','value':'modified','classification':'declared','source_index':0,'method':'fixture'}],'missing':[]})
        refreshed=c.call('studio_work',{'work_id':work['id']})
        self.assertNotEqual(refreshed['activity_token'],current['activity_token'])
        self.assertEqual(refreshed['selected']['state']['id'],cp['state']['id'])
        self.assertEqual(c.call('studio_work',{'work_id':work['id'],'activity_only':True})['activity_token'],refreshed['activity_token'])
        self.assertEqual(refreshed['selected']['status']['adoption'],'unadopted')

    def test_saved_verification_plan_is_scoped_to_work_and_preserves_state(self):
        from test_bot_learning import BotLearningTests
        c=BotLearningTests();c.setUp();self.addCleanup(c.tearDown)
        task=c.task('designer')
        with c.worker('designer') as worker:
            ref=c.claimed(worker,task)
            c.clients['designer'].call('checkpoint_bot_task',{**ref,'snapshot':c.base['snapshot'],
                'summary':'Plan checkpoint','rationale':'Record input before planning','unfinished':['Verification'],
                'capture':{'scope':'Saved fixture files','missing':[]}})
            task_view=c.clients['designer'].call('get_bot_task',{'task_id':task['id']})
            work=task_view['own_change']; before=c.owner.call('studio_work',{'work_id':work['id']})
            c.clients['designer'].call('record_bot_action',{**ref,'kind':'plan_verification','details':{
                'result':{'status':'planned','input_state':c.base['id'],'question':'Check nominal fit',
                    'tool':{'name':'verify'},'execution':{'performed':False},'formal_adoption':False}}})
            after=c.owner.call('studio_work',{'work_id':work['id']})
            plans=after['verification_plans'];self.assertEqual(len(plans['items']),1)
            self.assertEqual(plans['items'][0]['result']['input_state'],c.base['id'])
            self.assertFalse(plans['items'][0]['result']['execution']['performed'])
            self.assertNotEqual(before['activity_token'],after['activity_token'])
            other=c.owner.call('begin_change',{'state_id':c.base['id'],'title':'Other','purpose':'Independent',
                'write_scope':['control.txt'],'dependencies':[],'assignee':'admin'})
            self.assertEqual(c.owner.call('studio_work',{'work_id':other['id']})['verification_plans']['items'],[])
