"""Studio requests use real Core/worker paths, fixture reasoning is explicit."""
import unittest
import test_bot_development as fixtures


class StudioBotTests(unittest.TestCase):
    setUp = fixtures.BotDevelopmentTests.setUp
    tearDown = fixtures.BotDevelopmentTests.tearDown
    artifact = fixtures.BotDevelopmentTests.artifact
    scope = fixtures.BotDevelopmentTests.scope
    fault = fixtures.BotDevelopmentTests.fault
    worker = fixtures.BotDevelopmentTests.worker
    infer = fixtures.BotDevelopmentTests.infer
    answer = fixtures.BotDevelopmentTests.answer
    assignment = fixtures.BotDevelopmentTests.assignment

    def work(self):
        project = self.owner.call('save_project', {'name':'Assembly', 'description':'Anonymous fixture', 'baseline_state':self.base['id']})
        self.owner.call('link_product_session', {'session_id':self.sid, 'project_id':project['id']})
        change = self.owner.call('begin_change', {'state_id':self.base['id'], 'title':'Update interface',
            'purpose':'Keep mechanical and control interfaces consistent', 'write_scope':self.scope('lead'),
            'dependencies':[], 'assignee':'admin'})
        return project, change

    def request(self, work, mode='ask', **extra):
        return {'work_id':work['id'], 'version':work['version'], 'state_id':work['head'],
            'anchor':{'kind':'work'}, 'mode':mode, 'bot_id':'designer', 'body':'Inspect the interface',
            'completion':['Return an evidence-based answer'], 'write_scope':[] if mode=='ask' else ['mechanical.txt'],
            **extra}

    def test_project_component_question_returns_without_creating_work(self):
        project, work = self.work()
        before = self.owner.call('studio_overview')['total']
        anchor = {'kind':'component','component_id':self.base['hierarchy'][0]['id']}
        target = {'project_id':project['id'],'state_id':self.base['id'],'anchor':anchor}
        related = self.owner.call('studio_related',target)
        person = next(p for p in related['participants'] if p['bot_ids'] and 'designer' in p['bot_ids'])
        self.assertTrue(person['name'])
        self.assertTrue(person['role'])
        for i in range(51):
            self.owner.call('studio_comment',{**target,'body':f'Earlier comment {i}','mentions':[]})
        request = self.owner.call('studio_request_bot',{**target,'version':related['session_version'],
            'mode':'ask','bot_id':'designer','body':'Inspect this saved component',
            'completion':['Return evidence and limitations'],'write_scope':[]})
        with self.worker('designer',lambda *args:{'output':self.answer(summary='Need measurement'),'provider':{'kind':'fixture'}}) as worker:
            self.assertEqual(worker.tick()[0]['task']['status'],'completed')
        view = self.owner.call('studio_related',target)
        self.assertEqual(view['bot_requests'][0]['status'],'completed')
        other=self.owner.call('studio_related',{**target,'anchor':{'kind':'project'}})
        self.assertFalse(other['bot_requests'])
        self.assertEqual(view['threads'][0]['messages'][-1]['body'].split('\n')[0],'Need measurement')
        self.assertEqual(self.owner.call('studio_overview')['total'],before)
        self.assertEqual(self.owner.call('studio_inbox')['items'][0]['project_id'],project['id'])

    def test_ask_pins_context_queues_offline_and_returns_to_same_selection(self):
        project, work = self.work()
        team = self.owner.call('studio_team', {'project_id':project['id']})
        self.assertEqual(team['sessions'][0]['bots'][0]['runtime']['presence'], 'offline')
        request = self.owner.call('studio_request_bot', self.request(work), 'ask-once')
        self.assertEqual(request, self.owner.call('studio_request_bot', self.request(work), 'ask-once'))
        seen = []
        def reply(ctx, schema, directory):
            seen.append(ctx['studio_request'])
            return {'output':self.answer(summary='Interface still needs measurement'), 'provider':{'kind':'fixture'}}
        with self.worker('designer', reply) as worker:
            self.assertEqual(worker.tick()[0]['task']['status'], 'completed')
        view = self.owner.call('studio_work', {'work_id':work['id']})
        self.assertEqual(view['work']['head'], work['head'])
        self.assertEqual(seen[0]['anchor'], {'kind':'work'})
        self.assertEqual(seen[0]['state_id'], work['head'])
        self.assertEqual(view['bot_requests'][0]['status'], 'completed')
        messages = view['threads'][0]['messages']
        self.assertEqual(messages[-1]['body'].split('\n')[0], 'Interface still needs measurement')
        self.assertEqual(messages[-1]['bot_id'], 'designer')
        self.assertEqual(self.owner.call('studio_inbox')['items'][0]['state_id'],work['head'])
        self.assertFalse(self.owner.call('review_automation_status', {'session_id':self.sid})['jobs'])
        self.assertTrue(self.owner.call('replay')['matched'])

    def test_ask_cannot_edit_delegate_or_integrate_and_bad_anchor_rolls_back(self):
        _, work = self.work()
        self.fault('invalid_input', lambda:self.owner.call('studio_request_bot',self.request(work,write_scope=['mechanical.txt'])))
        self.fault('invalid_input', lambda:self.owner.call('studio_request_bot',self.request(work,anchor={'kind':'code','path':'mechanical.txt','hash':'bad','line':1})))
        self.assertFalse(self.owner.call('list_bot_tasks', {'session_id':self.sid})['items'])
        request = self.owner.call('studio_request_bot',self.request(work,bot_id='lead'))
        with self.worker('lead') as worker:
            result = worker.tick()[0]
            self.assertEqual(result['reason'], 'scope_denied')
        view = self.owner.call('studio_work', {'work_id':work['id']})
        self.assertEqual(view['bot_requests'][0]['status'], 'held')
        self.assertEqual(len(self.owner.call('list_bot_tasks', {'session_id':self.sid})['items']),1)

    def test_assignment_returns_shared_candidate_without_overwriting_origin(self):
        _, work = self.work()
        self.owner.call('studio_request_bot',self.request(work,'assign'))
        with self.worker('designer') as worker:
            task = worker.tick()[0]['task']
        view = self.owner.call('studio_work', {'work_id':work['id']})
        self.assertEqual(view['bot_requests'][0]['result_work_id'],task['change_id'])
        candidate = self.owner.call('studio_work', {'work_id':task['change_id']})
        self.assertEqual(candidate['selected']['status']['sharing'], 'shared')
        self.assertEqual(candidate['selected']['status']['adoption'], 'unadopted')
        self.assertEqual(candidate['selected']['status']['verification'], 'unverified')
        self.assertEqual(view['work']['head'], work['head'])
        self.fault('scope_denied', lambda:self.owner.call('studio_request_bot',self.request(work,'assign',write_scope=['control.txt'])))

    def test_plain_mention_does_not_dispatch_and_stale_assignment_is_rejected(self):
        _, work = self.work()
        self.owner.call('studio_comment', {'work_id':work['id'],'state_id':work['head'], 'anchor':{'kind':'work'},'body':'Hello','mentions':['designer']})
        self.assertFalse(self.owner.call('list_bot_tasks', {'session_id':self.sid})['items'])
        self.fault('stale_basis',lambda:self.owner.call('studio_request_bot',self.request(work,'assign',version=work['version']+1)))
        self.fault('unauthorized',lambda:self.clients['control'].call('studio_request_bot',self.request(work,'assign')))

    def test_team_setup_retains_identity_requires_owner_and_existing_delegation(self):
        project, work=self.work()
        current=self.owner.call('studio_team',{'project_id':project['id']})['sessions'][0]
        members=[dict(bot_id=row['bot']['id'],name=row['bot']['name'],parent_bot_id=row['bot']['parent_bot_id'],
            profile=row['bot']['profile'],**{k:row['binding'][k] for k in ('principal_id','write_scope','can_assign','can_integrate')}) for row in current['bots']]
        args={'session_id':self.sid,'configuration_token':current['configuration_token'],'goal':'Continue assembly design',
            'acceptance':['Measured compatible interfaces'],'lead_bot_id':'lead','members':members}
        self.fault('unauthorized',lambda:self.clients['lead'].call('studio_setup_team',args))
        updated=self.owner.call('studio_setup_team',args)
        self.assertEqual({b['bot']['id'] for b in updated['bots']},set(self.clients))
        self.fault('stale_basis',lambda:self.owner.call('studio_setup_team',args))
        self.assertNotIn('fence',str(updated))
        self.assertNotIn('token_hash',str(updated))

    def test_handoff_fences_source_requires_stop_ack_and_recipient_acceptance(self):
        _, work=self.work()
        req=self.owner.call('studio_request_bot',self.request(work,'assign'))
        with self.worker('designer') as source:
            old=self.clients['designer'].call('claim_bot_task',{'task_id':req['task_id'],'version':1,'runtime_fence':source.runtime['fence']})
            ref={'task_id':req['task_id'],'fence':old['task']['fence']}
            cp=self.clients['designer'].call('checkpoint_bot_task',{**ref,'snapshot':self.artifact({'mechanical.txt':'intermediate','control.txt':'1'}),
                'summary':'Intermediate saved design','rationale':'Needs more work','unfinished':['Measure clearance'],
                'capture':{'scope':'saved files','missing':['unsaved operations']}})
            task=self.owner.call('get_bot_task',{'task_id':req['task_id']})['task']
            handoff=self.owner.call('request_bot_handoff',{'task_id':task['id'],'version':task['version'],'to_bot_id':'mechanical','reason':'Department manager takes over'})
            self.fault('stale_basis',lambda:self.clients['designer'].call('check_bot_task',ref))
            with self.worker('mechanical') as recipient:
                args={'handoff_id':handoff['id'],'version':handoff['version'],'runtime_fence':recipient.runtime['fence']}
                self.fault('invalid_state',lambda:self.clients['mechanical'].call('accept_bot_handoff',args))
                ready=self.clients['designer'].call('acknowledge_bot_handoff',{'handoff_id':handoff['id'],'version':handoff['version'],
                    'confirm_stopped':'Executor stopped; saved checkpoint inspected','summary':'Continue the saved intermediate design','unfinished':['Measure clearance']})
                accepted=self.clients['mechanical'].call('accept_bot_handoff',{**args,'version':ready['version']})
                current=self.clients['mechanical'].call('get_bot_task',{'task_id':accepted['successor_task_id']})
                self.assertEqual(current['task']['state_id'],cp['state']['id'])
                self.assertEqual(current['handoff']['unfinished'],['Measure clearance'])
                self.assertEqual(self.owner.call('get_bot_task',{'task_id':task['id']})['task']['status'],'cancelled')
                view=self.owner.call('studio_work',{'work_id':work['id']})
                self.assertEqual(view['bot_requests'][0]['bot_id'],'mechanical')
                self.assertEqual(len(view['bot_requests'][0]['task_ids']),2)
        self.assertTrue(self.owner.call('replay')['matched'])

    def test_read_only_ask_rejects_direct_mcp_side_effects(self):
        _,work=self.work()
        other=self.owner.call('assign_bot_task',dict(self.assignment('control'),session_id=self.sid))
        ask=self.owner.call('studio_request_bot',self.request(work,bot_id='lead'))
        with self.worker('lead') as worker:
            claim=self.clients['lead'].call('claim_bot_task',{'task_id':ask['task_id'],'version':1,'runtime_fence':worker.runtime['fence']})
            ref={'task_id':ask['task_id'],'fence':claim['task']['fence']}
            note=self.clients['lead'].call('update_bot_working_state',{**ref,'version':0,
                'focus':'Answer the selected interface question','next_steps':['Read saved evidence'],
                'commitments':[],'unknowns':['Clearance not measured'],'watch_paths':[],
                'watch_tasks':[],'due_at':None})
            self.assertEqual(note['source_task_id'],ask['task_id'])
            self.fault('scope_denied',lambda:self.clients['lead'].call('assign_bot_task',dict(self.assignment('mechanical'),session_id=self.sid,requested_by_bot='lead')))
            self.fault('scope_denied',lambda:self.clients['lead'].call('stop_bot_task',{**ref,'target_task_id':other['id'],'version':other['version'],'reason':'Not authorized by Ask'}))
            self.fault('unauthorized',lambda:self.clients['lead'].call('begin_change',{'state_id':self.base['id'],'title':'Bypass','purpose':'No','write_scope':['mechanical.txt'],'dependencies':[],'assignee':'lead'}))
            self.clients['lead'].call('finish_bot_task',{**ref,'report':{k:v for k,v in self.answer().items() if k!='edits'}})
        self.assertEqual(self.owner.call('get_bot_task',{'task_id':other['id']})['task']['status'],'pending')

    def test_handoff_returns_saved_edits_and_unblocks_downstream_task(self):
        _,work=self.work(); req=self.owner.call('studio_request_bot',self.request(work,'assign'))
        downstream=self.owner.call('assign_bot_task',dict(self.assignment('control'),session_id=self.sid,after_tasks=[req['task_id']]))
        with self.worker('designer') as source:
            claimed=self.clients['designer'].call('claim_bot_task',{'task_id':req['task_id'],'version':1,'runtime_fence':source.runtime['fence']})
            saved=self.clients['designer'].call('checkpoint_bot_task',{'task_id':req['task_id'],'fence':claimed['task']['fence'],
                'snapshot':self.artifact({'mechanical.txt':'saved edit','control.txt':'1'}),'summary':'Saved edit','rationale':'Partial work','unfinished':['Review'],
                'capture':{'scope':'saved files','missing':[]}})
            task=self.owner.call('get_bot_task',{'task_id':req['task_id']})['task']
            h=self.owner.call('request_bot_handoff',{'task_id':task['id'],'version':task['version'],'to_bot_id':'mechanical','reason':'Review and continue'})
        self.owner.call('acknowledge_bot_handoff',{'handoff_id':h['id'],'version':1,'confirm_stopped':'Worker exited','summary':'Continue saved edit','unfinished':['Review']})
        with self.worker('mechanical',lambda *args:{'output':self.answer(summary='Reviewed saved edit'),'provider':{'kind':'fixture'}}) as worker:
            result=worker.tick()[-1]['task']
        self.assertEqual(result['status'],'completed')
        candidate=self.owner.call('studio_work',{'work_id':result['change_id']})
        self.assertEqual(candidate['work']['base_state'],self.base['id'])
        self.assertEqual(candidate['selected']['status']['sharing'],'shared')
        self.assertEqual(candidate['selected']['manifest']['mechanical.txt']['hash'],self.owner.call('get_development_state',{'state_id':saved['state']['id']})['manifest']['mechanical.txt']['hash'])
        with self.worker('control') as worker:self.assertEqual(worker.tick()[0]['task']['status'],'completed')
        self.assertTrue(self.owner.call('replay')['matched'])

    def test_runtime_cannot_be_reconfigured_while_online(self):
        from gantry.bot_worker import environment_manifest
        with self.worker('designer'):
            self.fault('conflict',lambda:self.owner.call('configure_bot_runtime',{'bot_id':'designer','version':1,
                'principal_id':'designer','enabled':True,'environment':environment_manifest(self.configs['designer'])}))

    def test_studio_parallel_candidates_manager_selection_and_return(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        _,work=self.work(); barrier=threading.Barrier(2)
        req=self.owner.call('studio_request_bot',self.request(work,'assign',bot_id='lead'))
        def manager(ctx,*args):
            if not ctx['children']:
                answer=self.answer(status='waiting',assignments=[self.assignment(name,candidate_id=cid,write_scope=['mechanical.txt']) for name,cid in [('designer','A'),('mechanical','B')]])
            else:
                chosen=next(c for c in ctx['candidate_changes'] if c['candidate_id']=='B')['change']
                answer=self.answer(summary='Fixture comparison selected candidate B',integrate_changes=[{'id':chosen['id'],'version':chosen['version']}])
            return {'output':answer,'provider':{'kind':'deterministic_fixture'}}
        def candidate(ctx,*args):
            barrier.wait(timeout=10)
            return {'output':self.answer(edits=[{'path':'mechanical.txt','content':ctx['task']['candidate_id']}]),'provider':{'kind':'deterministic_fixture'}}
        with self.worker('lead',manager) as lead:
            self.assertEqual(lead.tick()[0]['task']['status'],'waiting')
            with self.worker('designer',candidate) as a,self.worker('mechanical',candidate) as b:
                with ThreadPoolExecutor(2) as pool:
                    futures=[pool.submit(w.tick) for w in (a,b)]
                    for f in futures:self.assertEqual(f.result()[0]['task']['status'],'completed')
            result=lead.tick()[0]['task']
        view=self.owner.call('studio_work',{'work_id':result['change_id']})
        self.assertEqual(view['work']['base_state'],self.base['id'])
        self.assertEqual(view['selected']['status']['sharing'],'shared')
        self.assertTrue(view['selected']['diffs'])
        self.assertEqual(view['selected']['status']['adoption'],'unadopted')
        original=self.owner.call('studio_work',{'work_id':work['id']})
        self.assertEqual(len(original['bot_requests'][0]['children']),2)
        self.assertEqual(original['work']['head'],work['head'])
        self.assertFalse(self.owner.call('review_automation_status',{'session_id':self.sid})['jobs'])

    def test_http_worker_external_executable_and_saved_queue_restart(self):
        import hashlib,json,sys,threading
        from gantry.server import Server
        from gantry.client import Client
        from gantry.service import Service
        from gantry.bot_worker import BotWorker,environment_manifest
        from test_development import LocalClient
        _,work=self.work();req=self.owner.call('studio_request_bot',self.request(work,'assign'))
        # Restart the ledger before a customer executor connects.
        self.service=Service(self.root/'ledger');self.owner=LocalClient(self.service,self.token)
        bridge=self.root/'bridge.py'
        bridge.write_text('import json,sys\nfrom pathlib import Path\np=json.load(sys.stdin)\nw=Path(p["context"]["workspace"])\nf=w/"mechanical.txt"\nf.write_text("2")\nassert f.read_text()=="2"\nprint(json.dumps('+repr(self.answer(summary='Saved file edited and checked by customer subprocess'))+'))\n')
        cfg={**self.configs['designer'],'command':[str(__import__('pathlib').Path(sys.executable).resolve()),str(bridge)],'executable_hash':hashlib.sha256(__import__('pathlib').Path(sys.executable).read_bytes()).hexdigest()}
        self.owner.call('configure_bot_runtime',{'bot_id':'designer','version':1,'principal_id':'designer','enabled':True,'environment':environment_manifest(cfg)})
        server=Server(('127.0.0.1',0),self.service);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            url='http://127.0.0.1:'+str(server.server_port)
            from urllib.request import urlopen
            for asset in ('studio_library_ui.js','studio_library_views.js'):
                with urlopen(url+'/'+asset) as response:
                    self.assertEqual(response.status,200)
                    self.assertIn('javascript',response.headers['Content-Type'])
            with BotWorker(Client(url,self.tokens['designer']),cfg,self.root/'http-worker') as worker:
                result=worker.tick()[0]
            self.assertIn('task',result,result)
            self.assertEqual(result['task']['status'],'completed',result)
            view=Client(url,self.token).call('studio_work',{'work_id':work['id']})
            candidate=Client(url,self.token).call('studio_work',{'work_id':view['bot_requests'][0]['result_work_id']})
            self.assertTrue(candidate['selected']['diffs'])
            self.assertEqual(candidate['selected']['status']['verification'],'unverified')
            self.assertIn('subprocess',view['threads'][0]['messages'][-1]['body'])
        finally:server.shutdown();server.server_close();thread.join()

    def test_interrupted_ask_can_restart_and_handoff_to_same_identity(self):
        from gantry.model import Fault
        _,work=self.work();req=self.owner.call('studio_request_bot',self.request(work))
        def interrupted(*args):raise Fault('provider_unavailable','Fixture process exited')
        with self.worker('designer',interrupted) as worker:self.assertEqual(worker.tick()[0]['status'],'held')
        # A stopped executor may reconnect despite the read-only task guard.
        with self.worker('designer',lambda *a:{'output':self.answer(),'provider':{'kind':'fixture'}}) as worker:
            result=worker.recover(req['task_id'],'Prior fixture process has exited')
            self.assertEqual(result['task']['status'],'completed')
        next_request=self.owner.call('studio_request_bot',self.request(work))
        with self.worker('designer') as worker:
            claim=self.clients['designer'].call('claim_bot_task',{'task_id':next_request['task_id'],'version':1,'runtime_fence':worker.runtime['fence']})
            h=self.owner.call('request_bot_handoff',{'task_id':next_request['task_id'],'version':claim['task']['version'],
                'to_bot_id':'designer','reason':'Reconnect with the same persistent identity'})
        self.owner.call('acknowledge_bot_handoff',{'handoff_id':h['id'],'version':1,'confirm_stopped':'Worker context exited',
            'summary':'Keep the exact question','unfinished':['Answer']})
        with self.worker('designer',lambda *a:{'output':self.answer(),'provider':{'kind':'fixture'}}) as worker:
            results=worker.tick();self.assertEqual(results[0]['phase'],'accepted');self.assertEqual(results[-1]['task']['status'],'completed')
        view=self.owner.call('studio_work',{'work_id':work['id']})
        self.assertTrue(all(r['status']=='completed' for r in view['bot_requests']))

    def test_cancelled_handoff_is_not_left_ready_to_retry(self):
        _,work=self.work();req=self.owner.call('studio_request_bot',self.request(work,'assign'))
        h=self.owner.call('request_bot_handoff',{'task_id':req['task_id'],'version':1,'to_bot_id':'mechanical','reason':'Transfer'})
        self.owner.call('acknowledge_bot_handoff',{'handoff_id':h['id'],'version':1,'confirm_stopped':'No executor started','summary':'Queued work','unfinished':[]})
        self.owner.call('cancel_bot_task',{'task_id':req['task_id'],'version':2,'reason':'Cancelled by owner'})
        self.assertEqual(self.owner.call('list_bot_handoffs',{'bot_id':'mechanical'})['items'][0]['phase'],'cancelled')
        with self.worker('mechanical') as worker:self.assertEqual(worker.tick(),[])

    def test_studio_execution_rejects_human_credentials_even_if_bound_to_bot(self):
        from gantry.service import token_hash
        from gantry.agent_connection import PROFILES
        project,work=self.work()
        proposal=self.owner.call('propose',{'title':'Fixture human-bound legacy Bot','changes':[{'id':'designer','type':'principal','expected_revision':self.owner.call('state')['entries']['designer']['revision_id'],
            'data':{'kind':'human','permissions':['read','record','work'],'token_hash':token_hash(self.tokens['designer']),
            'zones':['root'],'allowed_commands':sorted(PROFILES['bot'])}}]})
        ref={'proposal_id':proposal['id'],'version':proposal['version']}
        self.owner.call('submit',ref);self.owner.call('endorse',{**ref,'reason':'Fixture'})
        self.owner.call('review_adoption',{**ref,'verdict':'approve','reason':'Fixture'});self.owner.call('commit',ref)
        self.fault('unauthorized',lambda:self.owner.call('studio_request_bot',self.request(work)))
        principals=self.owner.call('studio_team',{'project_id':project['id']})['sessions'][0]['principals']
        self.assertNotIn('designer',[p['id'] for p in principals])
