"""Large authorized evidence is retrievable without repeated full-prompt copies."""
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from gantry.bot_execution import _input
from gantry.crew_runtime import _execute
from gantry.model import canonical, digest, Fault
import test_bot_development as fixtures


class BotBoundedContextTests(unittest.TestCase):
    def setUp(self):
        self.c = fixtures.BotDevelopmentTests(); self.c.setUp(); self.addCleanup(self.c.tearDown)
        self.task = self.c.task('designer', dependencies=['mechanical.txt'])
        self.full = self.c.clients['designer'].call('get_bot_task', {'task_id': self.task['id']})
        self.workspace = self.c.root/'bounded'/'workspace'; self.workspace.mkdir(parents=True)
        for name in ('mechanical.txt', 'control.txt'): (self.workspace/name).write_text('1')

    def test_large_optional_collections_are_bounded_and_explicitly_retrievable(self):
        full = self.full
        full['memory'] = {'items': [dict(id=f'memory-{i}', observation='evidence '*700,
            applicability='Only the recorded state', limitations=['Not physical proof'], paths=[], input_hashes={}) for i in range(100)]}
        full['task']['reports'] = [{'attempt': i, 'report': {'summary': 'old report '*500}} for i in range(70)]
        full['messages'] = [{'id': 'active-question', 'blocking': True, 'status': 'open', 'question': 'Unresolved authority condition'}]
        full['consultations'] = [{'id': 'pending-consultation', 'blocking': True, 'status': 'open', 'question': 'unresolved '*1000}]
        full['issues'] = [{'id': 'open-issue', 'status': 'open', 'completion': ['Unmet condition '*1000]}]
        expected_task = {k:v for k,v in full['task'].items() if k != 'reports'}
        result = _input(full, self.workspace)
        self.assertLess(len(canonical(result).encode()), 180000)
        self.assertEqual({k:v for k,v in result['task'].items() if k != 'reports'}, expected_task)
        self.assertEqual(result['messages'], full['messages'])
        self.assertEqual(result['consultations'], full['consultations'])
        self.assertEqual(result['issues'], full['issues'])
        self.assertEqual(result['project'], full['project'])
        self.assertEqual(result['development']['state']['context'], full['development']['state']['context'])
        summary = result['context_capture']['collections']['/memory/items']
        self.assertEqual(summary['total_count'], 100)
        self.assertGreater(summary['omitted_count'], 0)
        self.assertEqual(summary['sha256'], digest(full['memory']['items']))
        self.assertEqual(summary['source_indices'], list(range(len(result['memory']['items']))))
        saved = json.loads(Path(result['full_context']['path']).read_text())
        self.assertEqual(saved, full)
        self.assertEqual(result['full_context']['sha256'], digest(saved))
        # The established context action still retrieves omitted authorized evidence.
        index = len(result['memory']['items'])
        self.assertEqual(summary['omitted_records'][0]['id'], full['memory']['items'][index]['id'])
        self.assertEqual(summary['omitted_records'][0]['sha256'], digest(full['memory']['items'][index]))
        fetched = _execute(self.c.clients['designer'], full, {}, {}, 'context',
            {'pointer': f'/memory/items/{index}', 'limit': 30}, self.workspace, self.workspace.parent, 'read-omitted')
        self.assertEqual(fetched['value']['id'], full['memory']['items'][index]['id'])
        self.assertEqual(fetched['value']['observation'], full['memory']['items'][index]['observation'])

    def test_preview_budget_accounts_for_unicode_and_json_escaping(self):
        for index in range(20):
            name = f'file-{index:02}.txt'; text = '😀"\\\n'*1500
            (self.workspace/name).write_text(text)
            raw = text.encode(); self.full['development']['manifest'][name] = {'size': len(raw), 'hash': hashlib.sha256(raw).hexdigest()}
        result = _input(self.full, self.workspace)
        self.assertLessEqual(len(canonical(result['files']).encode()), 49152)
        self.assertEqual(next(iter(result['files'])), 'mechanical.txt')
        self.assertGreater(result['capture']['omitted_file_count'], 0)

    def test_snapshot_does_not_change_when_a_later_context_is_built(self):
        first = _input(self.full, self.workspace); original_path = Path(first['full_context']['path'])
        original = original_path.read_bytes()
        later = json.loads(json.dumps(self.full)); later['seq'] = later.get('seq', 0) + 1
        second = _input(later, self.workspace)
        self.assertNotEqual(first['full_context']['path'], second['full_context']['path'])
        self.assertEqual(original_path.read_bytes(), original)
        self.assertEqual(digest(json.loads(original)), first['full_context']['sha256'])

    def test_completed_child_history_is_previewed_without_dropping_active_contracts_or_unknowns(self):
        completed=[]
        for i in range(12):
            completed.append({'id':f'child-{i}','status':'completed','completion':['Original acceptance'],
                'output_state':f'output-{i}','reports':[{'attempt':j,'state_id':f'output-{i}',
                'design_assessment':{'history':'x'*20000},'report':{'status':'completed',
                'summary':'Observed result '*200,'rationale':'Evidence '*1000,
                'unverified':['Physical behavior remains unknown'],'followups':[{'id':'future'}]}} for j in range(3)]})
        active={'id':'active','status':'waiting','completion':['Do not omit this condition'],
                'reports':[{'report':{'summary':'Active details','unverified':['Blocking dependency']}}]}
        self.full['children']=completed+[active]
        result=_input(self.full,self.workspace)
        self.assertLess(len(canonical(result).encode()),150000)
        self.assertEqual(result['children'][-1],active)
        for child,original in zip(result['children'][:-1],completed):
            self.assertEqual(child['completion'],original['completion'])
            self.assertEqual(child['output_state'],original['output_state'])
            self.assertEqual(child['reports'][0]['report']['unverified'],['Physical behavior remains unknown'])
            self.assertEqual(child['report_count'],3)
            self.assertEqual(child['reports_detail_reference']['sha256'],digest(original['reports']))
            self.assertTrue(child['reports_detail_reference']['omitted_details'])
        self.assertEqual(json.loads(Path(result['full_context']['path']).read_text()),self.full)

    def test_oversize_essential_contract_is_not_silently_truncated(self):
        self.full['task']['completion'] = ['Mandatory condition ' + 'x'*450000]
        expected = list(self.full['task']['completion'])
        with self.assertRaises(Fault) as caught: _input(self.full, self.workspace)
        self.assertEqual(caught.exception.code, 'context_limit')
        self.assertEqual(self.full['task']['completion'], expected)

    def test_optional_file_previews_yield_to_aggregate_contract_budget(self):
        self.full['task']['completion'] = ['Required: ' + 'x' * 360000]
        text = 'e' * 40000
        (self.workspace/'evidence.txt').write_text(text)
        self.full['development']['manifest']['evidence.txt'] = {
            'size': len(text), 'hash': hashlib.sha256(text.encode()).hexdigest()}
        result = _input(self.full, self.workspace)
        self.assertLessEqual(len(canonical(result).encode()), 400000)
        self.assertEqual(result['task']['completion'], self.full['task']['completion'])
        self.assertNotIn('evidence.txt', result['files'])
        self.assertIn('evidence.txt', result['capture']['omitted_file_bodies'])
        self.assertGreater(result['context_capture']['budget_trimmed']['file_previews'], 0)
        self.assertEqual(json.loads(Path(result['full_context']['path']).read_text()), self.full)
        self.assertEqual((self.workspace/'evidence.txt').read_text(), text)

    def test_aggregate_budget_omits_oldest_optional_observations_not_authority(self):
        self.full['task']['completion'] = ['Required: ' + 'x' * 345000]
        old = {'items': [{'id': str(i), 'text': 'a' * 11000} for i in range(4)], 'coverage': {}}
        reads = {'items': [{'id': str(i), 'text': 'b' * 8000} for i in range(3)], 'coverage': {}}
        with patch('gantry.bot_observations.recent_context', return_value=old), \
             patch('gantry.bot_observations.recent_reads', return_value=reads):
            result = _input(self.full, self.workspace)
        self.assertLessEqual(len(canonical(result).encode()), 400000)
        self.assertEqual(result['task']['completion'], self.full['task']['completion'])
        retained = result['context_observations']['items']
        self.assertTrue(retained)
        self.assertEqual(retained[-1]['id'], '3')
        omitted = result['context_observations']['coverage']['omitted_by_total_budget']
        self.assertEqual(len(retained) + omitted, 4)
        self.assertGreater(omitted, 0)
