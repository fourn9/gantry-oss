import base64
import copy
import json
from pathlib import Path
import secrets
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor

from gantry.model import Fault, digest
from gantry.service import Service, token_hash
from gantry.backup import restore_backup
from gantry.runner import run_contract, mentor_once, tick, capture_tree


class LocalClient:
    def __init__(self, service, token): self.service, self.token = service, token
    def call(self, name, args=None, key=None):
        return self.service.call(self.token, name, args or {}, key or secrets.token_hex(12))


class DevelopmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.service = Service(self.root / 'ledger'); self.token = self.service.bootstrap()['token']
        self.client = LocalClient(self.service, self.token)
        self.recipe = {'argv': [sys.executable, '-c', 'import json;open("result.json","w").write(json.dumps({"verdict":"pass"}))'], 'timeout_seconds': 10}
        self.snapshot = self.artifact({'input.txt': 'initial'})
        self.session = self.connect()

    def tearDown(self): self.temp.cleanup()
    def call(self, name, args=None, key=None): return self.client.call(name, args, key)
    def artifact(self, files):
        return self.call('capture_artifact', {'files': {p: base64.b64encode(v.encode()).decode() for p,v in files.items()}})['revision_id']
    def policy(self, mode='execute'):
        return {'mode': mode, 'actors': ['admin'], 'write_scope': ['result.json'], 'recipes': {'test': digest(self.recipe)},
                'max_executions': 3, 'timeout_seconds': 30, 'max_parallel': 1}
    def connect(self, mode='execute'):
        return self.call('connect_development', {'title': 'Existing robot development', 'snapshot': self.snapshot,
                         'capture': {'scope': 'saved files', 'missing': ['earlier history']}, 'unverified': ['motion'], **self.policy(mode)})
    def detail(self): return self.call('development_state', {'session_id': self.session['id']})
    def contract(self):
        return {'title': 'Check recorded input', 'input_snapshot': self.snapshot, 'write_scope': ['result.json'],
                'recipe': 'test', 'recipe_hash': digest(self.recipe), 'expected_outputs': ['result.json'],
                'completion': {'description': 'Result verdict is pass', 'require_exit_zero': True,
                               'required_files': ['result.json'], 'verdict_file': 'result.json'},
                'dependencies': [], 'hypothesis': 'The fixed input satisfies the check', 'rationale': 'Verify before proceeding'}
    def propose(self, changes=None):
        m = next(m for m in self.detail()['milestones'] if m['status'] == 'pending')
        c = self.contract(); c.update(changes or {})
        return self.call('mentor_propose', {'session_id': self.session['id'], 'milestone_id': m['id'], 'contract': c})
    def start(self, c): return self.call('start_execution', {'contract_id': c['id'], 'version': c['version']})
    def finish(self, e, **overrides):
        args = {'execution_id': e['id'], 'output_snapshot': self.artifact({'input.txt':'initial', 'result.json':'{"verdict":"pass"}'}),
                'exit_code': 0, 'execution_status': 'completed', 'capture': {'scope':'final files', 'missing':[]},
                'unverified':['real hardware'], 'summary':'trial completed', 'hypothesis':'h', 'rationale':'r'}
        args.update(overrides); return self.call('finish_execution', args)
    def fault(self, code, f):
        with self.assertRaises(Fault) as caught: f()
        self.assertEqual(caught.exception.code, code)

    def test_partial_modes_and_separate_permission(self):
        self.session = self.connect('record')
        self.fault('mode_disabled', self.propose)
        observed = self.call('observe_execution', {'session_id': self.session['id'], 'input_snapshot': self.snapshot,
            'tool':'CAD', 'conditions':{}, 'hypothesis':'h', 'rationale':'r', 'capture':{'scope':'final only','missing':['tool calls']}})
        result = self.finish(observed)
        self.assertEqual(result['engineering_verdict'], 'unknown')
        self.assertFalse(observed['execution_permission'])
        self.session = self.connect('suggest'); c = self.propose()
        self.assertFalse(self.start(c)['allowed'])
        self.assertEqual(self.detail()['executions'], [])
        self.assertEqual(self.detail()['contracts'][0]['status'], 'proposed')

    def test_recheck_stale_scope_recipe_and_budget(self):
        c = self.propose(); self.assertTrue(self.call('check_execution', {'contract_id': c['id']})['allowed'])
        d = self.detail()['session']
        self.call('advance_development', {'session_id': d['id'], 'version': d['version'], 'snapshot': self.snapshot,
                                         'reason':'dependency assumption changed', 'capture': d['capture'], 'unverified':d['unverified']})
        self.assertIn('stale_basis', self.start(c)['reasons'])
        self.session = self.connect(); c = self.propose({'write_scope':['private/'], 'expected_outputs':['private/output'],
            'completion': {'description':'output', 'require_exit_zero':True, 'required_files':['private/output']}})
        self.assertIn('scope_denied', self.start(c)['reasons'])
        self.session = self.connect(); c = self.propose({'recipe_hash':'f'*64})
        self.assertIn('recipe_not_allowed', self.start(c)['reasons'])
        self.session = self.connect(); c = self.propose(); d = self.detail()['session']
        self.call('configure_development', {'session_id':d['id'],'version':d['version'],'reason':'no budget',**{**self.policy(),'max_executions':0}})
        self.assertIn('budget_exhausted',self.start(c)['reasons'])

    def test_atomic_claim_and_idempotency(self):
        c = self.propose()
        def attempt(_):
            try: return self.start(c)
            except Fault as e: return {'error':e.code}
        with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(attempt, range(2)))
        self.assertEqual(sum(x.get('allowed',False) for x in results),1)
        self.assertEqual(self.detail()['session']['used_executions'],1)
        self.assertEqual(len(self.detail()['executions']),1)

    def test_explicit_long_simulation_budget_is_bounded(self):
        from gantry.runner import validate_recipe
        self.recipe = {**self.recipe, 'timeout_seconds': 7200}
        validate_recipe(self.recipe)
        d = self.detail()['session']
        policy = {**self.policy(), 'timeout_seconds': 7200}
        args = dict(session_id=d['id'], version=d['version'], reason='Measured physics runtime', **policy)
        self.fault('invalid_input', lambda: self.call('configure_development', {**args, 'timeout_seconds':7201}))
        self.fault('invalid_input', lambda: validate_recipe({**self.recipe, 'timeout_seconds':7201}))
        self.call('configure_development', args)
        result = self.start(self.propose())
        self.assertTrue(result['allowed'])
        self.assertEqual(result['execution']['deadline'] - result['execution']['started_at'], 7200000)

    def test_completion_verdict_scope_capture_and_stale_results(self):
        for failure in ['verdict', 'scope', 'capture', 'stale']:
            self.session = self.connect(); c = self.propose(); e = self.start(c)['execution']
            extras = {}
            if failure == 'verdict': extras['output_snapshot'] = self.artifact({'input.txt':'initial','result.json':'{"verdict":"fail"}'})
            if failure == 'scope': extras['output_snapshot'] = self.artifact({'input.txt':'changed','result.json':'{"verdict":"pass"}'})
            if failure == 'capture': extras['capture'] = {'scope':'final only','missing':['inputs unavailable']}
            if failure == 'stale':
                d = self.detail()['session']; self.call('advance_development', {'session_id':d['id'],'version':d['version'],
                    'snapshot':self.snapshot, 'reason':'assumption changed','capture':d['capture'],'unverified':[]})
            self.finish(e, **extras)
            self.assertEqual(self.detail()['contracts'][0]['status'],'blocked',failure)
        self.session = self.connect(); c = self.propose(); self.finish(self.start(c)['execution'])
        self.assertEqual(self.detail()['contracts'][0]['status'],'done')
        self.assertIsNone(self.call('state')['head'])

    def test_revocation_keeps_slot_until_confirmed_stop(self):
        c = self.propose(); e = self.start(c)['execution']; d = self.detail()['session']
        self.call('configure_development', {'session_id':d['id'],'version':d['version'],'reason':'pause',**self.policy('record')})
        self.assertEqual(self.detail()['executions'][0]['status'],'cancelling')
        self.finish(e)
        self.assertEqual(self.detail()['contracts'][0]['status'],'blocked')

    def test_authentication_cannot_spoof_or_change_delegation(self):
        token = secrets.token_urlsafe(32)
        p = self.call('propose', {'title':'agent','changes':[{'id':'agent','type':'principal','data':{
            'kind':'agent','permissions':['read','record','work','propose'],'token_hash':token_hash(token)}}]})
        args={'proposal_id':p['id'],'version':p['version']}
        self.call('submit',args); self.call('endorse',{**args,'reason':'test'}); self.call('review_adoption',{**args,'reason':'test','verdict':'approve'}); self.call('commit',args)
        agent=LocalClient(self.service,token)
        self.fault('unauthorized',lambda:agent.call('development_state',{'session_id':self.session['id']}))
        d=self.detail()['session']; policy={**self.policy(),'actors':['admin','agent']}
        self.call('configure_development',{'session_id':d['id'],'version':d['version'],'reason':'delegate',**policy})
        d=self.detail()['session']
        self.fault('human_approval_required',lambda:agent.call('configure_development',{'session_id':d['id'],'version':d['version'],'reason':'escalate',**policy}))
        c=self.propose(); e=agent.call('start_execution',{'contract_id':c['id'],'version':c['version']})['execution']
        self.fault('unauthorized',lambda:self.finish(e))

    def test_runner_real_process_isolation_capture_and_replay(self):
        c = self.propose()
        result = run_contract(self.client,c['id'],{'test':self.recipe},self.root/'runs')
        self.assertEqual(result['engineering_verdict'],'pass')
        self.assertEqual(result['changed_paths'],['result.json'])
        self.assertEqual(self.detail()['contracts'][0]['status'],'done')
        self.assertEqual(run_contract(self.client,c['id'],{'test':self.recipe},self.root/'runs'),result)
        self.assertTrue(self.call('replay')['matched'])
        bundle=self.call('export'); restore_backup(self.root/'restored',bundle)
        restored=LocalClient(Service(self.root/'restored'),self.token)
        self.assertEqual(restored.call('development_state',{'session_id':self.session['id']}),self.detail())

    def test_mentor_external_provider_and_bounded_tick(self):
        contract=self.contract()
        provider={'argv':[sys.executable,'-c', 'import json,sys; ctx=json.load(sys.stdin); assert ctx["trigger"]; print('+repr(json.dumps(contract))+')']}
        result=tick(self.client,self.session['id'],provider,{'test':self.recipe},self.root/'worker')
        self.assertEqual(result['mentor']['status'],'proposed')
        self.assertEqual(result['execution']['engineering_verdict'],'pass')
        self.assertEqual(len(self.detail()['contracts']),1)
        self.assertEqual(sum(m['status'] == 'proposed' for m in self.detail()['milestones']),1)

    def test_ambiguous_process_is_not_launched_again(self):
        c=self.propose(); folder=self.root/'runs'/c['id']/'attempt-1'; folder.mkdir(parents=True)
        (folder/'journal.json').write_text(json.dumps({'phase':'launched','execution':{'id':'uncertain'}}))
        self.fault('job_uncertain',lambda:run_contract(self.client,c['id'],{'test':self.recipe},self.root/'runs'))
        self.assertEqual(self.detail()['executions'],[])

    def test_late_connect_never_adopts_or_invents_history(self):
        d=self.detail()
        self.assertEqual(d['session']['capture']['missing'],['earlier history'])
        self.assertEqual(d['session']['unverified'],['motion'])
        self.assertIsNone(self.call('state')['head'])
        self.assertIn('History before connection',self.call('mentor_context',{'session_id':self.session['id']})['omissions'][1])

    def test_failed_run_can_retry_in_new_workspace_and_budget_is_shared(self):
        self.recipe = {'argv': [sys.executable, '-c', 'raise SystemExit(2)'], 'timeout_seconds': 5}
        self.session = self.connect(); c = self.propose()
        first = run_contract(self.client, c['id'], {'test': self.recipe}, self.root / 'runs')
        self.assertEqual(first['exit_code'], 2)
        c = self.detail()['contracts'][0]
        self.call('retry_contract', {'contract_id': c['id'], 'version': c['version'], 'reason': 'reproduce failure'})
        second = run_contract(self.client, c['id'], {'test': self.recipe}, self.root / 'runs')
        self.assertNotEqual(first['attempt_id'], second['attempt_id'])
        self.assertEqual(self.detail()['session']['used_executions'], 2)

    def test_lost_start_response_does_not_duplicate_execution(self):
        c = self.propose(); delegate = self.client
        class DropOnce:
            dropped = False
            def call(inner, name, args=None, key=None):
                result = delegate.call(name, args, key)
                if name == 'start_execution' and not inner.dropped:
                    inner.dropped = True; raise OSError('response lost')
                return result
        client = DropOnce()
        with self.assertRaises(OSError): run_contract(client, c['id'], {'test':self.recipe}, self.root/'runs')
        result = run_contract(client, c['id'], {'test':self.recipe}, self.root/'runs')
        self.assertEqual(result['engineering_verdict'], 'pass')
        self.assertEqual(len(self.detail()['executions']), 1)

    def test_timeout_and_mentor_failure_preserve_records(self):
        self.recipe = {'argv':[sys.executable, '-c', 'import time;time.sleep(10)'], 'timeout_seconds':1}
        self.session = self.connect(); c = self.propose()
        result = run_contract(self.client,c['id'],{'test':self.recipe},self.root/'runs')
        self.assertEqual(result['status'],'failed')
        self.assertEqual(self.detail()['contracts'][0]['status'],'blocked')
        self.session = self.connect('suggest')
        provider = {'argv':[sys.executable,'-c','print("not json")']}
        with self.assertRaises(ValueError): mentor_once(self.client,self.session['id'],provider,self.root/'mentor')
        self.assertEqual(self.detail()['milestones'][0]['status'],'pending')

    def test_matching_evidence_reuse_and_invalidation(self):
        first=self.propose(); self.finish(self.start(first)['execution'])
        second=self.propose()
        receipt=self.call('reuse_contract',{'contract_id':second['id'],'version':second['version']})
        self.assertTrue(receipt['reused'])
        self.assertEqual(receipt['contract']['reuse_receipt']['source_contract'],first['id'])
        self.assertEqual(self.detail()['session']['used_executions'],1)
        latest=next(c for c in self.detail()['contracts'] if c['id']==first['id'])
        self.call('invalidate_submission',{'contract_id':latest['id'],'version':latest['version'],'reason':'evaluator defect discovered'})
        third=self.propose()
        self.assertFalse(self.call('reuse_contract',{'contract_id':third['id'],'version':third['version']})['reused'])

    def test_dependency_blocks_until_verified_completion(self):
        first=self.propose()
        self.call('signal_development',{'session_id':self.session['id'],'kind':'submission','summary':'independent request','references':[]})
        second=self.propose({'dependencies':[first['id']]})
        self.assertIn('dependency_pending',self.start(second)['reasons'])
        self.finish(self.start(first)['execution'])
        self.assertTrue(self.start(second)['allowed'])

    def test_external_final_only_adapter_preserves_gaps(self):
        from gantry.runner import observe_saved_development
        external=self.root/'external'; external.mkdir(); (external/'input.txt').write_text('external edit')
        result=observe_saved_development(self.client,self.session['id'],external,self.root/'observe.json','h','r','external result',0)
        self.assertIn('intermediate operations',result['capture']['missing'])
        self.assertEqual(result['engineering_verdict'],'unknown')
        self.assertEqual(self.detail()['session']['used_executions'],0)
        self.assertIsNone(self.call('state')['head'])

    def test_milestones_are_available_via_existing_event_cursor(self):
        sub=self.call('subscribe',{'targets':[self.session['id']]})
        m=self.call('signal_development',{'session_id':self.session['id'],'kind':'failure','summary':'contact failed','references':[]})
        events=self.call('events',{'cursor':sub['cursor']})
        self.assertIn(m['id'],[e.get('milestone_id') for e in events['events']])

    def test_upstream_invalidation_during_run_blocks_downstream_completion(self):
        up=self.propose();self.finish(self.start(up)['execution'])
        down=self.propose({'dependencies':[up['id']]}); e=self.start(down)['execution']
        latest=next(c for c in self.detail()['contracts'] if c['id']==up['id'])
        self.call('invalidate_submission',{'contract_id':up['id'],'version':latest['version'],'reason':'bad evaluator'})
        result=self.finish(e)
        self.assertIn('dependency_invalidated',result['reasons'])
        self.assertEqual(next(c for c in self.detail()['contracts'] if c['id']==down['id'])['status'],'blocked')

    def test_reconcile_stopped_uncertain_job_then_handoff(self):
        from gantry.runner import recover_run, persist
        c=self.propose(); start=self.start(c)
        folder=self.root/'runs'/c['id']/'attempt-1'; folder.mkdir(parents=True)
        persist(folder/'journal.json',{'phase':'launched','execution':start['execution'],'contract':start['contract'],
            'recipe':self.recipe,'timeout':30,'zone':'root'})
        result=recover_run(self.client,c['id'],{'test':self.recipe},self.root/'runs','launch outcome lost; operator confirmed stopped')
        self.assertEqual(result['status'],'failed')
        self.assertFalse(result['valid'])
        c=self.detail()['contracts'][0]
        self.call('retry_contract',{'contract_id':c['id'],'version':c['version'],'reason':'new attempt after reconciliation'})
        result=run_contract(self.client,c['id'],{'test':self.recipe},self.root/'runs')
        self.assertEqual(result['engineering_verdict'],'pass')

if __name__ == '__main__': unittest.main()
