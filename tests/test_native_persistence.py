"""Synthetic native-host receipts: these tests do not run licensed Altium."""
import json
import tempfile
import unittest
from pathlib import Path
from gantry.model import Fault
from gantry.integrations.bundle import read_bundle
from gantry.native.scripts import prepare_script, collect_script


class AltiumPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.board = self.root / 'board.PcbDoc'; self.board.write_bytes(b'original native PCB')
        self.package = self.root / 'package'
        self.config = dict(product='altium', document='board.PcbDoc', selector='R1', version='operator-2026')

    def prepare(self):
        return prepare_script(self.root, self.config, 'old', 'new', 'Clarify comment', [],
                              self.package, save_format='PCB Binary')

    def report_saved(self, result):
        self.board.write_bytes(b'new native PCB')
        (self.package / 'native-saved.PcbDoc').write_bytes(self.board.read_bytes())
        (self.package / 'started').write_text('started')
        (self.package / 'result.json').write_text(json.dumps(dict(
            plan_hash=result['plan_hash'], status='saved_and_reloaded', before='old', after='new',
            saved=True, reloaded=True, capture='native-saved.PcbDoc')))

    def test_save_reload_is_explicit_and_raw_bytes_survive_collection(self):
        r = self.prepare(); self.report_saved(r)
        b = collect_script(self.package, self.root)
        self.assertEqual(b['manifest']['source']['outcome'], 'saved_and_reloaded')
        self.assertEqual(b['manifest']['verification'], 'unverified')
        self.assertEqual(b['files']['after/native/board.PcbDoc'], b'new native PCB')
        self.assertEqual(b['files']['before/native/board.PcbDoc'], b'original native PCB')
        source = (self.package / r['script']).read_text()
        self.assertIn('DoFileSave', source)
        self.assertIn('DoFileLoad', source)
        self.assertIn('Document.Modified', source)
        self.assertIn('GantryFindComponent(Board', source)
        self.assertIn('GantrySameFile', source)
        self.assertIn('Host-reported save/reload; native runtime not qualified', b['manifest']['missing'])

    def test_missing_save_receipt_remains_unknown(self):
        self.prepare(); (self.package / 'started').write_text('started')
        b = collect_script(self.package, self.root)
        self.assertEqual(b['manifest']['source']['outcome'], 'unknown')
        self.assertIn('Native save not verified', b['manifest']['missing'])

    def test_changed_or_missing_snapshot_rejects_saved_claim(self):
        r = self.prepare(); self.report_saved(r)
        self.board.write_bytes(b'changed since reported save')
        with self.assertRaises(Fault): collect_script(self.package, self.root)
        self.board.write_bytes(b'new native PCB'); (self.package / 'native-saved.PcbDoc').unlink()
        with self.assertRaises(Fault): collect_script(self.package, self.root)

    def test_save_failure_and_wrong_receipt_cannot_claim_success(self):
        r = self.prepare(); self.report_saved(r)
        receipt = json.loads((self.package / 'result.json').read_text()); receipt['saved'] = False
        (self.package / 'result.json').write_text(json.dumps(receipt))
        with self.assertRaises(Fault): collect_script(self.package, self.root)

    def test_no_implicit_format_conversion_or_other_product_save(self):
        for fmt in ('PCB ASCII', 'PCB Binary\nInjected', ''):
            with self.subTest(format=fmt), self.assertRaises(Fault):
                prepare_script(self.root,self.config,'old','new','reason',[],self.package,save_format=fmt)
        with self.assertRaises(Fault):
            prepare_script(self.root,{**self.config,'product':'cadence'},'old','new','reason',[],
                           self.package,save_format='PCB Binary')

    def test_legacy_in_memory_plan_keeps_its_contract(self):
        r = prepare_script(self.root,self.config,'old','new','reason',[],self.package)
        self.assertEqual(json.loads(read_bundle(self.package)['files']['plan.json'])['version'], 1)
        (self.package / 'started').write_text('started')
        (self.package / 'result.json').write_text(json.dumps(dict(plan_hash=r['plan_hash'],
            status='applied_in_memory',before='old',after='new',saved=False)))
        self.assertEqual(collect_script(self.package,self.root)['manifest']['source']['outcome'], 'applied_in_memory')
