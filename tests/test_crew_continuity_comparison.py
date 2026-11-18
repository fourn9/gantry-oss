import unittest
from copy import deepcopy


def result():
    return {'root_status':'completed','validation':{'accepted':True},'workflow_accepted':True,
            'verify':{'valid':True},'replay':{'matched':True},'within_observation_window':True,
            'errors':[],'pending_reflections':0,'started_at_ns':10**9,'finished_at_ns':9*10**9,
            'model':'fixed','reasoning_effort':'low','case_hash':'same','condition':'recall'}


def span(start,end,phase='action',category='work',actor='bot'):
    return {'id':str(start)+phase,'actor_type':actor,'bot_id':'worker' if actor=='bot' else None,
            'phase':phase,'category':category,'started_at_ns':start*10**9,'finished_at_ns':end*10**9}


class ContinuityComparisonTests(unittest.TestCase):
    def score(self,r=None,calls=(),spans=(),end=10):
        from gantry.crew_continuity_comparison import score
        return score(r or result(),{'started_at_ns':0,'finished_at_ns':end*10**9,
            'monotonic_seconds':end},calls,spans)

    def test_primary_includes_setup_and_final_audit_not_only_bot_time(self):
        s=self.score();self.assertTrue(s['success']);self.assertEqual(s['completion_seconds'],10)

    def test_reflection_only_failure_is_separate_but_task_errors_still_fail(self):
        r=result();r['pending_reflections']=1;r['errors']=[{'result':{'reflection_id':'r','reason':'invalid_input'}}]
        s=self.score(r);self.assertTrue(s['success']);self.assertFalse(s['memory_pipeline_complete'])
        r['errors'].append({'result':{'job_id':'task','reason':'experiment_stopped'}})
        self.assertFalse(self.score(r)['success'])

    def test_early_stop_or_timeout_is_censored_not_fast_success(self):
        from gantry.crew_continuity_comparison import compare
        r=result();r['root_status']='running';a=self.score(r,end=2);b=self.score(end=10)
        report=compare({'before':[a,deepcopy(a)],'after':[b,deepcopy(b)]})
        self.assertIsNone(report['speed_ratio_before_over_after']);self.assertEqual(report['arms']['before']['successes'],0)
        r=result();r['within_observation_window']=False;self.assertFalse(self.score(r)['success'])

    def test_real_calls_replace_model_spans_and_nested_action_wrappers(self):
        calls=[{'operation':'reflect_on_experience','bot_id':'worker','started_at_ns':2*10**9,'finished_at_ns':5*10**9,'output':{}}]
        spans=[span(0,8),span(2,5,'model','judgment'),span(5,6,'tool'),span(7,8,'wait','waiting')]
        s=self.score(calls=calls,spans=spans);t=s['timing']
        self.assertEqual(t['by_activity']['memory_update']['union_seconds'],3)
        self.assertEqual(t['by_activity']['verification']['union_seconds'],1)
        self.assertEqual(t['by_activity']['waiting']['union_seconds'],1)
        self.assertEqual(t['dropped_container_spans'],1)
        self.assertEqual(sum(t['exclusive_wall_seconds'].values()),10)

    def test_model_only_container_and_missing_final_audit_do_not_invent_success(self):
        r=result();r['validation']=None
        calls=[{'operation':'action','bot_id':'worker','started_at_ns':2*10**9,
                'finished_at_ns':5*10**9,'output':{'action':'edit'}}]
        s=self.score(r,calls=calls,spans=[span(0,8)])
        self.assertFalse(s['success'])
        self.assertEqual(s['timing']['by_activity']['editing']['union_seconds'],3)
        self.assertEqual(s['timing']['dropped_container_spans'],1)

    def test_actor_overlap_and_unknown_rework_are_explicit(self):
        s=self.score(spans=[span(0,5,'edit'),span(3,7,'repair',actor='parent')])
        self.assertEqual(s['timing']['exclusive_wall_seconds']['overlap'],2)
        self.assertEqual(s['timing']['by_actor']['parent']['union_seconds'],4)
        self.assertIsNone(s['timing']['host_sleep_seconds']);self.assertEqual(s['timing']['rework']['unknown']['union_seconds'],7)

    def test_incomparable_models_or_memory_conditions_reject_speed_claim(self):
        from gantry.crew_continuity_comparison import compare
        a=self.score();b=self.score();b['model']='different'
        with self.assertRaises(ValueError):compare({'before':[a,a],'after':[b,b]})

    def test_wrapper_audit_deadline_applies_equally_to_old_and_new_result_windows(self):
        r=result();r['started_at_ns']=10**9;r['finished_at_ns']=10*10**9
        # Baseline's result stopped before verify/replay; wrapper records all of it.
        s=self.score(r,end=1802)
        self.assertFalse(s['within_observation_window']);self.assertFalse(s['success'])

    def test_action_intents_cover_delegation_mixed_reads_and_tool_leaf(self):
        from gantry.crew_continuity_comparison import activity
        import json
        def call(action,args=None):return {'operation':'action','output':{'action':action,
            'arguments_json':json.dumps(args or {})}}
        self.assertEqual(activity(call('finish',{'assignments':[{'bot_id':'peer'}]})),'consultation')
        self.assertEqual(activity(call('finish')),'recording')
        self.assertEqual(activity(call('integrate')),'editing')
        self.assertEqual(activity(call('publish_physical')),'verification')
        self.assertEqual(activity(call('observe',{'requests':[{'action':'read'},{'action':'inspect'}]})),'unknown')
        self.assertEqual(activity(call('inspect')),'consultation')
        leaf=span(2,3);leaf['action']='edit'
        s=self.score(spans=[leaf]);self.assertEqual(s['timing']['by_activity']['editing']['union_seconds'],1)

    def test_payloads_do_not_leak_and_completed_ratio_is_descriptive(self):
        from gantry.crew_continuity_comparison import compare
        r=result();r['secret']='private';a=self.score(r,end=10);b=self.score(end=5)
        c=compare({'before':[a,a],'after':[b,b]});self.assertEqual(c['speed_ratio_before_over_after'],2)
        self.assertNotIn('private',str(c));self.assertIn('preliminary',c['interpretation'])
