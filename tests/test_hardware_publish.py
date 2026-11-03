import copy
import hashlib
import json
from pathlib import Path
from test_continuity import ContinuityTests
from test_physical_evidence import PhysicalEvidenceTests

class HardwarePublishTests(ContinuityTests):
    def prepare(self):
        f=PhysicalEvidenceTests();f.setUp(); self.check=f.check
        self.plan={'version':1,'components':[{'id':'bracket','role':'load_support','assembly':'frame',
            'paths':['bracket.step','material.json']}],'checks':[self.check]}
        files={'input.txt':'initial','bracket.step':'original','material.json':'steel',
               'physical-plan.json':json.dumps(self.plan)}
        self.snapshot=self.artifact(files)
        self.session=self.connect();base=self.initialize()
        change=self.begin(base,['bracket.step','stress.json'])
        root=self.root/'candidate';root.mkdir()
        for p,v in files.items():(root/p).write_text(v)
        (root/'bracket.step').write_text('changed')
        f.report['inputs']={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in self.check['inputs']}
        (root/'stress.json').write_text(json.dumps(f.report))
        return base,change,root
    def test_checkpoint_evidence_reaches_review_and_invalidates(self):
        from gantry.hardware import publish
        from gantry.engineering_context import assess
        base,change,root=self.prepare()
        cp=publish(self.client,base['id'],change['id'],change['version'],root,'physical-plan.json','physical-1')
        view=self.call('get_development_state',{'state_id':cp['state']['id']})
        engineering=view['engineering']
        self.assertEqual(engineering['checks'][0]['effective_status'],'pass')
        self.assertEqual(view['status']['adoption'],'unadopted')
        self.assertEqual(view['status']['verification'],'unverified')
        self.assertEqual(engineering['checks'][0]['physical_result']['comparisons'][0]['observation']['value'],40)
        manifest=copy.deepcopy(view['manifest']);manifest['bracket.step']['hash']='f'*64
        self.assertEqual(assess(cp['state']['context'],manifest)['checks'][0]['effective_status'],'unknown')
        self.assertTrue(self.call('replay')['matched'])
    def test_changed_acceptance_is_not_silently_used(self):
        from gantry.hardware import publish
        base,change,root=self.prepare()
        self.plan['checks'][0]['criteria'][0]['max']=1000
        (root/'physical-plan.json').write_text(json.dumps(self.plan))
        self.fault('stale_basis',lambda:publish(self.client,base['id'],change['id'],change['version'],root,'physical-plan.json','bad'))
    def test_missing_report_is_saved_as_unknown(self):
        from gantry.hardware import publish
        base,change,root=self.prepare();(root/'stress.json').unlink()
        cp=publish(self.client,base['id'],change['id'],change['version'],root,'physical-plan.json','missing')
        self.assertEqual(cp['state']['context']['environment']['engineering']['checks'][0]['status'],'unknown')

    def test_malformed_report_is_retained_but_cannot_pass(self):
        from gantry.hardware import publish
        base,change,root=self.prepare();(root/'stress.json').write_text('{broken')
        cp=publish(self.client,base['id'],change['id'],change['version'],root,'physical-plan.json','malformed')
        self.assertEqual(cp['state']['context']['environment']['engineering']['checks'][0]['status'],'unknown')

    def test_successful_retry_clears_only_adapter_owned_unfinished_item(self):
        from gantry.hardware import publish
        base,change,root=self.prepare()
        original=(root/'stress.json').read_text(); r=json.loads(original); r['status']='error'
        (root/'stress.json').write_text(json.dumps(r))
        first=publish(self.client,base['id'],change['id'],change['version'],root,'physical-plan.json','failed')
        self.assertIn('physical-check:load',first['state']['unfinished'])
        (root/'stress.json').write_text(original)
        second=publish(self.client,first['state']['id'],change['id'],first['change']['version'],root,'physical-plan.json','retried')
        self.assertNotIn('physical-check:load',second['state']['unfinished'])
        self.assertEqual(second['state']['unfinished'],base['unfinished'])

import test_change_review as review_fixtures
class HardwareReviewTests(review_fixtures.ChangeReviewTests):
    def test_imported_failed_solver_reaches_mentor_and_blocks_ok(self):
        from gantry.hardware import publish
        self.setup_review()
        check={'id':'physical','scope':'structural','components':['part'],'required':True,
            'inputs':['input.txt'],'report':'stress.json','conditions':{'load_N':100},
            'evaluator':{'name':'solver','version':'1'},'environment':{'mesh':'m1'},
            'criteria':[{'metric':'stress','unit':'MPa','max':50}]}
        plan={'version':1,'components':[{'id':'part','role':'support','assembly':'robot','paths':['input.txt']}],'checks':[check]}
        change=self.begin(self.cp['state'],['physical-plan.json','stress.json'])
        files={'input.txt':'modified','physical-plan.json':json.dumps(plan)}
        prepared=self.checkpoint(change,files)
        root=self.root/'hardware';root.mkdir()
        for p,v in files.items():(root/p).write_text(v)
        (root/'stress.json').write_text(json.dumps({'status':'error'}))
        work=self.begin(prepared['state'],['stress.json'])
        cp=publish(self.client,prepared['state']['id'],work['id'],work['version'],root,'physical-plan.json','review-evidence')
        submission=self.submit(cp['change']);self.report(submission);lease=self.claim(submission)
        view=self.mentor.call('get_change_review',{'submission_id':submission['id']})
        self.assertEqual(view['engineering']['review_gaps'],['physical'])
        self.assertIn('execution_not_completed',view['engineering']['checks'][0]['physical_result']['reasons'])
        self.fault('review_pending',lambda:self.complete(submission,lease,'ok'))
        self.complete(submission,lease,'changes_requested')
