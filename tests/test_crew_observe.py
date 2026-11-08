"""Anonymous retrieval comparison through the real Core/worker; inference is a fixture."""
import json
from pathlib import Path
import tempfile
import unittest
import test_bot_development as fixtures
from gantry.crew_runtime import _execute, result_preview
from gantry.model import Fault, canonical


class ObserveTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        self.root = Path(t.name).resolve()
        (self.root/'part.txt').write_text('shared geometry')
        self.context = {'task': {'write_scope': ['part.txt'], 'studio_mode': 'ask'}}

    def observe(self, requests):
        return _execute(None, self.context, {}, {}, 'observe', {'requests': requests}, self.root, self.root, 'fixture')

    def test_batch_returns_individual_source_hashes_and_errors(self):
        result = self.observe([{'action': 'read', 'arguments': {'path': 'part.txt'}},
                               {'action': 'context', 'arguments': {'pointer': '/missing'}}])
        self.assertEqual(result['items'][0]['result']['text'], 'shared geometry')
        self.assertIn('hash', result['items'][0]['result'])
        self.assertEqual(result['items'][1]['result']['error'], 'not_found')
        self.assertEqual(result_preview(result), result)
        self.assertFalse(result['atomic_snapshot'])

    def test_rejects_mutations_recursion_and_overlarge_batch_before_any_execution(self):
        for action in ('edit', 'tool', 'observe', 'decision'):
            with self.subTest(action=action), self.assertRaises(Fault):
                self.observe([{'action':'read','arguments':{'path':'part.txt'}}, {'action':action,'arguments':{}}])
        with self.assertRaises(Fault):
            self.observe([{'action':'read','arguments':{'path':'part.txt'}}]*5)
        self.assertEqual((self.root/'part.txt').read_text(), 'shared geometry')

    def test_encoded_results_are_bounded_and_omissions_have_retrieval_reference(self):
        self.context['large'] = {str(i): 'x'*7000 for i in range(8)}
        result = self.observe([{'action':'context','arguments':{'pointer':'/large'}}]*4)
        self.assertLess(len(canonical(result).encode()), 90000)
        for item in result['items']:
            self.assertTrue(item['result']['truncated'])
            self.assertIn('sha256', item['result'])
            self.assertEqual(item['request']['arguments']['pointer'], '/large')

    def test_path_traversal_stays_rejected_inside_batch(self):
        result = self.observe([{'action':'read','arguments':{'path':'../outside'}}])
        self.assertEqual(result['items'][0]['result']['error'], 'scope_denied')

    def test_batched_reads_deliver_exact_byte_cursor_and_bounded_unicode(self):
        raw=('😀"\\\n'*3000).encode(); (self.root/'part.txt').write_bytes(raw)
        result=self.observe([{'action':'read','arguments':{'path':'part.txt','length':6000}}]*4)
        import base64
        for item in result['items']:
            chunk=item['result']
            data=chunk['text'].encode() if 'text' in chunk else base64.b64decode(chunk['base64'])
            self.assertEqual(data,raw[:2000]); self.assertEqual(chunk['next_offset'],2000)
        self.assertEqual(result_preview(result),result)
        self.assertLess(len(canonical(result).encode()),90000)

    def test_peer_project_restriction_is_preserved(self):
        class Client:
            def call(self,*args): return {'task':{'session_id':'foreign'}}
        self.context['task']['session_id']='own'
        result=_execute(Client(),self.context,{}, {},'observe',{'requests':[
            {'action':'inspect','arguments':{'task_id':'foreign-task'}}]},self.root,self.root,'fixture')
        self.assertEqual(result['items'][0]['result']['error'],'scope_denied')

    def test_unicode_context_batch_survives_the_actual_inline_preview_budget(self):
        self.context['unicode']='😀'*4000
        result=self.observe([{'action':'context','arguments':{'pointer':'/unicode'}}]*4)
        self.assertEqual(result_preview(result),result)
        self.assertEqual(len(result['items']),4)
        self.assertLessEqual(len(json.dumps(result).encode()),96000)

    def test_mixed_batch_history_keeps_newest_observations_in_time_order(self):
        from gantry.bot_observations import recent_context
        def action(i,kind,result):
            return {'id':str(i),'task_id':'own','attempt':1,'kind':kind,
                'details':{'arguments':'{}','result':result}}
        singles=[action(i,'context',{'value':i}) for i in range(8,3,-1)]
        batch=action('batch','observe',{'items':[{'request':{'action':'context','arguments':{'pointer':'/value'}},
            'result':{'value':i}} for i in range(4)]})
        packet=recent_context({'task':{'id':'own'},'actions':singles+[batch]})
        self.assertEqual([item['result']['value'] for item in packet['items']],list(range(1,9)))
        self.assertEqual([item['observation_index'] for item in packet['items'][:3]],[1,2,3])
        self.assertEqual(packet['coverage']['scanned_actions'],6)


class ObserveWorkerTests(unittest.TestCase):
    def run_fixture(self, batched):
        import test_bot_development as fixtures
        from gantry.bot_worker import environment_manifest
        c = fixtures.BotDevelopmentTests(); original = c.artifact
        c.artifact = lambda files: original({**files, 'sensor.txt':'sensor input', 'limits.txt':'accepted limits'})
        c.setUp(); self.addCleanup(c.tearDown)
        c.configs['designer']['agent_loop'] = True
        c.owner.call('configure_bot_runtime', {'bot_id':'designer','version':1,'principal_id':'designer',
            'enabled':True,'environment':environment_manifest(c.configs['designer'])})
        task = c.task('designer', kind='report', write_scope=[])
        requests = [{'action':'read','arguments':{'path':p}} for p in ['mechanical.txt','control.txt','sensor.txt','limits.txt']]
        contexts = []; observed = []
        def infer(context, schema, directory):
            contexts.append(context)
            if context['last_result'] is not None:
                if batched: observed.extend(i['result'] for i in context['last_result']['items'])
                else: observed.append(context['last_result'])
            index = len(contexts)-1
            if index < (1 if batched else 4):
                action, args = ('observe', {'requests':requests}) if batched else (requests[index]['action'],requests[index]['arguments'])
            else:
                if batched:
                    self.assertEqual(len(context['read_observations']['items']), 4)
                    self.assertEqual({i['observation_index'] for i in context['read_observations']['items']}, {0,1,2,3})
                action,args='finish',c.answer(summary='Read four saved sources')
            return {'output':{'action':action,'arguments_json':json.dumps(args),'rationale':'Retrieve independent sources'}}
        with c.worker('designer',infer) as worker: outcome=worker.tick()[0]
        self.assertEqual(outcome['task']['status'],'completed')
        self.assertTrue(c.owner.call('replay')['matched'])
        from gantry.crew_timing import summarize
        timing=summarize(c.root)
        self.assertEqual(timing['phases']['model']['count'],len(contexts))
        self.assertEqual(timing['incomplete'],0)
        return len(contexts), observed

    def test_four_observations_need_two_model_turns_instead_of_five_with_equal_sources(self):
        single_count, single = self.run_fixture(False)
        batch_count, batch = self.run_fixture(True)
        self.assertEqual((single_count,batch_count),(5,2))
        self.assertEqual(single,batch)
