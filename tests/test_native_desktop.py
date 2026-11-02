import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace

from gantry.model import Fault
from gantry.native import workflow
from gantry.native.drivers import SolidWorks


class Dimension:
    def __init__(self, doc): self.doc = doc
    def GetSystemValue3(self, config, names):
        assert (config, names) == (1, None)
        return [self.doc.value]
    def SetSystemValue3(self, value, config, names):
        assert (config, names) == (1, None)
        self.doc.value = value; self.doc.dirty = True; self.doc.writes += 1
        return 0


class Part:
    def __init__(self, path):
        self.path = path; self.value = 0.025; self.dirty = False; self.writes = 0
        self.ConfigurationManager = SimpleNamespace(ActiveConfiguration=SimpleNamespace(Name='Default'))
    def GetPathName(self): return str(self.path)
    def GetSaveFlag(self): return self.dirty
    def GetType(self): return 1
    def Parameter(self, name): return Dimension(self) if name == 'D1@Sketch1' else None
    def EditRebuild3(self): return True
    def save(self):
        self.path.write_bytes(('native part '+str(self.value)).encode()); self.dirty = False
        return {'errors':0,'warnings':0}


class NativeWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.part = self.root/'bracket.SLDPRT'
        self.part.write_bytes(b'native original')
        self.doc = Part(self.part)
        app = SimpleNamespace(ActiveDoc=self.doc, RevisionNumber=lambda:'34.0.0')
        self.driver = SolidWorks(app, save_document=lambda doc:doc.save())
        self.config = {'product':'solidworks','document':'bracket.SLDPRT',
                       'selector':'D1@Sketch1','unit':'SI','version':'34.0.0'}

    def plan(self):
        return workflow.prepare(self.root,self.config,0.03,'Increase bracket reach',[],self.root/'plan',self.driver)

    def test_read_modify_save_readback_and_retry(self):
        p = self.plan(); self.assertEqual(self.doc.writes,0)
        result = workflow.apply(self.root/'plan',p['plan_hash'],self.root,self.driver,exclusive=True)
        self.assertEqual(result['status'],'verified')
        self.assertEqual(self.doc.value,0.03)
        self.assertEqual(workflow.apply(self.root/'plan',p['plan_hash'],self.root,self.driver,exclusive=True),result)
        self.assertEqual(self.doc.writes,1)
        evidence = workflow.evidence(self.root/'plan',self.root)
        self.assertEqual(evidence['files']['before/native/bracket.SLDPRT'],b'native original')
        self.assertEqual(evidence['manifest']['verification'],'unverified')

    def test_stale_dirty_wrong_target_and_approval_refused(self):
        p=self.plan()
        for action in ['stale','dirty','target','approval','configuration','version']:
            with self.subTest(action=action):
                self.doc.value=0.025;self.doc.dirty=False;self.doc.path=self.part
                self.doc.ConfigurationManager.ActiveConfiguration.Name='Default'
                self.driver.app.RevisionNumber=lambda:'34.0.0'
                if action=='stale': self.doc.value=0.026
                if action=='dirty': self.doc.dirty=True
                if action=='target': self.doc.path=self.root/'other.SLDPRT'
                if action=='configuration': self.doc.ConfigurationManager.ActiveConfiguration.Name='Other'
                if action=='version': self.driver.app.RevisionNumber=lambda:'different'
                with self.assertRaises(Fault):
                    workflow.apply(self.root/'plan','wrong' if action=='approval' else p['plan_hash'],self.root,self.driver,exclusive=True)
                self.assertEqual(self.doc.writes,0)

    def test_inspection_discovers_version_without_authorizing_an_update(self):
        from gantry.native.__main__ import native_operation
        config={**self.config,'version':'operator-unknown'}
        (self.root/'config.json').write_text(json.dumps(config))
        r=native_operation({'command':'inspect','config':str(self.root/'config.json'),'root':str(self.root)},self.driver)
        self.assertEqual(r['application_version'],'34.0.0')
        with self.assertRaises(Fault):workflow.prepare(self.root,config,0.03,'test',[],self.root/'bad',self.driver)

    def test_configuration_change_during_write_is_not_reported_verified(self):
        p=self.plan();original=self.driver.write
        def changed(*args):
            result=original(*args);self.doc.ConfigurationManager.ActiveConfiguration.Name='Another';return result
        self.driver.write=changed
        result=workflow.apply(self.root/'plan',p['plan_hash'],self.root,self.driver,exclusive=True)
        self.assertEqual(result['status'],'unknown')

    def test_crash_after_dispatch_is_not_retried_and_can_be_reconciled(self):
        p=self.plan(); original=self.driver.write
        def crash(*args): original(*args); raise KeyboardInterrupt()
        self.driver.write=crash
        with self.assertRaises(KeyboardInterrupt):
            workflow.apply(self.root/'plan',p['plan_hash'],self.root,self.driver,exclusive=True)
        r=workflow.apply(self.root/'plan',p['plan_hash'],self.root,self.driver,exclusive=True)
        self.assertEqual(r['status'],'dispatching');self.assertEqual(self.doc.writes,1)
        with self.assertRaises(Fault):workflow.reconcile(self.root/'plan',self.root,self.driver)
        r=workflow.reconcile(self.root/'plan',self.root,self.driver,writer_stopped=True)
        self.assertEqual(r['status'],'observed_desired')
        self.assertEqual(self.doc.writes,1)

    def test_no_implicit_desktop_concurrency_guarantee(self):
        p=self.plan()
        with self.assertRaises(Fault): workflow.apply(self.root/'plan',p['plan_hash'],self.root,self.driver)

    def test_path_secret_and_nonfinite_refused(self):
        for config,value in [({**self.config,'document':'../outside'},1),
                             (self.config,float('nan')),
                             (self.config,10**1000),
                             ({**self.config,'method':'Delete'},1)]:
            with self.assertRaises(Fault):
                workflow.prepare(self.root,config,value,'test',[],self.root/'bad',self.driver)

    def test_changing_observation_and_symlink_output_are_rejected(self):
        original=self.driver.inspect
        calls=[]
        def unstable(c):
            calls.append(1)
            if len(calls)>1:self.doc.value=0.026
            return original(c)
        self.driver.inspect=unstable
        with self.assertRaises(Fault): self.plan()
        self.driver.inspect=original;self.doc.value=0.025
        alias=self.root/'alias.SLDPRT';alias.symlink_to(self.part)
        def linked(c):
            metadata,_=original(c)
            return metadata,[str(alias)]
        self.driver.inspect=linked
        with self.assertRaises(Fault): self.plan()

    def test_terminal_receipt_is_immutable_when_reconciling_later(self):
        p=self.plan()
        first=workflow.apply(self.root/'plan',p['plan_hash'],self.root,self.driver,exclusive=True)
        self.doc.value=0.045;self.doc.save()
        later=workflow.reconcile(self.root/'plan',self.root,self.driver,writer_stopped=True)
        self.assertEqual(first,later)

    def test_relocated_operator_root_cannot_repeat_native_write(self):
        import shutil
        p=self.plan()
        other=self.root/'other';other.mkdir();shutil.copy(self.part,other/self.part.name)
        self.doc.path=other/self.part.name
        with self.assertRaises(Fault):
            workflow.apply(self.root/'plan',p['plan_hash'],other,self.driver,exclusive=True)
        self.assertEqual(self.doc.writes,0)

    def test_independent_targets_serialize_and_nonterminal_holds_survive(self):
        p=self.plan()
        original=self.driver.write
        def lost(*args): original(*args);raise RuntimeError('private CAD detail')
        self.driver.write=lost
        r=workflow.apply(self.root/'plan',p['plan_hash'],self.root,self.driver,exclusive=True)
        self.assertEqual(r['status'],'unknown');self.assertNotIn('private CAD',json.dumps(r))
        p2=workflow.prepare(self.root,self.config,0.04,'Another change',[],self.root/'plan2',self.driver)
        with self.assertRaises(Fault):
            workflow.apply(self.root/'plan2',p2['plan_hash'],self.root,self.driver,exclusive=True)

    def test_secret_reason_and_journal_symlink_are_rejected_before_write(self):
        with self.assertRaises(Fault):
            workflow.prepare(self.root,self.config,0.03,'api_key='+('a'*25),[],self.root/'secret',self.driver)
        p=self.plan();other=self.root/'elsewhere';other.mkdir()
        (self.root/'.gantry-native').symlink_to(other,target_is_directory=True)
        with self.assertRaises(Fault):
            workflow.apply(self.root/'plan',p['plan_hash'],self.root,self.driver,exclusive=True)
        self.assertEqual(self.doc.writes,0)

    def test_timeout_does_not_retry_worker(self):
        import subprocess,io,contextlib
        from gantry.native.__main__ import main
        output=io.StringIO()
        with patch('gantry.native.__main__.subprocess.run',side_effect=subprocess.TimeoutExpired('worker',1)) as run:
            with contextlib.redirect_stdout(output):
                result=main(['apply','--plan','unused','--root',str(self.root),'--expect-plan','unused','--exclusive'])
        self.assertEqual(result,1);self.assertEqual(run.call_count,1)
        self.assertEqual(json.loads(output.getvalue())['status'],'unknown')

    def test_portable_cli_import_does_not_load_posix_runner(self):
        import subprocess,sys
        code="""import sys, importlib.abc
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self, fullname, path=None, target=None):
  if fullname in {'fcntl', 'gantry.project_connect', 'gantry.runner'}: raise ImportError(fullname)
sys.meta_path.insert(0,Block())
from gantry.native.__main__ import main
assert main(['catalog'])==0
"""
        result=subprocess.run([sys.executable,'-B','-c',code],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(len(json.loads(result.stdout)),8)


class OtherDriverContracts(unittest.TestCase):
    def test_catia_numeric_parameter_with_relation_guard(self):
        from gantry.native.drivers import Catia
        parameter=SimpleNamespace(Value=4.0,ReadOnly=False,OptionalRelation=None)
        doc=SimpleNamespace(FullName='part.CATPart',Saved=True,
            Part=SimpleNamespace(Parameters=SimpleNamespace(Item=lambda name:parameter),Update=lambda:None),Save=lambda:None)
        d=Catia(SimpleNamespace(ActiveDocument=doc,SystemConfiguration=SimpleNamespace(Version='V5',Release='34',ServicePack='0')))
        c={'selector':'Length'}
        self.assertEqual(d.inspect(c)[0]['value'],4.0)
        d.write(c,5.0);self.assertEqual(d.inspect(c)[0]['value'],5.0)
        parameter.OptionalRelation=object()
        with self.assertRaises(Fault):d.inspect(c)

    def test_creo_uses_native_union_and_retains_versioned_file(self):
        from gantry.native.drivers import Creo
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'part.prt.7').write_bytes(b'original')
            parameter=SimpleNamespace(Value=SimpleNamespace(DoubleValue=2.0))
            model=SimpleNamespace(FileName='part.prt',Origin=tmp,IsModified=False,VersionStamp='stamp',
                GetParam=lambda name:parameter,Regenerate=lambda options:None,Save=lambda:(root/'part.prt.8').write_bytes(b'changed'))
            connection=SimpleNamespace(Session=SimpleNamespace(CurrentModel=model,GetCurrentDirectory=lambda:tmp))
            factory=SimpleNamespace(CreateDoubleParamValue=lambda v:SimpleNamespace(DoubleValue=v))
            d=Creo(connection,factory);c={'selector':'LENGTH','value_type':'double'}
            self.assertTrue(d.inspect(c)[1][0].endswith('.7'))
            d.write(c,3.0)
            self.assertEqual(d.inspect(c)[0]['value'],3.0)
            self.assertTrue(d.inspect(c)[1][0].endswith('.8'))
            self.assertIsNone(d.inspect(c)[0]['application_version'])

    def test_electrical_uses_error_first_comtypes_and_project_binding(self):
        from gantry.native.drivers import Electrical
        values={1:'old'};calls=[]
        def put(i,v):values[i]=v;calls.append('set');return 0
        project=SimpleNamespace(getID=lambda:7,getUserData=lambda i:(0,values[i]),
            getModificationDate=lambda:(0,'date'),setUserData=put,update=lambda:calls.append('update') or 0)
        env=SimpleNamespace(getHostname=lambda:(0,'test-host'),getWorkingFolder=lambda:(0,'test-folder'))
        app=SimpleNamespace(getEwProjectCurrent=lambda:(0,project),getEwEnvironment=lambda:(0,env),getApplicationVersion=lambda:'2026.0.0')
        d=Electrical(app,0);c={'project_id':'7','environment':{'hostname':'test-host','working_folder':'test-folder'},'field':1}
        self.assertEqual(d.inspect(c)[0]['value'],'old')
        d.write(c,'new');self.assertEqual(d.inspect(c)[0]['value'],'new')
        self.assertEqual(calls,['set','update'])
        with self.assertRaises(Fault):d.inspect({**c,'project_id':'8'})
        with self.assertRaises(Fault):d.result((5,project))


class NativeScriptContracts(unittest.TestCase):
    def test_native_script_uses_api_and_preserves_unverified_boundary(self):
        from gantry.native.scripts import prepare_script, collect_script
        for product,name,selector,api in [('altium','board.PcbDoc','R1','PCBServer.PreProcess'),
                                         ('cadence','board.brd','DESIGN_NOTE','axlDBAddProp')]:
            with self.subTest(product=product),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/name).write_bytes(b'original board')
                config={'product':product,'document':name,'selector':selector,'version':'2026'}
                result=prepare_script(root,config,'old','new','Clarify value',[],root/'package')
                source=(root/'package'/result['script']).read_text()
                self.assertIn(api,source);self.assertIn('old',source)
                self.assertIn('started',source)
                with self.assertRaises(Fault):collect_script(root/'package',root)
                # Synthetic native-host receipt, not an actual vendor run.
                receipt={'plan_hash':result['plan_hash'],'status':'applied_in_memory',
                         'before':'old','after':'new','saved':False}
                (root/'package'/'started').write_text('started')
                (root/'package'/'result.json').write_text(json.dumps(receipt))
                bundle=collect_script(root/'package',root)
                self.assertEqual(bundle['manifest']['verification'],'unverified')
                self.assertIn('Native save not verified',bundle['manifest']['missing'])
                receipt['plan_hash']='wrong'
                (root/'package'/'result.json').write_text(json.dumps(receipt))
                with self.assertRaises(Fault):collect_script(root/'package',root)

    def test_script_input_injection_and_missing_sdk_fail_closed(self):
        from gantry.native.scripts import prepare_script
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'board.brd').write_bytes(b'board')
            for product,selector in [('cadence','A") deleteFile("x'),('capital','A'),('zuken-e3','A')]:
                with self.assertRaises(Fault):
                    prepare_script(root,{'product':product,'document':'board.brd','selector':selector,'version':'2026'},
                                   'old','new','test',[],root/'bad')


if __name__=='__main__': unittest.main()
