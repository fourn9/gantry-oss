import copy
import unittest
from unittest.mock import patch
from gantry import manifest_store
import test_studio as fixtures
import test_requirement_traceability as requirements


class LibraryTests(unittest.TestCase):
    setUp = fixtures.StudioTests.setUp
    tearDown = fixtures.StudioTests.tearDown
    call = fixtures.StudioTests.call
    artifact = fixtures.StudioTests.artifact
    policy = fixtures.StudioTests.policy
    detail = fixtures.StudioTests.detail
    connect = fixtures.StudioTests.connect
    initialize = fixtures.StudioTests.initialize
    begin = fixtures.StudioTests.begin
    checkpoint = fixtures.StudioTests.checkpoint
    fault = fixtures.StudioTests.fault
    setup_work = fixtures.StudioTests.setup_work
    requirement = requirements.TraceabilityIntegrationTests.requirement

    def linked(self):
        p, base, _ = self.setup_work()
        change = self.begin(base, ['input.txt','notes.md'])
        ref = self.requirement()
        context = copy.deepcopy(base['context']); context['requirement_refs'] = [ref]
        h = self.call('get_development_state', {'state_id':base['id']})['manifest']['input.txt']['hash']
        context['environment']['engineering'] = {'version':1,
            'components':[{'id':'arm','role':'motion','assembly':'robot','inputs':{'input.txt':h}}],
            'checks':[{'id':'travel','scope':'motion','components':['arm'],'required':True,
                'status':'pass','inputs':{'input.txt':h},'evidence':{'input.txt':h},'requirement_refs':[ref]}]}
        cp = self.checkpoint(change, {'input.txt':'initial','notes.md':'notes'}, context=context)
        return p, cp['state'], cp['change'], ref

    def test_files_page_exact_state_and_original_bytes_not_in_context(self):
        p, st, work, ref = self.linked()
        args = {'project_id':p['id'],'state_id':st['id']}
        first = self.call('studio_library', {**args,'section':'files','limit':1})
        self.assertEqual(first['items'][0]['path'], 'input.txt')
        self.assertTrue(first['next'])
        second = self.call('studio_library', {**args,'section':'files','after':first['next'],'limit':1})
        self.assertEqual(second['items'][0]['path'], 'notes.md')
        self.assertIsNone(second['next'])
        versions=self.call('studio_library',{**args,'section':'versions'})
        self.assertIn(st['id'],[v['id'] for v in versions['items']])
        ctx = self.call('studio_context', {**args,'anchor':{'kind':'file','path':'input.txt','hash':first['items'][0]['hash']}})
        self.assertEqual(ctx['mandatory']['requirements'][0]['requirement_id'], ref['requirement_id'])
        self.assertEqual(ctx['mandatory']['requirements'][0]['status'], 'unverified')
        self.assertIn('no hardware', ctx['mandatory']['constraints'])
        self.assertNotIn('manifest', ctx)
        self.assertNotIn('content', ctx)
        self.assertEqual(ctx['source']['state_id'], st['id'])
        self.assertTrue(ctx['retrieval'])

    def test_related_requirement_checks_work_and_changed_inputs(self):
        p, st, work, ref = self.linked()
        related = self.call('studio_related', {'project_id':p['id'],'state_id':st['id'],
            'anchor':{'kind':'requirement',**ref}})
        self.assertEqual(related['requirements'][0]['gaps'], ['load'])
        self.assertEqual(related['files'][0]['path'], 'input.txt')
        changed = self.checkpoint(work, {'input.txt':'different','notes.md':'notes'})['state']
        page = self.call('studio_library', {'project_id':p['id'],'state_id':changed['id'],'section':'requirements'})
        self.assertEqual(page['items'][0]['status'], 'unverified')
        self.requirement(ref['revision_id'])
        page = self.call('studio_library', {'project_id':p['id'],'state_id':st['id'],'section':'requirements'})
        self.assertEqual(page['items'][0]['status'], 'needs_review')

    def test_parent_related_records_include_child_component_files(self):
        self.initialize = lambda:self.call('initialize_continuity', {
            'session_id':self.session['id'],'version':self.detail()['session']['version'],
            'summary':'Nested saved assembly','hierarchy':[
                {'id':'robot','title':'Robot','kind':'robot','paths':[],'editable':True},
                {'id':'arm','parent':'robot','title':'Arm','kind':'part','paths':['input.txt'],'editable':True}],
            'context':{'requirements':[],'constraints':[],'decisions':[],
                       'open_questions':[],'environment':{}}})
        p,st,work,ref=self.linked()
        args={'project_id':p['id'],'state_id':st['id']}
        files=self.call('studio_library',{**args,'section':'files','component_id':'robot'})
        related=self.call('studio_related',{**args,'anchor':{'kind':'component','component_id':'robot'}})
        self.assertEqual([f['path'] for f in files['items']],['input.txt'])
        self.assertEqual([f['path'] for f in related['files']],['input.txt'])
        self.assertEqual(related['requirements'][0]['requirement_id'],ref['requirement_id'])
        self.assertEqual(related['checks'][0]['id'],'travel')
        self.assertEqual(related['works'][0]['id'],work['id'])

    def test_cross_project_state_and_unknown_targets_rejected(self):
        p, st, work = self.setup_work()
        other = self.call('save_project', {'name':'Other','description':'Separate'})
        self.fault('scope_denied', lambda:self.call('studio_library', {'project_id':other['id'],
            'state_id':st['id'],'section':'files'}))
        self.fault('invalid_input', lambda:self.call('studio_related', {'project_id':p['id'],
            'state_id':st['id'],'anchor':{'kind':'file','path':'input.txt','hash':'0'*64}}))
        page = self.call('studio_library', {'project_id':p['id'],'state_id':st['id'],'section':'requirements'})
        self.assertFalse(page['items'])
        self.assertEqual(page['unlinked_requirements'], ['motion'])

    def test_library_adoption_lookup_does_not_expand_unrelated_artifacts(self):
        p, st, _ = self.setup_work()
        unrelated = self.artifact({'elsewhere.step':'unrelated saved source'})
        with self.service.store.connect() as con:
            root = con.execute('SELECT root FROM artifact_roots WHERE revision_id=?',(unrelated,)).fetchone()[0]
        original = manifest_store.Tree.items
        def selected_only(tree,current,after=''):
            if current == root: raise AssertionError('Unrelated snapshot expanded')
            return original(tree,current,after)
        with patch.object(manifest_store.Tree,'items',selected_only):
            page=self.call('studio_library',{'project_id':p['id'],'state_id':st['id'],'section':'files'})
            self.assertEqual(page['state']['adoption'],'unadopted')

    def test_project_discussion_without_work_and_exact_requirement_revision(self):
        p, st, work, ref = self.linked()
        before = len(self.call('studio_overview')['works'])
        args = {'project_id':p['id'],'state_id':st['id'],'anchor':{'kind':'requirement',**ref}}
        message = self.call('studio_comment', {**args,'body':'Please check this requirement','mentions':['admin']})
        related = self.call('studio_related', args)
        self.assertEqual(related['threads'][0]['id'], message['thread_id'])
        self.assertEqual(len(self.call('studio_overview')['works']), before)
        inbox = self.call('studio_inbox')['items'][0]
        self.assertEqual(inbox['project_id'], p['id'])
        self.assertIsNone(inbox['work_id'])
        self.assertEqual(inbox['anchor'], args['anchor'])
        next_state = self.checkpoint(work)['state']
        self.fault('invalid_input', lambda:self.call('studio_comment', {**args,'state_id':next_state['id'],
            'thread_id':message['thread_id'],'body':'Wrong state','mentions':[]}))
        self.assertTrue(self.call('replay')['matched'])

    def test_exact_state_work_relations_do_not_mix_parallel_or_future_work(self):
        p, base, work = self.setup_work()
        one = self.checkpoint(work)
        other = self.checkpoint(self.begin(base))
        future = self.begin(other['state'])
        args = {'project_id':p['id'],'state_id':one['state']['id'],'anchor':{'kind':'project'}}
        related = self.call('studio_related',args)
        self.assertEqual([(w['id'],w['relation']) for w in related['works']],[(work['id'],'contains_checkpoint')])
        from_base = self.call('studio_related',{**args,'state_id':base['id']})
        self.assertNotIn(future['id'],[w['id'] for w in from_base['works']])
        self.assertTrue(all(w['relation']=='starts_from_state' for w in from_base['works']))

    def test_messages_have_independent_stable_cursor_and_exact_anchor(self):
        p, st, work = self.setup_work()
        args = {'project_id':p['id'],'state_id':st['id'],'anchor':{'kind':'project'}}
        ids=set()
        for i in range(7):
            ids.add(self.call('studio_comment',{**args,'body':f'Message {i}','mentions':[]})['id'])
        other = self.call('studio_comment',{**args,'anchor':{'kind':'component','component_id':'robot'},'body':'Other target','mentions':[]})
        seen=[];cursor=None
        while True:
            result=self.call('studio_related',{**args,'limit':2,**({'message_after':cursor} if cursor else {})})
            messages=[m for t in result['threads'] for m in t['messages']]
            self.assertLessEqual(len(messages),2);seen.extend(m['id'] for m in messages)
            cursor=result['message_next']
            if not cursor: break
        self.assertEqual(set(seen),ids);self.assertEqual(len(seen),7)
        self.fault('invalid_input',lambda:self.call('studio_related',{**args,'message_after':other['id']}))

    def test_delta_cursor_does_not_consume_related_work_cursor(self):
        p, st, work, ref = self.linked()
        changed=self.checkpoint(work,{'input.txt':'changed','notes.md':'changed'})['state']
        args={'project_id':p['id'],'state_id':changed['id'],'anchor':{'kind':'project'},'since_state':st['id'],'limit':1}
        result=self.call('studio_context',{**args,'after':'zzzz'})
        self.assertEqual(result['delta']['items'],[{'path':'input.txt'}])
        more=self.call('studio_context',{**args,'limit':100,'delta_after':result['delta']['next']})
        self.assertEqual(more['delta']['items'],[{'path':'notes.md'}])
        self.assertEqual(more['related']['works'][0]['id'],work['id'])

    def test_long_thread_starts_with_newest_page_after_submission(self):
        p, st, work = self.setup_work()
        self.service.clock = lambda: 123456789  # Concurrent comments can share a millisecond.
        args={'project_id':p['id'],'state_id':st['id'],'anchor':{'kind':'project'}}
        for i in range(52):
            message=self.call('studio_comment',{**args,'body':f'Message {i}','mentions':[]})
        result=self.call('studio_related',args)
        messages=result['threads'][0]['messages']
        self.assertEqual(len(messages),50)
        self.assertEqual(messages[-1]['id'],message['id'])
        older=self.call('studio_related',{**args,'message_after':result['message_next']})
        self.assertEqual(len(older['threads'][0]['messages']),2)
        self.assertFalse(set(m['id'] for m in messages)&set(m['id'] for m in older['threads'][0]['messages']))
