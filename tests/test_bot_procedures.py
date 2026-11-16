"""Real Core lifecycle checks; fixture reasoning is not a learning benefit claim."""
import json
import sys
import unittest

from gantry import project_sandbox
from gantry.bot_worker import environment_manifest
from gantry.service import Service
import test_bot_learning as fixtures
from test_development import LocalClient


class BotProcedureTests(unittest.TestCase):
    def setUp(self):
        self.c = fixtures.BotLearningTests(); self.c.setUp()
        self.addCleanup(self.c.tearDown)

    def lesson(self):
        c = self.c; task = c.task('designer', title='Clamp route')
        with c.worker('designer') as worker:
            ref = c.claimed(worker, task); c.plan(ref)
            report = {k:v for k,v in c.answer(status='failed').items() if k != 'edits'}
            c.clients['designer'].call('finish_bot_task', {**ref, 'report':report})
        job = c.clients['designer'].call('list_bot_reflections', {'bot_id':'designer'})['items'][0]
        output = {'lessons':[{'kind':'procedure', 'observation':'Clamp route needs an early check',
            'strategy':'Check saved clearance before routing', 'when_to_use':'This saved assembly',
            'when_not_to_use':['Changed geometry or requirements'], 'paths':['mechanical.txt'],
            'tags':['clamp'], 'evidence':[task['id']], 'supersedes':[], 'contradicts':[],
            'procedure_steps':['Read saved mechanical input', 'Run the scoped check']}],
            'feedback':[], 'unknowns':['No physical validation'],
            'self_assessment':{'needs_independent_check':False, 'concerns':[], 'reason':'Self confidence only'}}
        result = c.clients['designer'].call('complete_bot_reflection',
            {'reflection_id':job['id'], 'version':job['version'], 'output':output})
        return result['memory_ids'][0]

    def decide(self, ref, memory_id, status='candidate', version=0, checks=None, key=None):
        return self.c.clients['designer'].call('record_bot_procedure_decision',
            {**ref, 'memory_id':memory_id, 'version':version, 'status':status,
             'reason':'Explicit Bot judgment for the pinned conditions', 'check_ids':checks or []}, key)

    def recalled(self, ref, memory_id):
        packet = self.c.clients['designer'].call('prepare_bot_learning', ref)
        return packet, next(m for m in packet['recall']['items'] if m['id'] == memory_id)

    def peer_check(self, ref, memory_id, result='sandbox'):
        c = self.c
        if result == 'sandbox':
            config = c.configs['control']
            config.update(agent_loop=True, sandbox=project_sandbox.backend(),
                tool_runtime=project_sandbox.runtime_roots(), local_tools={'check':{
                    'argv':[sys.executable, '-B', '-c',
                        'from pathlib import Path; assert Path("mechanical.txt").read_text() == "1"; print("fixture check passed")'],
                    'timeout_seconds':20}})
            runtime = c.owner.call('get_persistent_bot', {'bot_id':'control'})['runtime']
            c.owner.call('configure_bot_runtime', {'bot_id':'control', 'version':runtime['version'],
                'principal_id':'control', 'enabled':True, 'environment':environment_manifest(config)})
        peer = c.clients['designer'].call('ask_bot', {**ref, 'to_bot_id':'control',
            'question':'Check the clamp procedure on these saved inputs', 'evidence':[],
            'memory_id':memory_id})['response_task']
        if result == 'sandbox':
            def infer(context, schema, directory):
                if context['round'] == 0: action, args = 'tool', {'name':'check'}
                else:
                    receipt = next(a for a in context['actions'] if a['kind'] == 'tool')
                    action, args = 'finish', c.answer(experience_check={'verdict':'supported_for_scope',
                        'reason':'The saved-input check passed; other claims remain unverified',
                        'action_ids':[receipt['id']]})
                return {'output':{'action':action, 'arguments_json':json.dumps(args),
                    'rationale':'Fixture review'}, 'provider':{'kind':'fixture'}}
            with c.worker('control', infer) as worker:
                completed = worker.tick()[0]
                self.assertEqual(completed.get('task', {}).get('status'), 'completed', completed)
        else:
            with c.worker('control') as worker:
                peer_ref = c.claimed(worker, peer, 'control')
                kind, details = ('read', {'path':'mechanical.txt'}) if result == 'read' else ('tool', {'result':result})
                action = c.clients['control'].call('record_bot_action', {**peer_ref, 'kind':kind, 'details':details})
                report = {k:v for k,v in c.answer(experience_check={'verdict':'supported_for_scope',
                    'reason':'Fixture peer opinion', 'action_ids':[action['id']]}).items() if k != 'edits'}
                c.clients['control'].call('finish_bot_task', {**peer_ref, 'report':report})
        c.clients['designer'].call('refresh_bot_task', ref)
        return c.clients['designer'].call('get_bot_task', {'task_id':peer['id']})['experience_check']['result']

    def test_candidate_cannot_apply_or_promote_from_self_assessment(self):
        c = self.c; mid = self.lesson(); task = c.task('designer', title='Clamp route')
        with c.worker('designer') as worker:
            ref = c.claimed(worker, task)
            decision = self.decide(ref, mid, key='candidate-once')
            self.assertEqual(decision, self.decide(ref, mid, key='candidate-once'))
            packet, memory = self.recalled(ref, mid)
            self.assertEqual(memory['procedure_decision']['status'], 'candidate')
            self.assertEqual(memory['allowed_uses'], ['recheck', 'reject'])
            c.fault('stale_basis', lambda:c.clients['designer'].call('submit_bot_learning_plan',
                {**ref, 'plan_id':packet['id'], 'output':c.plan_output(packet,
                    [{'memory_id':mid, 'use':'apply', 'reason':'Self-assessed confidence'}])}))
            c.fault('invalid_input', lambda:self.decide(ref, mid, 'preferred', version=1))

    def test_peer_opinion_without_successful_tool_receipt_cannot_promote(self):
        c = self.c; mid = self.lesson(); task = c.task('designer', title='Clamp route')
        with c.worker('designer') as worker:
            ref = c.claimed(worker, task); check = self.peer_check(ref, mid, 'read')
            c.fault('invalid_input', lambda:self.decide(ref, mid, 'preferred', checks=[check['id']]))

    def test_sandbox_peer_check_supports_preference_and_recall_after_restart(self):
        c = self.c; mid = self.lesson(); task = c.task('designer', title='Clamp route')
        with c.worker('designer') as worker:
            ref = c.claimed(worker, task); check = self.peer_check(ref, mid)
            decision = self.decide(ref, mid, 'preferred', checks=[check['id']])
            self.assertFalse(decision['formal_adoption'])
            self.assertEqual(decision['evidence_status'], 'peer_report_with_successful_tool_receipts')
        next_task = c.task('designer', title='Clamp route')
        fresh = LocalClient(Service(c.root/'ledger'), c.tokens['designer'])
        with c.worker('designer', client=fresh) as worker:
            ref = c.claimed(worker, next_task)
            packet = fresh.call('prepare_bot_learning', ref)
            memory = next(m for m in packet['recall']['items'] if m['id'] == mid)
            self.assertEqual(memory['procedure_decision']['effective_status'], 'tested_for_scope')
            self.assertIn('apply', memory['allowed_uses'])
        self.assertTrue(c.owner.call('replay')['matched'])

    def test_retired_procedure_is_reject_only_and_revision_is_checked(self):
        c = self.c; mid = self.lesson(); task = c.task('designer', title='Clamp route')
        with c.worker('designer') as worker:
            ref = c.claimed(worker, task); self.decide(ref, mid)
            c.fault('stale_basis', lambda:self.decide(ref, mid, 'retired'))
            self.decide(ref, mid, 'retired', version=1)
            packet, memory = self.recalled(ref, mid)
            self.assertEqual(memory['allowed_uses'], ['reject'])
            c.fault('stale_basis', lambda:c.clients['designer'].call('submit_bot_learning_plan',
                {**ref, 'plan_id':packet['id'], 'output':c.plan_output(packet)}))

    def test_changed_task_conditions_require_recheck_without_erasing_preference(self):
        c = self.c; mid = self.lesson(); task = c.task('designer', title='Clamp route')
        with c.worker('designer') as worker:
            ref = c.claimed(worker, task); check = self.peer_check(ref, mid)
            self.decide(ref, mid, 'preferred', checks=[check['id']])
        next_task = c.task('designer', title='Clamp route', completion=['A changed acceptance condition'])
        with c.worker('designer') as worker:
            ref = c.claimed(worker, next_task); _, memory = self.recalled(ref, mid)
            self.assertEqual(memory['procedure_decision']['status'], 'preferred')
            self.assertEqual(memory['procedure_decision']['effective_status'], 'requires_recheck')
            self.assertIn('procedure_conditions_changed', memory['applicability_flags'])
            self.assertNotIn('apply', memory['allowed_uses'])
            c.fault('stale_basis', lambda:self.decide(ref, mid, 'preferred', version=1, checks=[check['id']]))

    def test_changed_peer_runtime_invalidates_old_support(self):
        c = self.c; mid = self.lesson(); task = c.task('designer', title='Clamp route')
        with c.worker('designer') as worker:
            ref = c.claimed(worker, task); check = self.peer_check(ref, mid)
            self.decide(ref, mid, 'preferred', checks=[check['id']])
            c.configs['control']['environment_definition'] = 'Changed tool environment'
            runtime = c.owner.call('get_persistent_bot', {'bot_id':'control'})['runtime']
            c.owner.call('configure_bot_runtime', {'bot_id':'control', 'version':runtime['version'],
                'principal_id':'control', 'enabled':True, 'environment':environment_manifest(c.configs['control'])})
            _, memory = self.recalled(ref, mid)
            self.assertEqual(memory['procedure_decision']['effective_status'], 'requires_recheck')
            self.assertIn('procedure_evidence_unavailable', memory['applicability_flags'])
            c.fault('stale_basis', lambda:self.decide(ref, mid, 'preferred', version=1, checks=[check['id']]))

    def test_failed_tool_cannot_be_laundered_by_supported_peer_verdict(self):
        c = self.c; mid = self.lesson(); task = c.task('designer', title='Clamp route')
        with c.worker('designer') as worker:
            ref = c.claimed(worker, task)
            check = self.peer_check(ref, mid, {'exit_code':1, 'reason':None,
                'sandbox':'macos-seatbelt', 'workspace_changes_applied':[],
                'output_artifact':c.artifact({'tool-output.txt':'fixture failure'})})
            c.fault('invalid_input', lambda:self.decide(ref, mid, 'preferred', checks=[check['id']]))

    def test_legacy_memory_remains_unchanged_and_requires_refinement_before_enrollment(self):
        c = self.c; task = c.task('designer', title='Clamp route')
        with c.worker('designer') as worker:
            ref = c.claimed(worker, task); memory = c.seed(ref)
            _, before = self.recalled(ref, memory['id'])
            self.assertNotIn('procedure_decision', before)
            c.fault('invalid_input', lambda:self.decide(ref, memory['id']))
            _, after = self.recalled(ref, memory['id'])
            self.assertEqual(before, after)

    def test_shared_procedure_does_not_disclose_private_decision_or_allow_other_author(self):
        c = self.c; mid = self.lesson(); task = c.task('designer', title='Clamp route')
        with c.worker('designer') as worker:
            ref = c.claimed(worker, task)
            c.clients['designer'].call('record_bot_procedure_decision', {**ref, 'memory_id':mid,
                'version':0, 'status':'retired', 'reason':'PRIVATE_PROCEDURE_REASON', 'check_ids':[]})
        other = c.task('lead', title='Clamp route')
        with c.worker('lead') as worker:
            ref = c.claimed(worker, other, 'lead')
            packet = c.clients['lead'].call('prepare_bot_learning', ref)
            memory = next(m for m in packet['recall']['items'] if m['id'] == mid)
            self.assertEqual(memory['allowed_uses'], ['reject'])
            self.assertNotIn('PRIVATE_PROCEDURE_REASON', json.dumps(packet))
            c.fault('unauthorized', lambda:c.clients['lead'].call('record_bot_procedure_decision',
                {**ref, 'memory_id':mid, 'version':1, 'status':'candidate', 'reason':'Other Bot', 'check_ids':[]}))

    def test_decision_change_invalidates_prepared_plan(self):
        c = self.c; mid = self.lesson(); task = c.task('designer', title='Clamp route')
        with c.worker('designer') as worker:
            ref = c.claimed(worker, task); packet, _ = self.recalled(ref, mid)
            self.decide(ref, mid)
            c.fault('stale_basis', lambda:c.clients['designer'].call('submit_bot_learning_plan',
                {**ref, 'plan_id':packet['id'], 'output':c.plan_output(packet)}))

    def test_ordinary_context_exposes_retirement_with_learning_disabled(self):
        c = self.c; mid = self.lesson(); task = c.task('designer', title='Clamp route')
        self.assertFalse(c.configs['designer'].get('experience_learning'))
        with c.worker('designer') as worker:
            ref = c.claimed(worker, task); self.decide(ref, mid, 'retired')
            view = c.clients['designer'].call('get_bot_task', {'task_id':task['id']})
            memory = next(m for m in view['memory']['items'] if m['id'] == mid)
            self.assertEqual(memory['procedure_decision']['status'], 'retired')
            self.assertEqual(memory['allowed_uses'], ['reject'])

    def test_read_only_consultation_cannot_select_authored_procedure_directly(self):
        c = self.c; mid = self.lesson(); task = c.task('lead', title='Ask about clamp route')
        with c.worker('lead') as worker:
            ref = c.claimed(worker, task, 'lead')
            peer = c.clients['lead'].call('ask_bot', {**ref, 'to_bot_id':'designer',
                'question':'Read-only clamp advice', 'evidence':[]})['response_task']
        with c.worker('designer') as worker:
            ref = c.claimed(worker, peer)
            c.fault('scope_denied', lambda: self.decide(ref, mid))
