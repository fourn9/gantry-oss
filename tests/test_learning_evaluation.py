import json
import hashlib
import contextlib
import io
from unittest.mock import patch
import tempfile
import unittest
from pathlib import Path

from gantry.model import Fault


class LearningEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        project = self.root/'project'; project.mkdir()
        (project/'mechanical.json').write_text('{"value":1}')
        (project/'control.json').write_text('{"value":1}')
        (project/'verify.py').write_text('import json\nfrom pathlib import Path\na=json.loads(Path("mechanical.json").read_text())["value"]\nb=json.loads(Path("control.json").read_text())["value"]\nprint("equal",a==b)\nassert a==b==2\n')
        self.case = {'name':'paired fixture', 'project_root':'project',
            'files':['mechanical.json','control.json','verify.py'],
            'write_scope':['mechanical.json','control.json'], 'goal':'Make both values 2',
            'acceptance':['Both values equal 2'], 'verifier':{'script':'verify.py','timeout_seconds':5},
            'experiences':[{'observation':'Check both sides before editing', 'applicability':'Matching interface',
                'limitations':['Synthetic fixture, not measured history'], 'source':'synthetic-fixture-v1'}]}
        self.case_path = self.root/'case.json'; self.case_path.write_text(json.dumps(self.case))
    def tearDown(self): self.temp.cleanup()

    def response(self, ctx):
        if ctx.get('operation') == 'plan_from_experience':
            return {'decisions': [{'memory_id': m['id'], 'use': 'recheck', 'reason': 'Fixture'}
                for m in ctx['packet']['recall']['items']], 'steps': ['Inspect both files'],
                'consult_bot_ids': [], 'unknowns': ['Physical behavior'], 'rationale': 'Fixture'}
        if ctx.get('operation') == 'reflect_on_experience':
            return {'lessons': [], 'feedback': [], 'unknowns': ['Fixture'], 'self_assessment': None}
        for name in ('mechanical.json', 'control.json'):
            if json.loads(ctx['files'][name])['value'] != 2:
                return {'action': 'edit', 'arguments_json': json.dumps({'path': name, 'content': '{"value":2}',
                    'expected_hash': hashlib.sha256(ctx['files'][name].encode()).hexdigest()}), 'rationale': 'Fixture edit'}
        return {'action': 'finish', 'arguments_json': json.dumps({'summary': 'Both values updated',
            'rationale': 'Fixture', 'unverified': ['Physical behavior'], 'status': 'completed',
            'assignments': [], 'integrate_changes': [], 'edits': []}), 'rationale': 'Fixture'}

    def test_saved_intermediate_failure_then_acceptance_and_regeneration(self):
        from gantry import project_sandbox
        from gantry.learning_evaluation import run_evaluation
        from gantry.learning_evaluation_report import regenerate
        if project_sandbox.backend() == 'unavailable': self.skipTest('OS sandbox unavailable')
        def infer(ctx, schema, directory, **options):
            self.assertEqual(options['model'], 'fixture-model')
            return {'output': self.response(ctx), 'provider': {'kind': 'deterministic_test_fixture',
                'usage': {'input_tokens': 10, 'cached_input_tokens': 0, 'output_tokens': 5}}}
        result = run_evaluation(self.case_path, self.root/'result', model='fixture-model', reasoning_effort='low',
            max_calls=6, seconds=30, infer_fn=infer)
        self.assertEqual([r['status'] for r in result['trials']], ['accepted', 'accepted'], result['trials'])
        for row in result['trials']:
            self.assertEqual([v['accepted'] for v in row['verification']], [False, False, True, True])
            self.assertEqual(row['action_order'], ['edit', 'edit', 'finish'])
            self.assertEqual(row['usage']['input_tokens'], 50)
            self.assertTrue(row['reflections'])
        self.assertEqual(regenerate(self.root/'result')['summary'], result['summary'])
        self.assertEqual((self.root/'project/mechanical.json').read_text(), '{"value":1}')

    def test_limit_and_provider_failure_do_not_become_success(self):
        from gantry import project_sandbox
        from gantry.learning_evaluation import run_evaluation
        if project_sandbox.backend() == 'unavailable': self.skipTest('OS sandbox unavailable')
        for label, limit, fail in [('limit', 1, False), ('rate-limit', 6, True)]:
            def infer(ctx, schema, directory, **options):
                if fail: raise Fault('provider_rate_limited', 'Synthetic 429')
                return {'output': self.response(ctx), 'provider': {'kind': 'deterministic_test_fixture'}}
            result = run_evaluation(self.case_path, self.root/label, model='fixture-model', reasoning_effort='low',
                max_calls=limit, seconds=30, infer_fn=infer)
            self.assertEqual(result['summary']['matched_successful_pairs'], 0)
            self.assertTrue(all(r['status'] == 'held' for r in result['trials']), result['trials'])
            self.assertTrue(all(len(r['calls']) == 1 for r in result['trials']))
            self.assertTrue(all(r['usage']['input_tokens'] is None for r in result['trials']))

    def test_timeout_preserves_action_order_and_failed_tool_receipts(self):
        from gantry import project_sandbox
        from gantry.learning_evaluation import run_evaluation
        if project_sandbox.backend() == 'unavailable': self.skipTest('OS sandbox unavailable')
        seen = {}
        def infer(ctx, schema, directory, **options):
            if ctx.get('operation'): output = self.response(ctx)
            elif seen.get(ctx['task']['id'], 0) < 2:
                count = seen.get(ctx['task']['id'], 0); seen[ctx['task']['id']] = count+1
                output = {'action': 'tool', 'arguments_json': '{' if count == 0 else '{"name":"missing_tool"}',
                    'rationale': 'Deliberate malformed or unknown tool'}
            else: raise Fault('evaluation_timeout', 'Synthetic timeout after a recorded error')
            return {'output': output, 'provider': {'kind': 'deterministic_test_fixture'}}
        result = run_evaluation(self.case_path, self.root/'timeout', model='fixture-model', reasoning_effort='low',
            max_calls=6, seconds=30, infer_fn=infer)
        for row in result['trials']:
            self.assertNotEqual(row['status'], 'accepted')
            self.assertEqual(row['action_order'], ['tool', 'tool'])
            self.assertEqual(row['failed_tool_checks'], 2)

    def test_frozen_case_detects_verifier_in_write_scope_and_symlinks(self):
        from gantry.learning_evaluation import freeze_case
        frozen = freeze_case(self.case_path)
        self.assertEqual(set(frozen['manifest']), set(self.case['files']))
        self.case['write_scope'].append('verify.py'); self.case_path.write_text(json.dumps(self.case))
        with self.assertRaises(Fault): freeze_case(self.case_path)
        self.case['write_scope'].remove('verify.py'); self.case_path.write_text(json.dumps(self.case))
        path=self.root/'project/mechanical.json'; path.unlink(); path.symlink_to(self.root/'project/control.json')
        with self.assertRaises(Fault): freeze_case(self.case_path)

    def test_cli_prints_summary_not_private_trial_contents(self):
        from gantry.cli import bots_main
        private = {'settings': {}, 'summary': {'accepted': 1}, 'trials': [{'private': 'PRIVATE_NATIVE_SOURCE'}]}
        output = io.StringIO()
        with patch('sys.argv', ['gantry-crew', 'evaluate-learning', '--case', str(self.case_path),
            '--output', str(self.root/'new'), '--model', 'fixture', '--reasoning-effort', 'low',
            '--max-calls', '6', '--seconds', '30', '--live-codex']), \
            patch('gantry.learning_evaluation.run_evaluation', return_value=private), contextlib.redirect_stdout(output):
            bots_main()
        self.assertNotIn('PRIVATE_NATIVE_SOURCE', output.getvalue())
        self.assertEqual(json.loads(output.getvalue())['summary'], {'accepted': 1})

    def test_failed_and_incomplete_trials_are_not_dropped(self):
        from gantry.learning_evaluation_report import summarize
        settings={'repetitions':2}
        rows=[{'pair':0,'arm':'without_experience','status':'accepted','total_seconds':20},
              {'pair':0,'arm':'with_experience','status':'accepted','total_seconds':10},
              {'pair':1,'arm':'without_experience','status':'timeout','total_seconds':30},
              {'pair':1,'arm':'with_experience','status':'running'}]
        result=summarize(settings,rows)
        self.assertEqual(result['arms']['without_experience']['success_rate'],0.5)
        self.assertEqual(result['arms']['with_experience']['success_rate'],0.5)
        self.assertEqual(result['matched_successful_pairs'],1)
        self.assertEqual(result['time_ratios_without_over_with'],[2])
        self.assertEqual(result['incomplete_trials'],1)

    def test_real_core_isolates_arms_and_does_not_trust_completion_claim(self):
        from gantry import project_sandbox
        from gantry.learning_evaluation import run_evaluation
        if project_sandbox.backend()=='unavailable': self.skipTest('OS sandbox unavailable')
        seen=[]
        def inference(ctx,schema,directory,**options):
            seen.append(ctx)
            if ctx.get('operation')=='plan_from_experience':
                output={'decisions':[{'memory_id':m['id'],'use':'recheck','reason':'Fixture'} for m in ctx['packet']['recall']['items']],
                    'steps':['Inspect both files'],'consult_bot_ids':[],'unknowns':['Physical behavior'],'rationale':'Fixture'}
            elif ctx.get('operation')=='reflect_on_experience':
                output={'lessons':[],'feedback':[],'unknowns':['Fixture'],'self_assessment':None}
            else:
                output={'action':'finish','arguments_json':json.dumps({'summary':'Claims success without editing',
                    'rationale':'Test untrusted claim','unverified':[],'status':'completed','assignments':[],
                    'integrate_changes':[],'edits':[]}), 'rationale':'Fixture'}
            return {'output':output,'provider':{'kind':'deterministic_test_fixture'}}
        result=run_evaluation(self.case_path,self.root/'result',model='fixture-model',reasoning_effort='low',
            max_calls=6,seconds=30,repetitions=1,seed=3,infer_fn=inference)
        plans=[c for c in seen if c.get('operation')=='plan_from_experience']
        self.assertEqual(sorted(len(c['packet']['recall']['items']) for c in plans),[0,1])
        self.assertNotEqual(plans[0]['task']['session_id'],plans[1]['task']['session_id'])
        self.assertTrue(all(r['status']=='not_accepted' for r in result['trials']), result['trials'])
        self.assertTrue(all(r['usage']['input_tokens'] is None for r in result['trials']))
        self.assertEqual(result['summary']['matched_successful_pairs'],0)
        self.assertEqual((self.root/'project/mechanical.json').read_text(),'{"value":1}')
