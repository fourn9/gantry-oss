from pathlib import Path
from types import SimpleNamespace
from test_vendor_bridge import VendorBridgeTests
from gantry.vendor_desktop import capture_active
from gantry.vendor_bridge import collect
from gantry.model import Fault

class DesktopContractTests(VendorBridgeTests):
    def app(self,dirty=False,path=None,version='test-version'):
        doc=SimpleNamespace(GetPathName=lambda:str(path or self.bundle/'input/part.native'),GetSaveFlag=lambda:dirty)
        return SimpleNamespace(ActiveDoc=doc,RevisionNumber=lambda:version)
    def test_solidworks_api_double_saved_capture(self):
        self.request();capture_active(self.bundle,self.app());out=collect(self.bundle,self.root/'collected')
        self.assertEqual((out/'native/part.native').read_bytes(),b'original native bytes')
    def test_dirty_or_other_document_cannot_be_captured(self):
        self.request()
        for app in [self.app(True),self.app(path=self.source/'part.native'),self.app(version='another')]:
            with self.assertRaises(Fault):capture_active(self.bundle,app)
        self.assertFalse((self.bundle/'result.json').exists())
    def test_catia_api_double_saved_capture(self):
        from gantry.vendor_bridge import prepare
        prepare(self.source,['part.native'],self.bundle,'catia-v5','5.30.1')
        app=SimpleNamespace(ActiveDocument=SimpleNamespace(FullName=str(self.bundle/'input/part.native'),Saved=True),
            SystemConfiguration=SimpleNamespace(Version=5,Release=30,ServicePack=1))
        capture_active(self.bundle,app);self.assertTrue((collect(self.bundle,self.root/'out')/'native/part.native').exists())
