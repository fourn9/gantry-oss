"""Learning contracts use real Core; reasoning is explicitly a deterministic fixture."""
from test_bot_development import BotDevelopmentTests


class BotLearningTests(BotDevelopmentTests):
    def claimed(self, worker, task, name='designer'):
        claim = self.clients[name].call('claim_bot_task', {'task_id': task['id'],
            'version': task['version'], 'runtime_fence': worker.runtime['fence']})
        return {'task_id': task['id'], 'fence': claim['task']['fence']}

    def seed(self, ref, text='Check clamp clearance before routing', name='designer'):
        return self.clients[name].call('record_bot_experience', {**ref, 'observation': text,
            'applicability': 'Same assembly; recheck other environments', 'limitations': ['Fixture only'],
            'evidence': [self.base['id']], 'used_memories': []})

    def plan_output(self, packet, decisions=None):
        return {'decisions': decisions if decisions is not None else [
            {'memory_id': m['id'], 'use': 'recheck', 'reason': 'Check evidence before use'}
            for m in packet['recall']['items']],
            'steps': ['Inspect clamp clearance before routing'], 'consult_bot_ids': [],
            'unknowns': ['Physical behavior'], 'rationale': 'Conditional experience changes ordering'}

    def plan(self, ref, decisions=None):
        p = self.clients['designer'].call('prepare_bot_learning', ref)
        return self.clients['designer'].call('submit_bot_learning_plan', {**ref, 'plan_id': p['id'],
            'output': self.plan_output(p, decisions)})

    def test_older_relevant_experience_reaches_frozen_plan(self):
        task = self.task('designer', title='Improve clamp clearance', dependencies=['mechanical.txt'])
        with self.worker('designer') as worker:
            ref = self.claimed(worker, task)
            old = self.seed(ref)
            for i in range(35): self.seed(ref, 'Unrelated administrative note '+str(i))
            p = self.clients['designer'].call('prepare_bot_learning', ref)
            self.assertEqual(p['recall']['items'][0]['id'], old['id'])
            self.assertEqual(p['recall']['method'], 'scoped_lexical_paths_requirements')
            result = self.clients['designer'].call('submit_bot_learning_plan', {**ref, 'plan_id': p['id'],
                'output': self.plan_output(p)})
            self.assertEqual(result['status'], 'completed')
            view = self.clients['designer'].call('get_bot_task', {'task_id': task['id']})
            self.assertEqual(view['learning_plan']['output']['steps'][0], 'Inspect clamp clearance before routing')
        self.assertTrue(self.owner.call('replay')['matched'])

    def test_actual_report_queues_reflection_and_next_task_receives_lesson(self):
        task = self.task('designer', dependencies=['mechanical.txt'])
        with self.worker('designer') as worker:
            ref = self.claimed(worker, task); self.plan(ref)
            report = {k:v for k,v in self.answer(status='failed', summary='Clamp interference observed').items() if k!='edits'}
            result = self.clients['designer'].call('finish_bot_task', {**ref, 'report': report})
            jobs = self.clients['designer'].call('list_bot_reflections', {'bot_id':'designer'})['items']
            self.assertEqual(len(jobs),1)
            packet = self.clients['designer'].call('get_bot_reflection', {'reflection_id':jobs[0]['id']})
            self.assertEqual(packet['report']['status'],'failed')
            lesson = {'kind':'procedure', 'observation':'Clamp interfered with route',
                'strategy':'Inspect clearance before detailed routing', 'when_to_use':'This assembly routing',
                'when_not_to_use':['Different fixture geometry'], 'paths':['mechanical.txt'], 'tags':['clamp'],
                'evidence':[task['id']], 'supersedes':[], 'contradicts':[]}
            args={'reflection_id':packet['id'], 'version':packet['version'],
                  'output':{'lessons':[lesson], 'feedback':[], 'unknowns':['Not physical certification']}}
            learned=self.clients['designer'].call('complete_bot_reflection',args,'learn-once')
            self.assertEqual(learned,self.clients['designer'].call('complete_bot_reflection',args,'learn-once'))
            self.assertEqual(learned['status'],'completed')
        other=self.task('designer', title='Route next clamp', dependencies=['mechanical.txt'])
        with self.worker('designer') as worker:
            ref=self.claimed(worker,other)
            p=self.clients['designer'].call('prepare_bot_learning',ref)
            self.assertTrue(any(m.get('lesson',{}).get('strategy')==lesson['strategy'] for m in p['recall']['items']))
        self.assertTrue(self.owner.call('replay')['matched'])

    def test_other_bot_cannot_prepare_or_finish_my_learning(self):
        task=self.task('designer')
        with self.worker('designer') as worker:
            ref=self.claimed(worker,task)
            self.fault('unauthorized',lambda:self.clients['control'].call('prepare_bot_learning',ref))

    def test_unseen_memory_cannot_be_claimed_as_used(self):
        task=self.task('designer')
        with self.worker('designer') as worker:
            ref=self.claimed(worker,task)
            p=self.clients['designer'].call('prepare_bot_learning',ref)
            self.fault('invalid_input',lambda:self.clients['designer'].call('submit_bot_learning_plan',{
                **ref,'plan_id':p['id'],'output':self.plan_output(p,[{'memory_id':'memory_fabricated','use':'apply','reason':'Guess'}])}))

    def enable_learning(self, name='designer'):
        from gantry.bot_worker import environment_manifest
        self.configs[name]['experience_learning'] = True
        self.owner.call('configure_bot_runtime', {'bot_id':name, 'version':1, 'principal_id':name,
            'enabled':True, 'environment':environment_manifest(self.configs[name])})

    def learning_infer(self, contexts):
        def infer(ctx, schema, directory):
            contexts.append(ctx)
            if ctx.get('operation') == 'plan_from_experience':
                out = self.plan_output(ctx['packet'])
                if not ctx['packet']['recall']['items']: out['steps'] = ['Inspect assembly without prior experience']
            elif ctx.get('operation') == 'reflect_on_experience':
                out = {'lessons':[{'kind':'procedure', 'observation':'Routing needs a clearance check',
                    'strategy':'Check clamp clearance before routing', 'when_to_use':'Next assembly routing task',
                    'when_not_to_use':['Changed geometry'], 'paths':['mechanical.txt'], 'tags':['clamp'],
                    'evidence':[ctx['packet']['task_id']], 'supersedes':[], 'contradicts':[]}],
                    'feedback':[{'memory_id':d['memory_id'], 'outcome':'unknown',
                        'reason':'No controlled evidence of benefit', 'evidence':[ctx['packet']['task_id']]}
                        for d in ctx['packet']['plan']['output']['decisions'] if d['use'] != 'reject'],
                    'unknowns':['No physical verification'],
                    'self_assessment':{'needs_independent_check':True, 'concerns':['Only a fixture'], 'reason':'Check physical behavior'}}
            else:
                self.assertTrue(ctx['learning_plan']['output']['steps'])
                out = self.answer(summary='Report from actual worker path')
            return {'output':out, 'provider':{'kind':'deterministic_fixture_not_model'}}
        return infer

    def test_worker_uses_plan_reflects_and_next_fresh_context_changes_order(self):
        self.enable_learning(); contexts=[]
        first=self.task('designer',title='Route clamp',dependencies=['mechanical.txt'])
        with self.worker('designer',self.learning_infer(contexts)) as worker: worker.tick()
        second=self.task('designer',title='Route clamp again',dependencies=['mechanical.txt'])
        with self.worker('designer',self.learning_infer(contexts)) as worker: worker.tick()
        work=[c for c in contexts if not c.get('operation')]
        self.assertEqual(len(work),2)
        self.assertNotEqual(work[0]['learning_plan']['output']['steps'],work[1]['learning_plan']['output']['steps'])
        self.assertTrue(work[1]['learning_plan']['recall']['items'])
        self.assertEqual(self.clients['designer'].call('list_bot_reflections',{'bot_id':'designer'})['items'],[])
        view=self.owner.call('get_bot_task',{'task_id':second['id']})
        self.assertEqual(view['task']['status'],'completed')
        self.assertFalse(view['limits']['formal_adoption'])
        self.assertTrue(self.owner.call('replay')['matched'])

    def test_unmeasured_conditions_cannot_be_applied_as_verified(self):
        task=self.task('designer',title='Check clamp',dependencies=['mechanical.txt'])
        with self.worker('designer') as worker:
            ref=self.claimed(worker,task); memory=self.seed(ref)
            p=self.clients['designer'].call('prepare_bot_learning',ref)
            self.fault('stale_basis',lambda:self.clients['designer'].call('submit_bot_learning_plan',{
                **ref,'plan_id':p['id'],'output':self.plan_output(p,[{'memory_id':memory['id'],'use':'apply','reason':'Assume'}])}))

    def test_new_experience_invalidates_inflight_plan(self):
        task=self.task('designer',title='Check clamp')
        with self.worker('designer') as worker:
            ref=self.claimed(worker,task); p=self.clients['designer'].call('prepare_bot_learning',ref)
            self.seed(ref)
            self.fault('stale_basis',lambda:self.clients['designer'].call('submit_bot_learning_plan',{
                **ref,'plan_id':p['id'],'output':self.plan_output(p)}))

    def test_reflection_does_not_accept_unrelated_evidence_or_foreign_bot(self):
        unrelated=self.task('control'); task=self.task('designer')
        with self.worker('designer') as worker:
            ref=self.claimed(worker,task); self.plan(ref)
            report={k:v for k,v in self.answer(status='failed').items() if k!='edits'}
            self.clients['designer'].call('finish_bot_task',{**ref,'report':report})
        item=self.clients['designer'].call('list_bot_reflections',{'bot_id':'designer'})['items'][0]
        self.fault('unauthorized',lambda:self.clients['control'].call('get_bot_reflection',{'reflection_id':item['id']}))
        lesson={'kind':'procedure','observation':'Guessed','strategy':'Guess','when_to_use':'Always',
            'when_not_to_use':[],'paths':[],'tags':[],'evidence':[unrelated['id']],'supersedes':[],'contradicts':[]}
        self.fault('invalid_input',lambda:self.clients['designer'].call('complete_bot_reflection',{
            'reflection_id':item['id'],'version':item['version'],'output':{'lessons':[lesson],'feedback':[],'unknowns':[]}}))

    def test_lost_plan_submit_ack_resumes_without_duplicate_inference(self):
        from gantry.model import Fault
        for committed in (False,True):
            with self.subTest(committed=committed):
                if not self.configs['designer'].get('experience_learning'): self.enable_learning()
                contexts=[]; task=self.task('designer'); client=self.clients['designer']; lost=[]
                class Proxy:
                    def call(_,op,args=None,key=None):
                        if op=='submit_bot_learning_plan' and not lost:
                            lost.append(True)
                            if committed: client.call(op,args,key)
                            raise Fault('temporarily_unavailable','Lost response')
                        return client.call(op,args,key)
                with self.worker('designer',self.learning_infer(contexts),Proxy()) as worker:
                    self.assertEqual(worker.tick()[0]['status'],'held')
                with self.worker('designer',self.learning_infer(contexts),Proxy()) as worker:
                    result=worker.recover(task['id'],'Old process stopped')
                    worker.tick()
                self.assertEqual(result['task']['status'],'completed')
                self.assertEqual(sum(c.get('operation')=='plan_from_experience' for c in contexts),1)
                self.assertTrue(self.owner.call('replay')['matched'])

    def test_reflection_response_loss_does_not_learn_twice(self):
        from gantry.model import Fault
        self.enable_learning(); contexts=[]; self.task('designer'); client=self.clients['designer']; lost=[]
        class Proxy:
            def call(_,op,args=None,key=None):
                result=client.call(op,args,key)
                if op=='complete_bot_reflection' and not lost:
                    lost.append(True); raise Fault('temporarily_unavailable','Lost reflection response')
                return result
        with self.worker('designer',self.learning_infer(contexts),Proxy()) as worker:
            self.fault('temporarily_unavailable',worker.tick)
        with self.worker('designer',self.learning_infer(contexts)) as worker: worker.tick()
        memories=self.clients['designer'].call('list_persistent_memories',{'bot_id':'designer','limit':100})['items']
        self.assertEqual(len({m['id'] for m in memories if m.get('source')=='experience_reflection'}),1)
        self.assertEqual(sum(c.get('operation')=='reflect_on_experience' for c in contexts),1)

    def test_replacement_is_retained_and_old_strategy_requires_recheck(self):
        self.enable_learning(); contexts=[]
        task=self.task('designer', title='Clamp routing',dependencies=['mechanical.txt'])
        with self.worker('designer') as worker:
            ref=self.claimed(worker,task); old=self.seed(ref)
            plan=self.plan(ref)
            client=self.clients['designer']
            report={k:v for k,v in self.answer(status='failed').items() if k!='edits'}
            client.call('finish_bot_task',{**ref,'report':report})
        item=client.call('list_bot_reflections',{'bot_id':'designer'})['items'][0]
        packet=client.call('get_bot_reflection',{'reflection_id':item['id']})
        out=self.learning_infer(contexts)({'operation':'reflect_on_experience','packet':packet},None,None)['output']
        out['lessons'][0]['supersedes']=[old['id']]
        learned=client.call('complete_bot_reflection',{'reflection_id':item['id'],'version':1,'output':out})
        self.assertEqual(learned['status'],'completed')
        self.assertEqual(self.owner.call('get_bot_reflection',{'reflection_id':item['id']})['output'],out)
        next_task=self.task('designer', title='Clamp routing',dependencies=['mechanical.txt'])
        with self.worker('designer') as worker:
            ref=self.claimed(worker,next_task); p=client.call('prepare_bot_learning',ref)
            remembered=next(m for m in p['recall']['items'] if m['id']==old['id'])
            self.assertIn('replacement_or_contradiction',remembered['applicability_flags'])
            self.assertEqual(remembered['reported_utility']['unknown'],1)
            decisions=self.plan_output(p)['decisions']
            next(d for d in decisions if d['memory_id']==old['id'])['use']='apply'
            self.fault('stale_basis',lambda:client.call('submit_bot_learning_plan',{
                **ref,'plan_id':p['id'],'output':self.plan_output(p,decisions)}))

    def test_changed_input_marks_experience_conditional(self):
        self.enable_learning(); self.task('designer',title='Clamp',dependencies=['mechanical.txt'])
        with self.worker('designer',self.learning_infer([])) as worker: worker.tick()
        change=self.owner.call('begin_change',{'state_id':self.base['id'],'title':'New geometry','purpose':'Test changed premise',
            'write_scope':['mechanical.txt'],'dependencies':[],'assignee':'admin'})
        checkpoint=self.owner.call('checkpoint_change',{'change_id':change['id'],'version':change['version'],
            'snapshot':self.artifact({'mechanical.txt':'changed','control.txt':'1'}),
            'summary':'Different input','rationale':'Fixture only','unfinished':['physics'],'work_status':'paused',
            'capture':{'scope':'files','missing':[]}})
        task=self.task('designer',title='Clamp',state_id=checkpoint['state']['id'],dependencies=['mechanical.txt'])
        with self.worker('designer') as worker:
            ref=self.claimed(worker,task); p=self.clients['designer'].call('prepare_bot_learning',ref)
            self.assertTrue(p['recall']['items'])
            self.assertTrue(all('input_changed' in m['applicability_flags'] for m in p['recall']['items']))

    def test_source_binding_revocation_hides_shared_memories(self):
        task=self.task('designer',title='Clamp',dependencies=['mechanical.txt'])
        with self.worker('designer') as worker:
            ref=self.claimed(worker,task); self.seed(ref)
            self.plan(ref)
            self.clients['designer'].call('finish_bot_task',{**ref,'report':{
                k:v for k,v in self.answer().items() if k!='edits'}})
        # The auto report memory was shared. Revocation must also remove that route.
        self.owner.call('bind_development_bot',{'session_id':self.sid,'bot_id':'designer','principal_id':'designer',
            'version':1,'write_scope':['mechanical.txt'],'can_assign':False,'can_integrate':False,'enabled':False})
        other=self.task('control',title='Clamp',dependencies=['mechanical.txt'])
        with self.worker('control') as worker:
            ref=self.claimed(worker,other,'control'); p=self.clients['control'].call('prepare_bot_learning',ref)
            self.assertEqual(p['recall']['items'],[])

    def test_learning_output_cannot_grant_permissions_or_adopt_design(self):
        task=self.task('designer')
        with self.worker('designer') as worker:
            ref=self.claimed(worker,task); p=self.clients['designer'].call('prepare_bot_learning',ref)
            out=self.plan_output(p); out['permissions']=['admin']
            self.fault('invalid_input',lambda:self.clients['designer'].call('submit_bot_learning_plan',{
                **ref,'plan_id':p['id'],'output':out}))
            self.assertFalse(self.clients['designer'].call('get_bot_task',{'task_id':task['id']})['limits']['formal_adoption'])

    def test_learning_wraps_iterative_tools_and_retains_failed_observations(self):
        import json, hashlib, sys
        from pathlib import Path
        from gantry.project_sandbox import backend, runtime_roots
        if backend()=='unavailable': self.skipTest('OS sandbox unavailable')
        self.configs['designer'].update(agent_loop=True,
            local_tools={'check':{'argv':[str(Path(sys.executable).resolve()),'-c',
                "from pathlib import Path; assert Path('mechanical.txt').read_text() == '2'"],'timeout_seconds':10}},
            tool_runtime=runtime_roots(),sandbox=backend())
        self.enable_learning(); contexts=[]; actions=[]; task=self.task('designer',title='Clamp clearance')
        learning=self.learning_infer(contexts)
        def infer(ctx,schema,directory):
            if ctx.get('operation'): return learning(ctx,schema,directory)
            self.assertTrue(ctx['learning_plan']['output']['steps'])
            sequence=[('tool',{'name':'check'}),('edit',{'path':'mechanical.txt','content':'2',
                'expected_hash':hashlib.sha256(b'1').hexdigest()}),('tool',{'name':'check'}),('finish',self.answer())]
            action,args=sequence[len(actions)]; actions.append(ctx)
            return {'output':{'action':action,'arguments_json':json.dumps(args),'rationale':'Fixture action'}}
        with self.worker('designer',infer) as worker: results=worker.tick()
        reflection=next(c for c in contexts if c.get('operation')=='reflect_on_experience')
        checks=[a for a in reflection['packet']['observations'] if a['kind']=='tool']
        self.assertEqual(sorted(a['details']['result']['exit_code'] for a in checks),[0,1])
        self.assertEqual(results[0]['task']['status'],'completed')
        self.assertEqual(len(results[1]['memory_ids']),1)

    def test_changed_acceptance_does_not_inherit_lesson_applicability(self):
        self.enable_learning(); self.task('designer',title='Clamp',dependencies=['mechanical.txt'])
        with self.worker('designer',self.learning_infer([])) as worker: worker.tick()
        task=self.task('designer',title='Clamp',dependencies=['mechanical.txt'],completion=['Different permitted clearance'])
        with self.worker('designer') as worker:
            ref=self.claimed(worker,task); p=self.clients['designer'].call('prepare_bot_learning',ref)
            lesson=next(m for m in p['recall']['items'] if m.get('lesson'))
            self.assertIn('context_changed',lesson['applicability_flags'])
            out=self.plan_output(p)
            next(d for d in out['decisions'] if d['memory_id']==lesson['id'])['use']='apply'
            self.fault('stale_basis',lambda:self.clients['designer'].call('submit_bot_learning_plan',{
                **ref,'plan_id':p['id'],'output':out}))
