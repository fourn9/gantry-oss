import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from gantry.model import canonical
import test_crew_runtime as fixtures


class BotReadObservationTests(unittest.TestCase):
    def test_actual_chunk_reads_survive_unrelated_result_and_edit_invalidates(self):
        c = fixtures.CrewRuntimeTests(); c.setUp(); self.addCleanup(c.tearDown)
        c.enable_loop('designer'); c.task('designer'); seen = []
        content = ''.join(f'{i:05}: anonymous source\n' for i in range(900))
        source_hash = hashlib.sha256(content.encode()).hexdigest()
        chunks = list(range(0, len(content.encode()), 6000))
        def infer(ctx, schema, directory):
            seen.append(ctx); n = len(seen)-1
            if n == 0:
                return c.action('edit', {'path': 'mechanical.txt', 'content': content,
                    'expected_hash': hashlib.sha256(b'1').hexdigest()})
            if n <= len(chunks): return c.action('read', {'path': 'mechanical.txt', 'offset': chunks[n-1]})
            if n == len(chunks)+1: return c.action('read', {'path': 'control.txt'})
            if n == len(chunks)+2:
                self.assertEqual(ctx['last_result']['text'], '1')
                observations = ctx['read_observations']['items']
                matching = sorted((o for o in observations if o['path'] == 'mechanical.txt'), key=lambda o:o['offset'])
                self.assertEqual(''.join(o['text'] for o in matching), content)
                self.assertTrue(all(o['hash'] == source_hash and o['action_id'] and o['attempt'] == 1 for o in matching))
                return c.action('edit', {'path':'mechanical.txt', 'content':'new source', 'expected_hash':source_hash})
            self.assertFalse([o for o in ctx['read_observations']['items'] if o['path'] == 'mechanical.txt'])
            self.assertGreater(ctx['read_observations']['coverage']['omitted'].get('stale_source', 0), 0)
            return c.action('finish', c.answer())
        with c.worker('designer', infer) as worker: result = worker.tick()[0]
        self.assertEqual(result['task']['status'], 'completed')
        self.assertTrue(c.owner.call('replay')['matched'])

    def context(self, root, text, count=1):
        raw=text.encode(); (root/'source.txt').write_bytes(raw); sha=hashlib.sha256(raw).hexdigest()
        actions=[]
        for i in range(count):
            offset=(i*4000)%max(1,len(raw))
            chunk=raw[offset:offset+4000]
            actions.append({'id':f'action-{i}', 'task_id':'task', 'attempt':1, 'kind':'read', 'details':{
                'arguments':json.dumps({'path':'source.txt','offset':offset}),
                'result':{'text':chunk.decode(), 'hash':sha,'size':len(raw),
                          'next_offset':offset+len(chunk) if offset+len(chunk)<len(raw) else None}}})
        return {'task':{'id':'task'},'actions':list(reversed(actions)),'development':{'manifest':{'source.txt':{'hash':sha,'size':len(raw)}}}}

    def test_packet_scan_and_source_io_are_bounded_and_duplicates_not_repeated(self):
        from gantry.bot_observations import recent_reads
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); context=self.context(root,'x'*100000,1000)
            result=recent_reads(context,root)
            self.assertLessEqual(len(canonical(result).encode()),32768)
            self.assertLessEqual(len(result['items']),8)
            self.assertLessEqual(result['coverage']['scanned_actions'],64)
            self.assertLessEqual(result['coverage']['source_bytes_checked'],2*1024*1024)
            self.assertEqual(result['coverage']['source_files_checked'],1)
            identities=[(o['path'],o['hash'],o['offset']) for o in result['items']]
            self.assertEqual(len(set(identities)),len(identities))
            self.assertGreater(result['coverage']['older_actions_not_scanned'],0)

    def test_foreign_symlink_secret_and_forged_bytes_never_enter_observations(self):
        from gantry.bot_observations import recent_reads
        for kind in ('foreign','symlink','secret','forged','changed'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp); context=self.context(root,'safe source')
                if kind=='foreign': context['actions'][0]['task_id']='other-task'
                if kind=='symlink':
                    (root/'source.txt').unlink(); (root/'target').write_text('safe source'); (root/'source.txt').symlink_to(root/'target')
                if kind=='secret':
                    context=self.context(root,'-----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY-----')
                if kind=='forged': context['actions'][0]['details']['result']['text']='forged answer'
                if kind=='changed': (root/'source.txt').write_text('changed outside ledger')
                result=recent_reads(context,root)
                self.assertEqual(result['items'],[])
                self.assertNotIn('secret',json.dumps(result))
                self.assertNotIn('forged answer',json.dumps(result))
