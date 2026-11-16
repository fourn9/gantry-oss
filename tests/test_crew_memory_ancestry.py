"""Synthetic audit regression tests; no model or private robot data."""
import base64
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO=Path(__file__).parents[1]
sys.path.insert(0,str(REPO))
MODULE=REPO/'examples/crew-memory-study/run.py'
spec=importlib.util.spec_from_file_location('audited_runner',MODULE);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class AncestorAuditTests(unittest.TestCase):
    def fixture(self,relationship='ancestor'):
        content={'design.json':b'{"x":0}','verify.py':b'pass\n','notes.md':b'Current note'}
        case={'manifest':{'design.json':m.sha(content['design.json']),'verify.py':m.sha(content['verify.py'])},
            'roles':{'lead':{'write_scope':['design.json','notes.md','report.json']}},'tools':{'verify':{'argv':[sys.executable,'-B','verify.py'],'timeout_seconds':5}},
            'final_verifier':'verify','tool_evidence':{'verify':{'plan_path':'plan.json'}}}
        check={'id':'x','required':True,'report':'report.json','inputs':['design.json'],
            'conditions':{'case':'fixed'},'evaluator':{'name':'test','version':'1'},'environment':{'runtime':'test'},
            'criteria':[{'metric':'failures','unit':'count','max':0}]}
        report={k:check[k] for k in ['conditions','evaluator','environment']}
        report.update(status='completed',inputs={'design.json':m.sha(content['design.json'])},limitations=[],measurements={'failures':{'value':0,'unit':'count'}})
        content.update({'report.json':json.dumps(report).encode(),'plan.json':json.dumps({'checks':[check]}).encode()})
        execution={'input_state':'basis','action_key':'real','exit_code':0,'output_artifact':'receipt'}
        raw={'id':'x','inputs':report['inputs'],'evidence':{'report.json':m.sha(content['report.json'])},'physical_result':{'status':'pass','execution':execution}}
        pub_id='final' if relationship=='self' else 'published'
        parents=['published'] if relationship=='ancestor' else ['other']
        detail={'state':{'id':'final','session_id':'session','parents':parents,'snapshot':'saved','context':{'environment':{'engineering':{'checks':[raw]}}}},
            'engineering':{'checks':[{**raw,'effective_status':'pass'}]}}
        publication_state={'state':{'id':pub_id,'session_id':'session','parents':[],'context':{'environment':{'engineering':{'checks':[json.loads(json.dumps(raw))]}}}}}
        states={'final':detail,'published':publication_state,'other':{'state':{'id':'other','session_id':'session','parents':[]}}}
        if relationship=='self':states['final']=detail
        action={'kind':'tool','input_state':'basis','details':{'arguments':'{"name":"verify"}','result':{'exit_code':0,'output_artifact':'receipt'}}}
        publication={'kind':'tool_evidence','details':{'result':{'exit_code':0,'refreshed_paths':['report.json'],
            'evidence_publication':{'state_id':pub_id,'checks':[json.loads(json.dumps(raw))]}}}}
        return case,content,states,[action,publication]
    def audit(self,fixture,audit_mutation=False):
        case,content,states,actions=fixture
        class Owner:
            def call(self,name,args):return states[args['state_id']]
        def restore(client,snapshot,path):
            path.mkdir()
            for name,value in content.items():(path/name).write_bytes(value)
        def execute(tool,path,*args):
            if audit_mutation:(path/'design.json').write_text('{"x":1}')
            return {'exit_code':0,'output':''}
        with tempfile.TemporaryDirectory() as d,patch.object(m,'restore_files',restore),patch.object(m,'execute',execute):
            return m.final_audit(Owner(),{'task':{'state_id':'basis','output_state':'final'}},{'t':{'actions':actions}},case,Path(d))
    def test_valid_ancestor_with_only_unrelated_notes_change(self):
        self.assertTrue(self.audit(self.fixture('ancestor'))['accepted'])
    def test_self_publication_still_accepted(self):
        self.assertTrue(self.audit(self.fixture('self'))['accepted'])
    def test_identical_but_unrelated_publication_rejected(self):
        self.assertFalse(self.audit(self.fixture('unrelated'))['accepted'])
    def test_cross_session_parent_rejected(self):
        f=self.fixture();f[2]['published']['state']['session_id']='other-session'
        self.assertFalse(self.audit(f)['accepted'])
    def test_changed_evaluated_input_rejected(self):
        f=self.fixture();f[1]['design.json']=b'{"x":2}'
        self.assertFalse(self.audit(f)['accepted'])
    def test_changed_evidence_rejected(self):
        f=self.fixture();f[1]['report.json']+=b'\n'
        self.assertFalse(self.audit(f)['accepted'])
    def test_different_raw_check_rejected(self):
        f=self.fixture();f[3][1]['details']['result']['evidence_publication']['checks'][0]['extra']='different'
        self.assertFalse(self.audit(f)['accepted'])
    def test_missing_actual_tool_receipt_rejected(self):
        f=self.fixture();f[3].pop(0)
        self.assertFalse(self.audit(f)['accepted'])
    def test_readonly_audit_cannot_repair_input(self):
        self.assertFalse(self.audit(self.fixture(),audit_mutation=True)['accepted'])
    def test_cycle_without_published_ancestor_rejected(self):
        f=self.fixture('unrelated');f[2]['other']['state']['parents']=['final']
        self.assertFalse(self.audit(f)['accepted'])

if __name__=='__main__':unittest.main()
