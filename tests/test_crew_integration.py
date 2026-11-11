import hashlib
import json
import os
import sys
import unittest
from pathlib import Path

import test_bot_development as fixtures
from gantry.bot_worker import environment_manifest
from gantry.bot_execution import safe_fingerprint
from gantry.model import Fault, digest
from gantry.project_sandbox import backend, runtime_roots
from gantry import crew_runtime

CHECK="from pathlib import Path; import json; values={n:Path(n).read_text() for n in ['mechanical.txt','control.txt']}; print(json.dumps(values)); assert set(values.values())=={'2'}, values"

def action(kind,args):
    return {'output':{'action':kind,'arguments_json':json.dumps(args),'rationale':'Explicit validation fixture, not autonomous reasoning'},'provider':{'kind':'scripted_validation'}}

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.c=fixtures.BotDevelopmentTests();self.c.setUp();self.addCleanup(self.c.tearDown)
        self.parent=self.c.task(kind='integrate',completion=['Integrate both changes then verify exact integrated content'])
        def seed(*_):return {'output':self.c.answer(status='waiting',assignments=[self.c.assignment('designer'),self.c.assignment('control')]),'provider':{'kind':'fixture_setup'}}
        with self.c.worker('lead',seed) as w:w.tick()
        for role in ['designer','control']:
            with self.c.worker(role) as w:w.tick()
        view=self.c.owner.call('get_bot_task',{'task_id':self.parent['id']})
        self.refs=[{'id':x['change']['id'],'version':x['change']['version']} for x in view['candidate_changes']]
    def config(self,role,runs_tool=True):
        if runs_tool and backend()=='unavailable': self.skipTest('OS sandbox unavailable')
        c=self.c.configs[role]
        c.update(agent_loop=True,local_tools={'verify':{'argv':[str(Path(sys.executable).resolve()),'-B','-c',CHECK],'timeout_seconds':20}},tool_runtime=runtime_roots(),sandbox=backend())
        self.c.owner.call('configure_bot_runtime',{'bot_id':role,'version':1,'principal_id':role,'enabled':True,'environment':environment_manifest(c)})
    def args(self,ref):
        return {**ref,'state_id':self.c.base['id'],'changes':self.refs,'summary':'Combine specialist outputs'}
    def claimed(self,w,task=None,role='lead'):
        task=task or self.c.owner.call('get_bot_task',{'task_id':self.parent['id']})['task']
        claim=self.c.clients[role].call('claim_bot_task',{'task_id':task['id'],'version':task['version'],'runtime_fence':w.runtime['fence']})
        return {'task_id':task['id'],'fence':claim['task']['fence']}
    def test_action_exists(self):
        self.assertIn('integrate',crew_runtime.SCHEMA['properties']['action']['enum'])
    def test_same_bot_exact_state_and_subsequent_edit(self):
        self.config('lead');seen=[]
        def infer(ctx,*_):
            seen.append(ctx)
            n=len(seen)
            if n==1:return action('integrate',{'state_id':self.c.base['id'],'changes':self.refs,'summary':'Combine specialist outputs'})
            if n==2:
                self.assertEqual({Path(ctx['workspace'],p).read_text() for p in ['mechanical.txt','control.txt']},{'2'})
                self.assertEqual(ctx['task']['status'],'running')
                return action('tool',{'name':'verify'})
            if n==3:
                self.assertEqual(ctx['last_result']['exit_code'],0)
                return action('edit',{'path':'mechanical.txt','content':'3','expected_hash':hashlib.sha256(b'2').hexdigest()})
            return action('finish',self.c.answer(summary='Tested integrated 2/2 then made an unverified follow-up edit'))
        with self.c.worker('lead',infer) as w:r=w.tick()[0]
        self.assertIn('task',r, 'Runtime did not continue: '+str(r))
        self.assertEqual(r['task']['status'],'completed',r)
        merged=seen[1]['development']['state']['id'];final=r['task']['output_state']
        self.assertNotEqual(merged,self.c.base['id']);self.assertNotEqual(final,merged)
        v=self.c.owner.call('get_bot_task',{'task_id':self.parent['id']})
        self.assertEqual(v['own_change']['base_state'],merged)
        tools=[a for a in v['actions'] if a['kind']=='tool']
        self.assertEqual(tools[0]['input_state'],merged)
        self.assertEqual(v['development']['status']['verification'],'unverified')
        self.assertEqual(v['development']['status']['adoption'],'unadopted')
        self.assertTrue(self.c.owner.call('verify')['valid'])
    def test_delegated_verification_returns_to_parent(self):
        self.config('lead');self.config('control');seen=[]
        def lead(ctx,*_):
            seen.append(ctx)
            if len(seen)==1:return action('integrate',{'state_id':self.c.base['id'],'changes':self.refs,'summary':'Combine for peer verification'})
            if len(seen)==2:
                sid=ctx['development']['state']['id']
                return action('finish',self.c.answer(status='waiting',assignments=[self.c.assignment('control',state_id=sid,kind='verify',write_scope=[],title='Verify exact integrated contents')]))
            return action('finish',self.c.answer(summary='Received verification of integrated target; physical behavior unknown'))
        with self.c.worker('lead',lead) as w:r=w.tick()[0]
        self.assertEqual(r['task']['status'],'waiting',r)
        sid=r['task']['output_state']; child=r['task']['children'][-1]
        self.assertEqual(self.c.owner.call('get_bot_task',{'task_id':child})['task']['state_id'],sid)
        rounds=[]
        def verify(ctx,*_):
            rounds.append(ctx)
            return action('tool',{'name':'verify'}) if len(rounds)==1 else action('finish',self.c.answer(summary='Actual sandbox contents agree'))
        with self.c.worker('control',verify) as w:r=w.tick()[0]
        self.assertEqual(r['task']['status'],'completed',r)
        self.assertEqual(rounds[1]['last_result']['exit_code'],0)
        self.assertEqual(rounds[0]['development']['state']['id'],sid)
        self.assertEqual(self.c.owner.call('get_bot_task',{'task_id':self.parent['id']})['task']['status'],'pending')
        with self.c.worker('lead',lead) as w:r=w.tick()[0]
        self.assertEqual(r['task']['status'],'completed',r)
        self.assertEqual(r['task']['output_state'],sid)
    def test_stale_candidate_and_idempotent_integration(self):
        with self.c.worker('lead') as w:
            ref=self.claimed(w);args=self.args(ref);bad=json.loads(json.dumps(args));bad['changes'][0]['version']-=1
            with self.assertRaises(Fault) as e:self.c.clients['lead'].call('integrate_bot_task',bad)
            self.assertEqual(e.exception.code,'stale_basis')
            self.assertNotIn('output_state',self.c.owner.call('get_bot_task',{'task_id':self.parent['id']})['task'])
            first=self.c.clients['lead'].call('integrate_bot_task',args,'stable-request')
            self.assertEqual(first,self.c.clients['lead'].call('integrate_bot_task',args,'stable-request'))
            self.assertEqual(first['task']['status'],'running')
            self.assertEqual(len(first['state']['integrated_changes']),2)

    def test_mid_task_integration_cannot_replace_pinned_constraints(self):
        change=self.c.owner.call('begin_change',{'state_id':self.c.base['id'],'title':'Changed premise',
            'purpose':'Needs new assignment','write_scope':['mechanical.txt'],'dependencies':[],'assignee':'admin'})
        context=json.loads(json.dumps(self.c.base['context']));context['constraints']=['Changed operating conditions']
        row=self.c.owner.call('checkpoint_change',{'change_id':change['id'],'version':change['version'],
            'snapshot':self.c.base['snapshot'],'summary':'Changed constraints','rationale':'Explicit proposal only',
            'context':context,'unfinished':[],'work_status':'working','capture':{'scope':'fixture','missing':[]}})
        shared=self.c.owner.call('share_change',{'change_id':change['id'],'version':row['change']['version']})['change']
        with self.c.worker('lead') as w:
            ref=self.claimed(w);args=self.args(ref);args['changes']=[{'id':shared['id'],'version':shared['version']}]
            with self.assertRaises(Fault) as e:self.c.clients['lead'].call('integrate_bot_task',args)
            self.assertEqual(e.exception.code,'scope_denied')
            self.assertNotIn('output_state',self.c.owner.call('get_bot_task',{'task_id':self.parent['id']})['task'])
            # A failed continuation must roll back integration, including candidate status.
            integrated=self.c.owner.call('integrate_changes',{'state_id':self.c.base['id'],
                'changes':[{'id':shared['id'],'version':shared['version']}],'summary':'Explicitly select changed premises separately'})
            self.assertTrue(integrated['integrated'])
    def test_dirty_workspace_refused(self):
        self.config('lead',runs_tool=False)
        def infer(ctx,*_):
            Path(ctx['workspace'],'mechanical.txt').write_text('unsaved private edit')
            return action('integrate',{'state_id':self.c.base['id'],'changes':self.refs,'summary':'Must not overwrite unsaved edit'})
        with self.c.worker('lead',infer) as w:r=w.tick()[0]
        self.assertEqual(r['status'],'held',r)
        v=self.c.owner.call('get_bot_task',{'task_id':self.parent['id']})
        self.assertNotIn('output_state',v['task'])
        files=list(self.c.root.glob('workers/**/workspace/mechanical.txt'))
        self.assertIn('unsaved private edit',[p.read_text() for p in files])

    def test_waiting_finish_cannot_resume_task_under_changed_constraints(self):
        change=self.c.owner.call('begin_change',{'state_id':self.c.base['id'],'title':'Changed premise',
            'purpose':'Needs separate assignment','write_scope':['mechanical.txt'],'dependencies':[],'assignee':'admin'})
        context=json.loads(json.dumps(self.c.base['context']));context['constraints']=['Different operating conditions']
        row=self.c.owner.call('checkpoint_change',{'change_id':change['id'],'version':change['version'],
            'snapshot':self.c.base['snapshot'],'summary':'Proposed premise change','rationale':'Reassessment required',
            'context':context,'unfinished':[],'work_status':'working','capture':{'scope':'fixture','missing':[]}})
        shared=self.c.owner.call('share_change',{'change_id':change['id'],'version':row['change']['version']})['change']
        with self.c.worker('lead') as w:
            ref=self.claimed(w)
            before=self.c.owner.call('get_bot_task',{'task_id':self.parent['id']})['task']
            report=self.c.answer(status='waiting',assignments=[self.c.assignment('control',kind='verify',write_scope=[])],
                integrate_changes=[{'id':shared['id'],'version':shared['version']}]);report.pop('edits')
            with self.assertRaises(Fault) as error:
                self.c.clients['lead'].call('finish_bot_task',{**ref,'report':report})
            self.assertEqual(error.exception.code,'scope_denied')
            after=self.c.owner.call('get_bot_task',{'task_id':self.parent['id']})['task']
            self.assertEqual(after['children'],before['children'])
            self.assertEqual(after['reports'],before['reports'])
            self.assertNotIn('output_state',after)

    def test_saved_edit_and_missing_integration_authority_refused(self):
        with self.c.worker('designer') as w:
            task=self.c.task('designer');ref=self.claimed(w,task,'designer')
            with self.assertRaises(Fault) as e:self.c.clients['designer'].call('integrate_bot_task',self.args(ref))
            self.assertEqual(e.exception.code,'unauthorized')
        with self.c.worker('lead') as w:
            ref=self.claimed(w)
            self.c.clients['lead'].call('checkpoint_bot_task',{**ref,'snapshot':self.c.artifact({'mechanical.txt':'own saved edit','control.txt':'1'}),'summary':'Own saved edit','rationale':'Keep it','unfinished':[],'capture':{'scope':'fixture','missing':[]}})
            before=self.c.owner.call('get_bot_task',{'task_id':self.parent['id']})['task']['output_state']
            with self.assertRaises(Fault) as e:self.c.clients['lead'].call('integrate_bot_task',self.args(ref))
            self.assertEqual(e.exception.code,'invalid_state')
            self.assertEqual(self.c.owner.call('get_bot_task',{'task_id':self.parent['id']})['task']['output_state'],before)

    def test_overlap_conflict_and_scope_are_not_silently_resolved(self):
        change=self.c.owner.call('begin_change',{'state_id':self.c.base['id'],'title':'Alternative mechanical change',
            'purpose':'Conflict probe','write_scope':['mechanical.txt'],'dependencies':[],'assignee':'admin'})
        row=self.c.owner.call('checkpoint_change',{'change_id':change['id'],'version':change['version'],
            'snapshot':self.c.artifact({'mechanical.txt':'3','control.txt':'1'}),'summary':'Alternative','rationale':'Independent candidate',
            'unfinished':[],'work_status':'working','capture':{'scope':'fixture','missing':[]}})
        shared=self.c.owner.call('share_change',{'change_id':change['id'],'version':row['change']['version']})['change']
        with self.c.worker('lead') as w:
            ref=self.claimed(w);args=self.args(ref);args['changes']=args['changes']+[{'id':shared['id'],'version':shared['version']}]
            with self.assertRaises(Fault) as e:self.c.clients['lead'].call('integrate_bot_task',args)
            self.assertEqual(e.exception.code,'conflict')
            self.assertNotIn('output_state',self.c.owner.call('get_bot_task',{'task_id':self.parent['id']})['task'])
            for x in self.c.owner.call('get_bot_task',{'task_id':self.parent['id']})['candidate_changes']:
                self.assertEqual(x['change']['sharing'],'shared')
        narrow=self.c.task('lead',kind='integrate',write_scope=['mechanical.txt'])
        with self.c.worker('lead') as w:
            ref=self.claimed(w,narrow)
            with self.assertRaises(Fault) as e:self.c.clients['lead'].call('integrate_bot_task',self.args(ref))
            self.assertEqual(e.exception.code,'scope_denied')

    def test_materialization_resumes_after_old_workspace_rename(self):
        from unittest.mock import patch
        from gantry.continuity_adapter import restore_development_state
        with self.c.worker('lead') as w:
            ref=self.claimed(w);result=self.c.clients['lead'].call('integrate_bot_task',self.args(ref),'merge-once')
            path=self.c.root/'restored';restore_development_state(self.c.clients['lead'],self.c.base['id'],path,'base-restore')
            workspace=path/'workspace';step=self.c.root/'step';step.mkdir()
            saved={'result':result,'before':safe_fingerprint(workspace)};original=Path.rename
            def crash(path,target):
                if path==step/'integrated-restore'/'workspace':raise OSError('Injected interruption after retaining predecessor')
                return original(path,target)
            with patch.object(Path,'rename',crash):
                with self.assertRaises(OSError):crew_runtime._materialize_integration(self.c.clients['lead'],workspace,step,saved,'switch')
            self.assertFalse(workspace.exists());self.assertEqual((step/'pre-integration-workspace'/'mechanical.txt').read_text(),'1')
            crew_runtime._materialize_integration(self.c.clients['lead'],workspace,step,saved,'switch')
            self.assertEqual((workspace/'mechanical.txt').read_text(),'2')
            self.assertEqual((workspace/'control.txt').read_text(),'2')
            crew_runtime._materialize_integration(self.c.clients['lead'],workspace,step,saved,'switch')
            self.assertEqual(saved['materialized'],result['state']['id'])

    def test_materialization_holds_if_local_files_change_during_restore(self):
        from unittest.mock import patch
        from gantry.continuity_adapter import restore_development_state
        with self.c.worker('lead') as w:
            ref=self.claimed(w);result=self.c.clients['lead'].call('integrate_bot_task',self.args(ref),'merge-once')
            path=self.c.root/'restored';restore_development_state(self.c.clients['lead'],self.c.base['id'],path,'base-restore')
            workspace=path/'workspace';step=self.c.root/'step';step.mkdir()
            saved={'result':result,'before':safe_fingerprint(workspace)}
            def changed_during_restore(*args,**kwargs):
                restored=restore_development_state(*args,**kwargs)
                (workspace/'mechanical.txt').write_text('Unsaved edit while transfer was in progress')
                return restored
            with patch('gantry.continuity_adapter.restore_development_state',changed_during_restore):
                with self.assertRaises(Fault) as error:
                    crew_runtime._materialize_integration(self.c.clients['lead'],workspace,step,saved,'switch')
            self.assertEqual(error.exception.code,'stale_basis')
            self.assertEqual((workspace/'mechanical.txt').read_text(),'Unsaved edit while transfer was in progress')
            self.assertNotIn('materialized',saved)
            self.assertFalse((step/'pre-integration-workspace').exists())

    def test_lost_integration_acknowledgement_reconciles_before_tool(self):
        self.config('lead');calls=[];baseclient=self.c.clients['lead']
        class LostAck:
            def __init__(self):self.lost=False
            def call(self,name,args=None,key=None):
                value=baseclient.call(name,args,key)
                if name=='integrate_bot_task' and not self.lost:
                    self.lost=True;raise OSError('Injected response loss after successful Core commit')
                return value
        bridge=LostAck()
        def infer(ctx,*_):
            calls.append(ctx)
            if len(calls)==1:return action('integrate',{'state_id':self.c.base['id'],'changes':self.refs,'summary':'Combine once'})
            if len(calls)==2:return action('tool',{'name':'verify'})
            self.assertEqual(ctx['last_result']['exit_code'],0)
            return action('finish',self.c.answer(summary='Recovered exact integration and tested'))
        with self.c.worker('lead',infer,bridge) as w:r=w.tick()[0]
        self.assertEqual(r['status'],'held')
        sid=self.c.owner.call('get_bot_task',{'task_id':self.parent['id']})['task']['output_state']
        with self.c.worker('lead',infer,bridge) as w:r=w.recover(self.parent['id'],'Stopped validation worker after injected lost acknowledgement')
        self.assertEqual(r['task']['status'],'completed',r)
        self.assertEqual(r['task']['output_state'],sid)
        self.assertEqual(len(calls),3)
        states=self.c.owner.call('list_development_states',{'session_id':self.c.sid})['states']
        self.assertEqual(sum(bool(s.get('integrated_changes')) for s in states),1)

if __name__=='__main__':unittest.main(verbosity=2)
