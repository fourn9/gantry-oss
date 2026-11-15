import unittest
import test_continuity as fixtures
from gantry.model import Fault

class ExtractTests(unittest.TestCase):
    def setUp(self):
        self.c=fixtures.ContinuityTests(); self.c.setUp(); self.addCleanup(self.c.tearDown); self.base=self.c.initialize()
    def state(self, text):
        change=self.c.begin(self.base)
        return self.c.checkpoint(change,{'input.txt':text})['state']
    def extract(self,state,**kw):
        return self.c.call('extract_json_evidence',dict(state_id=state['id'],subject_id='robot',path='input.txt',
            profile='controller.v1',fields=[{'name':'target','pointer':'/target','unit':'mm','frame':'assembly','time_basis':'configuration'}],**kw))
    def test_exact_source_kept_missing_is_unknown_and_unit_is_declared(self):
        st=self.state('{"target":12,"native_vendor_data":{"x":[1,2,3]}}')
        v=self.extract(st);self.assertEqual(v['fields'][0]['value'],12)
        self.assertEqual(v['fields'][0]['classification'],'declared')
        self.assertEqual(v['sources'][0]['locator'],'/target')
        self.assertEqual(v['sources'][0]['revision_id'],st['snapshot'])
        other=self.state('{"native_vendor_data":1}')
        missing=self.extract(other);self.assertIsNone(missing['fields'][0]['value'])
        self.assertEqual(missing['fields'][0]['classification'],'unknown')
        self.assertTrue(missing['missing']);self.assertTrue(self.c.call('replay')['matched'])
    def test_duplicate_keys_nonfinite_and_non_scalar_are_not_certified(self):
        for raw in ('{"target":1,"target":2}','{"target":NaN}','{"target":1e309}','{"target":{"x":1}}'):
            with self.assertRaises(Fault) as error:self.extract(self.state(raw))
            self.assertEqual(error.exception.code,'invalid_input')

    def test_encoded_credentials_and_invalid_pointers_rejected(self):
        st=self.state('{"note":"\\u002d----BEGIN PRIVATE KEY-----"}')
        with self.assertRaises(Fault) as error:self.extract(st)
        self.assertEqual(error.exception.code,'credential_detected')
        st=self.state('{"values":[1,2],"bad~2":1}')
        for pointer in ('/values/-1','/values/01','/bad~2'):
            with self.assertRaises(Fault) as error:
                self.c.call('extract_json_evidence',{'state_id':st['id'],'subject_id':'robot','path':'input.txt',
                    'profile':'test','fields':[{'name':'x','pointer':pointer}]})
            self.assertEqual(error.exception.code,'invalid_input')
