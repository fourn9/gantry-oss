import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from gantry.model import Fault
from gantry.vendor_bridge import prepare, collect, PRODUCTS

class VendorBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.source=self.root/'source';self.source.mkdir()
        (self.source/'part.native').write_bytes(b'original native bytes')
        self.bundle=self.root/'bundle'
    def request(self,product='solidworks'):
        return prepare(self.source,['part.native'],self.bundle,product,'test-version','capture')
    def result(self,request):
        p=self.bundle/'output';(p/'part.native').write_bytes(b'captured native bytes')
        h=hashlib.sha256((p/'part.native').read_bytes()).hexdigest()
        result={'schema_version':1,'request_id':request['request_id'],'request_hash':request['request_hash'],
            'product':request['product'],'version':request['version'],'operation':'capture','status':'completed',
            'files':{'part.native':h},'observations':[{'kind':'component','source_id':'native:1','attributes':{'name':'part'},'source_path':'part.native'}],
            'coverage':{'captured':['saved native file'],'missing':['unsaved changes','dependencies'],'inferred':[]}}
        (self.bundle/'result.json').write_text(json.dumps(result));return result
    def test_all_products_preserve_native_and_observations(self):
        for product in PRODUCTS:
            self.bundle=self.root/product
            request=self.request(product);self.result(request)
            collected=collect(self.bundle,self.root/(product+'-collected'))
            self.assertEqual((collected/'native/part.native').read_bytes(),b'captured native bytes')
            self.assertEqual(json.loads((collected/'vendor-evidence.json').read_text())['coverage']['missing'],['unsaved changes','dependencies'])
    def test_changed_input_rejected(self):
        req=self.request();self.result(req);(self.bundle/'input/part.native').write_text('changed')
        with self.assertRaises(Fault):collect(self.bundle,self.root/'out')
    def test_changed_output_rejected(self):
        req=self.request();self.result(req);(self.bundle/'output/part.native').write_text('changed')
        with self.assertRaises(Fault):collect(self.bundle,self.root/'out')
    def test_wrong_request_or_product_rejected(self):
        req=self.request();result=self.result(req);result['product']='catia-v5'
        (self.bundle/'result.json').write_text(json.dumps(result))
        with self.assertRaises(Fault):collect(self.bundle,self.root/'out')
    def test_undeclared_file_rejected(self):
        req=self.request();self.result(req);(self.bundle/'output/secret.txt').write_text('extra')
        with self.assertRaises(Fault):collect(self.bundle,self.root/'out')
    def test_symlink_escape_rejected(self):
        req=self.request();self.result(req);(self.bundle/'output/part.native').unlink()
        (self.bundle/'output/part.native').symlink_to(self.source/'part.native')
        with self.assertRaises(Fault):collect(self.bundle,self.root/'out')
    def test_missing_coverage_and_failed_status_rejected(self):
        req=self.request();result=self.result(req);result.pop('coverage')
        (self.bundle/'result.json').write_text(json.dumps(result))
        with self.assertRaises(Fault):collect(self.bundle,self.root/'out')
    def test_cannot_claim_verified(self):
        req=self.request();result=self.result(req);result['verified']=True
        (self.bundle/'result.json').write_text(json.dumps(result))
        with self.assertRaises(Fault):collect(self.bundle,self.root/'out')
    def test_edit_is_not_advertised(self):
        with self.assertRaises(Fault):prepare(self.source,['part.native'],self.bundle,'solidworks','v1','edit')
    def test_source_secret_excluded(self):
        (self.source/'.env').write_text('SECRET=not-for-upload')
        with self.assertRaises(Fault):prepare(self.source,['.env'],self.bundle,'solidworks','v1','capture')

if __name__=='__main__':unittest.main()

class VendorPublishTests(VendorBridgeTests):
    def test_real_core_capture_retains_vendor_metadata(self):
        from gantry.service import Service
        from gantry.vendor_bridge import publish
        import secrets
        service=Service(self.root/'ledger');token=service.bootstrap()['token']
        class Client:
            def call(self,op,args=None,key=None):return service.call(token,op,args or {},key or secrets.token_hex(16))
        req=self.request();self.result(req);collection=collect(self.bundle,self.root/'collected')
        out=publish(Client(),collection,'vendor-capture')
        self.assertFalse(out['adopted'])
        manifest=Client().call('restore_artifact',{'revision_id':out['artifact'],'metadata_only':True})
        self.assertIn('vendor-evidence.json',manifest['manifest']['files'])
        (collection/'native/part.native').write_text('changed after collection')
        with self.assertRaises(Fault):publish(Client(),collection,'vendor-again')
