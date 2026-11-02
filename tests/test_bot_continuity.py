"""Real Core/worker continuity; model decisions here are labeled fixtures."""
from test_bot_learning import BotLearningTests


class BotContinuityTests(BotLearningTests):
    def note(self, ref, version=0, **extra):
        return self.clients['designer'].call('update_bot_working_state', {**ref, 'version': version,
            'focus': 'Check routing before detailed design', 'next_steps': ['Check clamp clearance'],
            'commitments': ['Report unresolved interference to mechanical manager'],
            'unknowns': ['Physical clearance'], 'watch_paths': ['mechanical.txt'],
            'watch_tasks': [], 'due_at': None, **extra})

    def permit(self, version=0, **extra):
        return self.owner.call('configure_bot_continuation', {'session_id': self.sid, 'bot_id': 'designer',
            'version': version, 'enabled': True, 'write_scope': ['mechanical.txt'],
            'dependencies': ['mechanical.txt'], 'completion': ['Reassess routing with evidence'], **extra})

    def pump(self, worker):
        return self.clients['designer'].call('poll_bot_continuations', {'bot_id': 'designer',
            'runtime_fence': worker.runtime['fence']})

    def test_working_note_survives_fresh_context_and_blocks_foreign_writer(self):
        task = self.task('designer')
        with self.worker('designer') as worker:
            ref = self.claimed(worker, task); note = self.note(ref)
            self.fault('stale_basis', lambda: self.note(ref))
            self.fault('unauthorized', lambda: self.clients['control'].call('update_bot_working_state',
                {**ref, 'version': 1, **note['content']}))
            self.clients['designer'].call('finish_bot_task', {**ref,
                'report': {k:v for k,v in self.answer().items() if k!='edits'}})
        second = self.task('designer')
        view = self.clients['designer'].call('get_bot_task', {'task_id': second['id']})
        self.assertEqual(view['working_state']['note']['content']['commitments'], note['content']['commitments'])
        self.assertEqual(view['working_state']['note']['last_report_task'], task['id'])
        self.assertEqual(view['working_state']['project']['goal'], self.project['goal'])
        self.fault('unauthorized', lambda: self.clients['control'].call('get_bot_working_state',
            {'session_id': self.sid, 'bot_id': 'designer'}))
        self.assertTrue(self.owner.call('replay')['matched'])

    def test_due_wake_requires_owner_delegation_and_is_deduplicated(self):
        task = self.task('designer')
        with self.worker('designer') as worker:
            ref = self.claimed(worker, task); self.note(ref, due_at=1)
            self.assertEqual(self.pump(worker)['items'], [])
            self.clients['designer'].call('finish_bot_task', {**ref,
                'report': {k:v for k,v in self.answer().items() if k!='edits'}})
            self.permit()
            first = self.pump(worker)['items'][0]
            self.assertEqual(first['status'], 'queued')
            self.assertEqual(self.pump(worker)['items'][0]['status'], 'active')
            self.assertEqual(len(self.owner.call('list_bot_tasks', {'session_id':self.sid})['items']), 2)
            self.permit(version=1, enabled=False)
            wake = self.owner.call('get_bot_task', {'task_id':first['task_id']})['task']
            self.fault('stale_basis', lambda:self.claimed(worker, wake))
        self.assertTrue(self.owner.call('replay')['matched'])

    def test_watching_task_wakes_after_change_without_new_user_assignment(self):
        other = self.task('control'); task = self.task('designer')
        with self.worker('designer') as worker:
            ref = self.claimed(worker, task); self.note(ref, watch_tasks=[other['id']])
            self.clients['designer'].call('finish_bot_task', {**ref,
                'report': {k:v for k,v in self.answer().items() if k!='edits'}})
            self.permit(); self.assertEqual(self.pump(worker)['items'][0]['status'], 'idle')
        with self.worker('control') as worker: worker.tick()
        with self.worker('designer') as worker:
            wake = self.pump(worker)['items'][0]
            self.assertEqual(wake['status'], 'queued')
            context = self.clients['designer'].call('get_bot_task', {'task_id':wake['task_id']})
            self.assertIn('watched_task_changed', context['task']['continuation_reason'])

    def test_memory_action_link_requires_this_attempt_and_reaches_reflection(self):
        task = self.task('designer', title='Check clamp')
        with self.worker('designer') as worker:
            ref = self.claimed(worker, task); memory = self.seed(ref); self.plan(ref)
            output_artifact=self.artifact({'tool-output.txt':'clearance failed'})
            action = self.clients['designer'].call('record_bot_action', {**ref, 'kind':'tool',
                'details':{'result':{'exit_code':1, 'output':'clearance failed', 'output_artifact':output_artifact}}})
            args = {**ref, 'memory_id':memory['id'], 'action_ids':[action['id']],
                'change':'Checked before editing', 'condition_check':'Geometry needs fresh evaluation'}
            used = self.clients['designer'].call('record_bot_learning_use', args)
            self.fault('invalid_input', lambda:self.clients['designer'].call('record_bot_learning_use',
                {**args, 'action_ids':['invented']}))
            self.clients['designer'].call('finish_bot_task', {**ref,
                'report': {k:v for k,v in self.answer(status='failed').items() if k!='edits'}})
            pending = self.clients['designer'].call('list_bot_reflections', {'bot_id':'designer'})['items'][0]
            packet = self.clients['designer'].call('get_bot_reflection', {'reflection_id':pending['id']})
            self.assertEqual(packet['experience_actions'][0]['id'], used['id'])
            self.assertEqual(packet['experience_actions'][0]['evidence_status'], 'reported_link_to_recorded_actions')
            output=self.learning_infer([])({'operation':'reflect_on_experience','packet':packet},None,None)['output']
            output['lessons'][0]['evidence']=[self.artifact({'unrelated.txt':'not observed by this task'})]
            self.fault('invalid_input',lambda:self.clients['designer'].call('complete_bot_reflection',{
                'reflection_id':pending['id'],'version':1,'output':output}))
            output['lessons'][0]['evidence']=[packet['plan_id'],output_artifact]
            output['lessons'][0]['procedure_steps']=None
            done=self.clients['designer'].call('complete_bot_reflection',{'reflection_id':pending['id'],'version':1,'output':output})
            self.assertEqual(done['status'],'completed')

    def test_owner_permission_cannot_be_created_by_bot(self):
        args = {'session_id':self.sid, 'bot_id':'designer', 'version':0, 'enabled':True,
            'write_scope':['mechanical.txt'], 'dependencies':[], 'completion':['Reassess']}
        self.fault('unauthorized', lambda:self.clients['designer'].call('configure_bot_continuation', args))
        self.fault('scope_denied', lambda:self.owner.call('configure_bot_continuation',
            {**args, 'write_scope':['control.txt']}))

    def enable_continuity(self, name='designer', **options):
        from gantry.bot_worker import environment_manifest
        self.configs[name].update(personal_continuity=True, **options)
        rt=self.owner.call('get_persistent_bot', {'bot_id':name})['runtime']
        self.owner.call('configure_bot_runtime', {'bot_id':name, 'version':rt['version'], 'principal_id':name,
            'enabled':True, 'environment':environment_manifest(self.configs[name])})

    def test_changed_working_context_invalidates_inflight_plan(self):
        task=self.task('designer')
        with self.worker('designer') as worker:
            ref=self.claimed(worker,task)
            p=self.clients['designer'].call('prepare_bot_learning',ref)
            self.note(ref)
            self.fault('stale_basis',lambda:self.clients['designer'].call('submit_bot_learning_plan',{
                **ref,'plan_id':p['id'],'output':self.plan_output(p)}))

    def test_wake_worker_restarts_and_does_not_infer_again_without_new_signal(self):
        self.enable_continuity(); task=self.task('designer')
        with self.worker('designer') as worker:
            ref=self.claimed(worker,task); self.note(ref,due_at=1)
            self.clients['designer'].call('finish_bot_task',{**ref,
                'report':{k:v for k,v in self.answer().items() if k!='edits'}})
        self.permit(); calls=[]
        def infer(ctx,schema,directory):
            calls.append(ctx); return {'output':self.answer(),'provider':{'kind':'fixture'}}
        with self.worker('designer',infer) as worker:
            self.assertEqual(worker.tick()[0]['task']['status'],'completed')
        with self.worker('designer',infer) as worker: self.assertEqual(worker.tick(),[])
        self.assertEqual(len(calls),1)
        self.assertTrue(calls[0]['working_state']['note']['content']['commitments'])
        self.assertEqual(calls[0]['task']['continuation_reason'],['due'])

    def test_revocation_blocks_running_root_and_pending_consultation(self):
        task=self.task('designer')
        with self.worker('designer') as worker:
            ref=self.claimed(worker,task); self.note(ref,due_at=1)
            self.clients['designer'].call('finish_bot_task',{**ref,
                'report':{k:v for k,v in self.answer().items() if k!='edits'}})
            self.permit(); queued=self.pump(worker)['items'][0]
            wake=self.owner.call('get_bot_task',{'task_id':queued['task_id']})['task']
            ref=self.claimed(worker,wake)
            asked=self.clients['designer'].call('ask_bot',{**ref,'to_bot_id':'control',
                'question':'Check interface','evidence':[wake['state_id']]})
            self.permit(version=1,enabled=False)
            self.fault('stale_basis',lambda:self.clients['designer'].call('refresh_bot_task',ref))
            with self.worker('control') as other:
                self.fault('stale_basis',lambda:self.clients['control'].call('claim_bot_task',{
                    'task_id':asked['response_task']['id'],'version':1,'runtime_fence':other.runtime['fence']}))

    def test_revocation_blocks_running_descendant(self):
        # A manager delegates from a standing wake, then the owner revokes it.
        task=self.task('mechanical'); c=self.clients['mechanical']
        policy={'session_id':self.sid,'bot_id':'mechanical','version':0,'enabled':True,
                'write_scope':['mechanical.txt'],'dependencies':[],'completion':['Reassess']}
        with self.worker('mechanical') as manager:
            claim=c.call('claim_bot_task',{'task_id':task['id'],'version':1,'runtime_fence':manager.runtime['fence']})
            ref={'task_id':task['id'],'fence':claim['task']['fence']}
            c.call('update_bot_working_state',{**ref,'version':0,'focus':'Reassess','next_steps':[],
                'commitments':[],'unknowns':[],'watch_paths':[],'watch_tasks':[],'due_at':1})
            c.call('finish_bot_task',{**ref,'report':{k:v for k,v in self.answer().items() if k!='edits'}})
            self.owner.call('configure_bot_continuation',policy)
            wake=c.call('poll_bot_continuations',{'bot_id':'mechanical','runtime_fence':manager.runtime['fence']})['items'][0]
            claim=c.call('claim_bot_task',{'task_id':wake['task_id'],'version':1,'runtime_fence':manager.runtime['fence']})
            c.call('finish_bot_task',{'task_id':wake['task_id'],'fence':claim['task']['fence'],
                'report':{k:v for k,v in self.answer(status='waiting',assignments=[self.assignment('designer')]).items() if k!='edits'}})
        with self.worker('designer') as worker:
            child=next(t for t in self.owner.call('list_bot_tasks',{'session_id':self.sid})['items'] if t.get('parent_task_id')==wake['task_id'])
            ref=self.claimed(worker,child)
            self.owner.call('configure_bot_continuation',{**policy,'version':1,'enabled':False})
            self.fault('stale_basis',lambda:self.clients['designer'].call('check_bot_task',ref))

    def test_failed_reflection_holds_only_itself_until_explicit_retry(self):
        from gantry.model import Fault
        self.enable_learning(); self.task('designer'); calls=[]
        normal=self.learning_infer(calls); failures=[]
        def infer(ctx,schema,directory):
            if ctx.get('operation')=='reflect_on_experience':
                failures.append(ctx); raise Fault('provider_failed','Fixture provider failure')
            return normal(ctx,schema,directory)
        with self.worker('designer',infer) as worker:
            result=worker.tick()
            self.assertEqual(result[0]['task']['status'],'completed')
            held=result[1]; self.assertEqual(held['status'],'held')
        second=self.task('designer')
        with self.worker('designer',infer) as worker:
            result=worker.tick()
            self.assertTrue(any(r.get('task',{}).get('id')==second['id'] for r in result))
        self.assertEqual(len(failures),2)  # Each report once, not every poll.
        with self.worker('designer',normal) as worker:
            self.fault('outcome_unknown',lambda:worker.recover_reflection(held['reflection_id'],'Previous process stopped'))
            result=worker.recover_reflection(held['reflection_id'],'Previous process stopped',retry_inference=True)
            self.assertEqual(result['status'],'completed')
        self.assertTrue(self.owner.call('replay')['matched'])

    def test_private_working_note_is_not_leaked_in_peer_action_receipts(self):
        task=self.task('designer')
        with self.worker('designer') as worker:
            ref=self.claimed(worker,task); note=self.note(ref,focus='Private unresolved strategy')
            self.clients['designer'].call('record_bot_action',{**ref,'kind':'working_state','details':{'result':note}})
            self.clients['designer'].call('record_bot_action',{**ref,'kind':'context','details':{'value':note}})
            nested=self.clients['designer'].call('get_bot_records',{'task_id':task['id'],'kind':'actions'})
            self.clients['designer'].call('record_bot_action',{**ref,'kind':'records','details':{'result':nested}})
            self.clients['designer'].call('record_bot_action',{**ref,'kind':'inspect','details':{'result':note}})
        import json
        for op,args in [('get_bot_task',{'task_id':task['id']}),
                        ('get_bot_records',{'task_id':task['id'],'kind':'actions'})]:
            self.assertNotIn('Private unresolved strategy',json.dumps(self.clients['control'].call(op,args)))
            self.assertIn('Private unresolved strategy',json.dumps(self.owner.call(op,args)))

    def test_iterative_worker_updates_context_and_links_action_to_procedure(self):
        import json
        first=self.task('designer',title='Check clamp')
        with self.worker('designer') as worker:
            ref=self.claimed(worker,first); old=self.seed(ref); self.note(ref)
            self.clients['designer'].call('finish_bot_task',{**ref,
                'report':{k:v for k,v in self.answer().items() if k!='edits'}})
        self.enable_continuity(experience_learning=True,agent_loop=True)
        next_task=self.task('designer',title='Check clamp'); contexts=[]
        ordinary=self.learning_infer(contexts)
        def infer(ctx,schema,directory):
            if ctx.get('operation')=='reflect_on_experience':
                out=ordinary(ctx,schema,directory)
                self.assertEqual(len(ctx['packet']['experience_actions']),1)
                lesson=out['output']['lessons'][0]
                lesson['procedure_steps']=['Read fixed inputs','Verify clamp clearance before routing']
                lesson['supersedes']=[old['id']]
                lesson['evidence']=[ctx['packet']['experience_actions'][0]['id']]
                return out
            if ctx.get('operation'): return ordinary(ctx,schema,directory)
            contexts.append(ctx); n=ctx['round']
            if n==0:
                action='working_state'; args={**ctx['working_state']['note']['content'],
                    'version':ctx['working_state']['note']['version'],'next_steps':['Verify clamp before routing']}
            elif n==1: action='read'; args={'path':'mechanical.txt'}
            elif n==2:
                actual=next(a for a in ctx['actions'] if a['kind']=='read')
                action='experience_use'; args={'memory_id':old['id'],'action_ids':[actual['id']],
                    'change':'Read before edit','condition_check':'Geometry remains unverified'}
            else: action='finish'; args=self.answer()
            return {'output':{'action':action,'arguments_json':json.dumps(args),'rationale':'Fixture action decision'},
                    'provider':{'kind':'deterministic_fixture'}}
        with self.worker('designer',infer) as worker:
            result=worker.tick(); self.assertEqual(result[0]['task']['status'],'completed',result)
        note=self.clients['designer'].call('get_bot_working_state',{'session_id':self.sid,'bot_id':'designer'})['note']
        self.assertEqual(note['content']['next_steps'],['Verify clamp before routing'])
        self.assertEqual(note['source_task_id'],next_task['id'])
        learned=result[-1]['output']['lessons'][0]
        self.assertEqual(learned['supersedes'],[old['id']]); self.assertEqual(len(learned['procedure_steps']),2)
        self.assertTrue(self.owner.call('replay')['matched'])

    def test_new_signal_during_wake_is_not_lost(self):
        controls=[self.task('control'),self.task('control')]; task=self.task('designer')
        with self.worker('designer') as worker:
            ref=self.claimed(worker,task); self.note(ref,watch_tasks=[t['id'] for t in controls])
            self.clients['designer'].call('finish_bot_task',{**ref,
                'report':{k:v for k,v in self.answer().items() if k!='edits'}})
            self.permit()
            with self.worker('control') as control:
                for i,t in enumerate(controls):
                    claim=self.clients['control'].call('claim_bot_task',{'task_id':t['id'],'version':1,'runtime_fence':control.runtime['fence']})
                    self.clients['control'].call('finish_bot_task',{'task_id':t['id'],'fence':claim['task']['fence'],
                        'report':{k:v for k,v in self.answer().items() if k!='edits'}})
                    if i==0:
                        queued=self.pump(worker)['items'][0]
                        wake=self.owner.call('get_bot_task',{'task_id':queued['task_id']})['task']
                        ref=self.claimed(worker,wake)
                    else: self.assertEqual(self.pump(worker)['items'][0]['status'],'active')
            self.clients['designer'].call('finish_bot_task',{**ref,
                'report':{k:v for k,v in self.answer().items() if k!='edits'}})
            second=self.pump(worker)['items'][0]
            self.assertEqual(second['status'],'queued'); self.assertNotEqual(second['task_id'],wake['id'])

    def test_local_candidate_note_does_not_look_like_new_shared_input(self):
        task=self.task('designer'); c=self.clients['designer']
        with self.worker('designer') as worker:
            ref=self.claimed(worker,task)
            c.call('checkpoint_bot_task',{**ref,'snapshot':self.artifact({'mechanical.txt':'2','control.txt':'1'}),
                'summary':'Unverified candidate','rationale':'Local experiment','unfinished':['interface'],
                'capture':{'scope':'saved files','missing':[]}})
            note=self.note(ref)
            c.call('finish_bot_task',{**ref,'report':{k:v for k,v in self.answer().items() if k!='edits'}})
            self.permit(); self.assertEqual(self.pump(worker)['items'][0]['status'],'idle')
            saved=c.call('get_bot_working_state',{'session_id':self.sid,'bot_id':'designer'})['note']
            self.assertEqual(saved['state_id'],note['state_id'])
