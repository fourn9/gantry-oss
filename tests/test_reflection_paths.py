"""Real-Core regression for absent evidence files, using anonymous fixtures."""
import copy
import test_bot_learning as learning


class ReflectionPathTests(learning.BotLearningTests):
    def reflection(self):
        task = self.task('designer', dependencies=['mechanical.txt'])
        with self.worker('designer') as worker:
            ref = self.claimed(worker, task)
            self.plan(ref)
            report = {k: v for k, v in self.answer().items() if k != 'edits'}
            self.clients['designer'].call('finish_bot_task', {**ref, 'report': report})
        item = self.clients['designer'].call('list_bot_reflections', {'bot_id': 'designer'})['items'][0]
        packet = self.clients['designer'].call('get_bot_reflection', {'reflection_id': item['id']})
        lesson = {'kind': 'procedure', 'observation': 'Verification has not run; report is not generated',
                  'strategy': 'Run the registered verification after integration',
                  'when_to_use': 'Next integration', 'when_not_to_use': ['No physical proof'],
                  'paths': ['mechanical.txt'], 'tags': ['verification'], 'evidence': [task['id']],
                  'supersedes': [], 'contradicts': []}
        return packet, {'reflection_id': item['id'], 'version': item['version'],
                        'output': {'lessons': [lesson], 'feedback': [], 'unknowns': ['Verification pending']}}

    def test_packet_exposes_bound_saved_paths_and_path_rules(self):
        packet, _ = self.reflection()
        rules = packet['evidence_rules']
        self.assertEqual(rules['saved_state_id'], packet['report_record']['state_id'])
        paths = {p['path']: p['hash'] for p in rules['saved_paths']}
        self.assertIn('mechanical.txt', paths)
        self.assertEqual(len(paths['mechanical.txt']), 64)
        self.assertNotIn('evidence/not-generated.json', paths)
        self.assertFalse(rules['saved_paths_truncated'])
        self.assertIn('unresolved_paths', rules['path_rules'])

    def test_unproduced_reference_is_preserved_without_becoming_evidence(self):
        _, args = self.reflection()
        lesson = args['output']['lessons'][0]
        lesson['unresolved_paths'] = [{'path': 'evidence/not-generated.json', 'status': 'planned',
                                       'reason': 'Verification has not executed'}]
        result = self.clients['designer'].call('complete_bot_reflection', args)
        self.assertEqual(result['status'], 'completed')
        memories = self.clients['designer'].call('list_persistent_memories', {'bot_id': 'designer'})['items']
        memory = next(m for m in memories if m['id'] == result['memory_ids'][0])
        self.assertEqual(memory['lesson']['unresolved_paths'], lesson['unresolved_paths'])
        self.assertNotIn('evidence/not-generated.json', memory['input_hashes'])
        self.assertEqual(memory['assessment'], 'inconclusive')
        self.assertTrue(self.owner.call('replay')['matched'])

    def test_absent_file_in_evidence_paths_is_still_rejected(self):
        packet, args = self.reflection()
        args['output']['lessons'][0]['paths'].append('evidence/not-generated.json')
        self.fault('invalid_input', lambda: self.clients['designer'].call('complete_bot_reflection', args))
        current = self.clients['designer'].call('get_bot_reflection', {'reflection_id': packet['id']})
        self.assertEqual(current['status'], 'pending')

    def test_unresolved_reference_cannot_hide_present_or_unsafe_paths(self):
        _, original = self.reflection()
        for path in ('mechanical.txt', '../outside.txt', '/tmp/outside.txt'):
            with self.subTest(path=path):
                args = copy.deepcopy(original)
                args['output']['lessons'][0]['unresolved_paths'] = [
                    {'path': path, 'status': 'not_captured', 'reason': 'Claimed absent'}]
                self.fault('invalid_input', lambda: self.clients['designer'].call('complete_bot_reflection', args))

    def test_rejected_reflection_does_not_prevent_peer_work_or_repeat_inference(self):
        self.enable_learning(); self.task('designer'); contexts = []
        normal = self.learning_infer(contexts)
        attempts = []
        def infer(context, schema, directory):
            result = normal(context, schema, directory)
            if context.get('operation') == 'reflect_on_experience':
                attempts.append(True)
                result['output']['lessons'][0]['paths'] = ['evidence/not-generated.json']
            return result
        with self.worker('designer', infer) as worker:
            results = worker.tick()
            self.assertEqual(results[-1]['status'], 'held')
            peer = self.task('control')
            with self.worker('control') as other:
                self.assertEqual(other.tick()[0]['task']['status'], 'completed')
            worker.tick()
        self.assertEqual(len(attempts), 1)
        self.assertEqual(self.owner.call('get_bot_task', {'task_id': peer['id']})['task']['status'], 'completed')

    def test_nullable_optional_field_is_compatible_with_monthly_strict_schema(self):
        from gantry.bot_learning_contracts import REFLECTION
        from gantry.contracts import validate
        from gantry.inference import strict_schema
        _, args = self.reflection()
        out = args['output']
        out['self_assessment'] = None
        out['lessons'][0].update(unresolved_paths=None, procedure_steps=None)
        validate(out, strict_schema(REFLECTION))
        validate(out, REFLECTION)
        self.assertEqual(self.clients['designer'].call('complete_bot_reflection', args)['status'], 'completed')

    def test_uncaptured_reference_is_not_later_promoted_to_verified_input(self):
        _, args = self.reflection()
        args['output']['lessons'][0]['unresolved_paths'] = [
            {'path': 'measurements/not-captured.csv', 'status': 'not_captured', 'reason': 'Not in saved state'}]
        self.clients['designer'].call('complete_bot_reflection', args)
        task = self.task('designer', title='Next integration verification', dependencies=['mechanical.txt'])
        with self.worker('designer') as worker:
            ref = self.claimed(worker, task)
            recalled = self.clients['designer'].call('prepare_bot_learning', ref)['recall']['items']
        memory = next(m for m in recalled if m.get('lesson', {}).get('unresolved_paths'))
        self.assertNotIn('measurements/not-captured.csv', memory['input_hashes'])
        self.assertEqual(memory['evidence_status'], 'reported_experience_not_independent_verification')
        self.assertIn('unresolved_path_references', memory['applicability_flags'])
        self.assertNotIn('apply', memory['allowed_uses'])

    def test_explicit_recovery_enriches_legacy_packet_with_current_path_rules(self):
        import json
        from gantry.runner import persist
        self.enable_learning(); self.task('designer'); contexts = []
        normal = self.learning_infer(contexts)
        calls = []
        def infer(context, schema, directory):
            result = normal(context, schema, directory)
            if context.get('operation') == 'reflect_on_experience':
                calls.append(context)
                if len(calls) == 1:
                    result['output']['lessons'][0]['paths'].append('evidence/not-generated.json')
                else:
                    self.assertIn('saved_paths', context['packet']['evidence_rules'])
                    self.assertIn('unresolved_paths', context['packet']['evidence_rules']['path_rules'])
                    self.assertIn('evidence/not-generated.json', context['previous_submission']['lessons'][0]['paths'])
                    result['output']['lessons'][0]['unresolved_paths'] = [
                        {'path': 'evidence/not-generated.json', 'status': 'planned', 'reason': 'Not generated'}]
            return result
        with self.worker('designer', infer) as worker:
            held = worker.tick()[-1]
            # Model a pre-upgrade held packet: previous input/receipt remain archived.
            marker = next(self.root.rglob('reflection.json'))
            saved = json.loads(marker.read_text())
            for key in ('saved_paths', 'saved_paths_total', 'saved_paths_truncated', 'path_rules'):
                saved['input']['packet']['evidence_rules'].pop(key, None)
            persist(marker, saved)
            result = worker.recover_reflection(held['reflection_id'], 'Prior request stopped and rejected', retry_inference=True)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(len(calls), 2)
