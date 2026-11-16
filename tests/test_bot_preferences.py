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
