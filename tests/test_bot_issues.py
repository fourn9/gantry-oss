"""Persistent residual issues; synthetic declarations, real tool and ledger paths."""
import copy
import json
import unittest
from gantry.model import Fault
from gantry.service import Service
from test_development import LocalClient
import test_crew_tool_evidence as evidence_fixtures


class BotIssueTests(unittest.TestCase):
    def setUp(self):
        self.c = evidence_fixtures.CrewToolEvidenceTests(); self.c.setUp()
        self.c.infer = lambda *a: {'output': self.c.answer()}
        self.addCleanup(self.c.tearDown)
        c = self.c
        source = c.task('designer')
        def report(*args):
            return {'output': c.answer(followups=[{'id': 'remaining-load', 'summary': 'Check support load',
                'reason': 'Not evaluated yet', 'disposition': 'defer', 'evidence': [source['id']],
                'requirement_refs': []}])}
        with c.worker('designer', report) as w: w.tick()
        self.source = source['id']


    def claim(self, role='designer', **extra):
        task = self.c.task(role, **extra)
        worker = self.c.worker(role); worker.__enter__(); self.addCleanup(worker.__exit__, None, None, None)
        claim = self.c.clients[role].call('claim_bot_task', {'task_id': task['id'], 'version': task['version'],
            'runtime_fence': worker.runtime['fence']})
        claimed = claim['task']
        return {'task_id': task['id'], 'fence': claimed['fence']}

    def opening(self, ref, owner='designer'):
        return {**ref, 'source_task_id': self.source, 'source_attempt': 1, 'followup_id': 'remaining-load',
            'owner_bot_id': owner, 'paths': ['mechanical.txt'], 'completion': ['Declared load check passes'],
            'verification_plan': 'physical-plan.json', 'check_ids': ['load']}

    def fault(self, code, call):
        with self.assertRaises(Fault) as e: call()
        self.assertEqual(e.exception.code, code, str(e.exception))

    def test_stable_promotion_and_historical_report_preserved(self):
        ref = self.claim()
        args = self.opening(ref)
        issue = self.c.clients['designer'].call('open_bot_issue', args)
        again = self.c.clients['designer'].call('open_bot_issue', args)
        self.assertEqual(issue['id'], again['id'])
        self.assertEqual(again['version'], 1)
        view = self.c.owner.call('get_bot_task', {'task_id': ref['task_id']})
        self.assertEqual(view['issues']['items'][0]['id'], issue['id'])
        self.assertFalse(view['issues']['items'][0]['product_complete'])
        self.assertEqual(self.c.owner.call('get_bot_task', {'task_id': self.source})['followups'][0]['status'], 'deferred')
        args['completion'] = ['Weakened criterion']
        self.fault('conflict', lambda: self.c.clients['designer'].call('open_bot_issue', args))
        self.assertTrue(self.c.owner.call('replay')['matched'])

    def test_completed_work_does_not_close_issue_and_peer_cannot_review(self):
        ref = self.claim('lead')
        issue = self.c.clients['lead'].call('open_bot_issue', self.opening(ref))
        task = self.c.task('designer', issue_ids=[issue['id']])
        with self.c.worker('designer', lambda *a: {'output': self.c.answer()}) as w: w.tick()
        row = self.c.owner.call('get_bot_issue', {'task_id': ref['task_id'], 'issue_id': issue['id']})
        self.assertEqual(row['issue']['status'], 'open')
        self.assertTrue(any(e.get('linked_task_id') == task['id'] for e in row['history']))
        other = self.claim('control')
        review = {**other, 'issue_id': issue['id'], 'version': 1, 'status': 'deferred',
            'state_id': self.c.base['id'], 'reason': 'Peer cannot defer another role', 'evidence': [task['id']]}
        self.fault('unauthorized', lambda: self.c.clients['control'].call('review_bot_issue', review))
        review.update(ref, status='resolved', verification_task_ids=[task['id']])
        self.fault('evidence_required', lambda: self.c.clients['lead'].call('review_bot_issue', review))

    def test_stale_version_and_missing_pass_rejected(self):
        ref = self.claim(); client = self.c.clients['designer']
        issue = client.call('open_bot_issue', self.opening(ref))
        args = {**ref, 'issue_id': issue['id'], 'version': 1, 'status': 'working',
            'state_id': self.c.base['id'], 'reason': 'Start investigation', 'evidence': [self.source]}
        row = client.call('review_bot_issue', args)
        self.assertEqual(row['version'], 2)
        self.fault('stale_basis', lambda: client.call('review_bot_issue', args))
        args.update(version=2, status='resolved', verification_task_ids=[])
        self.fault('evidence_required', lambda: client.call('review_bot_issue', args))

    def test_null_legacy_followups_and_incomplete_plan_rejected(self):
        c = self.c
        source = c.task('designer')
        with c.worker('designer', lambda *a: {'output':c.answer(followups=None)}) as w: w.tick()
        ref = self.claim()
        args = {**self.opening(ref), 'source_task_id':source['id']}
        self.fault('not_found', lambda:c.clients['designer'].call('open_bot_issue',args))
        args = self.opening(ref); args['check_ids'] = []
        self.fault('invalid_input', lambda:c.clients['designer'].call('open_bot_issue',args))

    def test_unlinked_manager_and_readonly_consultation_cannot_dispose(self):
        c = self.c; ref = self.claim('designer')
        issue = c.clients['designer'].call('open_bot_issue',self.opening(ref))
        manager = self.claim('lead')
        args = {**manager,'issue_id':issue['id'],'version':1,'status':'deferred',
            'state_id':c.base['id'],'reason':'Unlinked task','evidence':[self.source]}
        self.fault('scope_denied',lambda:c.clients['lead'].call('review_bot_issue',args))
        question = c.clients['designer'].call('ask_bot',{**ref,'to_bot_id':'control','question':'Review issue', 'evidence':[issue['id']]})
        response = c.owner.call('get_bot_task',{'task_id':question['response_task']['id']})['task']
        self.assertEqual(response['issue_ids'],[issue['id']])

    def test_source_ownership_cannot_be_captured_by_peer(self):
        c=self.c
        # Give control overlapping file scope; source ownership must still matter.
        c.owner.call('bind_development_bot',{'session_id':c.sid,'bot_id':'control','principal_id':'control',
            'version':1,'write_scope':['mechanical.txt','control.txt'],'can_assign':False,'can_integrate':False,'enabled':True})
        ref=self.claim('control',write_scope=['mechanical.txt'])
        self.fault('unauthorized',lambda:c.clients['control'].call('open_bot_issue',self.opening(ref,owner='control')))

    def test_child_links_and_history_pagination(self):
        c=self.c; ref=self.claim('lead'); issue=c.clients['lead'].call('open_bot_issue',self.opening(ref,owner='lead'))
        report=c.answer(status='waiting',assignments=[c.assignment('mechanical')]);report.pop('edits')
        finished=c.clients['lead'].call('finish_bot_task',{**ref,'report':report})
        child=c.owner.call('get_bot_task',{'task_id':finished['task']['children'][0]})['task']
        self.assertEqual(child['issue_ids'],[issue['id']])
        first=c.owner.call('get_bot_issue',{'task_id':ref['task_id'],'issue_id':issue['id'],'limit':1})
        self.assertEqual(first['history'][0]['kind'],'opened')
        second=c.owner.call('get_bot_issue',{'task_id':ref['task_id'],'issue_id':issue['id'],'limit':1,'after':first['next_cursor']})
        self.assertEqual(second['history'][0]['kind'],'assignment')

    def test_explicit_reassessment_preserves_old_plan(self):
        c=self.c; ref=self.claim('designer')
        issue=c.clients['designer'].call('open_bot_issue',self.opening(ref))
        session=c.owner.call('development_state',{'session_id':c.sid})['session']
        c.owner.call('configure_development',{'session_id':c.sid,'version':session['version'],
            'reason':'Owner authorizes acceptance maintenance',**{**c.policy,'write_scope':['mechanical.txt','control.txt','physical-plan.json']}})
        before=c.owner.call('get_development_state',{'state_id':c.base['id']})
        from gantry.adapters import artifact_file_parts
        import base64
        files={p:b''.join(artifact_file_parts(c.owner,before['state']['snapshot'],p,info)) for p,info in before['manifest'].items()}
        plan=json.loads(files['physical-plan.json']);plan['checks'][0]['criteria'][0]['max']=45
        files['physical-plan.json']=json.dumps(plan).encode()
        snap=c.owner.call('capture_artifact',{'files':{p:base64.b64encode(v).decode() for p,v in files.items()}})['revision_id']
        change=c.owner.call('begin_change',{'state_id':c.base['id'],'title':'Stricter acceptance','purpose':'Explicit reassessment',
            'write_scope':['physical-plan.json'],'dependencies':[],'assignee':'admin'})
        candidate=c.owner.call('checkpoint_change',{'change_id':change['id'],'version':change['version'],'snapshot':snap,
            'summary':'Stricter declared limit','rationale':'New acceptance candidate','unfinished':[],'work_status':'working',
            'capture':{'scope':'saved fixture files','missing':[]}})['state']
        manager=self.claim('mechanical',state_id=candidate['id'],issue_ids=[issue['id']])
        result=c.clients['mechanical'].call('review_bot_issue',{**manager,'issue_id':issue['id'],'version':1,'status':'reopened',
            'state_id':candidate['id'],'reason':'Accept stricter experimental limit; rerun required','evidence':[candidate['id']],
            'reassessment':{'verification_plan':'physical-plan.json','check_ids':['load'],'requirement_refs':[]}})
        self.assertNotEqual(result['verification_plan'],issue['verification_plan'])
        history=c.owner.call('get_bot_issue',{'task_id':manager['task_id'],'issue_id':issue['id']})['history']
        event=next(e for e in history if e['kind']=='reassessment')
        self.assertEqual(event['previous']['verification_plan'],issue['verification_plan'])
        self.assertGreater(result['cycle_started_seq'],issue['cycle_started_seq'])

    def test_failed_execution_cannot_resolve_completed_verification(self):
        c=self.c;c.configure_tool('failed');lead=self.claim('lead')
        issue=c.clients['lead'].call('open_bot_issue',self.opening(lead))
        task=c.task('designer',kind='verify',write_scope=c.tool_scope,issue_ids=[issue['id']])
        def infer(ctx,*args):
            return c.action('finish',c.answer()) if ctx.get('last_result') else c.action('tool',{'name':'stress'})
        with c.worker('designer',infer) as w: result=w.tick()[0]
        self.assertEqual(result['task']['status'],'completed')
        self.fault('evidence_required',lambda:c.clients['lead'].call('review_bot_issue',{**lead,'issue_id':issue['id'],
            'version':1,'status':'resolved','state_id':result['task']['output_state'],'reason':'Completed work is insufficient',
            'evidence':[task['id']],'verification_task_ids':[task['id']]}))

    def test_prepared_but_uncommitted_claim_resumes_with_new_runtime(self):
        from unittest.mock import patch
        c=self.c;task=c.task('control')
        with c.worker('control') as w:
            with patch.object(Service,'cmd_claim_bot_task',side_effect=Fault('invalid_input','Before claim commit')):
                first=w.tick()[0]
            self.assertEqual(first['reason'],'invalid_input')
        self.assertEqual(c.owner.call('get_bot_task',{'task_id':task['id']})['task']['status'],'pending')
        with c.worker('control') as w: result=w.tick()[0]
        self.assertEqual(result.get('task',{}).get('status'),'completed',result)

    def test_real_tool_resolution_resume_and_changed_files_need_recheck(self):
        c = self.c; c.configure_tool()
        lead = self.claim('lead')
        issue = c.clients['lead'].call('open_bot_issue', self.opening(lead))
        task = c.task('designer', kind='verify', write_scope=c.tool_scope, issue_ids=[issue['id']])
        def infer(ctx, schema, directory):
            if not ctx.get('last_result'): return c.action('tool', {'name': 'stress'})
            return c.action('finish', c.answer())
        with c.worker('designer', infer) as w: result = w.tick()[0]
        self.assertEqual(result.get('task', {}).get('status'), 'completed', result)
        state = result['task']['output_state']
        args = {**lead, 'issue_id': issue['id'], 'version': 1, 'status': 'resolved', 'state_id': state,
            'reason': 'Reviewed the declared load result; physical behavior still unverified',
            'evidence': [task['id'], state], 'verification_task_ids': [task['id']]}
        resolved = c.clients['lead'].call('review_bot_issue', args)
        self.assertEqual(resolved['status'], 'resolved')
        fresh = LocalClient(Service(c.root/'ledger'), c.tokens['lead'])
        query = {'task_id': lead['task_id'], 'issue_id': issue['id'], 'state_id': state}
        row = fresh.call('get_bot_issue', query)['issue']
        self.assertEqual(row['effective_status'], 'resolved')
        self.assertFalse(row['formal_adoption'])
        changed = c.task('designer', state_id=state, issue_ids=[issue['id']])
        # Direct leased checkpoint represents an external editor, not fake verification.
        with c.worker('designer') as w:
            claim = c.clients['designer'].call('claim_bot_task', {'task_id': changed['id'], 'version': 1,
                'runtime_fence': w.runtime['fence']})['task']
            before = c.owner.call('get_development_state', {'state_id': state})
            from gantry.adapters import artifact_file_parts
            files = {p: b''.join(artifact_file_parts(c.owner, before['state']['snapshot'], p, info)).decode()
                for p,info in before['manifest'].items()}
            files['mechanical.txt'] = '2'
            output = c.clients['designer'].call('checkpoint_bot_task', {'task_id': changed['id'], 'fence': claim['fence'],
                'snapshot': c.artifact(files), 'summary': 'Changed support', 'rationale': 'New candidate',
                'unfinished': ['Recheck load'], 'capture': {'scope': 'saved test files', 'missing': []}})
        newer = output['state']['id']
        row = fresh.call('get_bot_issue', {**query, 'state_id': newer})['issue']
        self.assertEqual(row['status'], 'resolved')
        self.assertEqual(row['effective_status'], 'needs_recheck')
        self.assertIn('mechanical.txt', row['changed_paths'])
        self.assertEqual(fresh.call('get_bot_issue', query)['issue']['effective_status'], 'resolved')
        # A new cycle cannot consume the previous verification again.
        reopened=c.clients['lead'].call('review_bot_issue',{**lead,'issue_id':issue['id'],'version':2,
            'status':'reopened','state_id':state,'reason':'Independent repeat requested','evidence':[task['id']]})
        self.fault('evidence_required',lambda:c.clients['lead'].call('review_bot_issue',{**args,'version':reopened['version']}))
        self.assertTrue(c.owner.call('replay')['matched'])

    def test_restricted_requirement_issue_is_not_readable_through_public_task(self):
        import base64
        c=self.c
        def adopt(change):
            p=c.owner.call('propose',{'title':'Read-only-review fixture setup','changes':[change]})
            a={'proposal_id':p['id'],'version':p['version']}
            c.owner.call('submit',a);c.owner.call('endorse',{**a,'reason':'Fixture owner approval'})
            c.owner.call('review_adoption',{**a,'verdict':'approve','reason':'Fixture owner approval'});c.owner.call('commit',a)
            return p['changes'][0]['revision_id']
        adopt({'id':'restricted','type':'zone','zone':'root','data':{'owner':'admin','participation':'participating'}})
        rid=adopt({'id':'private_req','type':'requirement','zone':'restricted','data':{'description':'Private threshold','verification_checks':['load']}})
        private_ref={'requirement_id':'private_req','revision_id':rid}
        with c.service.store.connect() as con: entry=copy.deepcopy(c.service.store.state(con)['entries']['lead'])
        principal=entry['data'];principal['zones']=['root','restricted']
        adopt({'id':'lead','type':'principal','zone':'root','expected_revision':entry['revision_id'],'data':principal})
        session=c.owner.call('development_state',{'session_id':c.sid})['session']
        c.owner.call('configure_development',{'session_id':c.sid,'version':session['version'],'reason':'Fixture plan scope',**{**c.policy,'write_scope':['mechanical.txt','control.txt','physical-plan.json']}})
        plan=copy.deepcopy(c.plan);plan['checks'][0]['requirement_refs']=[private_ref]
        files={'mechanical.txt':b'1','control.txt':b'1','physical-plan.json':json.dumps(plan).encode()}
        snapshot=c.owner.call('capture_artifact',{'files':{p:base64.b64encode(v).decode() for p,v in files.items()}})['revision_id']
        change=c.owner.call('begin_change',{'state_id':c.base['id'],'title':'Private criterion','purpose':'Private fixture','write_scope':['physical-plan.json'],'dependencies':[],'assignee':'admin'})
        context=copy.deepcopy(c.base['context']);context['requirement_refs']=[private_ref]
        private=c.owner.call('checkpoint_change',{'change_id':change['id'],'version':change['version'],'snapshot':snapshot,'summary':'Private scoped candidate','rationale':'Fixture','unfinished':[],'work_status':'working','capture':{'scope':'saved fixture','missing':[]},'context':context})['state']
        source=c.task('lead',state_id=private['id'])
        def infer(*args): return {'output':c.answer(followups=[{'id':'private-followup','summary':'SECRET-PRIVATE-THRESHOLD','reason':'Private review','disposition':'defer','evidence':[source['id']],'requirement_refs':[private_ref]}])}
        with c.worker('lead',infer) as w: w.tick()
        ref=self.claim('lead',state_id=private['id'])
        issue=c.clients['lead'].call('open_bot_issue',{**self.opening(ref,owner='lead'),'source_task_id':source['id'],'followup_id':'private-followup'})
        public_task=c.task('designer')
        args={'task_id':public_task['id'],'issue_id':issue['id']}
        self.fault('unauthorized',lambda:c.clients['designer'].call('get_bot_issue',args))
        self.assertEqual(c.clients['designer'].call('list_bot_issues',{'task_id':public_task['id']})['items'],[])
        self.assertEqual(c.clients['designer'].call('get_bot_task',{'task_id':public_task['id']})['issues']['items'],[])
