"""Supervisor invariants: learning failures cannot masquerade as completion."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('study_supervision',Path(__file__).parents[1]/'examples/crew-memory-study/run.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class SupervisionTests(unittest.TestCase):
    def test_reflection_hold_does_not_stop_other_work_and_is_deduplicated(self):
        warnings=[];errors=[]
        held={'status':'held','reflection_id':'reflection-a','reason':'invalid_input'}
        self.assertFalse(m.classify_worker_result('mechanical',held,warnings,errors))
        self.assertFalse(m.classify_worker_result('mechanical',held,warnings,errors))
        self.assertFalse(m.classify_worker_result('control',{'status':'completed'},warnings,errors))
        self.assertEqual(len(warnings),1);self.assertEqual(errors,[])
        self.assertTrue(m.classify_worker_result('lead',{'status':'held','job_id':'job-a'},warnings,errors))
        self.assertEqual(len(errors),1)
    def test_reflection_exception_is_local_but_shared_quota_or_authority_is_not(self):
        for code in ['invalid_input','provider_timeout','context_limit','provider_failed']:
            self.assertFalse(m.inference_failure_fatal('reflect_on_experience',code))
            self.assertTrue(m.inference_failure_fatal('action',code))
        for error in [ValueError('Malformed JSON'), OSError('Receipt storage unavailable')]:
            self.assertFalse(m.inference_failure_fatal('reflect_on_experience',error))
            self.assertTrue(m.inference_failure_fatal('action',error))
        for code in ['subscription_rate_limited','unauthorized','runtime_offline','observation_timeout']:
            self.assertTrue(m.inference_failure_fatal('reflect_on_experience',code))
    def test_primary_success_requires_same_engineering_review_and_integrity(self):
        result=dict(root_status='completed',engineering_accepted=True,workflow_accepted=True,
            within_observation_window=True,errors=[],pending_reflections=1,
            verify={'valid':True},replay={'matched':True})
        self.assertTrue(m.development_accepted(result))
        for key in ['engineering_accepted','workflow_accepted','within_observation_window']:
            self.assertFalse(m.development_accepted({**result,key:False}))
        self.assertFalse(m.development_accepted({**result,'root_status':'failed'}))
        self.assertFalse(m.development_accepted({**result,'errors':[{'code':'provider_failed'}]}))
    def test_activity_distinguishes_memory_edit_and_verification(self):
        self.assertEqual(m.activity('reflect_on_experience',{}),'memory_update')
        self.assertEqual(m.activity('plan_from_experience',{}),'judgment')
        self.assertEqual(m.activity('action',{'action':'edit'}),'editing')
        self.assertEqual(m.activity('action',{'action':'tool'}),'verification')
        self.assertEqual(m.activity('action',{'action':'ask'}),'consultation')

    def test_actual_threaded_supervisor_continues_after_reflection_hold(self):
        from unittest.mock import patch
        import tempfile, threading
        warnings_seen=threading.Event(); developed=threading.Event()
        class Owner:
            def call(self,name,args=None):
                if name=='get_bot_task':return {'task':{'status':'completed' if developed.is_set() else 'working'}}
                if name=='verify':return {'valid':True}
                if name=='replay':return {'matched':True}
                raise AssertionError(name)
        class Worker:
            def __init__(self,client,config,*args):self.bot=config['bot_id']
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def tick(self):
                if self.bot=='mechanical':
                    warnings_seen.set()
                    return [{'status':'held','reflection_id':'r','reason':'invalid_input'}]
                if self.bot=='control':
                    assert warnings_seen.wait(2)
                    developed.set()
                return []
        owner=Owner(); task={'id':'root','session_id':'s'}
        config={bot:{'bot_id':bot} for bot in m.BOTS}
        views={'root':{'task':{'status':'completed','state_id':'s'}}}
        with tempfile.TemporaryDirectory() as tmp, patch.object(m,'setup',return_value=(owner,{b:None for b in m.BOTS},config,task,[])), patch.object(m,'BotWorker',Worker), patch.object(m,'collect',return_value=(views,{}, {'mechanical':[{'status':'pending'}]})), patch.object(m,'final_audit',return_value={'accepted':True}), patch.object(m,'workflow_check',return_value={'accepted':True}), patch.object(m,'runtime_spans',return_value=[]):
            result=m.run({},Path(tmp),'recall','fake-test-only',60)
            self.assertTrue(developed.is_set())
            self.assertTrue(result['development_accepted'])
            self.assertFalse(result['all_pipeline_accepted'])
            self.assertEqual(result['pending_reflections'],1)
            self.assertEqual(len(result['reflection_warnings']),1)
            self.assertEqual(result['errors'],[])
