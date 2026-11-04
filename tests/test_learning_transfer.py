"""Real ledgers/sandbox; deterministic inference tests experiment integrity only."""
import json

from test_learning_evaluation import LearningEvaluationTests


class LearningTransferTests(LearningEvaluationTests):
    def test_failure_generated_lesson_transfers_without_answers_or_manual_seed(self):
        from gantry.learning_transfer import run_transfer_evaluation
        from gantry import project_sandbox
        if project_sandbox.backend() == 'unavailable': self.skipTest('OS sandbox unavailable')
        training = dict(self.case, experiences=[])
        train = self.root/'training.json'; train.write_text(json.dumps(training))
        target = self.root/'target.json'; target.write_text(json.dumps(training))
        seen = []
        def infer(ctx, schema, directory, **options):
            seen.append(ctx)
            output = self.response(ctx)
            if ctx.get('operation') == 'reflect_on_experience':
                output['lessons'] = [{'kind': 'procedure', 'observation': 'Both interface values must agree',
                    'strategy': 'Inspect and change both mechanical and control values before verifying',
                    'when_to_use': 'Matched interface', 'when_not_to_use': ['Different acceptance'],
                    'paths': ['mechanical.json','control.json'], 'tags': ['interface'],
                    'evidence': [ctx['packet']['task_id']], 'supersedes': [], 'contradicts': []}]
            return {'output': output, 'provider': {'kind': 'deterministic_fixture'}}
        result = run_transfer_evaluation(train, [target], self.root/'transfer', model='fixture-model',
            reasoning_effort='low', max_calls=8, seconds=30, infer_fn=infer)
        self.assertEqual(result['training']['status'], 'accepted')
        self.assertFalse(result['training']['verification'][0]['accepted'])
        self.assertEqual(len(result['generated_lessons']), 1)
        plans = [x for x in seen if x.get('operation') == 'plan_from_experience']
        self.assertEqual(len(plans[0]['packet']['recall']['items']), 0)
        self.assertEqual(sorted(len(p['packet']['recall']['items']) for p in plans[1:]), [0,1])
        lesson = next(p['packet']['recall']['items'][0] for p in plans[1:] if p['packet']['recall']['items'])
        self.assertIn('Generated training reflection', lesson['observation'])
        self.assertEqual(result['evaluations'][0]['summary']['matched_successful_pairs'], 1)
        self.assertTrue(result['training']['total_seconds'] > 0)
        self.assertNotIn('Both values updated', lesson['observation'])

    def test_no_lesson_is_inconclusive_without_fabricating_experience(self):
        from gantry.learning_transfer import run_transfer_evaluation
        from gantry import project_sandbox
        if project_sandbox.backend() == 'unavailable': self.skipTest('OS sandbox unavailable')
        case = dict(self.case, experiences=[])
        train = self.root/'training.json'; train.write_text(json.dumps(case))
        def infer(ctx, schema, directory, **options):
            return {'output': self.response(ctx), 'provider': {'kind': 'deterministic_fixture'}}
        result = run_transfer_evaluation(train, [train], self.root/'transfer', model='fixture-model',
            reasoning_effort='low', max_calls=8, seconds=30, infer_fn=infer)
        self.assertEqual(result['status'], 'inconclusive_no_generated_lessons')
        self.assertEqual(result['evaluations'], [])
