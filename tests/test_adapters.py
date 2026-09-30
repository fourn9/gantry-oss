import base64
from pathlib import Path
import subprocess
import unittest

import test_service as fixtures
from gantry.adapters import capture_git, files_payload, restore_files, watch_saved_files
from gantry.model import Fault


class LocalClient:
    def __init__(self, case): self.case = case
    def call(self, command, args=None, key=None): return self.case.call(command, args, key=key)


class AdapterTests(unittest.TestCase):
    setUp = fixtures.LedgerTests.setUp
    tearDown = fixtures.LedgerTests.tearDown
    call = fixtures.LedgerTests.call
    assertFault = fixtures.LedgerTests.assertFault

    def work(self):
        return self.call('create_work', {'title': 'capture', 'completion_condition': 'files saved'})['id']

    def test_git_capture_same_commit_for_two_works_and_restore(self):
        repo = Path(self.temp.name) / 'repo'; repo.mkdir()
        def git(*args):
            return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True).stdout
        git('init', '-q')
        (repo / 'control.py').write_text('gain = 1\n')
        git('add', 'control.py')
        git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'initial')
        base = git('rev-parse', 'HEAD').decode().strip()
        (repo / 'control.py').write_text('gain = 2\n')
        git('add', 'control.py')
        git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'gain')
        client = LocalClient(self)
        first = capture_git(client, repo, self.work(), base=base)
        second = capture_git(client, repo, self.work(), base=base)
        self.assertEqual(first['artifact']['revision_id'], second['artifact']['revision_id'])
        self.assertEqual(first['software_version']['revision_id'], second['software_version']['revision_id'])
        self.assertNotEqual(first['operation']['revision_id'], second['operation']['revision_id'])
        self.assertIn('+gain = 2', first['operation']['data']['diff'])
        destination = Path(self.temp.name) / 'restore'
        restore_files(client, first['artifact']['revision_id'], destination)
        self.assertEqual((destination / 'control.py').read_text(), 'gain = 2\n')
        self.assertFault('invalid_input', lambda: restore_files(client, first['artifact']['revision_id'], destination))

    def test_watcher_recovers_lost_response_without_duplicate(self):
        root = Path(self.temp.name) / 'cad'; root.mkdir()
        (root / 'part.CATPart').write_bytes(b'CAD file fixture')
        journal = Path(self.temp.name) / 'watch.json'; work = self.work()
        good = LocalClient(self)
        class LostResponse:
            def call(self, command, args=None, key=None):
                result = good.call(command, args, key)
                if command == 'capture_artifact': raise OSError('Simulated response lost after commit')
                return result
        with self.assertRaises(OSError):
            watch_saved_files(LostResponse(), root, ['part.CATPart'], work, 'root', journal, once=True)
        restored = watch_saved_files(good, root, ['part.CATPart'], work, 'root', journal, once=True)
        self.assertEqual(len(self.call('operations')['items']), 1)
        self.assertEqual(len([e for e in self.call('state')['entries'].values() if e['type'] == 'artifact_snapshot']), 1)
        (root / 'part.CATPart').write_bytes(b'CAD file revision 2')
        watch_saved_files(good, root, ['part.CATPart'], work, 'root', journal, once=True)
        ops = self.call('operations')['items']
        self.assertEqual(len(ops), 2)
        self.assertTrue(any(e['data'].get('input_artifact') == restored['artifact_revision'] for e in ops))

    def test_watcher_rejects_journal_for_different_work(self):
        root = Path(self.temp.name) / 'cad'; root.mkdir()
        (root / 'part.step').write_bytes(b'fixture')
        journal = Path(self.temp.name) / 'watch.json'; client = LocalClient(self)
        watch_saved_files(client, root, ['part.step'], self.work(), 'root', journal, once=True)
        other = self.work()
        self.assertFault('invalid_input', lambda: watch_saved_files(client, root, ['part.step'], other, 'root', journal, once=True))

    def test_capture_rejects_symlinks_and_parent_escape(self):
        root = Path(self.temp.name) / 'files'; root.mkdir()
        (root / 'inside').write_bytes(b'file')
        (root / 'link').symlink_to(root / 'inside')
        self.assertFault('invalid_input', lambda: files_payload(root, ['link']))
        self.assertFault('invalid_input', lambda: files_payload(root, ['../outside']))


class GitCapturePrivacyTests(unittest.TestCase):
    def test_committed_sensitive_file_and_removed_secret_are_rejected_before_upload(self):
        import tempfile
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def git(*args):
                return subprocess.run(['git','-C',str(root),*args],check=True,capture_output=True).stdout
            git('init','-q')
            def commit(name, content):
                (root/name).write_text(content);git('add',name)
                git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','fixture')
            commit('.env','APP_MODE=fixture')
            client=Mock()
            with self.assertRaises(Fault) as error:capture_git(client,root,'work')
            self.assertEqual(error.exception.code,'credential_detected');client.call.assert_not_called()
            git('rm','.env');commit('settings.txt','api_key='+('x'*30))
            baseline=git('rev-parse','HEAD').decode().strip()
            with self.assertRaises(Fault):capture_git(client,root,'work')
            client.call.assert_not_called()
            commit('settings.txt','mode=fixture')
            with self.assertRaises(Fault):capture_git(client,root,'work',base=baseline)
            client.call.assert_not_called()
            with self.assertRaises(Fault):capture_git(client,root,'work',base='--output=unexpected')
            self.assertFalse((root/'unexpected').exists());client.call.assert_not_called()


if __name__ == '__main__': unittest.main()
