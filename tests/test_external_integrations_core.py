import copy
import json
import unittest
from pathlib import Path
from gantry.integrations.bundle import make_bundle,write_bundle
from gantry.integrations.publication import publish
import test_requirement_traceability as fixtures


class PublicationTests(unittest.TestCase):
    setUp=fixtures.TraceabilityIntegrationTests.setUp
    tearDown=fixtures.TraceabilityIntegrationTests.tearDown
    call=fixtures.TraceabilityIntegrationTests.call
    artifact=fixtures.TraceabilityIntegrationTests.artifact
    policy=fixtures.TraceabilityIntegrationTests.policy
    connect=fixtures.TraceabilityIntegrationTests.connect
    detail=fixtures.TraceabilityIntegrationTests.detail
    initialize=fixtures.TraceabilityIntegrationTests.initialize
    begin=fixtures.TraceabilityIntegrationTests.begin
    checkpoint=fixtures.TraceabilityIntegrationTests.checkpoint
    requirement=fixtures.TraceabilityIntegrationTests.requirement
    fault=fixtures.TraceabilityIntegrationTests.fault
    def prepare(self):
        ref=self.requirement();base=self.initialize()
        ctx=copy.deepcopy(base['context']);ctx['requirement_refs']=[ref]
        state=self.checkpoint(self.begin(base),{'input.txt':'initial'},context=ctx)['state']
        b=make_bundle('python','analysis',{'result.json':b'{"stress":40,"unit":"MPa"}'},[ref],{'result.json':['/stress']})
        path=self.root/'capture';write_bundle(path,b)
        c=self.begin(state,['imports/analysis/'])
        return state,c,path,ref
    def test_publish_restore_mentor_and_retry(self):
        state,c,path,ref=self.prepare()
        result=publish(self.client,state['id'],c['id'],c['version'],path,'publish-1')
        view=self.call('get_development_state',{'state_id':result['state']['id']})
        self.assertIn('input.txt',view['manifest'])
        self.assertIn('imports/analysis/payload/result.json',view['manifest'])
        source=view['state']['context']['environment']['external_sources']['analysis']
        self.assertEqual(source['requirement_refs'],[ref])
        self.assertEqual(view['requirement_coverage']['items'][0]['status'],'unverified')
        self.assertEqual(view['status']['adoption'],'unadopted')
        retry=publish(self.client,state['id'],c['id'],c['version'],path,'publish-1')
        self.assertEqual(retry,result)
        self.fault('stale_basis',lambda:publish(self.client,state['id'],c['id'],c['version'],path,'different-key'))
        self.call('select_development_state',{'state_id':result['state']['id'],
            'version':self.detail()['session']['version'],'reason':'Review newly captured evidence'})
        mentor=self.call('mentor_context',{'session_id':self.session['id']})
        self.assertIn('analysis',json.dumps(mentor))
        self.assertTrue(self.call('replay')['matched'])
    def test_scope_and_mismatched_requirement(self):
        state,c,path,ref=self.prepare()
        other=self.begin(state,['input.txt'])
        self.fault('scope_denied',lambda:publish(self.client,state['id'],other['id'],other['version'],path,'scope'))
        b=make_bundle('python','analysis',{'x.json':b'{}'},[{**ref,'revision_id':'rev_unknown'}])
        path2=self.root/'different';write_bundle(path2,b)
        self.fault('invalid_input',lambda:publish(self.client,state['id'],c['id'],c['version'],path2,'different'))
    def test_requirement_changed_import_stays_historical(self):
        state,c,path,ref=self.prepare();self.requirement(ref['revision_id'])
        cp=publish(self.client,state['id'],c['id'],c['version'],path,'history')
        view=self.call('get_development_state',{'state_id':cp['state']['id']})
        self.assertEqual(view['requirement_coverage']['items'][0]['status'],'needs_review')

    def test_native_update_evidence_flows_into_core(self):
        from gantry.integrations.writes import prepare,apply,evidence
        from test_external_writes import CONFIG,CHANGE,FakeGithub
        state,old_change,unused,ref=self.prepare();remote=FakeGithub()
        planpath=self.root/'native-plan';journal=self.root/'native-journal'
        plan=prepare(CONFIG,CHANGE,'Requirement-linked controller update',[ref],planpath,'GANTRY_CONNECTOR_TEST',remote)
        applied=apply(planpath,plan['plan_hash'],journal,'GANTRY_CONNECTOR_TEST',transport=remote)
        self.assertEqual(applied['status'],'verified')
        bundle=evidence(planpath,journal);path=self.root/'native-evidence';write_bundle(path,bundle)
        source=bundle['manifest']['source_id'];change=self.begin(state,['imports/'+source+'/'])
        result=publish(self.client,state['id'],change['id'],change['version'],path,'native-evidence')
        view=self.call('get_development_state',{'state_id':result['state']['id']})
        self.assertIn('imports/'+source+'/payload/after.json',view['manifest'])
        self.assertEqual(view['requirement_coverage']['items'][0]['status'],'unverified')
        self.assertEqual(view['status']['adoption'],'unadopted')
        self.assertEqual(view['state']['context']['environment']['external_sources'][source]['requirement_refs'],[ref])
        self.assertTrue(self.call('replay')['matched'])

    def test_desktop_api_write_capture_roundtrips_requirement_linked_state(self):
        from gantry.native.workflow import prepare,apply,evidence
        from gantry.native.drivers import SolidWorks
        from test_native_desktop import Part
        from types import SimpleNamespace
        import base64
        state,_,_,ref=self.prepare()
        native=self.root/'native';native.mkdir();part=native/'bracket.SLDPRT';part.write_bytes(b'original')
        doc=Part(part);driver=SolidWorks(SimpleNamespace(ActiveDoc=doc,RevisionNumber=lambda:'34'),lambda d:d.save())
        config={'product':'solidworks','document':part.name,'selector':'D1@Sketch1','unit':'SI','version':'34'}
        plan=prepare(native,config,0.03,'Reach requirement',[ref],native/'plan',driver)
        result=apply(native/'plan',plan['plan_hash'],native,driver,exclusive=True)
        self.assertEqual(result['status'],'verified')
        bundle=evidence(native/'plan',native);path=self.root/'desktop-capture';write_bundle(path,bundle)
        source=bundle['manifest']['source_id'];change=self.begin(state,['imports/'+source+'/'])
        cp=publish(self.client,state['id'],change['id'],change['version'],path,'desktop-evidence')
        view=self.call('get_development_state',{'state_id':cp['state']['id']})
        self.assertEqual(view['requirement_coverage']['items'][0]['status'],'unverified')
        self.assertEqual(view['status']['adoption'],'unadopted')
        self.assertIn('imports/'+source+'/payload/after/native/bracket.SLDPRT',view['manifest'])
        self.assertEqual(view['state']['context']['environment']['external_sources'][source]['requirement_refs'],[ref])
        self.assertTrue(self.call('replay')['matched'])

    def test_cloud_bytes_and_nested_notes_survive_cli_capture_core_and_restore(self):
        from unittest.mock import patch
        from contextlib import redirect_stdout
        import io
        from gantry.integrations.__main__ import main
        from gantry.integrations.transport import Response
        from gantry.continuity_adapter import restore_development_state
        state,_,_,ref=self.prepare()
        cfg=self.root/'file-config.json';cfg.write_text(json.dumps({'provider':'google-drive','file':'part'}))
        refs=self.root/'requirement-links.json';refs.write_text(json.dumps([ref]))
        meta={'id':'part','size':'6','version':'1','mimeType':'application/octet-stream',
              'capabilities':{'canDownload':True}}
        def transport(req,token):return Response(b'CAD\x00\x01\x02' if 'alt=media' in req.url else json.dumps(meta).encode(),{})
        from gantry.integrations.files import capture_file
        capture=self.root/'cloud-capture'
        with patch('gantry.integrations.files.capture_file',side_effect=lambda *a,**kw:capture_file(*a,**kw,transport=transport)), redirect_stdout(io.StringIO()):
            self.assertEqual(main(['pull-file','--config',str(cfg),'--source-id','cloud-part',
                '--requirements',str(refs),'--output',str(capture)]),0)
        change=self.begin(state,['imports/cloud-part/'])
        cp=publish(self.client,state['id'],change['id'],change['version'],capture,'cloud-body')
        destination=self.root/'restored-cloud'
        restored=restore_development_state(self.client,cp['state']['id'],destination,'restore-cloud')
        destination=Path(restored['workspace'])
        self.assertEqual((destination/'imports/cloud-part/payload/content.bin').read_bytes(),b'CAD\x00\x01\x02')
        view=self.call('get_development_state',{'state_id':cp['state']['id']})
        self.assertEqual(view['requirement_coverage']['items'][0]['status'],'unverified')
        self.assertEqual(view['status']['adoption'],'unadopted')
        # A partial note capture remains partial after the same publication route.
        from gantry.integrations.collections import capture_collection
        def page(req,token):return Response(b'{"results":[],"has_more":true,"next_cursor":"next"}',{})
        notes=capture_collection({'provider':'notion','block':'root'},'notes',[ref],max_requests=1,transport=page)
        write_bundle(self.root/'notes',notes)
        change=self.begin(cp['state'],['imports/notes/'])
        next_cp=publish(self.client,cp['state']['id'],change['id'],change['version'],self.root/'notes','notes-body')
        restored=restore_development_state(self.client,next_cp['state']['id'],self.root/'restored-notes','restore-notes')
        workspace=Path(restored['workspace'])
        index=json.loads((workspace/'imports/notes/payload/collection.json').read_text())
        self.assertEqual(index['status'],'partial');self.assertEqual(len(index['pending']),1)
        self.assertEqual((workspace/'imports/cloud-part/payload/content.bin').read_bytes(),b'CAD\x00\x01\x02')
        self.assertTrue(self.call('replay')['matched'])
