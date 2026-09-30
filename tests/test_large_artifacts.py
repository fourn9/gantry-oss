import base64
import copy
import hashlib
from pathlib import Path
import unittest

import test_service as fixtures
from test_adapters import LocalClient
from gantry.adapters import capture_saved_files, restore_files
from gantry.backup import restore_backup
from gantry.service import Service
from gantry.model import digest


class LargeArtifactTests(unittest.TestCase):
    setUp = fixtures.LedgerTests.setUp
    tearDown = fixtures.LedgerTests.tearDown
    call = fixtures.LedgerTests.call
    assertFault = fixtures.LedgerTests.assertFault

    def part(self, raw):
        e = self.call('capture_artifact', {'files': {'part': base64.b64encode(raw).decode()}})
        return {'revision_id': e['revision_id'], 'path': 'part'}

    def assembly(self, parts, name='assembly.step'):
        return self.call('capture_artifact', {'files': {}, 'assembled_files': {name: parts}})

    def test_order_hash_restore_and_v2_backup(self):
        parts = [self.part(b'left'), self.part(b'right')]
        a = self.assembly(parts); b = self.assembly(parts[::-1])
        self.assertEqual(a['data']['files']['assembly.step']['hash'], hashlib.sha256(b'leftright').hexdigest())
        self.assertNotEqual(a['data']['files'], b['data']['files'])
        self.assertFault('stream_required', lambda: self.call('restore_artifact', {'revision_id': a['revision_id']}))
        for rid, raw, folder in [(a['revision_id'], b'leftright', 'a'), (b['revision_id'], b'rightleft', 'b')]:
            dest = Path(self.temp.name) / folder
            restore_files(LocalClient(self), rid, dest)
            self.assertEqual((dest / 'assembly.step').read_bytes(), raw)
        backup = self.call('export'); self.assertEqual(backup['format'], 'gantry-backup-v2')
        restored_dir = Path(self.temp.name) / 'backup'
        restore_backup(restored_dir, backup); restored = Service(restored_dir)
        result = restored.call(self.token, 'read_artifact_chunk', {'revision_id': a['revision_id'], 'path': 'assembly.step', 'index': 1})
        self.assertEqual(base64.b64decode(result['content']), b'right')
        self.assertEqual(restored.call(self.token, 'state'), self.call('state'))
        bad = copy.deepcopy(backup); del bad['blobs'][hashlib.sha256(b'right').hexdigest()]
        self.assertFault('artifact_missing', lambda: restore_backup(Path(self.temp.name) / 'missing', bad))

    def test_rejects_unsafe_nested_missing_and_invalid_parts(self):
        ref = self.part(b'data'); a = self.assembly([ref])
        for name in ['../escape', '/absolute', 'x//y']:
            self.assertFault('invalid_input', lambda: self.assembly([ref], name))
        self.assertFault('invalid_input', lambda: self.assembly([{'revision_id': a['revision_id'], 'path': 'assembly.step'}]))
        self.assertFault('invalid_input', lambda: self.assembly([{**ref, 'path': 'missing'}]))
        normal = self.call('record', {'type': 'incident', 'data': {'text': 'fixture'}})
        self.assertFault('invalid_input', lambda: self.assembly([{'revision_id': normal['revision_id'], 'path': 'part'}]))
        self.assertFault('invalid_input', lambda: self.assembly([]))
        self.assertFault('invalid_input', lambda: self.call('capture_artifact', {'files': {'x': ''}, 'assembled_files': {'x': [ref]}}))
        for index in [-1, 1, True]:
            self.assertFault('invalid_input', lambda: self.call('read_artifact_chunk', {'revision_id': a['revision_id'], 'path': 'assembly.step', 'index': index}))

    def test_corrupt_part_does_not_publish_restore_directory(self):
        ref = self.part(b'original'); a = self.assembly([ref])
        h = hashlib.sha256(b'original').hexdigest()
        (self.svc.store.blobs / h).write_bytes(b'corrupted')
        dest = Path(self.temp.name) / 'restore'
        self.assertFault('integrity_error', lambda: restore_files(LocalClient(self), a['revision_id'], dest))
        self.assertFalse(dest.exists())
        self.assertFalse(list(dest.parent.glob('.gantry-restore-*')))
        self.assertFault('integrity_error', lambda: self.assembly([ref]))

    def test_real_33_mib_file_and_idempotent_retry(self):
        root = Path(self.temp.name) / 'source'; root.mkdir()
        path = root / 'assembly.step'
        with path.open('wb') as f:
            for i in range(33): f.write(bytes([i]) * 1024**2)
        client = LocalClient(self)
        first = capture_saved_files(client, root, ['assembly.step'], 'large-fixture')
        second = capture_saved_files(client, root, ['assembly.step'], 'large-fixture')
        self.assertEqual([a['revision_id'] for a in first], [a['revision_id'] for a in second])
        self.assertEqual(len(first), 1)
        self.assertEqual(len(first[0]['data']['files']['assembly.step']['chunks']), 3)
        dest = Path(self.temp.name) / 'restored-large'
        restore_files(client, first[0]['revision_id'], dest)
        self.assertEqual(hashlib.sha256((dest / path.name).read_bytes()).digest(), hashlib.sha256(path.read_bytes()).digest())

    def test_mutating_file_never_publishes_assembly(self):
        root = Path(self.temp.name) / 'source'; root.mkdir()
        path = root / 'large'; path.write_bytes(b'a' * (33 * 1024**2))
        good = LocalClient(self)
        class MutatingClient:
            def call(self, command, args=None, key=None):
                result = good.call(command, args, key)
                if command == 'capture_artifact':
                    with path.open('ab') as f: f.write(b'changed')
                return result
        self.assertFault('capture_incomplete', lambda: capture_saved_files(MutatingClient(), root, ['large'], 'mutation'))
        entries = self.call('state')['entries'].values()
        self.assertFalse(any('chunks' in info for e in entries if e['type'] == 'artifact_snapshot' for info in e['data']['files'].values()))


if __name__ == '__main__': unittest.main()
