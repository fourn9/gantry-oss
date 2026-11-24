"""Human-attributed personalization, not learned authority or verified design."""
import unittest
import test_bot_learning as fixtures


class BotPreferenceTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.BotLearningTests(); self.f.setUp(); self.addCleanup(self.f.tearDown)

    def set_pref(self):
        f = self.f
        return f.owner.call('set_bot_preference', dict(session_id=f.sid, bot_id='designer',
            key='reports', version=0, scope='project', task_id=None,
            text='Report measurements before recommendations', reason='Owner review feedback', enabled=True))

    def test_project_feedback_reaches_fresh_task_and_withdrawal_preserves_history(self):
        f=self.f; item=self.set_pref(); task=f.task('designer')
        view=f.clients['designer'].call('get_bot_task', {'task_id':task['id']})
        self.assertEqual(view['personal_preferences']['items'][0]['text'], item['text'])
        self.assertEqual(view['personal_preferences']['items'][0]['author_id'],'admin')
        f.owner.call('set_bot_preference', {k:item[k] for k in ('session_id','bot_id','key','version','scope','task_id','text','reason')} | {'enabled':False})
        self.assertEqual(f.clients['designer'].call('get_bot_task', {'task_id':task['id']})['personal_preferences']['items'], [])
        self.assertTrue(f.owner.call('replay')['matched'])

    def test_task_scope_does_not_leak_to_another_task_or_peer(self):
        f=self.f; a=f.task('designer'); b=f.task('designer')
        args=dict(session_id=f.sid,bot_id='designer',key='one-off',version=0,scope='task',task_id=a['id'],
            text='For this investigation report raw samples',reason='One task only',enabled=True)
        f.owner.call('set_bot_preference',args)
        self.assertEqual(len(f.clients['designer'].call('get_bot_task',{'task_id':a['id']})['personal_preferences']['items']),1)
        self.assertEqual(f.clients['designer'].call('get_bot_task',{'task_id':b['id']})['personal_preferences']['items'],[])
        self.assertIsNone(f.clients['control'].call('get_bot_task',{'task_id':a['id']})['personal_preferences'])
        f.fault('unauthorized',lambda:f.clients['designer'].call('set_bot_preference',args))

    def test_feedback_change_invalidates_inflight_learning_and_does_not_grant_scope(self):
        f=self.f; t=f.task('designer')
        with f.worker('designer') as worker:
            ref=f.claimed(worker,t); p=f.clients['designer'].call('prepare_bot_learning',ref)
            self.set_pref()
            f.fault('stale_basis',lambda:f.clients['designer'].call('submit_bot_learning_plan',
                {**ref,'plan_id':p['id'],'output':f.plan_output(p)}))
            self.assertEqual(f.clients['designer'].call('get_bot_task',{'task_id':t['id']})['task']['write_scope'],['mechanical.txt'])

    def test_owner_feedback_discards_prepared_edit_before_effect(self):
        import test_crew_runtime as runtime
        f=runtime.CrewRuntimeTests(); f.setUp(); self.addCleanup(f.tearDown)
        f.enable_loop('designer'); task=f.task('designer'); contexts=[]
        def infer(ctx, schema, directory):
            contexts.append(ctx)
            if len(contexts)==1:
                f.owner.call('set_bot_preference',dict(session_id=f.sid,bot_id='designer',key='reports',version=0,
                    scope='project',task_id=None,text='Describe options before editing',reason='Owner feedback',enabled=True))
                return f.action('edit', {'path':'mechanical.txt','content':'unreviewed','expected_hash':__import__('hashlib').sha256(b'1').hexdigest()})
            self.assertEqual(ctx['personal_preferences']['items'][0]['text'],'Describe options before editing')
            return f.action('finish',f.answer(summary='Reconsidered after owner feedback'))
        with f.worker('designer',infer) as worker: result=worker.tick()[0]
        self.assertEqual(result['task']['status'],'completed')
        self.assertEqual(len(contexts),2)
        self.assertTrue(contexts[1]['last_result']['discarded_model_answer'])
        self.assertNotIn('output_state',result['task'])

    def test_legacy_plan_without_preference_pin_cannot_ignore_new_feedback(self):
        from unittest.mock import patch
        f=self.f; t=f.task('designer'); original=f.service._dev_save
        def legacy_save(s,fx,table,record):
            if table=='bot_learning_plans':
                record.pop('personal_preferences',None);record.pop('commitment_context',None)
            return original(s,fx,table,record)
        with f.worker('designer') as worker:
            ref=f.claimed(worker,t)
            with patch.object(f.service,'_dev_save',legacy_save):
                p=f.clients['designer'].call('prepare_bot_learning',ref)
            self.set_pref()
            f.fault('stale_basis',lambda:f.clients['designer'].call('submit_bot_learning_plan',
                {**ref,'plan_id':p['id'],'output':f.plan_output(p)}))

    def test_old_credential_does_not_advertise_new_personal_actions(self):
        from unittest.mock import patch
        from gantry.agent_connection import PROFILES
        import test_crew_runtime as runtime
        additions={'create_bot_commitment','update_bot_commitment','get_bot_commitment',
            'list_bot_commitments','record_bot_procedure_decision'}
        f=runtime.CrewRuntimeTests()
        with patch.dict(PROFILES,{'bot':PROFILES['bot']-additions}):f.setUp()
        self.addCleanup(f.tearDown); f.enable_loop('designer'); f.task('designer')
        def infer(ctx,schema,directory):
            self.assertNotIn('commitment_create',ctx['action_guide'])
            self.assertNotIn('procedure_decision',ctx['action_schemas'])
            self.assertNotIn('commitment',schema['properties']['action']['enum'])
            return f.action('finish',f.answer())
        with f.worker('designer',infer) as worker:
            self.assertEqual(worker.tick()[0]['task']['status'],'completed')

    def test_one_time_exception_shadows_but_preserves_project_default_on_restart(self):
        from gantry.service import Service
        from test_development import LocalClient
        f = self.f
        default = self.set_pref()
        first, second = f.task('designer'), f.task('designer')
        args = dict(session_id=f.sid, bot_id='designer', key=default['key'], scope='task',
                    task_id=first['id'], text='Ask before editing this change', reason='One-off review', enabled=True)
        exception = f.owner.call('set_bot_preference', {**args, 'version':0})
        client = LocalClient(Service(f.root/'ledger'), f.tokens['designer'])
        def active(task):
            return client.call('get_bot_task', {'task_id':task['id']})['personal_preferences']['items']
        self.assertEqual([r['id'] for r in active(first)], [exception['id']])
        self.assertEqual([r['id'] for r in active(second)], [default['id']])
        f.owner.call('set_bot_preference', {**args, 'version':1, 'enabled':False})
        self.assertEqual([r['id'] for r in active(first)], [default['id']])

    def test_phase_guidance_matches_only_the_recorded_input_phase(self):
        f = self.f
        default = self.set_pref()
        args = dict(session_id=f.sid, bot_id='designer', key=default['key'], version=0,
                    scope='phase', phase='production', task_id=None, text='Consult assembly',
                    reason='Tooling freeze', enabled=True)
        phase = f.owner.call('set_bot_preference', args)
        task = f.task('designer')
        self.assertEqual([row['id'] for row in f.clients['designer'].call('get_bot_task', {'task_id':task['id']})
                          ['personal_preferences']['items']], [default['id']])
        change=f.owner.call('begin_change',{'state_id':f.base['id'],'title':'Production handoff',
            'purpose':'Mark the released fixture phase','write_scope':['mechanical.txt'],'dependencies':[],'assignee':'admin'})
        context={**f.base['context'],'environment':{**f.base['context']['environment'],'development_phase':'production'}}
        release=f.owner.call('checkpoint_change',{'change_id':change['id'],'version':change['version'],
            'snapshot':f.base['snapshot'],'context':context,'summary':'Production','rationale':'Fixture released',
            'unfinished':[],'capture':{'scope':'fixture','missing':[]},'work_status':'working'})['state']
        new=f.task('designer',state_id=release['id'])
        for t,expected in [(new,phase),(task,default)]:
            items=f.clients['designer'].call('get_bot_task',{'task_id':t['id']})['personal_preferences']['items']
            self.assertEqual([r['id'] for r in items],[expected['id']])

    def test_guidance_view_is_owner_only_and_keeps_available_guidance_separate_from_use(self):
        f = self.f
        self.set_pref()
        t = f.task('designer')
        ref = {'session_id':f.sid, 'bot_id':'designer', 'task_id':t['id']}
        view = f.owner.call('studio_bot_guidance', ref)
        self.assertEqual(view['rules'][0]['author_id'], 'admin')
        self.assertEqual(view['selected']['id'], t['id'])
        self.assertEqual(view['selected']['experience_uses'], [])
        f.fault('unauthorized', lambda: f.clients['control'].call('studio_bot_guidance', ref))
        foreign = f.task('control')
        f.fault('scope_denied', lambda: f.owner.call('studio_bot_guidance', {**ref, 'task_id':foreign['id']}))

    def test_single_response_worker_cannot_publish_an_edit_after_owner_correction(self):
        f=self.f
        task=f.task('designer')
        def inference(ctx,schema,directory):
            self.set_pref()
            return {'output':f.answer(edits=[{'path':'mechanical.txt','content':'old advice'}]),
                    'provider':{'kind':'fixture'}}
        with f.worker('designer',inference) as worker:
            result=worker.tick()[0]
        self.assertEqual(result['status'],'held')
        state=f.owner.call('get_bot_task',{'task_id':task['id']})
        self.assertIsNone(state['own_change'])

    def test_retrospective_owner_guess_needs_confirmation_and_stays_private(self):
        f=self.f; c=f.clients['designer']
        task=f.task('designer',title='Design guide')
        with f.worker('designer') as worker:
            ref=f.claimed(worker,task);f.plan(ref)
            report={k:v for k,v in f.answer(summary='A review was requested').items() if k!='edits'}
            c.call('finish_bot_task',{**ref,'report':report})
        item=c.call('list_bot_reflections',{'bot_id':'designer'})['items'][0]
        self.set_pref()
        packet=c.call('get_bot_reflection',{'reflection_id':item['id']})
        self.assertNotEqual(packet['current_owner_guidance']['basis'],packet['plan']['personal_preferences']['basis'])
        lesson=dict(kind='preference',observation='The reviewer requested a guide check',
            strategy='Check routing first',when_to_use='Before routing',when_not_to_use=['If conditions differ'],
            paths=['mechanical.txt'],tags=['guide'],evidence=[task['id']],supersedes=[],contradicts=[])
        saved=c.call('complete_bot_reflection',{'reflection_id':item['id'],'version':item['version'],
            'guidance_basis':packet['current_owner_guidance']['basis'],
            'output':{'lessons':[lesson],'feedback':[],'unknowns':[]}})
        mid=saved['memory_ids'][0]
        other=f.task('designer',title='Design second guide')
        with f.worker('designer') as worker:
            ref=f.claimed(worker,other)
            p=c.call('prepare_bot_learning',ref)
            memory=next(m for m in p['recall']['items'] if m['id']==mid)
            self.assertNotIn('apply',memory['allowed_uses'])
            self.assertEqual([r['key'] for r in p['personal_preferences']['items']],['reports'])
            ordinary=c.call('get_bot_task',{'task_id':other['id']})
            self.assertNotIn('apply',next(m for m in ordinary['memory']['items'] if m['id']==mid)['allowed_uses'])
        peer=f.clients['control'].call('list_persistent_memories',{'bot_id':'control'})
        self.assertNotIn(mid,[m['id'] for m in peer['items']])

    def test_owner_corrects_a_specific_lesson_and_can_withdraw_it(self):
        f = self.f
        client = f.clients['designer']
        task = f.task('designer')
        with f.worker('designer') as worker:
            ref = f.claimed(worker, task)
            f.plan(ref)
            report = {k:v for k,v in f.answer().items() if k != 'edits'}
            client.call('finish_bot_task', {**ref, 'report':report})
        reflection = client.call('list_bot_reflections', {'bot_id':'designer'})['items'][0]
        lesson = dict(kind='procedure', observation='An old fixture was amber', strategy='Prefer amber guides',
            when_to_use='Fixture changes', when_not_to_use=['New signed register'], paths=['mechanical.txt'],
            tags=['guide'], evidence=[task['id']], supersedes=[], contradicts=[])
        record = client.call('complete_bot_reflection', {'reflection_id':reflection['id'],
            'version':reflection['version'], 'output':{'lessons':[lesson], 'feedback':[], 'unknowns':[]}})
        mid = record['memory_ids'][0]
        target = {'bot_id':'designer','session_id':f.sid}
        view = f.owner.call('studio_bot_guidance', target)
        self.assertEqual(view['lessons'][0]['evidence'], [task['id']])
        self.assertEqual(view['lessons'][0]['source_task_id'], task['id'])
        args = {**target, 'key':'lesson-'+mid, 'memory_id':mid, 'scope':'project', 'task_id':None,
                'version':0, 'reason':'The fixture changed', 'text':'Check the current signed register', 'enabled':True}
        f.fault('scope_denied',lambda:f.owner.call('set_bot_preference', {**args, 'bot_id':'control'}))
        rule = f.owner.call('set_bot_preference', args)
        next_task = f.task('designer', title='Select fixture guide')
        def recall():
            ctx = client.call('get_bot_task', {'task_id':next_task['id']})
            return next(m for m in ctx['memory']['items'] if m['id']==mid), ctx['personal_preferences']['items']
        m, prefs = recall()
        self.assertIn('corrected_by_owner', m['applicability_flags'])
        self.assertNotIn('apply', m['allowed_uses'])
        self.assertEqual(prefs[0]['memory_id'], mid)
        f.owner.call('set_bot_preference', {**args,'version':rule['version'],'enabled':False})
        m, prefs = recall()
        self.assertNotIn('corrected_by_owner', m.get('applicability_flags',[]))
        self.assertFalse(prefs)

    def test_revised_guidance_fences_atomic_return_and_checkpoint(self):
        f = self.f
        task = f.task('designer')
        with f.worker('designer') as worker:
            ref = f.claimed(worker, task)
            c = f.clients['designer']
            pin = c.call('get_bot_task', {'task_id':task['id']})['personal_preferences']['basis']
            ref = {**ref,'preferences_basis':pin}
            self.set_pref()
            report = {k:v for k,v in f.answer().items() if k!='edits'}
            f.fault('stale_basis',lambda:c.call('finish_bot_task',{**ref,'report':report}))
            f.fault('stale_basis',lambda:c.call('checkpoint_bot_task',{**ref,'snapshot':f.base['snapshot'],
                    'summary':'Old', 'rationale':'Old', 'unfinished':[],
                    'capture':{'scope':'fixture','missing':[]}}))
            view = c.call('get_bot_task', {'task_id':task['id']})
            self.assertIsNone(view['own_change'])
            self.assertEqual(view['task']['status'],'running')

    def test_reflection_sees_prior_outcomes_from_own_project_and_checks_their_provenance(self):
        f=self.f; c=f.clients['designer']
        def reported(title):
            task=f.task('designer',title=title)
            with f.worker('designer') as worker:
                ref=f.claimed(worker,task);f.plan(ref)
                c.call('finish_bot_task',{**ref,'report':{k:v for k,v in f.answer(summary=title).items() if k!='edits'}})
            return next(r for r in c.call('list_bot_reflections',{'bot_id':'designer'})['items'] if r['task_id']==task['id'])
        prior=reported('Released fixture changed')
        current=reported('Register inspected before review')
        packet=c.call('get_bot_reflection',{'reflection_id':current['id']})
        self.assertEqual([(p['reflection_id'],p['summary']) for p in packet['previous_outcomes']],
                         [(prior['id'],'Released fixture changed')])
        args={'reflection_id':current['id'],'version':current['version'],
              'guidance_basis':packet['current_owner_guidance']['basis'],
              'output':{'lessons':[],'feedback':[],'unknowns':['Insufficient evidence']}}
        f.fault('invalid_input',lambda:c.call('complete_bot_reflection',{**args,'previous_outcome_ids':[current['id']]}))
        self.assertEqual(c.call('complete_bot_reflection',{**args,'previous_outcome_ids':[prior['id']]})['status'],'completed')
