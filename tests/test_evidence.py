import unittest
import test_continuity as fixture

class EvidenceTests(unittest.TestCase):
    setUp=fixture.ContinuityTests.setUp; tearDown=fixture.ContinuityTests.tearDown; call=fixture.ContinuityTests.call
    artifact=fixture.ContinuityTests.artifact; policy=fixture.ContinuityTests.policy; connect=fixture.ContinuityTests.connect
    detail=fixture.ContinuityTests.detail; fault=fixture.ContinuityTests.fault; initialize=fixture.ContinuityTests.initialize
    def test_native_source_and_selected_view(self):
        state=self.initialize()
        art=self.call('restore_artifact',{'revision_id':self.snapshot,'metadata_only':True})
        source={'revision_id':self.snapshot,'path':'input.txt','sha256':art['manifest']['files']['input.txt']['hash'],'locator':'whole-file'}
        args={'state_id':state['id'],'subject_id':'robot','profile':'mechanical.geometry.v1','extractor':'test-v1',
              'sources':[source],'fields':[{'name':'note','value':'initial','classification':'declared','source_index':0,'method':'submitted'},
              {'name':'temperature','value':None,'classification':'unknown','source_index':0,'method':'not-acquired'}], 'missing':['temperature']}
        view=self.call('record_evidence_view',args)
        got=self.call('get_evidence_view',{'view_id':view['id'],'fields':['note']})
        self.assertEqual(got['omitted_fields'],['temperature'])
        self.assertEqual(self.call('query_evidence',{'state_id':state['id']})['items'][0]['id'],view['id'])
        source['sha256']='0'*64
        self.fault('stale_basis',lambda:self.call('record_evidence_view',args))
        self.assertEqual(self.call('restore_artifact',{'revision_id':self.snapshot})['files']['input.txt'],'aW5pdGlhbA==')
        self.assertTrue(self.call('replay')['matched'])
