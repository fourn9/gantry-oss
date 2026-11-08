import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class CrewTimingTests(unittest.TestCase):
    def test_failure_records_only_class_and_closed_intervals(self):
        from gantry.crew_timing import span, summarize
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with patch('gantry.crew_timing.time.time_ns', side_effect=[1000000000,5000000000]), \
                 patch('gantry.crew_timing.time.monotonic_ns', side_effect=[2000000000,3000000000]):
                with self.assertRaises(ValueError), span(root,'model'):
                    raise ValueError('sensitive-input-must-not-appear')
            content=''.join(p.read_text() for p in root.rglob('*.json'))
            self.assertNotIn('sensitive-input',content)
            report=summarize(root)
            self.assertEqual(report['phases']['model']['monotonic_seconds'],1)
            self.assertEqual(report['phases']['model']['wall_seconds'],4)
            self.assertEqual(report['phases']['model']['failed'],1)
            self.assertNotIn('sleep_seconds',report)

    def test_unclosed_intervals_are_unknown_and_overlaps_are_not_added_as_elapsed(self):
        from gantry.crew_timing import summarize
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); folder=root/'timing'; folder.mkdir()
            for i,(start,end) in enumerate(((1,5),(3,7),(8,None))):
                (folder/f'{i}.json').write_text(json.dumps({'schema':1,'phase':'model',
                    'started_at_ns':start*10**9,'finished_at_ns':None if end is None else end*10**9,
                    'monotonic_seconds':None if end is None else end-start,'status':'started' if end is None else 'completed'}))
            report=summarize(root)
            self.assertEqual(report['covered_wall_seconds'],6)
            self.assertEqual(report['phases']['model']['wall_seconds'],8)
            self.assertEqual(report['incomplete'],1)

    def test_forbids_arbitrary_payload_fields_and_phase_names(self):
        from gantry.crew_timing import span
        with tempfile.TemporaryDirectory() as d, self.assertRaises(ValueError):
            with span(Path(d),'private-payload'): pass
