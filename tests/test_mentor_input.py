import copy,json,tempfile,unittest
from pathlib import Path
from gantry.mentor_input import compact_review, collect_files

class MentorInputTests(unittest.TestCase):
    def test_large_cad_duplicate_diffs_fit_without_losing_review_contract(self):
        cad={'path':'candidate/shaft.step','before':None,'after':'sha-cad','text':'ISO-10303-21;\n' * 25000}
        code={'path':'candidate/control.py','before':'old','after':'new','text':'-limit=1\n+limit=2'}
        review={'state_id':'state','context_fingerprint':'pinned','acceptance':['Do not change travel'],
                'specialists':{'electrical':{'unresolved':['Power loss']}},'pr_diff':[cad,code],
                'development':{'diffs':[{**cad,'kind':'added'},{**code,'kind':'modified'}],'state':{'snapshot':'artifact'}},'question':'Compare designs'}
        original=copy.deepcopy(review)
        self.assertGreater(len(json.dumps(review)),500000)
        compact=compact_review(review)
        self.assertLess(len(json.dumps(compact)),20000)
        self.assertEqual(review,original)
        self.assertEqual(compact['acceptance'],review['acceptance'])
        self.assertEqual(compact['specialists'],review['specialists'])
        self.assertEqual(compact['pr_diff'][1]['text'],code['text'])
        self.assertEqual(compact['pr_diff'][0]['after'],'sha-cad')
        self.assertEqual(compact['pr_diff'][0]['text_omitted']['reason'],'cad_serialization')
        self.assertEqual(compact['development']['diffs'][1]['text_omitted']['reason'],'duplicate_pr_diff')

    def test_nonduplicate_code_diff_is_kept(self):
        review={'pr_diff':[], 'development':{'diffs':[{'path':'run.py','text':'important change'}]}}
        self.assertEqual(compact_review(review)['development']['diffs'][0]['text'],'important change')

    def test_file_selection_does_not_spend_budget_on_cad_or_hide_omissions(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'a.step').write_text('CAD'*2000);(p/'b.py').write_text('x'*12);(p/'c.json').write_text('{}')
            files,coverage=collect_files(p,max_total=10)
            self.assertEqual(files,{'c.json':'{}'})
            reasons={r['path']:r['reason'] for r in coverage['omitted']}
            self.assertEqual(reasons['a.step'],'cad_serialization')
            self.assertEqual(reasons['b.py'],'total_text_budget')
            self.assertEqual(coverage['omitted_count'],2)

    def test_inventory_and_long_history_do_not_displace_review_contract(self):
        review={'state_id':'fixed','question':'Read current.json','acceptance':['No hidden pass'],
                'specialists':{'mechanical':{'unresolved':['Clamp strength']}},
                'pr_diff':[{'path':f'old/{i}.json','text':'x'*14000} for i in range(30)] + [{'path':'current.json','text':'Current evidence'}],
                'development':{'manifest':{str(i):'x'*800 for i in range(400)},
                               'state':{'snapshot':'immutable','components':['x'*100 for _ in range(200)]}}}
        original=copy.deepcopy(review);result=compact_review(review)
        self.assertLess(len(json.dumps(result)),30000)
        self.assertEqual(review,original)
        self.assertEqual(result['specialists'],review['specialists'])
        self.assertEqual(result['acceptance'],review['acceptance'])
        self.assertEqual(result['pr_diff'][-1]['text'],'Current evidence')
        self.assertEqual(result['development']['state']['snapshot'],'immutable')
        self.assertEqual(result['development']['manifest_omitted']['count'],400)
        self.assertIn('sha256',result['pr_diff'][0]['text_omitted'])

    def test_question_named_file_is_selected_before_historical_files(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'a-old.txt').write_text('old'*10);(p/'z-current.json').write_text('{}')
            files,coverage=collect_files(p,max_total=30,priority_text='Read z-current.json')
            self.assertEqual(files,{'z-current.json':'{}'})
            self.assertEqual(coverage['omitted_count'],1)
