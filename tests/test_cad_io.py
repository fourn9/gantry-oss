import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path
from gantry.model import Fault

@unittest.skipUnless(importlib.util.find_spec('cadquery'), 'optional CadQuery not installed')
class CadIOTests(unittest.TestCase):
    def test_step_read_modify_write_and_original_preserved(self):
        import cadquery as cq
        from gantry.cad_io import edit
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cq.exporters.export(cq.Workplane().box(10, 10, 10), str(root/'in.step'))
            raw = (root/'in.step').read_bytes()
            request = {'unit':'mm','frame':'assembly','steps':[
                {'id':'a','op':'import_step','path':'in.step','sha256':hashlib.sha256(raw).hexdigest()},
                {'id':'hole','op':'cylinder','radius':2,'height':20},
                {'id':'b','op':'cut','left':'a','right':'hole'},
                {'id':'out','op':'translate','source':'b','vector':[20,0,0]}], 'export':['out']}
            result = edit(root, request, root/'result')
            shape = cq.importers.importStep(str(root/'result/out.step')).val()
            self.assertTrue(shape.isValid())
            self.assertLess(shape.Volume(), 1000)
            self.assertGreater(shape.Center().x, 19)
            self.assertEqual(raw, (root/'in.step').read_bytes())
            self.assertEqual(result['outputs']['out.step'],hashlib.sha256((root/'result/out.step').read_bytes()).hexdigest())
            with self.assertRaises(Fault): edit(root, request, root/'result')
            request['steps'][0]['sha256']='0'*64
            with self.assertRaises(Fault): edit(root, request, root/'bad')

    def test_no_code_execution_or_path_escape(self):
        from gantry.cad_io import edit
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for step in [{'id':'a','op':'python','code':'raise Exception()'},
                         {'id':'../escape','op':'box','size':[1,1,1]},
                         {'id':'a','op':'import_step','path':'../x.step','sha256':'a'*64}]:
                with self.assertRaises(Fault):
                    edit(root, {'unit':'mm','frame':'assembly','steps':[step],'export':[step['id']]},root/'out')
                self.assertFalse((root/'out').exists())

    def test_screen_report_measures_real_collision_and_clearance(self):
        import cadquery as cq
        from gantry.hardware import screen_report
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name,offset in [('a',0),('b',5)]:cq.exporters.export(cq.Workplane().box(10,10,10).translate((offset,0,0)),str(root/(name+'.step')))
            request={'unit':'mm','frame':'assembly','clearance':1,'overlap_tolerance':0.001,
                'parts':[{'id':n,'path':n+'.step','sha256':hashlib.sha256((root/(n+'.step')).read_bytes()).hexdigest()} for n in ['a','b']], 'pairs':[['a','b']]}
            check={'inputs':['a.step','b.step']}
            report=screen_report(root,request,check)
            self.assertEqual(report['measurements']['violating_pairs']['value'],1)
            self.assertGreater(report['raw']['pairs'][0]['overlap_volume'],0)
            cq.exporters.export(cq.Workplane().box(10,10,10).translate((20,0,0)),str(root/'b.step'))
            request['parts'][1]['sha256']=hashlib.sha256((root/'b.step').read_bytes()).hexdigest()
            report=screen_report(root,request,check)
            self.assertEqual(report['measurements']['violating_pairs']['value'],0)
