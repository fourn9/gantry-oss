"""A timeline must not count concurrent Bot seconds as elapsed seconds."""
import unittest


def interval(key, bot, start, end, category='work', rework=False, **extra):
    return {'id':key,'actor_type':'bot','bot_id':bot,'category':category,
        'phase':'model' if category=='judgment' else 'action',
        'started_at_ns':int(start*1e9), 'finished_at_ns':None if end is None else int(end*1e9),
        'rework':rework,**extra}


class CrewExperimentTimingTests(unittest.TestCase):
    def test_parallel_seconds_and_category_overlap_are_explicit(self):
        from gantry.crew_experiment_timing import summarize
        spans=[interval('a','lead',0,6,'judgment'),interval('b','mechanical',2,8),
               interval('c','lead',8,9,'consultation')]
        report=summarize(spans,0,10*10**9)
        self.assertEqual(report['summed_span_seconds'],13)
        self.assertEqual(report['active_union_seconds'],9)
        self.assertEqual(report['uncovered_seconds'],1)
        self.assertEqual(report['exclusive_wall_seconds']['overlap'],4)
        self.assertEqual(report['exclusive_wall_seconds']['judgment'],2)
        self.assertEqual(report['exclusive_wall_seconds']['work'],2)
        self.assertEqual(sum(report['exclusive_wall_seconds'].values()),10)
        self.assertEqual(report['per_bot']['lead']['active_union_seconds'],7)

    def test_parent_wait_and_rework_are_separate_axes(self):
        from gantry.crew_experiment_timing import summarize
        spans=[interval('a','lead',0,5,'judgment',None),
               interval('b','worker',2,7,'work',True),
               interval('c','lead',5,8,'waiting'),
               interval('d',None,7,9,'work',actor_type='parent',phase='repair')]
        report=summarize(spans,0,10*10**9)
        self.assertEqual(report['bot']['active_union_seconds'],7)
        self.assertEqual(report['parent']['active_union_seconds'],2)
        self.assertEqual(report['active_union_seconds'],9)
        self.assertEqual(report['accounted_union_seconds'],9)
        self.assertEqual(report['rework']['true']['union_seconds'],5)
        self.assertEqual(report['rework']['unknown']['union_seconds'],5)
        self.assertEqual(report['rework']['true']['count'],1)
        self.assertIsNone(report['host_sleep_seconds'])
        self.assertEqual(report['per_category']['waiting']['union_seconds'],3)

    def test_duplicate_and_invalid_or_incomplete_records_do_not_invent_time(self):
        from gantry.crew_experiment_timing import summarize
        a=interval('a','lead',0,2)
        report=summarize([a,dict(a),interval('open','lead',3,None),
            interval('bad','lead',4,3),interval('nan','lead',5,6,monotonic_seconds=float('nan'))],0,10*10**9)
        self.assertEqual(report['active_union_seconds'],2)
        self.assertEqual(report['duplicates'],1)
        self.assertEqual(report['incomplete'],1)
        self.assertEqual(report['invalid'],2)
        self.assertEqual(report['uncovered_seconds'],8)
        self.assertFalse(report['records_complete'])

    def test_conflicting_identity_is_excluded_and_window_clipping_is_visible(self):
        from gantry.crew_experiment_timing import summarize
        spans=[interval('same','lead',0,3),interval('same','lead',0,8),
               interval('before','lead',-5,-1),interval('cross','worker',-1,2),
               interval('after','worker',8,12)]
        report=summarize(spans,0,10*10**9)
        self.assertEqual(report['conflicting_ids'],1)
        self.assertEqual(report['clipped'],2)
        self.assertEqual(report['outside_window'],1)
        self.assertEqual(report['summed_span_seconds'],4)
        self.assertEqual(report['active_union_seconds'],4)

    def test_no_payload_or_reason_text_is_copied_to_report(self):
        from gantry.crew_experiment_timing import summarize
        import json
        row=interval('row','lead',0,1,task_id='task-one',action_key='action-one',
            rationale='private-design-secret',token='secret-credential',monotonic_seconds=.5)
        report=summarize([row],0,10**9)
        self.assertNotIn('private-design-secret',json.dumps(report))
        self.assertNotIn('secret-credential',json.dumps(report))
        self.assertEqual(report['clock_comparison']['max_absolute_wall_monotonic_delta_seconds'],.5)
        self.assertIsNone(report['host_sleep_seconds'])

    def test_invalid_window_and_noninteger_timestamps_are_rejected(self):
        from gantry.crew_experiment_timing import summarize
        with self.assertRaises(ValueError):summarize([],10,0)
        with self.assertRaises(ValueError):summarize([],False,10)
        row=interval('a','lead',0,1);row['started_at_ns']=0.5
        report=summarize([row],0,10**9)
        self.assertEqual(report['invalid'],1)

if __name__=='__main__':unittest.main()
