import copy
import unittest
from gantry.engineering_proposals import bind_plan, candidate_context
from gantry.model import Fault
from gantry.mentor_daemon import process_job
from test_mentor_jobs import MentorJobsTests


def plan(state):
    return {'components':[{'id':'tank','role':'water_storage','assembly':'fluid','paths':['input.txt'],
                          'rationale':'Supplied design describes a tank','evidence':[state]}],
            'checks':[{'id':'removal','scope':'service','components':['tank'],'paths':['input.txt'],
                       'required':True,'method':'Sweep tank extraction path against retained parts',
                       'acceptance':'No interference over the declared withdrawal path',
                       'rationale':'Placement alone does not establish removability','evidence':[state],'finding_id':'f1'}],
            'limitations':['Geometry not measured; fixture inference']}


class ProposalTests(unittest.TestCase):
    def setUp(self):
        self.manifest={'input.txt':{'hash':'a'*64}}
        self.context={'environment':{}}
    def bind(self, p=None):
        return bind_plan(p or plan('state'),self.context,self.manifest,'review','state',{'f1'},lambda refs:None)
    def test_core_binds_and_never_copies_claim_of_success(self):
        bound=self.bind();self.assertEqual(bound['components'][0]['inputs'],{'input.txt':'a'*64})
        updated=candidate_context(self.context,bound,{'input.txt':{'hash':'b'*64}})
        check=updated['environment']['engineering']['checks'][0]
        self.assertEqual(check['status'],'unverified')
        self.assertEqual(check['evidence'],{})
        self.assertEqual(check['proposal_inputs'],{'input.txt':'a'*64})
        self.assertEqual(check['inputs'],{'input.txt':'b'*64})
        self.assertEqual(check['source_state'],'state')
        self.assertEqual(self.context,{'environment':{}})
    def test_missing_sources_unknown_components_and_unlinked_findings_rejected(self):
        for field,value in [('paths',['absent.step']),('components',['absent']),('finding_id','absent')]:
            p=plan('state');p['checks'][0][field]=value
            with self.subTest(field=field),self.assertRaises(Fault):self.bind(p)
    def test_no_overwrite_of_existing_check_or_role(self):
        self.context['environment']['engineering']={'version':1,'components':[{'id':'tank'}],'checks':[]}
        with self.assertRaises(Fault):self.bind()
    def test_component_inputs_cannot_be_omitted_from_check(self):
        p=plan('state');p['checks'][0]['paths']=['condition.txt']
        self.manifest['condition.txt']={'hash':'b'*64}
        check=self.bind(p)['checks'][0]
        self.assertEqual(set(check['inputs']),{'input.txt','condition.txt'})

    def test_removed_file_cannot_be_silently_rebound(self):
        with self.assertRaises(Fault):candidate_context(self.context,self.bind(),{})


class ProposalLoopTests(MentorJobsTests):
    def test_plan_flows_through_real_checkpoint_and_re_review(self):
        first=self.setup_jobs()
        import sys
        from gantry.model import digest
        recipe={'argv':[sys.executable,'-c','from pathlib import Path; assert Path("input.txt").read_text()=="corrected"; print("source verification passed")'], 'timeout_seconds':10}
        d=self.detail()['session']
        self.call('configure_development',{'session_id':d['id'],'version':d['version'],'reason':'Delegate fixture source check',
            **{**self.policy(),'actors':['admin','mentor'],'write_scope':['input.txt'],'recipes':{'source':digest(recipe)}}})
        def infer(ctx,schema,directory):
            receipt=self.inference(ctx,schema,directory)
            if ctx['task']=='coordinator':
                out=receipt['output']
                if not ctx['review']['engineering']['configured']:
                    out['engineering_plan']=plan(ctx['review']['state_id'])
                else:
                    self.assertEqual(ctx['review']['engineering']['checks'][0]['effective_status'],'unverified')
                    out.update(verdict='insufficient_evidence',findings=[],unverified=['removal test has not run'])
            if ctx['task']=='developer':
                self.assertEqual(ctx['review']['engineering_proposal']['checks'][0]['method'],
                                 'Sweep tank extraction path against retained parts')
            return receipt
        def run(kind):
            job=self.job(kind)
            return process_job(self.client if kind=='developer' else self.mentor,job['id'],self.root/'plan-loop',infer,verification=recipe if kind=='developer' else None)
        run('specialist');run('coordinator');result=run('developer')
        from pathlib import Path
        saved=__import__('json').loads((self.root/'plan-loop'/digest(result['job_id'])/'verification.json').read_text())
        self.assertEqual(saved['exit_code'],0)
        self.assertIn('source verification passed',saved['stdout'])
        candidate=self.call('get_development_state',{'state_id':result['result']['candidate']})
        check=candidate['state']['context']['environment']['engineering']['checks'][0]
        self.assertEqual(check['status'],'unverified');self.assertEqual(check['provenance'],'mentor_inferred')
        self.assertEqual(check['source_submission'],first['id'])
        self.assertEqual(check['inputs']['input.txt'],candidate['manifest']['input.txt']['hash'])
        self.assertEqual(candidate['status']['adoption'],'unadopted')
        run('specialist');run('coordinator');run('reflection')
        final=self.call('get_change_review',{'submission_id':result['result']['resubmission_id']})
        self.assertEqual(final['output']['verdict'],'insufficient_evidence')
        self.assertTrue(self.call('replay')['matched'])

    def test_model_cannot_mark_proposed_check_passed(self):
        self.setup_jobs();self.run_job('specialist');job=self.job('coordinator')
        def bad(ctx,schema,directory):
            receipt=self.inference(ctx,schema,directory)
            receipt['output']['engineering_plan']=plan(ctx['review']['state_id'])
            receipt['output']['engineering_plan']['checks'][0]['status']='pass'
            return receipt
        self.fault('invalid_input',lambda:process_job(self.mentor,job['id'],self.root/'bad-plan',bad))
