import hashlib
import importlib.util
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest

from gantry.cad_screen import capture_bounds, lower_bound, screen
from gantry.model import Fault


class BoundsTests(unittest.TestCase):
    def test_one_calculation_per_shape_and_fresh_pose(self):
        class Shape:
            def __init__(self, x): self.x = x; self.calls = 0
            def BoundingBox(self):
                self.calls += 1
                return SimpleNamespace(xmin=self.x, xmax=self.x+1, ymin=0, ymax=1, zmin=0, zmax=1)
        a, b = Shape(0), Shape(4)
        bounds, metrics = capture_bounds({'a': a, 'b': b})
        for _ in range(100): self.assertEqual(lower_bound(bounds['a'], bounds['b']), 3)
        self.assertEqual((a.calls, b.calls), (1, 1)); self.assertEqual(metrics['bounds_computations'], 2)
        a.x = 2
        updated, _ = capture_bounds({'a': a, 'b': b})
        self.assertEqual(lower_bound(updated['a'], updated['b']), 1)
        self.assertEqual(lower_bound(bounds['a'], bounds['b']), 3)
        with self.assertRaises(TypeError): bounds['a'] = updated['a']


@unittest.skipUnless(importlib.util.find_spec('cadquery'), 'Optional CAD runtime unavailable')
class NativeScreenTests(unittest.TestCase):
    def test_hash_pinned_native_screen_and_changed_geometry(self):
        import cadquery as cq
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); parts = []
            for name, x in [('a', 0), ('b', .5), ('c', 10)]:
                path = root / (name + '.step')
                cq.exporters.export(cq.Workplane('XY').box(1, 1, 1).translate((x, 0, 0)), str(path))
                parts.append({'id': name, 'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
            request = {'parts': parts, 'pairs': [['a', 'b'], ['a', 'c'], ['b', 'c']],
                       'clearance': .1, 'overlap_tolerance': 1e-6, 'unit': 'mm', 'frame': 'assembly'}
            result = screen(root, request)
            self.assertFalse(result['passed_requested_pairs'])
            self.assertEqual(result['metrics']['bounds_computations'], 3)
            self.assertEqual(result['metrics']['exact_pairs'], 1)
            self.assertAlmostEqual(result['pairs'][0]['overlap_volume'], .5)
            (root / 'a.step').write_text('changed')
            with self.assertRaises(Fault) as error: screen(root, request)
            self.assertEqual(error.exception.code, 'stale_basis')
