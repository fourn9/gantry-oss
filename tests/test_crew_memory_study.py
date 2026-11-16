import base64,importlib.util,json,sys,tempfile,unittest
from unittest.mock import patch
from pathlib import Path

spec=importlib.util.spec_from_file_location('memory_study',Path(__file__).parents[1]/'examples/crew-memory-study/run.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class MemoryStudyTests(unittest.TestCase):
    def fixture(self):
        data={'design.json':b'{"x":0}','verify.py':b'print("fixture")\n'}
        return {'name':'Test only','files':{k:base64.b64encode(v).decode() for k,v in data.items()},
            'manifest':{k:m.sha(v) for k,v in data.items()},'goal':'Inspect saved fixture','acceptance':['Report truthful evidence'],
            'roles':{b:{'responsibilities':['Inspect'], 'onboarding':[], 'write_scope':['design.json']} for b in m.BOTS},
            'tools':{'verify':{'argv':[sys.executable,'-B','verify.py'],'timeout_seconds':5}},
            'dependencies':list(data),'experiences':[{'bot_id':'lead','observation':'Prior observation','applicability':'Recheck changed inputs','limitations':['Prior data, not current proof'],'source':'prior receipt hash'}],
            'final_verifier':'verify'}
    def test_loader_rejects_tampered_or_unsafe_paths(self):
        from gantry.model import Fault
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'case.json';case=self.fixture();p.write_text(json.dumps(case));self.assertEqual(m.load_case(p)['manifest'],case['manifest'])
            case['manifest']['design.json']='x';p.write_text(json.dumps(case))
            with self.assertRaises(Fault):m.load_case(p)
            case=self.fixture();case['files']['../bad']=case['files'].pop('design.json');p.write_text(json.dumps(case))
            with self.assertRaises(Fault):m.load_case(p)
    def test_same_runtime_and_files_only_imported_memories_differ(self):
        from gantry.service import Service
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);case=self.fixture();states=[];configs=[];memories=[]
            for condition in ['cold','recall']:
                target=root/condition;target.mkdir()
                owner,clients,cfg,task,seed=m.setup(target,case,condition,'test-model',60)
                view=owner.call('get_bot_task',{'task_id':task['id']})
                states.append({k:v['hash'] for k,v in view['development']['manifest'].items()});configs.append(cfg)
                memories.append(seed)
                tasks=owner.call('list_bot_tasks',{'session_id':task['session_id'],'limit':100})['items']
                self.assertEqual(sum(t['status']=='cancelled' for t in tasks),3)
                self.assertEqual(sum(t['status']=='pending' for t in tasks),1)
            self.assertEqual(states[0],states[1]);self.assertEqual(configs[0],configs[1])
            self.assertEqual(memories[0],[]);self.assertEqual(len(memories[1]),1)
    def test_identity_handles_learning_and_reflection_contexts(self):
        x=m.identity({'operation':'reflect_on_experience','packet':{'bot_id':'lead','task_id':'t','attempt':2}},'lead')
        self.assertEqual(x['task_id'],'t');self.assertEqual(x['operation'],'reflect_on_experience')
        self.assertEqual(m.category('action',{'action':'finish','arguments_json':'{"assignments":[{}]}'}),'consultation')
        self.assertEqual(m.category('reflect_on_experience',{}),'judgment')
    def test_engineering_result_cannot_substitute_for_actual_collaboration(self):
        case=self.fixture();case['required_worker_bots']=['mechanical','control']
        views={'lead':{'task':{'bot_id':'lead','status':'completed'}}};records={'lead':{'actions':[]}}
        self.assertFalse(m.workflow_check(views,records,case)['accepted'])
        for bot in ['mechanical','control']:
            views[bot]={'task':{'bot_id':bot,'status':'completed','parent_task_id':'lead'},'own_change':{'id':bot+'-change'}}
            records[bot]={'actions':[{'id':'edit-'+bot,'kind':'edit','details':{'result':{},'workspace_before':'a','workspace_after':'b'}}]}
            records['lead']['actions'].append({'kind':'inspect','details':{'arguments':json.dumps({'task_id':bot}),'result':{}}})
        self.assertFalse(m.workflow_check(views,records,case)['accepted'])
        records['lead']['actions'].append({'kind':'integrate','details':{'arguments':json.dumps({'changes':[{'id':b+'-change'} for b in ['mechanical','control']]}),'result':{'integrated':True}}})
        self.assertTrue(m.workflow_check(views,records,case)['accepted'])
        records['control']['actions'][0]['details']['result']={'error':'scope_denied'}
        self.assertFalse(m.workflow_check(views,records,case)['accepted'])
    def test_runtime_phase_join_excludes_duplicate_model_span(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);step=root/'journals/b/actions/0';timing=step/'timing';timing.mkdir(parents=True)
            (step/'input.json').write_text(json.dumps({'task':{'id':'t','bot_id':'mechanical','attempt':1},'round':0}))
            (step/'action.json').write_text(json.dumps({'receipt':{'output':{'action':'tool'}}}))
            for phase in ['model','action','record']:
                (timing/(phase+'.json')).write_text(json.dumps({'phase':phase,'started_at_ns':1,'finished_at_ns':2,'monotonic_seconds':1e-9}))
            rows=m.runtime_spans(root)
            self.assertEqual({r['phase'] for r in rows},{'action','record'})
            self.assertEqual({r['bot_id'] for r in rows},{'mechanical'})
    def test_final_audit_requires_actual_fresh_receipts_and_unchanged_inputs(self):
        case=self.fixture();case['tool_evidence']={'verify':{'plan_path':'plan.json'}}
        check={'id':'x','required':True,'report':'report.json','inputs':['design.json'],
            'conditions':{'case':'fixed'},'evaluator':{'name':'test','version':'1'},'environment':{'runtime':'test'},
            'criteria':[{'metric':'failures','unit':'count','max':0}]}
        report={k:check[k] for k in ['conditions','evaluator','environment']}
        report.update(status='completed',inputs={'design.json':case['manifest']['design.json']},limitations=[],measurements={'failures':{'value':0,'unit':'count'}})
        content={k:base64.b64decode(v) for k,v in case['files'].items()}
        content.update({'report.json':json.dumps(report).encode(),'plan.json':json.dumps({'checks':[check]}).encode()})
        execution={'input_state':'basis','action_key':'real','exit_code':0,'output_artifact':'receipt'}
        raw={'id':'x','inputs':report['inputs'],'evidence':{'report.json':m.sha(content['report.json'])},'physical_result':{'status':'pass','execution':execution}}
        detail={'state':{'id':'final','snapshot':'saved','context':{'environment':{'engineering':{'checks':[raw]}}}},'engineering':{'checks':[{**raw,'effective_status':'pass'}]}}
        class Owner:
            def call(self,*a):return detail
        def restore(client,snapshot,path):
            path.mkdir()
            for name,value in content.items():(path/name).write_bytes(value)
        action={'kind':'tool','input_state':'basis','details':{'arguments':'{"name":"verify"}','result':{'exit_code':0,'output_artifact':'receipt'}}}
        publication={'kind':'tool_evidence','details':{'result':{'exit_code':0,'refreshed_paths':['report.json'],'evidence_publication':{'state_id':'final','checks':[raw]}}}}
        with tempfile.TemporaryDirectory() as d,patch.object(m,'restore_files',restore):
            for index,actions in enumerate([[],[action,publication],[action,publication]]):
                root=Path(d)/str(index);root.mkdir()
                def execute(tool,path,*args):
                    if index==2:(path/'design.json').write_text('{"x":999}')
                    return {'exit_code':0,'output':''}
                with patch.object(m,'execute',execute):
                    result=m.final_audit(Owner(),{'task':{'state_id':'basis','output_state':'final'}},{'t':{'actions':actions}},case,root)
                self.assertEqual(result['accepted'],index==1)
    def test_provider_failure_stops_without_parent_recovery_or_retry(self):
        from gantry.model import Fault
        calls=[]
        def fail(*args,**kwargs):
            calls.append(1);raise Fault('subscription_rate_limited','Fixture exhaustion; no provider invoked')
        with tempfile.TemporaryDirectory() as d,patch.object(m,'execute',return_value={'exit_code':0,'output':''}):
            result=m.run(self.fixture(),Path(d),'cold','test-model',60,infer_fn=fail)
            self.assertEqual(len(calls),1);self.assertFalse(result['accepted'])
            self.assertEqual(result['parent_semantic_interventions'],[])
            self.assertTrue(result['errors']);self.assertTrue(result['verify']['valid']);self.assertTrue(result['replay']['matched'])
            self.assertTrue((Path(d)/'normalized-spans.json').exists())
