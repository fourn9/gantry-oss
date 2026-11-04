from test_bot_learning import BotLearningTests


class ExperienceCheckTests(BotLearningTests):
    def request(self, ref, memory, peer='control'):
        return self.clients['designer'].call('ask_bot', {**ref, 'to_bot_id':peer,
            'question':'Check whether this clamp lesson applies to the current state',
            'evidence':[self.base['id']], 'memory_id':memory['id']}, 'lesson-check')

    def test_peer_reads_shared_lesson_reports_and_requester_resumes(self):
        task = self.task('designer', title='Clamp route')
        with self.worker('designer') as worker:
            ref = self.claimed(worker, task); memory = self.seed(ref)
            response = self.request(ref, memory)
            self.assertEqual(response, self.request(ref, memory))
            self.clients['designer'].call('refresh_bot_task', ref)
            report = {k:v for k,v in self.answer(status='waiting').items() if k!='edits'}
            self.clients['designer'].call('finish_bot_task', {**ref, 'report':report})
        peer = response['response_task']
        with self.worker('control') as worker:
            peer_ref = self.claimed(worker, peer, 'control')
            context = self.clients['control'].call('get_bot_task', {'task_id':peer['id']})
            self.assertEqual(context['experience_check']['memory']['id'], memory['id'])
            self.assertEqual(context['task']['write_scope'], [])
            action = self.clients['control'].call('record_bot_action', {**peer_ref,'kind':'read','details':{'path':'mechanical.txt'}})
            report = {k:v for k,v in self.answer(experience_check={'verdict':'inconclusive',
                'reason':'Need physical clearance evidence', 'action_ids':[action['id']]}).items() if k!='edits'}
            self.clients['control'].call('finish_bot_task', {**peer_ref,'report':report})
        view = self.owner.call('get_bot_task', {'task_id':task['id']})
        self.assertTrue(any(m['kind']=='answer' for m in view['messages']))
        next_task = self.task('designer', title='Clamp route')
        with self.worker('designer') as worker:
            ref = self.claimed(worker, next_task); plan = self.clients['designer'].call('prepare_bot_learning', ref)
            recalled = next(m for m in plan['recall']['items'] if m['id']==memory['id'])
            self.assertEqual(recalled['peer_checks'][0]['verdict'], 'inconclusive')
            self.assertIn('peer_check_requires_reassessment', recalled['applicability_flags'])
        self.assertTrue(self.owner.call('replay')['matched'])

    def test_private_lesson_and_self_review_are_rejected(self):
        from test_bots import profile
        self.owner.call('configure_organization', {'organization_id':'team', 'version':1, 'name':'Private',
            'profile':profile(),
            'enabled':True, 'share_reflections':False})
        task=self.task('designer')
        with self.worker('designer') as worker:
            ref=self.claimed(worker,task); memory=self.seed(ref)
            self.fault('unauthorized', lambda:self.request(ref,memory))
            self.fault('invalid_input', lambda:self.request(ref,memory,'designer'))

    def test_original_author_cannot_review_another_requesters_lesson(self):
        task=self.task('designer')
        with self.worker('designer') as w:
            ref=self.claimed(w,task); memory=self.seed(ref)
        other=self.task('lead')
        with self.worker('lead') as w:
            ref=self.claimed(w,other,'lead')
            self.fault('unauthorized',lambda:self.clients['lead'].call('ask_bot',{**ref,'to_bot_id':'designer',
                'question':'Check this lesson','evidence':[],'memory_id':memory['id']}))

    def test_check_needs_actual_evidence_and_hides_private_report(self):
        task=self.task('designer')
        with self.worker('designer') as w:
            ref=self.claimed(w,task); memory=self.seed(ref); peer=self.request(ref,memory)['response_task']
        with self.worker('control') as w:
            ref=self.claimed(w,peer,'control')
            report={k:v for k,v in self.answer().items() if k!='edits'}
            self.fault('invalid_input',lambda:self.clients['control'].call('finish_bot_task',{**ref,'report':report}))
            report['experience_check']={'verdict':'supported_for_scope','reason':'PRIVATE_CHECK_REASON','action_ids':[task['id']]}
            self.fault('not_found',lambda:self.clients['control'].call('finish_bot_task',{**ref,'report':report}))
            action=self.clients['control'].call('record_bot_action',{**ref,'kind':'read','details':{'path':'mechanical.txt'}})
            report.update(summary='PRIVATE_CHECK_REASON',rationale='PRIVATE_CHECK_REASON',unverified=['PRIVATE_CHECK_REASON'])
            report['experience_check']['action_ids']=[action['id']]
            self.clients['control'].call('finish_bot_task',{**ref,'report':report},'check-result')
            self.clients['control'].call('finish_bot_task',{**ref,'report':report},'check-result')
        import json
        private=self.clients['designer'].call('get_bot_task',{'task_id':peer['id']})
        self.assertEqual(private['experience_check']['result']['reason'],'PRIVATE_CHECK_REASON')
        public=self.clients['mechanical'].call('get_bot_task',{'task_id':peer['id']})
        self.assertFalse(public['experience_check']['available'])
        self.assertNotIn('PRIVATE_CHECK_REASON',json.dumps(public))
        self.assertNotIn('PRIVATE_CHECK_REASON',json.dumps(self.clients['mechanical'].call('list_bot_tasks',{'session_id':self.sid})))
        self.assertTrue(self.owner.call('replay')['matched'])

    def test_source_rebinding_holds_execution_and_revokes_read(self):
        task=self.task('designer')
        with self.worker('designer') as w:
            ref=self.claimed(w,task); memory=self.seed(ref); peer=self.request(ref,memory)['response_task']
        with self.worker('control') as w:
            ref=self.claimed(w,peer,'control')
            self.owner.call('bind_development_bot',{'session_id':self.sid,'bot_id':'designer','principal_id':'designer',
                'version':1,'write_scope':['mechanical.txt'],'can_assign':False,'can_integrate':False,'enabled':False})
            self.fault('unauthorized',lambda:self.clients['control'].call('check_bot_task',ref))
            view=self.clients['control'].call('get_bot_task',{'task_id':peer['id']})
            self.assertFalse(view['experience_check']['available'])

    def test_failed_check_has_no_verification_receipt(self):
        task=self.task('designer')
        with self.worker('designer') as w:
            ref=self.claimed(w,task); peer=self.request(ref,self.seed(ref))['response_task']
        with self.worker('control') as w:
            ref=self.claimed(w,peer,'control')
            report={k:v for k,v in self.answer(status='failed').items() if k!='edits'}
            self.clients['control'].call('finish_bot_task',{**ref,'report':report})
        view=self.clients['designer'].call('get_bot_task',{'task_id':peer['id']})
        self.assertIsNone(view['experience_check']['result']['verdict'])
        self.assertEqual(view['experience_check']['result']['status'],'failed')
        self.assertEqual(view['experience_check']['result']['report']['rationale'], report['rationale'])

    def test_real_worker_returns_check_and_gates_decisions(self):
        import json
        from gantry.bot_worker import environment_manifest
        task=self.task('designer')
        with self.worker('designer') as w:
            ref=self.claimed(w,task); memory=self.seed(ref); peer=self.request(ref,memory)['response_task']
        self.configs['control']['agent_loop']=True
        self.owner.call('configure_bot_runtime',{'bot_id':'control','version':1,'principal_id':'control',
            'enabled':True,'environment':environment_manifest(self.configs['control'])})
        def infer(ctx,schema,directory):
            if ctx['round']==0:
                kind='decision';args={'verdict':'revise','targets':[peer['id']],'rationale':'PRIVATE_CHECK_DECISION',
                    'evidence':[self.base['id']],'alternatives':[],'conditions':[]}
            elif ctx['round']==1: kind='read';args={'path':'mechanical.txt'}
            else:
                kind='finish'; action=next(a for a in ctx['actions'] if a['kind']=='read')
                args=self.answer(experience_check={'verdict':'inconclusive','reason':'Missing clearance proof','action_ids':[action['id']]})
            return {'output':{'action':kind,'arguments_json':json.dumps(args),'rationale':'Fixture review'},'provider':{'kind':'fixture'}}
        with self.worker('control',infer) as worker: self.assertEqual(worker.tick()[0]['task']['status'],'completed')
        requester=self.clients['designer'].call('get_bot_task',{'task_id':peer['id']})
        self.assertEqual(requester['experience_check']['result']['verdict'],'inconclusive')
        self.assertTrue(any(a.get('details',{}).get('arguments') for a in requester['actions']))
        for op,args in [('get_bot_task',{'task_id':peer['id']}),('get_bot_records',{'task_id':peer['id'],'kind':'decisions'})]:
            self.assertNotIn('PRIVATE_CHECK_DECISION',json.dumps(self.clients['mechanical'].call(op,args)))

    def test_disabled_requester_cannot_leave_review_authorized(self):
        task=self.task('designer')
        with self.worker('designer') as w:
            ref=self.claimed(w,task); peer=self.request(ref,self.seed(ref))['response_task']
        entry=self.owner.call('state')['entries']['designer']
        from gantry.service import token_hash
        data=dict(entry['data'], enabled=False, token_hash=token_hash(self.tokens['designer']))
        p=self.owner.call('propose',{'title':'Revoke requester','changes':[{'id':'designer','type':'principal','data':data,'expected_revision':entry['revision_id']}]})
        ref={'proposal_id':p['id'],'version':p['version']}
        self.owner.call('submit',ref);self.owner.call('endorse',{**ref,'reason':'Revoke'})
        self.owner.call('review_adoption',{**ref,'reason':'Revoke','verdict':'approve'});self.owner.call('commit',ref)
        with self.worker('control') as w:
            self.fault('unauthorized',lambda:self.claimed(w,peer,'control'))

    def test_existing_correction_is_pinned_and_new_correction_invalidates_check(self):
        memory=None
        def correction():
            nonlocal memory
            task=self.task('designer',title='Clamp route')
            with self.worker('designer') as w:
                ref=self.claimed(w,task)
                if memory is None: memory=self.seed(ref)
                self.plan(ref)
                report={k:v for k,v in self.answer(status='failed').items() if k!='edits'}
                self.clients['designer'].call('finish_bot_task',{**ref,'report':report})
            job=self.clients['designer'].call('list_bot_reflections',{'bot_id':'designer'})['items'][0]
            packet=self.clients['designer'].call('get_bot_reflection',{'reflection_id':job['id']})
            output=self.learning_infer([])({'operation':'reflect_on_experience','packet':packet},None,None)['output']
            output['lessons'][0]['contradicts']=[memory['id']]
            self.clients['designer'].call('complete_bot_reflection',{'reflection_id':job['id'],'version':job['version'],'output':output})
        correction()
        task=self.task('designer',title='Clamp route')
        with self.worker('designer') as w:
            ref=self.claimed(w,task); peer=self.request(ref,memory)['response_task']
        with self.worker('control') as w:
            ref=self.claimed(w,peer,'control')
            self.assertEqual(len(peer['experience_check']['related_updates']),1)
            correction()
            self.fault('stale_basis',lambda:self.clients['control'].call('check_bot_task',ref))
            self.assertFalse(self.clients['control'].call('get_bot_task',{'task_id':peer['id']})['experience_check']['available'])

    def test_stale_review_can_be_explicitly_discarded_without_blocking_task(self):
        task=self.task('designer',title='Clamp route')
        with self.worker('designer') as w:
            ref=self.claimed(w,task); memory=self.seed(ref); request=self.request(ref,memory); peer=request['response_task']
            self.clients['designer'].call('refresh_bot_task',ref)
            report={k:v for k,v in self.answer(status='waiting').items() if k!='edits'}
            self.clients['designer'].call('finish_bot_task',{**ref,'report':report})
        with self.worker('control') as w:
            peer_ref=self.claimed(w,peer,'control')
            action=self.clients['control'].call('record_bot_action',{**peer_ref,'kind':'read','details':{'path':'mechanical.txt'}})
            report={k:v for k,v in self.answer(experience_check={'verdict':'supported_for_scope','reason':'Fixture opinion','action_ids':[action['id']]}).items() if k!='edits'}
            self.clients['control'].call('finish_bot_task',{**peer_ref,'report':report})
        # A subsequent legitimate contradiction is a new record, not mutation of the old memory.
        correction=self.task('designer',title='Clamp route')
        with self.worker('designer') as w:
            ref=self.claimed(w,correction);self.plan(ref)
            report={k:v for k,v in self.answer(status='failed').items() if k!='edits'}
            self.clients['designer'].call('finish_bot_task',{**ref,'report':report})
        job=self.clients['designer'].call('list_bot_reflections',{'bot_id':'designer'})['items'][0]
        packet=self.clients['designer'].call('get_bot_reflection',{'reflection_id':job['id']})
        output=self.learning_infer([])({'operation':'reflect_on_experience','packet':packet},None,None)['output']
        output['lessons'][0]['contradicts']=[memory['id']]
        self.clients['designer'].call('complete_bot_reflection',{'reflection_id':job['id'],'version':job['version'],'output':output})
        resolved=self.owner.call('resolve_bot_message',{'message_id':request['message']['id'],
            'reason':'Discard stale opinion; do not treat it as validation','evidence':[]})
        self.assertFalse(resolved['experience_check_resolution']['available'])
        current=self.owner.call('get_bot_task',{'task_id':task['id']})['task']
        with self.worker('designer') as w:
            ref=self.claimed(w,current)
            report={k:v for k,v in self.answer(unverified=['Stale check discarded']).items() if k!='edits'}
            result=self.clients['designer'].call('finish_bot_task',{**ref,'report':report})
        self.assertEqual(result['task']['status'],'completed')
        self.assertFalse(self.owner.call('get_bot_task',{'task_id':peer['id']})['experience_check']['available'])
        self.assertFalse(result['formal_adoption'])
