import json

from gantry.bot_worker import environment_manifest
from test_bot_learning import BotLearningTests


class LearningSelectionTests(BotLearningTests):
    def test_empty_recall_saves_routing_without_model_but_still_reflects(self):
        self.configs['designer'].update(experience_learning=True, learning_mode='selective')
        self.owner.call('configure_bot_runtime', {'bot_id':'designer', 'version':1, 'principal_id':'designer',
            'enabled':True, 'environment':environment_manifest(self.configs['designer'])})
        task = self.task('designer'); contexts = []
        with self.worker('designer', self.learning_infer(contexts)) as worker: worker.tick()
        self.assertEqual([c.get('operation','action') for c in contexts], ['action','reflect_on_experience'])
        plan = self.owner.call('get_bot_task', {'task_id': task['id']})['learning_plan']
        self.assertEqual(plan['selection_method'], 'no_matching_experience')
        self.assertEqual(plan['output']['decisions'], [])
        self.assertTrue(self.owner.call('replay')['matched'])

    def test_empty_route_cannot_skip_relevant_or_new_experience(self):
        task = self.task('designer', title='Clamp route')
        with self.worker('designer') as worker:
            ref = self.claimed(worker, task)
            packet = self.clients['designer'].call('prepare_bot_learning', ref)
            self.seed(ref)
            self.fault('stale_basis', lambda: self.clients['designer'].call('complete_empty_bot_learning',
                {**ref,'plan_id':packet['id']}))
            packet = self.clients['designer'].call('prepare_bot_learning', ref)
            self.fault('invalid_input', lambda: self.clients['designer'].call('complete_empty_bot_learning',
                {**ref,'plan_id':packet['id']}))

    def test_selective_manifest_differs_and_invalid_modes_are_rejected(self):
        config = self.configs['designer']
        before = environment_manifest(config)
        config.update(experience_learning=True, learning_mode='selective')
        self.assertNotEqual(before, environment_manifest(config))
        config['learning_mode'] = 'guess'
        self.fault('invalid_input', lambda: self.worker('designer'))

    def test_compact_prompt_retains_ids_and_does_not_group_changed_conditions(self):
        from gantry.bot_learning_recall import planning_view
        task = self.task('designer', title='Clamp route')
        with self.worker('designer') as worker:
            ref = self.claimed(worker, task)
            for _ in range(4): self.seed(ref, 'Check clamp clearance before routing. '*30)
            p = self.clients['designer'].call('prepare_bot_learning', {**ref,'compact':True})
            view = planning_view(p)
            self.assertEqual(len(view['recall']['items']), 4)
            self.assertEqual(sum('duplicate_of' in x for x in view['recall']['items']), 3)
            self.assertLess(len(json.dumps(view)), len(json.dumps(p)))
            changed = json.loads(json.dumps(p))
            changed['recall']['items'][1]['limitations'] = ['Different load']
            view2 = planning_view(changed)
            self.assertNotIn('duplicate_of', view2['recall']['items'][1])
            self.assertEqual(len(p['recall']['items']), 4)

    def test_correction_links_are_never_grouped(self):
        from gantry.bot_learning_recall import planning_view
        task = self.task('designer', title='Clamp route')
        with self.worker('designer') as worker:
            ref=self.claimed(worker,task)
            self.seed(ref); self.seed(ref)
            packet=self.clients['designer'].call('prepare_bot_learning',{**ref,'compact':True})
            for field in ('supersedes','contradicts','related_updates'):
                for nested in (False,True):
                    data=json.loads(json.dumps(packet))
                    for memory in data['recall']['items']:
                        dest=memory.setdefault('lesson',{}) if nested and field!='related_updates' else memory
                        dest[field]=['older-source']
                    self.assertFalse(any('duplicate_of' in m for m in planning_view(data)['recall']['items']))

    def empty_recovery(self, committed):
        from gantry.model import Fault
        self.configs['designer'].update(experience_learning=True,learning_mode='selective')
        self.owner.call('configure_bot_runtime',{'bot_id':'designer','version':1,'principal_id':'designer',
            'enabled':True,'environment':environment_manifest(self.configs['designer'])})
        task=self.task('designer',title='Unrelated numerical '+str(committed)); client=self.clients['designer']; lost=[]; contexts=[]
        class Proxy:
            def call(_,op,args=None,key=None):
                if op=='complete_empty_bot_learning' and not lost:
                    lost.append(True)
                    if committed: client.call(op,args,key)
                    raise Fault('temporarily_unavailable','Lost acknowledgement')
                return client.call(op,args,key)
        def infer(ctx,schema,directory):
            contexts.append(ctx)
            out={'lessons':[],'feedback':[],'unknowns':[]} if ctx.get('operation')=='reflect_on_experience' else self.answer()
            return {'output':out,'provider':{'kind':'fixture'}}
        with self.worker('designer',infer,Proxy()) as worker: self.assertEqual(worker.tick()[0]['status'],'held')
        with self.worker('designer',infer,Proxy()) as worker:
            self.assertEqual(worker.recover(task['id'],'Stopped prior process')['task']['status'],'completed')
            worker.tick()
        self.assertEqual(sum(c.get('operation')=='plan_from_experience' for c in contexts),0)
        self.assertEqual(sum(c.get('operation')=='reflect_on_experience' for c in contexts),1)
        self.assertTrue(self.owner.call('replay')['matched'])

    def test_empty_route_recovers_lost_uncommitted_ack(self):
        self.empty_recovery(False)

    def test_empty_route_recovers_lost_committed_ack(self):
        self.empty_recovery(True)
