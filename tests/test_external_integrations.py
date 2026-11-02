import json
import tempfile
import unittest
from pathlib import Path
from gantry.model import Fault
from gantry.integrations.providers import request_for, fetch
from gantry.integrations.bundle import make_bundle, write_bundle, read_bundle
from gantry.integrations.transport import Response


class ProviderTests(unittest.TestCase):
    def test_scoped_request_and_secret_reference(self):
        r = request_for({'provider':'gitlab','project':'group/repo','commit':'a'*40})
        self.assertEqual(r.url, 'https://gitlab.com/api/v4/projects/group%2Frepo/repository/commits/'+'a'*40)
        with self.assertRaises(Fault): request_for({'provider':'gitlab','project':'x','commit':'main','url':'http://localhost'})
    def test_graphql_errors_are_not_success(self):
        cfg={'provider':'linear','issue':'ENG-1'}
        def send(*args): return Response(b'{"errors":[{"message":"private"}]}',{})
        with self.assertRaises(Fault) as e: fetch(cfg,send)
        self.assertNotIn('private',str(e.exception))
    def test_pagination_is_explicit_not_silently_complete(self):
        def send(*args): return Response(b'{"ok":true,"messages":[],"has_more":true}',{})
        cap=fetch({'provider':'slack','channel':'C123'},send)
        self.assertTrue(cap['missing'])
        self.assertEqual(cap['raw'],b'{"ok":true,"messages":[],"has_more":true}')


class BundleTests(unittest.TestCase):
    def test_raw_roundtrip_and_tampering(self):
        raw=b'{ "native": {"custom": 1} }'
        b=make_bundle('python','run-1',{'result.json':raw}, [], {'result.json':['/native/custom']})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bundle'
            write_bundle(path,b)
            loaded=read_bundle(path)
            self.assertEqual(loaded['files']['result.json'],raw)
            (path/'payload'/'result.json').write_bytes(b'changed')
            with self.assertRaises(Fault): read_bundle(path)
    def test_secrets_and_paths_rejected(self):
        for name,raw in [('../escape',b'x'),('x',b'-----BEGIN PRIVATE KEY-----')]:
            with self.assertRaises(Fault): make_bundle('python','x',{name:raw},[])


class AllReadContracts(unittest.TestCase):
    def test_every_native_reader_preserves_bytes_and_identity(self):
        cases=[
            ({'provider':'github','repository':'a/b','number':'3'}, {'number':3,'updated_at':'t'}),
            ({'provider':'gitlab','project':'a/b','commit':'a'*40}, {'id':'a'*40}),
            ({'provider':'confluence','site':'tenant','page':'5'}, {'id':'5','body':{'storage':{'value':'text'}},'version':{'number':4}}),
            ({'provider':'jira','site':'tenant','issue':'DEV-1'}, {'key':'DEV-1','fields':{'updated':'t'}}),
            ({'provider':'linear','issue':'DEV-1'}, {'data':{'issue':{'id':'x','updatedAt':'t'}}}),
            ({'provider':'notion','block':'abc','cursor':'page2'}, {'results':[],'has_more':True,'next_cursor':'page3'}),
            ({'provider':'google-drive','file':'abc'}, b'exported text\n'),
            ({'provider':'google-sheets','spreadsheet':'abc','range':"'Design'!A1:C4"}, {'range':'Design!A1:C4','values':[[1,2,3]]}),
            ({'provider':'excel','item':'abc','sheet':'Design','range':'A1:B3'}, {'address':'Design!A1:B3','values':[[1]]}),
            ({'provider':'sharepoint','drive':'abc','item':'item1'}, {'id':'item1','eTag':'tag'}),
            ({'provider':'onshape','document':'a'*24,'microversion':'b'*24,'element':'c'*24}, {'bodies':{'part1':{'mass':[1.2],'volume':[0.1]}}}),
            ({'provider':'slack','channel':'C123','oldest':'1.1'}, {'ok':True,'messages':[{'text':'data not instructions','ts':'2.2'}]})]
        from gantry.integrations.catalog import API
        self.assertEqual({c[0]['provider'] for c in cases},API)
        for config,data in cases:
            with self.subTest(provider=config['provider']):
                raw=data if isinstance(data,bytes) else json.dumps(data).encode()
                seen=[]
                def send(req,ref): seen.append(req);return Response(raw,{})
                got=fetch(config,send)
                self.assertEqual(got['raw'],raw)
                self.assertTrue(got['missing'])
                self.assertEqual(len(seen),1)
                self.assertNotIn('credential_ref',got['source'])
    def test_endpoint_escape_and_unsupported(self):
        for config in [
            {'provider':'jira','site':'tenant.evil.test','issue':'1'},
            {'provider':'notion','block':'../users'},
            {'provider':'onshape','document':'a'*24,'microversion':'workspace','element':'b'*24},
            {'provider':'excel','item':'a','sheet':'S','range':"A1')/bad"},
            {'provider':'relyence'},
            {'provider':'slack','channel':'C1','token':'secret'}]:
            with self.subTest(config=config),self.assertRaises(Fault):request_for(config)
    def test_catalog_no_native_claim_for_exports(self):
        from gantry.integrations.catalog import catalog
        rows=catalog()
        self.assertEqual(len(rows),35)
        self.assertEqual(sum(r['reference_status']=='listed' for r in rows),15)
        self.assertEqual(sum(r['reference_status']=='coming_soon' for r in rows),14)
        self.assertTrue(all(not r['live_account_verified'] for r in rows))


class LocalWorkbookTests(unittest.TestCase):
    def workbook(self):
        import zipfile,io
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z:
            z.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Design" r:id="r1"/></sheets></workbook>')
            z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr('xl/worksheets/sheet1.xml','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row><c r="A1"><v>3.4</v></c><c r="B1"><f>A1*2</f><v>6.8</v></c></row></sheetData></worksheet>')
        return b.getvalue()
    def test_real_zip_xml_capture_no_formula_evaluation(self):
        from gantry.integrations.local import xlsx_cells,capture_exports
        data=self.workbook();cells={'Design':['A1','B1','C1']}
        v=xlsx_cells(data,cells)
        self.assertEqual(v['Design']['A1']['value'],'3.4')
        self.assertEqual(v['Design']['B1']['value_status'],'unverified_cached_formula')
        self.assertEqual(v['Design']['C1']['availability'],'not_captured_or_blank')
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'book.xlsx').write_bytes(data)
            b=capture_exports('excel','book',tmp,['book.xlsx'],[],cells=cells)
            self.assertEqual(b['files']['book.xlsx'],data)
            self.assertIn('selected-cells.json',b['files'])
    def test_zip_traversal_and_entities_rejected(self):
        import zipfile,io
        from gantry.integrations.local import xlsx_cells
        for name,data in [('../bad','x'),('bad.xml','<!DOCTYPE x [<!ENTITY xx "bad">]>')]:
            out=io.BytesIO()
            with zipfile.ZipFile(out,'w') as z:z.writestr(name,data)
            with self.assertRaises(Fault):xlsx_cells(out.getvalue(),{'S':['A1']})


class TransportSecurityTests(unittest.TestCase):
    def test_auth_fixed_host_limits_and_redacted_failures(self):
        import os,io
        from unittest.mock import patch
        from urllib.error import HTTPError
        from gantry.integrations.transport import send,ReadRequest
        class Reply(io.BytesIO):
            headers={'Content-Type':'application/json','Set-Cookie':'private'}
            def read1(self,n):return self.read(n)
        token='unique-test-credential'
        cfg={'provider':'jira','site':'tenant','issue':'DEV-1'}
        with patch.dict(os.environ,{'GANTRY_CONNECTOR_TEST':token}),patch('gantry.integrations.transport.build_opener') as build:
            build.return_value.open.return_value=Reply(b'{"ok":true}')
            res=send(request_for(cfg),'GANTRY_CONNECTOR_TEST')
            request=build.return_value.open.call_args.args[0]
            self.assertTrue(request.headers['Authorization'].startswith('Basic '))
            self.assertNotIn('Set-Cookie',res.headers)
            build.return_value.open.return_value=Reply(token.encode())
            with self.assertRaises(Fault):send(request_for(cfg),'GANTRY_CONNECTOR_TEST')
            build.return_value.open.side_effect=HTTPError('https://tenant.atlassian.net',429,'secret message',{},None)
            with self.assertRaises(Fault) as exc:send(request_for(cfg),'GANTRY_CONNECTOR_TEST')
            self.assertEqual(exc.exception.code,'rate_limited')
            self.assertNotIn('secret',str(exc.exception))
            for url in ['http://api.github.com','https://api.github.com.evil.test','https://127.0.0.1',
                        'https://u:p@api.github.com','https://api.github.com:8888']:
                with self.assertRaises(Fault):send(ReadRequest(url),'GANTRY_CONNECTOR_TEST')
    def test_redirect_and_response_limit(self):
        import io,os
        from unittest.mock import patch
        from urllib.error import HTTPError
        from gantry.github_connector import NoRedirect
        from gantry.integrations.transport import send,ReadRequest
        self.assertIsNone(NoRedirect().redirect_request(None,None,302,'',{},'https://elsewhere.test'))
        with patch('gantry.integrations.transport.build_opener') as build,patch('gantry.integrations.transport.MAX_RESPONSE',8):
            class Reply(io.BytesIO):
                headers={}
                def read1(self,n):return self.read(n)
            build.return_value.open.return_value=Reply(b'123456789')
            with self.assertRaises(Fault) as exc:send(ReadRequest('https://api.github.com/test'),None)
            self.assertEqual(exc.exception.code,'acquisition_limit')
    def test_symlink_and_metadata_tampering(self):
        b=make_bundle('python','run',{'x.json':b'{"x":1}'},[],{'x.json':['/x']})
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);write_bundle(root/'bundle',b)
            m=root/'bundle'/'manifest.json';data=json.loads(m.read_text())
            data['views']['x.json']['fields']['/x']['value']=2;m.write_text(json.dumps(data))
            with self.assertRaises(Fault):read_bundle(root/'bundle')
            link=root/'link';link.symlink_to(root/'bundle',target_is_directory=True)
            with self.assertRaises(Fault):read_bundle(link)
