"""Process-boundary tests, not licensed Altium execution."""
import hashlib
import json
import tempfile
import unittest
import contextlib
import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from gantry.model import Fault
from gantry.native.scripts import prepare_script


class AltiumLaunchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.board = self.root/'board.PcbDoc'; self.board.write_bytes(b'original PCB')
        self.exe = self.root/'X2.EXE'; self.exe.write_bytes(b'MZ synthetic executable')
        self.exe_hash = hashlib.sha256(self.exe.read_bytes()).hexdigest()
        self.config = dict(product='altium',document='board.PcbDoc',selector='R1',version='operator-declared')
        self.package = self.root/'package'
        self.prepared = prepare_script(self.root,self.config,'old','new','test',[],self.package,save_format='PCB Binary')

    def run_host(self, package=None, prepared=None):
        from gantry.native.launcher import run_script
        return run_script(package or self.package,self.root,(prepared or self.prepared)['plan_hash'],
                          self.exe,self.exe_hash,exclusive=True)

    def report_saved(self):
        self.board.write_bytes(b'persisted changed PCB')
        (self.package/'native-saved.PcbDoc').write_bytes(self.board.read_bytes())
        (self.package/'started').write_text('started')
        (self.package/'result.json').write_text(json.dumps(dict(plan_hash=self.prepared['plan_hash'],
            status='saved_and_reloaded',before='old',after='new',saved=True,reloaded=True,capture='native-saved.PcbDoc')))

    def test_dispatch_is_once_shell_free_and_exit_is_not_success(self):
        with patch('gantry.native.launcher.platform','win32'), patch('gantry.native.launcher.subprocess.Popen') as popen:
            popen.return_value=SimpleNamespace(pid=1234)
            first=self.run_host(); second=self.run_host()
            self.assertEqual(first,second);self.assertEqual(popen.call_count,1)
            self.assertEqual(first['status'],'dispatched')
            args,kwargs=popen.call_args
            self.assertEqual(args[0][0],str(self.exe))
            self.assertIn('ScriptingSystem:RunScriptFile',args[0][1])
            self.assertIn('ProcName="GantryApply"',args[0][1])
            self.assertFalse(kwargs['shell'])
            self.assertEqual(first['executable_sha256'],self.exe_hash)

    def test_client_interruption_cannot_dispatch_twice(self):
        with patch('gantry.native.launcher.platform','win32'), patch('gantry.native.launcher.subprocess.Popen',side_effect=KeyboardInterrupt) as popen:
            with self.assertRaises(KeyboardInterrupt):self.run_host()
            self.assertEqual(self.run_host()['status'],'dispatching')
            self.assertEqual(popen.call_count,1)

    def test_failed_dispatch_retains_hold_and_never_retries(self):
        with patch('gantry.native.launcher.platform','win32'), patch('gantry.native.launcher.subprocess.Popen',side_effect=OSError('private detail')) as popen:
            result=self.run_host()
            self.assertEqual(result['status'],'unknown');self.assertNotIn('private detail',json.dumps(result))
            self.run_host();self.assertEqual(popen.call_count,1)
            p2=self.root/'other';r2=prepare_script(self.root,self.config,'old','next','test',[],p2,save_format='PCB Binary')
            with self.assertRaises(Fault):self.run_host(p2,r2)

    def test_unapproved_stale_wrong_binary_script_and_platform_fail_before_launch(self):
        from gantry.native.launcher import run_script
        with patch('gantry.native.launcher.subprocess.Popen') as popen:
            with self.assertRaises(Fault):self.run_host()
            with patch('gantry.native.launcher.platform','win32'):
                for overrides in ({'exclusive':False},{'expected_hash':'0'*64},{'executable_sha256':'0'*64}):
                    kw=dict(package=self.package,root=self.root,expected_hash=self.prepared['plan_hash'],
                            executable=self.exe,executable_sha256=self.exe_hash,exclusive=True);kw.update(overrides)
                    with self.assertRaises(Fault):run_script(**kw)
                self.board.write_bytes(b'stale')
                with self.assertRaises(Fault):self.run_host()
                self.board.write_bytes(b'original PCB')
                (self.package/'operation.pas').write_text('different script')
                with self.assertRaises(Fault):self.run_host()
            popen.assert_not_called()

    def test_pending_then_recover_saved_evidence_without_reexecution(self):
        from gantry.native.launcher import script_status, script_evidence
        with patch('gantry.native.launcher.platform','win32'), patch('gantry.native.launcher.subprocess.Popen') as popen:
            popen.return_value=SimpleNamespace(pid=1234);self.run_host()
            pending=script_status(self.package,self.root)
            self.assertEqual(pending['status'],'dispatched')
            self.report_saved()
            self.assertEqual(script_status(self.package,self.root)['status'],'awaiting_writer_stop_confirmation')
            result=script_status(self.package,self.root,writer_stopped=True)
            self.assertEqual(result['status'],'saved_and_reloaded')
            self.board.write_bytes(b'later independent change')
            self.assertEqual(script_status(self.package,self.root),result)
            evidence=script_evidence(self.package,self.root)
            self.assertEqual(evidence['files']['after/native/board.PcbDoc'],b'persisted changed PCB')
            self.assertEqual(evidence['manifest']['verification'],'unverified')
            self.run_host();self.assertEqual(popen.call_count,1)

    def test_wrong_receipt_cannot_release_native_target(self):
        from gantry.native.launcher import script_status
        with patch('gantry.native.launcher.platform','win32'), patch('gantry.native.launcher.subprocess.Popen',return_value=SimpleNamespace(pid=42)):
            self.run_host();self.report_saved()
            (self.package/'native-saved.PcbDoc').write_bytes(b'wrong bytes')
            result=script_status(self.package,self.root,writer_stopped=True)
            self.assertEqual(result['status'],'unknown')
            p2=self.root/'other';r2=prepare_script(self.root,self.config,'old','next','test',[],p2,save_format='PCB Binary')
            with self.assertRaises(Fault):self.run_host(p2,r2)

    def test_fast_native_completion_cannot_be_overwritten_by_launch_return(self):
        from gantry.native.launcher import script_status
        def finish(*args,**kwargs):
            self.report_saved()
            self.assertEqual(script_status(self.package,self.root,writer_stopped=True)['status'],'saved_and_reloaded')
            return SimpleNamespace(pid=123)
        with patch('gantry.native.launcher.platform','win32'), patch('gantry.native.launcher.subprocess.Popen',side_effect=finish):
            self.assertEqual(self.run_host()['status'],'saved_and_reloaded')

    def test_injection_paths_and_legacy_plans_cannot_launch(self):
        with patch('gantry.native.launcher.platform','win32'), patch('gantry.native.launcher.subprocess.Popen') as popen:
            for name in ('bad|parameters','bad"quote'):
                package=self.root/name
                prepared=prepare_script(self.root,self.config,'old','new','test',[],package,save_format='PCB Binary')
                with self.assertRaises(Fault):self.run_host(package,prepared)
            legacy=self.root/'legacy'
            prepared=prepare_script(self.root,self.config,'old','new','test',[],legacy)
            with self.assertRaises(Fault):self.run_host(legacy,prepared)
            popen.assert_not_called()

    def test_cli_run_status_export_preserves_originals_and_unverified_status(self):
        from gantry.native.__main__ import main
        from gantry.integrations.bundle import read_bundle
        def cli(*args):
            stream=io.StringIO()
            with contextlib.redirect_stdout(stream):
                code=main([*args,'--root',str(self.root),'--package',str(self.package)])
            self.assertEqual(code,0,stream.getvalue())
            return json.loads(stream.getvalue())
        with patch('gantry.native.launcher.platform','win32'), patch('gantry.native.launcher.subprocess.Popen',return_value=SimpleNamespace(pid=9)):
            result=cli('script-run','--expect-plan',self.prepared['plan_hash'],
                '--executable',str(self.exe),'--expect-executable',self.exe_hash,'--exclusive')
            self.assertEqual(result['status'],'dispatched')
            self.report_saved();self.assertEqual(cli('script-status','--writer-stopped')['status'],'saved_and_reloaded')
            out=self.root/'evidence';cli('script-evidence','--output',str(out))
            b=read_bundle(out)
            self.assertEqual(b['files']['before/native/board.PcbDoc'],b'original PCB')
            self.assertEqual(b['files']['after/native/board.PcbDoc'],b'persisted changed PCB')
            self.assertIn('launcher-receipt.json',b['files'])
            self.assertEqual(b['manifest']['verification'],'unverified')

    def test_hardlinked_and_symlinked_executable_or_existing_manual_result_refused(self):
        import os
        with patch('gantry.native.launcher.platform','win32'), patch('gantry.native.launcher.subprocess.Popen') as popen:
            alias=self.root/'alias';os.link(self.exe,alias)
            with self.assertRaises(Fault):self.run_host()
            alias.unlink();self.exe.unlink();self.exe.symlink_to(self.board)
            with self.assertRaises(Fault):self.run_host()
            self.exe.unlink();self.exe.write_bytes(b'MZ synthetic executable')
            self.report_saved()
            with self.assertRaises(Fault):self.run_host()
            popen.assert_not_called()

    def test_cli_unknown_dispatch_is_nonzero_and_does_not_expose_error_detail(self):
        from gantry.native.__main__ import main
        output=io.StringIO()
        with patch('gantry.native.launcher.platform','win32'), patch('gantry.native.launcher.subprocess.Popen',side_effect=OSError('private reason')):
            with contextlib.redirect_stdout(output):
                result=main(['script-run','--root',str(self.root),'--package',str(self.package),
                    '--expect-plan',self.prepared['plan_hash'],'--executable',str(self.exe),
                    '--expect-executable',self.exe_hash,'--exclusive'])
        self.assertEqual(result,1)
        self.assertEqual(json.loads(output.getvalue())['status'],'unknown')
        self.assertNotIn('private reason',output.getvalue())
