import tempfile
import unittest
from pathlib import Path
from gantry.generation import bind_generation,check_generation
from gantry.model import Fault

class GenerationTests(unittest.TestCase):
    def test_source_edit_cannot_reuse_old_generated_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);(r/'datum.json').write_text('70');(r/'part.step').write_text('native CAD')
            receipt=bind_generation(r,['datum.json'],['part.step'],method='adapter inspection',evidence=['native proof'])
            self.assertTrue(check_generation(r,receipt)['ready_for_bound_recipe'])
            (r/'datum.json').write_text('69')
            check=check_generation(r,receipt)
            self.assertFalse(check['ready_for_bound_recipe']);self.assertEqual(check['differences'][0]['role'],'inputs')
            (r/'part.step').unlink();self.assertEqual(len(check_generation(r,receipt)['differences']),2)
            self.assertEqual(check['adoption'],'unadopted')
    def test_unrelated_log_does_not_invalidate_and_escape_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);(r/'source').write_text('x');(r/'output').write_text('y')
            receipt=bind_generation(r,['source'],['output'],method='observed',evidence=['proof'])
            (r/'new.log').write_text('independent log')
            self.assertTrue(check_generation(r,receipt)['ready_for_bound_recipe'])
            with self.assertRaises(Fault):bind_generation(r,['../escape'],['output'],method='x',evidence=['x'])
