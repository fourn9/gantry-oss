"""Anonymous peer retrieval regressions; inference is deterministic fixture logic."""
import json
import unittest
from pathlib import Path
import test_bot_development as fixtures
from gantry.crew_runtime import _execute, result_preview
from gantry.model import Fault


class PeerEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.peer = {'task': {'id':'peer','version':2,'session_id':'same','status':'completed',
            'reports':[{'report':{'summary':'😀'*20000,'unverified':['physical behavior']}}]},
            'own_change':{'id':'candidate','version':1,'files':{'a/b~c.txt':{'content':'x'*100000}}},
            'actions':[{'id':str(i),'details':{'result':{'output':'z'*50000}}} for i in range(40)],
            'development':{'state':{'id':'state'},'manifest':{}},
            'memory':{'secret':'private lesson'},'learning_plan':{'secret':'private plan'},
            'working_state':{'secret':'private note'}}
        outer=self
        class Client:
            def call(self, operation, args):
                if operation != 'get_bot_task': raise AssertionError(operation)
                return outer.peer
        self.client=Client()

    def inspect(self, **args):
        return _execute(self.client, {'task':{'session_id':'same','write_scope':[]}}, {}, {},
            'inspect', {'task_id':'peer',**args}, Path('.'), Path('.'), 'fixture')

    def test_default_overview_survives_large_result_and_avoids_private_sections(self):
        result=self.inspect()
        self.assertEqual(result['view'],'overview')
        self.assertEqual(result_preview(result),result)
        self.assertLess(len(json.dumps(result).encode()),18000)
        self.assertEqual(result['sections']['reports']['request'],{'task_id':'peer','pointer':'/task/reports'})
        for name in ['own_change','actions','development']:
            self.assertEqual(result['sections'][name]['request']['pointer'],'/'+name)
        self.assertNotIn('private',json.dumps(result))
        self.assertNotIn('memory',result['sections'])

    def test_nested_omissions_have_exact_escaped_requests(self):
        result=self.inspect(pointer='/own_change/files')
        item=result['value']['a/b~c.txt']
        self.assertTrue(item['omitted'])
        self.assertEqual(item['request']['pointer'],'/own_change/files/a~1b~0c.txt')
        child=self.inspect(**{k:v for k,v in item['request'].items() if k!='task_id'})
        leaf=child['value']['content']['request']
        self.assertEqual(leaf['pointer'],'/own_change/files/a~1b~0c.txt/content')
        chunk=self.inspect(pointer=leaf['pointer'])
        self.assertEqual(chunk['value'],'x'*chunk['next_offset'])

    def test_exact_pagination_and_unicode_survive_observe(self):
        result=self.inspect(pointer='/actions',limit=2)
        self.assertEqual(result['total'],40)
        self.assertEqual(result['next_request'],{'task_id':'peer','pointer':'/actions','offset':2,'limit':2})
        pointer='/task/reports/0/report/summary'
        first=self.inspect(pointer=pointer)
        self.assertEqual(first['value'],'😀'*first['next_offset'])
        second=self.inspect(**{k:v for k,v in first['next_request'].items() if k!='task_id'})
        self.assertEqual(second['value'],self.peer['task']['reports'][0]['report']['summary'][first['next_offset']:second['next_offset']])
        batch=_execute(self.client,{'task':{'session_id':'same','write_scope':[]}}, {}, {},'observe',
            {'requests':[{'action':'inspect','arguments':{'task_id':'peer','pointer':pointer}}]*4},Path('.'),Path('.'),'fixture')
        self.assertEqual(result_preview(batch),batch)
        self.assertNotIn('truncated',batch['items'][0]['result'])

    def test_explicit_root_and_small_pages_keep_existing_shape(self):
        self.peer={'task':{'session_id':'same'},'actions':[1,2,3]}
        self.assertEqual(self.inspect(pointer='/actions',offset=1,limit=1)['value'],[2])
        self.assertIn('value',self.inspect(pointer=''))
        self.assertIn('value',self.inspect(offset=0,limit=1))

    def test_cross_session_denied_before_overview_and_explicit_read(self):
        self.peer['task']['session_id']='foreign'
        for args in ({},{'pointer':'/task/reports'}):
            with self.assertRaises(Fault) as caught: self.inspect(**args)
            self.assertEqual(caught.exception.code,'scope_denied')


class PeerEvidenceWorkerTests(unittest.TestCase):
    def test_worker_follows_saved_reports_and_peer_redaction(self):
        from test_bot_continuity import BotContinuityTests
        from gantry.bot_worker import environment_manifest
        c=BotContinuityTests(); c.setUp(); self.addCleanup(c.tearDown)
        peer=c.task('designer')
        summary='Saved anonymous evidence. '*1000
        with c.worker('designer') as worker:
            ref=c.claimed(worker,peer)
            note=c.note(ref,focus='Private fixture strategy')
            c.clients['designer'].call('record_bot_action',{**ref,'kind':'working_state','details':{'result':note}})
            c.clients['designer'].call('finish_bot_task',{**ref,
                'report':{k:v for k,v in c.answer(summary=summary).items() if k!='edits'}})
        own=c.task('control',kind='report',write_scope=[])
        context={'task':{'session_id':c.sid,'write_scope':[]}}
        def inspect(**args):
            return _execute(c.clients['control'],context,{}, {},'inspect',
                {'task_id':peer['id'],**args},c.root,c.root,'fixture')
        self.assertNotIn('Private fixture strategy',json.dumps(inspect(pointer='/actions')))
        self.assertIsNone(inspect(pointer='/working_state')['value'])
        with self.assertRaises(Fault) as caught: inspect(pointer='/learning_plan')
        self.assertEqual(caught.exception.code,'not_found')
        c.configs['control']['agent_loop']=True
        c.owner.call('configure_bot_runtime',{'bot_id':'control','version':1,'principal_id':'control',
            'enabled':True,'environment':environment_manifest(c.configs['control'])})
        calls=[]; retrieved=[]
        def infer(ctx,schema,directory):
            calls.append(ctx)
            last=ctx['last_result']
            if len(calls)==1: action,args='inspect',{'task_id':peer['id']}
            elif last.get('view')=='overview':
                action,args='inspect',last['sections']['reports']['request']
            elif last['pointer']=='/task/reports':
                action,args='inspect',last['value'][0]['request']
            elif last['pointer']=='/task/reports/0':
                action,args='inspect',last['value']['report']['request']
            elif last['pointer']=='/task/reports/0/report':
                action,args='inspect',last['value']['summary']['request']
            else:
                retrieved.append(last['value'])
                if last['next_request']: action,args='inspect',last['next_request']
                else: action,args='finish',c.answer(summary='Retrieved saved peer report; physical behavior remains unverified')
            return {'output':{'action':action,'arguments_json':json.dumps(args),'rationale':'Fixture follows exact peer result pointers'}}
        with c.worker('control',infer) as worker: result=worker.tick()[0]
        self.assertEqual(result['task']['status'],'completed')
        self.assertEqual(''.join(retrieved),summary)
        self.assertTrue(c.owner.call('replay')['matched'])

    def test_peer_records_retrieve_beyond_recent_window_and_page_large_receipts(self):
        from test_bot_continuity import BotContinuityTests
        c=BotContinuityTests(); c.setUp(); self.addCleanup(c.tearDown)
        peer=c.task('designer')
        ids=[]
        with c.worker('designer') as worker:
            ref=c.claimed(worker,peer)
            for i in range(25):
                item=c.clients['designer'].call('record_bot_action',{**ref,'kind':'tool',
                    'details':{'result':{'output':str(i)+'x'*24000,'exit_code':0}}})
                ids.append(item['id'])
            note=c.note(ref,focus='Private historical fixture')
            c.clients['designer'].call('record_bot_action',{**ref,'kind':'working_state','details':{'result':note}})
        context={'task':{'session_id':c.sid,'write_scope':[]}}
        def run(action,args):
            return _execute(c.clients['control'],context,{}, {},action,args,c.root,c.root,'fixture')
        overview=run('inspect',{'task_id':peer['id']})
        request=overview['history']['actions']['request']; seen=[]
        while request:
            page=run('records',request)
            self.assertEqual(result_preview(page),page)
            self.assertNotIn('Private historical fixture',json.dumps(page))
            for item in page['items']:
                if item.get('omitted'):
                    row=run('records',item['request'])
                    if row['value'].get('kind')=='tool':
                        seen.append(row['value']['id'])
                        details=run('records',row['value']['details']['request'])
                        result=run('records',details['value']['result']['request'])
                        chunk=run('records',result['value']['output']['request'])
                        self.assertTrue(chunk['value'])
                        self.assertIsNotNone(chunk['next_request'])
                elif item.get('kind')=='tool': seen.append(item['id'])
            request=page['next_request']
        self.assertEqual(set(seen),set(ids))
        with self.assertRaises(Fault) as caught:
            run('records',{'task_id':peer['id'],'kind':'actions','page_hash':'stale'})
        self.assertEqual(caught.exception.code,'stale_basis')
        with self.assertRaises(Fault) as caught:
            run('records',{'task_id':peer['id'],'kind':'learning_uses'})
        self.assertEqual(caught.exception.code,'unauthorized')
        context['task']['session_id']='foreign'
        with self.assertRaises(Fault) as caught:
            run('records',{'task_id':peer['id'],'kind':'actions'})
        self.assertEqual(caught.exception.code,'scope_denied')
