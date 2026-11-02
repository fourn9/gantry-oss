import base64
import json
import tempfile
import unittest
from pathlib import Path
from gantry.model import Fault
from gantry.integrations.transport import Response
from gantry.integrations.writes import prepare, apply, reconcile


class FakeGithub:
    def __init__(self):
        self.content = 'old\n'
        self.sha = 'a' * 40
        self.writes = 0
        self.lose_response = False
    def __call__(self, request, credential_ref):
        if request.method == 'PUT':
            body = json.loads(request.body)
            assert body['sha'] == self.sha
            assert body['branch'] == 'design'
            self.writes += 1
            self.content = base64.b64decode(body['content']).decode()
            self.sha = 'b' * 40
            if self.lose_response:
                raise Fault('remote_unavailable', 'Lost response')
            return Response(json.dumps({'content': {'sha': self.sha}}).encode(), {})
        return Response(json.dumps({'type': 'file', 'path': 'src/controller.py',
            'sha': self.sha, 'encoding': 'base64',
            'content': base64.b64encode(self.content.encode()).decode()}).encode(), {})


CONFIG = {'provider': 'github', 'operation': 'file.update',
          'repository': 'example/robot', 'branch': 'design', 'path': 'src/controller.py'}
CHANGE = {'content': 'new\n', 'message': 'Update controller'}


class WriteLifecycleTests(unittest.TestCase):
    def prepare(self, root, remote):
        return prepare(CONFIG, CHANGE, 'Adjust behavior', [], root/'plan', 'GANTRY_CONNECTOR_TEST', remote)
    def test_prepare_apply_capture_and_repeat(self):
        remote = FakeGithub()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); plan = self.prepare(root, remote)
            self.assertEqual(remote.writes, 0)
            result = apply(root/'plan', plan['plan_hash'], root/'journal', 'GANTRY_CONNECTOR_TEST', transport=remote)
            self.assertEqual(result['status'], 'verified')
            self.assertEqual(remote.content, 'new\n')
            repeated = apply(root/'plan', plan['plan_hash'], root/'journal', 'GANTRY_CONNECTOR_TEST', transport=remote)
            self.assertEqual(repeated, result)
            self.assertEqual(remote.writes, 1)
            from gantry.integrations.writes import evidence
            bundle = evidence(root/'plan', root/'journal')
            self.assertEqual(bundle['manifest']['adoption'], 'unadopted')
            self.assertIn('before.json', bundle['files'])
            self.assertIn('after.json', bundle['files'])
    def test_changed_baseline_blocks_without_mutation(self):
        remote = FakeGithub()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); plan=self.prepare(root,remote); remote.sha='c'*40
            with self.assertRaises(Fault) as exc:
                apply(root/'plan',plan['plan_hash'],root/'journal','GANTRY_CONNECTOR_TEST',transport=remote)
            self.assertEqual(exc.exception.code,'stale_basis')
            self.assertEqual(remote.writes,0)
    def test_lost_response_never_resends_and_reconciles(self):
        remote = FakeGithub()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); plan=self.prepare(root,remote); remote.lose_response=True
            result=apply(root/'plan',plan['plan_hash'],root/'journal','GANTRY_CONNECTOR_TEST',transport=remote)
            self.assertEqual(result['status'],'unknown')
            self.assertEqual(apply(root/'plan',plan['plan_hash'],root/'journal','GANTRY_CONNECTOR_TEST',transport=remote)['status'],'unknown')
            result=reconcile(root/'plan',root/'journal','GANTRY_CONNECTOR_TEST',transport=remote)
            self.assertEqual(result['status'],'observed_desired')
            self.assertEqual(remote.writes,1)


class NativeRecipeContracts(unittest.TestCase):
    def cases(self):
        return [
            ({'provider':'github','operation':'issue.update','repository':'example/robot','number':'7'},
             {'title':'New'}, {'number':7,'title':'Old','updated_at':'t1'}, 'PATCH','/issues/7'),
            ({'provider':'gitlab','operation':'file.update','project':'example/robot','branch':'design','path':'controller.py'},
             {'content':'new','message':'Update'}, {'file_path':'controller.py','encoding':'base64','content':'b2xk','last_commit_id':'a'*40},'PUT','/repository/files/controller.py'),
            ({'provider':'confluence','operation':'page.update','site':'tenant','page':'5'},
             {'title':'New','storage':'<p>Body</p>'}, {'id':'5','title':'Old','status':'current','body':{'storage':{'value':'<p>Old</p>'}},'version':{'number':2}},'PUT','/pages/5'),
            ({'provider':'jira','operation':'issue.update','site':'tenant','issue':'ENG-1'},
             {'summary':'New'}, {'key':'ENG-1','fields':{'summary':'Old','updated':'t1'}},'PUT','/issue/ENG-1'),
            ({'provider':'linear','operation':'issue.update','issue':'ENG-1'},
             {'title':'New'}, {'data':{'issue':{'id':'issue-uuid','identifier':'ENG-1','title':'Old','updatedAt':'t1'}}},'POST','/graphql'),
            ({'provider':'notion','operation':'paragraph.update','block':'abc'},
             {'text':'New'}, {'id':'abc','type':'paragraph','last_edited_time':'t1','paragraph':{'rich_text':[{'plain_text':'Old','text':{'content':'Old'}}]}},'PATCH','/blocks/abc'),
            ({'provider':'google-drive','operation':'metadata.update','file':'abc'},
             {'description':'New'}, {'id':'abc','description':'Old','version':'2'},'PATCH','/files/abc'),
            ({'provider':'google-sheets','operation':'values.update','spreadsheet':'abc','range':'Design!A1:B1'},
             {'values':[[1,2]]}, {'range':'Design!A1:B1','values':[[0,0]]},'PUT','/values/Design%21A1%3AB1'),
            ({'provider':'excel','operation':'values.update','item':'abc','sheet':'Design','range':'A1:B1'},
             {'values':[[1,2]]}, {'address':'Design!A1:B1','values':[[0,0]],'formulas':[[0,0]]},'PATCH',"/range(address='A1:B1')"),
            ({'provider':'sharepoint','operation':'metadata.update','drive':'drive','item':'abc'},
             {'name':'New.txt'}, {'id':'abc','name':'Old.txt','eTag':'"2"'},'PATCH','/items/abc'),
            ({'provider':'slack','operation':'message.update','channel':'C123','ts':'10.100'},
             {'text':'New'}, {'ok':True,'messages':[{'ts':'10.100','text':'Old'}]},'POST','/chat.update'),
            ({'provider':'onshape','operation':'parameters.update','document':'a'*24,'workspace':'b'*24,'element':'c'*24,'feature':'feature1'},
             {'expressions':{'depth':'12 mm'}}, {'sourceMicroversion':'d'*24,'serializationVersion':'1','libraryVersion':100,
                 'features':[{'featureId':'feature1','btType':'BTMFeature-134','featureType':'extrude','parameters':[
                     {'parameterId':'depth','expression':'10 mm','btType':'BTMParameterQuantity-147'},
                     {'parameterId':'other','expression':'1 mm','btType':'BTMParameterQuantity-147'}]}]},'POST','/features/featureid/feature1')]
    def test_provider_specific_updates_and_readbacks(self):
        from gantry.integrations.write_recipes import observe, write_request, OPERATIONS
        cases=self.cases()
        self.assertEqual({cfg['provider'] for cfg, *_ in cases},set(OPERATIONS))
        for config,change,data,method,suffix in cases:
            with self.subTest(provider=config['provider']):
                obs=observe(config,change,'GANTRY_CONNECTOR_TEST',lambda *a:Response(json.dumps(data).encode(),{}))
                request=write_request(config,change,obs['baseline'])
                self.assertEqual(request.method,method)
                self.assertTrue(request.url.split('?')[0].endswith(suffix), request.url)
                body=json.loads(request.body)
                if config['provider']=='onshape':
                    self.assertTrue(body['rejectMicroversionSkew'])
                    self.assertEqual(body['sourceMicroversion'],'d'*24)
                    self.assertEqual(body['feature']['parameters'][0]['expression'],'12 mm')
                    self.assertEqual(body['feature']['parameters'][1]['expression'],'1 mm')
                if config['provider']=='gitlab':self.assertEqual(body['last_commit_id'],'a'*40)
                if config['provider']=='confluence':self.assertEqual(body['version']['number'],3)
                if config['provider']=='sharepoint':self.assertEqual(request.headers['If-Match'],'"2"')

    def test_all_providers_complete_update_and_readback_loop(self):
        import copy
        for config,change,before,method,_ in self.cases():
            p=config['provider']; after=copy.deepcopy(before)
            if p=='gitlab':
                after['content']=base64.b64encode(change['content'].encode()).decode();after['last_commit_id']='b'*40
            elif p=='confluence':
                after.update(title=change['title'],version={'number':3});after['body']['storage']['value']=change['storage']
            elif p=='jira':after['fields'].update(change,updated='t2')
            elif p=='linear':after['data']['issue'].update(change,updatedAt='t2')
            elif p=='notion':after['paragraph']['rich_text']=[{'plain_text':change['text']}];after['last_edited_time']='t2'
            elif p in {'excel','google-sheets'}:after['values']=change['values']
            elif p=='slack':after['messages'][0].update(text=change['text'],edited={'ts':'11.100'})
            elif p=='onshape':
                after['sourceMicroversion']='e'*24;after['features'][0]['parameters'][0]['expression']='12 mm'
            else:after.update(change)
            applied=[]
            def remote(req,ref):
                # A fixed GraphQL query remains a read even though its HTTP verb is POST.
                writing=req.method!='GET' and not (p=='linear' and json.loads(req.body)['query'].startswith('query'))
                if writing:
                    applied.append(req)
                    reply={'ok':True} if p=='slack' else {'data':{'issueUpdate':{'success':True}}} if p=='linear' else {}
                    return Response(b'' if p=='jira' else json.dumps(reply).encode(),{})
                return Response(json.dumps(after if applied else before).encode(),{})
            with self.subTest(provider=p),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);plan=prepare(config,change,'Native update contract',[],root/'plan','GANTRY_CONNECTOR_TEST',remote)
                outcome=apply(root/'plan',plan['plan_hash'],root/'journal','GANTRY_CONNECTOR_TEST',True,remote)
                self.assertEqual(outcome['status'],'verified')
                self.assertEqual(len(applied),1)
                from gantry.integrations.writes import evidence
                b=evidence(root/'plan',root/'journal')
                self.assertEqual(json.loads(b['files']['after.json']),after)


class WriteSafetyTests(unittest.TestCase):
    prepare = WriteLifecycleTests.prepare
    def test_nonatomic_requires_acknowledgement(self):
        c={'provider':'github','operation':'issue.update','repository':'example/robot','number':'7'}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            remote=lambda *a:Response(b'{"number":7,"title":"Old","updated_at":"t1"}',{})
            plan=prepare(c,{'title':'New'},'Review',[],root/'plan','GANTRY_CONNECTOR_TEST',remote)
            with self.assertRaises(Fault) as exc:apply(root/'plan',plan['plan_hash'],root/'journal','GANTRY_CONNECTOR_TEST',transport=remote)
            self.assertEqual(exc.exception.code,'nonatomic_write')
    def test_validation_precedes_reads_or_writes(self):
        from gantry.integrations.write_recipes import validate
        bad=[({**CONFIG,'path':'../credentials'},CHANGE),
             ({**CONFIG,'url':'https://evil.test'},CHANGE),
             ({**CONFIG,'operation':'file.delete'},CHANGE),
             ({'provider':'jira','operation':'issue.update','site':'tenant.evil.test','issue':'1'},{'summary':'bad'}),
             ({'provider':'excel','operation':'values.update','item':'i','sheet':'s','range':'A1'},{'values':[['=DANGEROUS()']]}),
             ({'provider':'google-sheets','operation':'values.update','spreadsheet':'s','range':'A1:B2'},{'values':[[1]]}),
             ({'provider':'google-sheets','operation':'values.update','spreadsheet':'s','range':'A1'},{'values':[[float('nan')]]}),
             ({'provider':'sharepoint','operation':'metadata.update','drive':'d','item':'i'},{'name':'../new'})]
        for c,ch in bad:
            with self.subTest(config=c),self.assertRaises(Fault):validate(c,ch)
    def test_unknown_mutation_outcome_is_not_false_failure(self):
        remote=FakeGithub()
        def uncertain(req,ref):
            if req.method=='PUT':
                remote(req,ref)
                return Response(b'{"errors":[{"message":"token or private text"}]}',{})
            return remote(req,ref)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan=self.prepare(root,uncertain)
            result=apply(root/'plan',plan['plan_hash'],root/'journal','GANTRY_CONNECTOR_TEST',transport=uncertain)
            self.assertEqual(result['status'],'unknown')
            self.assertNotIn('private',json.dumps(result))
            self.assertEqual(remote.writes,1)
    def test_crash_after_dispatch_marker_never_repeats(self):
        remote=FakeGithub()
        def crash(req,ref):
            result=remote(req,ref)
            if req.method=='PUT':raise KeyboardInterrupt()
            return result
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan=self.prepare(root,remote)
            with self.assertRaises(KeyboardInterrupt):apply(root/'plan',plan['plan_hash'],root/'journal','GANTRY_CONNECTOR_TEST',transport=crash)
            self.assertEqual(apply(root/'plan',plan['plan_hash'],root/'journal','GANTRY_CONNECTOR_TEST',transport=remote)['status'],'dispatching')
            self.assertEqual(reconcile(root/'plan',root/'journal','GANTRY_CONNECTOR_TEST',remote)['status'],'observed_desired')
            self.assertEqual(remote.writes,1)
    def test_concurrent_callers_cannot_dispatch_twice(self):
        import threading
        remote=FakeGithub();entered=threading.Event();release=threading.Event();outputs=[]
        def slow(req,ref):
            if req.method=='PUT':entered.set();release.wait(5)
            return remote(req,ref)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan=self.prepare(root,remote)
            def first():outputs.append(apply(root/'plan',plan['plan_hash'],root/'journal','GANTRY_CONNECTOR_TEST',transport=slow))
            thread=threading.Thread(target=first);thread.start()
            try:
                self.assertTrue(entered.wait(5))
                with self.assertRaises(Fault) as exc:apply(root/'plan',plan['plan_hash'],root/'journal','GANTRY_CONNECTOR_TEST',transport=remote)
                self.assertEqual(exc.exception.code,'conflict')
            finally:release.set();thread.join(5)
            self.assertEqual(outputs[0]['status'],'verified');self.assertEqual(remote.writes,1)
    def test_refusal_readback_mismatch_and_noop(self):
        for mode in ('refused','mismatch','noop'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);remote=FakeGithub()
                if mode=='noop':remote.content='new\n'
                def send(req,ref):
                    if req.method=='PUT':
                        if mode=='refused':raise Fault('remote_http_412','Version conflict')
                        remote(req,ref)
                        if mode=='mismatch':remote.content='other\n'
                        return Response(b'{}',{})
                    return remote(req,ref)
                plan=self.prepare(root,send)
                result=apply(root/'plan',plan['plan_hash'],root/'journal','GANTRY_CONNECTOR_TEST',transport=send)
                self.assertEqual(result['status'],{'refused':'refused','mismatch':'readback_mismatch','noop':'unchanged'}[mode])
    def test_plan_hash_and_credential_data_protection(self):
        remote=FakeGithub()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan=self.prepare(root,remote)
            with self.assertRaises(Fault):apply(root/'plan','wrong',root/'journal','GANTRY_CONNECTOR_TEST',transport=remote)
            with self.assertRaises(Fault):prepare(CONFIG,{**CHANGE,'content':'-----BEGIN PRIVATE KEY-----'},'reason',[],root/'secret','GANTRY_CONNECTOR_TEST',remote)
            self.assertEqual(remote.writes,0)
    def test_onshape_missing_parameter_cannot_be_invented(self):
        from gantry.integrations.write_recipes import observe
        c,ch,data,_,_=NativeRecipeContracts().cases()[-1]
        ch['expressions']={'unknown':'1 mm'}
        with self.assertRaises(Fault):observe(c,ch,'GANTRY_CONNECTOR_TEST',lambda *a:Response(json.dumps(data).encode(),{}))


class WriteTransportTests(unittest.TestCase):
    def test_actual_http_request_headers_and_payload(self):
        import io,os
        from unittest.mock import patch
        from gantry.integrations.transport import send_write,send,ReadRequest
        class Reply(io.BytesIO):
            headers={}
            def read1(self,n):return self.read(n)
        with patch.dict(os.environ,{'GANTRY_CONNECTOR_TEST':'test-credential-not-a-real-token'}),patch('gantry.integrations.transport.build_opener') as build:
            build.return_value.open.return_value=Reply(b'{}')
            send_write(CONFIG,CHANGE,{'revision':'a'*40},'GANTRY_CONNECTOR_TEST')
            req=build.return_value.open.call_args.args[0]
            self.assertEqual(req.method,'PUT')
            self.assertEqual(json.loads(req.data)['sha'],'a'*40)
            self.assertTrue(req.headers['Authorization'].startswith('Bearer '))
            for bad in [ReadRequest('https://api.github.com/repos/example/robot','PATCH',b'{}'),
                        ReadRequest('https://api.linear.app/graphql','POST',b'{"query":"mutation { issueDelete(id:1){success}}"}')]:
                with self.assertRaises(Fault):send(bad,'GANTRY_CONNECTOR_TEST')
            with self.assertRaises(Fault):send_write(CONFIG,CHANGE,{'revision':'a'*40},None)


class WriteCliTests(unittest.TestCase):
    def test_cli_prepare_apply_reconcile_export(self):
        import io
        from contextlib import redirect_stdout,redirect_stderr
        from unittest.mock import patch
        from gantry.integrations.__main__ import main
        from gantry.integrations.bundle import read_bundle
        remote=FakeGithub()
        # Exercise CLI + actual recipe/transport boundary without live credentials.
        with tempfile.TemporaryDirectory() as tmp,patch('gantry.integrations.transport._exchange',side_effect=remote):
            root=Path(tmp);(root/'target.json').write_text(json.dumps(CONFIG));(root/'change.json').write_text(json.dumps(CHANGE))
            def cli(args):
                out=io.StringIO();err=io.StringIO()
                with redirect_stdout(out),redirect_stderr(err):code=main(args)
                self.assertEqual(code,0,err.getvalue());return json.loads(out.getvalue())
            plan=cli(['prepare-write','--config',str(root/'target.json'),'--change',str(root/'change.json'),
                      '--reason','Adjust controller','--credential-ref','GANTRY_CONNECTOR_TEST','--output',str(root/'plan')])
            args=['--plan',str(root/'plan'),'--journal',str(root/'journal'),'--credential-ref','GANTRY_CONNECTOR_TEST']
            result=cli(['apply-write',*args,'--expect-plan',plan['plan_hash']])
            self.assertEqual(result['status'],'verified');self.assertNotIn('after',result)
            self.assertEqual(cli(['reconcile-write',*args])['status'],'observed_desired')
            output=cli(['export-write','--plan',str(root/'plan'),'--journal',str(root/'journal'),'--output',str(root/'evidence')])
            self.assertFalse(output['published'])
            b=read_bundle(root/'evidence');self.assertIn('write-response.json',b['files'])
            self.assertEqual(remote.writes,1)


class WriteSecretAndIntentTests(unittest.TestCase):
    def test_base64_source_cannot_hide_configured_credential(self):
        import os
        from unittest.mock import patch
        remote=FakeGithub();remote.content='an-opaque-configured-token-value'
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'GANTRY_CONNECTOR_TEST':remote.content}):
            with self.assertRaises(Fault) as exc:
                prepare(CONFIG,CHANGE,'Update',[],Path(tmp)/'plan','GANTRY_CONNECTOR_TEST',remote)
            self.assertEqual(exc.exception.code,'credential_detected')
            self.assertFalse((Path(tmp)/'plan').exists())
    def test_new_explicit_plan_is_distinct_but_retry_is_stable(self):
        remote=FakeGithub()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            first=prepare(CONFIG,CHANGE,'Update',[],root/'one','GANTRY_CONNECTOR_TEST',remote)
            second=prepare(CONFIG,CHANGE,'Update',[],root/'two','GANTRY_CONNECTOR_TEST',remote)
            self.assertNotEqual(first['plan_hash'],second['plan_hash'])
            from gantry.integrations.writes import load_plan
            self.assertEqual(load_plan(root/'one')[1],first['plan_hash'])
