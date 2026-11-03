import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TimingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()

    def at(self,t,fn):
        with patch('gantry.workflow_journal.time.time',return_value=1000+t),patch('gantry.workflow_journal.time.monotonic',return_value=t):
            return fn()

    def test_parallel_time_pause_resume_and_unknown_are_not_invented(self):
        from gantry.workflow_journal import start_span, transition, timing_report
        a=self.at(0,lambda:start_span(self.root,'editing','s','a'))
        b=self.at(2,lambda:start_span(self.root,'calculation','s','b'))
        self.at(5,lambda:transition(self.root,a,'pause'))
        self.at(8,lambda:transition(self.root,b,'finish'))
        a2=self.at(10,lambda:transition(self.root,a,'resume'))
        self.at(12,lambda:transition(self.root,a2,'finish'))
        self.at(13,lambda:start_span(self.root,'inference','s','lost-process'))
        r=timing_report(self.root)
        self.assertEqual(r['measured_wall_seconds'],10)
        self.assertEqual(r['summed_span_seconds'],13)
        self.assertEqual(r['observed_elapsed_seconds'],12)
        self.assertEqual(r['open_spans'],1)
        self.assertEqual(r['spans'][0]['metadata']['state_id'],'s')

    def test_clock_discontinuity_and_double_finish(self):
        from gantry.workflow_journal import start_span, transition, timing_report
        from gantry.model import Fault
        a=self.at(10,lambda:start_span(self.root,'waiting','s','x'))
        self.at(5,lambda:transition(self.root,a,'finish'))
        self.assertEqual(timing_report(self.root)['unknown_duration_spans'],1)
        with self.assertRaises(Fault): transition(self.root,a,'finish')
