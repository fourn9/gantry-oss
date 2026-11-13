"""Analytic geometry and installation boundaries for the no-VTK runtime."""
import importlib.util
import math
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(importlib.util.find_spec('OCP'), 'Optional OCP runtime unavailable')
class KernelTests(unittest.TestCase):
    def test_geometry_and_step_roundtrip(self):
        from gantry import cad_kernel as k
        a=k.box(10,10,10); b=a.translate((5,0,0))
        self.assertAlmostEqual(a.Volume(),1000)
        self.assertAlmostEqual(a.intersect(b).Volume(),500)
        self.assertAlmostEqual(a.fuse(b).Volume(),1500)
        self.assertAlmostEqual(a.cut(b).Volume(),500)
        self.assertAlmostEqual(a.Volume(),1000)
        self.assertAlmostEqual(b.Volume(),1000)
        self.assertAlmostEqual(a.distance(a.translate((20,0,0))),10)
        self.assertAlmostEqual(k.cylinder(2,20).Volume(),math.pi*80)
        self.assertAlmostEqual(a.BoundingBox().xmin,-5,places=5)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'assembly.step'
            k.export_step(k.compound([a,a.translate((30,0,0))]),p)
            restored=k.import_step(p)
            self.assertEqual(len(restored.Solids()),2)
            self.assertAlmostEqual(restored.Volume(),2000)
            self.assertTrue(restored.isValid())
            p.write_text('not STEP')
            with self.assertRaises(ValueError):k.import_step(p)

    def test_review_subprocess_without_vtk(self):
        from gantry import cad_kernel as k
        from gantry.review_context import inspect_cad
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'part.step';k.export_step(k.box(2,3,4),p)
            result=inspect_cad(d,['part.step'])['files'][0]['current']
            self.assertEqual(result['status'],'measured',result)
            self.assertAlmostEqual(result['volume'],24)
            self.assertEqual(result['physical_acceptance'],'not_evaluated')

    def test_touching_disjoint_and_stl_inspection(self):
        from gantry import cad_kernel as k
        from gantry.review_context import inspect_cad
        a=k.box(2,2,2)
        self.assertAlmostEqual(a.intersect(a.translate((5,0,0))).Volume(),0)
        self.assertAlmostEqual(a.intersect(a.translate((2,0,0))).Volume(),0)
        self.assertAlmostEqual(a.distance(a.translate((2,0,0))),0)
        self.assertEqual(len(k.compound([a,a]).Solids()),1)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'part.stl'; k.export_stl(a,p)
            report=inspect_cad(d,['part.stl'])['files'][0]['current']
            self.assertEqual(report['status'],'measured',report)
            self.assertIsNone(report['volume'])
            self.assertEqual(report['mesh_volume'],'unknown')

    def test_conflicting_full_ocp_is_rejected(self):
        from unittest.mock import patch
        from gantry import cad_kernel as k
        with patch.object(k,'version',return_value='7.9.3.1.1'):
            with self.assertRaisesRegex(ImportError,'Conflicting OCP'):
                k.runtime()
