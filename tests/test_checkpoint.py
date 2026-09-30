import importlib.util
import tempfile
from pathlib import Path
import unittest
from gantry.checkpoint import save_bundle,load_bundle
from gantry.model import Fault

@unittest.skipUnless(importlib.util.find_spec('numpy'),'NumPy adapter tests run in an optional NumPy environment')
class CheckpointTests(unittest.TestCase):
    def test_corrupt_missing_and_mismatched_inputs(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'point';binding={'model':'original','evaluator':'fixed'}
            receipt=save_bundle(path,binding,{'physics':np.arange(4),'evaluation':{'next_step':4},'axes':{'axis_a':1,'axis_b':2}},['physics','evaluation'])
            state=load_bundle(path,binding,receipt['manifest_sha256']);self.assertEqual(state['evaluation']['next_step'],4)
            self.assertEqual(list(state['axes']),['axis_a','axis_b'])
            with self.assertRaises(Fault) as wrong:load_bundle(path,{'model':'changed'},receipt['manifest_sha256'])
            self.assertEqual(wrong.exception.code,'checkpoint_incompatible')
            with self.assertRaises(Fault):save_bundle(Path(tmp)/'bad',binding,{'physics':[]},['evaluation'])
            (path/'array-0.npy').write_bytes(b'corrupt')
            with self.assertRaises(Fault) as corrupt:load_bundle(path,binding,receipt['manifest_sha256'])
            self.assertEqual(corrupt.exception.code,'integrity_error')
    def test_unknown_python_objects_and_c_layout_are_not_silently_dropped(self):
        import ctypes as ct
        class State(ct.Structure):_fields_=[('counter',ct.c_uint32)]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(Fault):save_bundle(Path(tmp)/'bad',{}, {'opaque':object()},['opaque'])
            receipt=save_bundle(Path(tmp)/'good',{}, {'controller':State(17)},['controller'])
            with self.assertRaises(Fault):load_bundle(Path(tmp)/'good',{},receipt['manifest_sha256'])
            restored=load_bundle(Path(tmp)/'good',{},receipt['manifest_sha256'],{'State':State})
            self.assertEqual(restored['controller'].counter,17)
