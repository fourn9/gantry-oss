import json
import unittest
import test_continuity as fixtures


class WorkflowTests(unittest.TestCase):
    for name in ('setUp','tearDown','call','artifact','policy','connect','detail','fault','initialize','begin','checkpoint'):
        locals()[name]=getattr(fixtures.ContinuityTests,name)

    def test_checkout_mapping_and_reopen_preserve_context(self):
        from gantry.engineering_workflow import checkout, bind_mapping, status
        base=self.initialize()
        workspace=checkout(self.client,base['id'],self.root/'checkout','Example','Bind tools',
                           ['input.txt','engineering-map.json'],'admin','start')['workspace']
        from pathlib import Path
        workspace=Path(workspace)
        mapping={'version':1,'components':[{'id':'part','role':'mechanism','assembly':'robot',
            'paths':['input.txt'],'native_refs':[{'provider':'fixture','document':'doc','object':'part',
                'revision':'r1','unit':'mm','frame':'robot','source_path':'input.txt'}]}], 'dependencies':[]}
        (workspace/'engineering-map.json').write_text(json.dumps(mapping))
        cp=bind_mapping(self.client,workspace,'engineering-map.json','Reviewed source IDs','mapping')
        repeated=bind_mapping(self.client,workspace,'engineering-map.json','Reviewed source IDs','mapping')
        self.assertEqual(cp['state']['id'],repeated['state']['id'])
        resumed=status(self.client,workspace)
        self.assertEqual(resumed['state_id'],cp['state']['id'])
        self.assertEqual(resumed['local_changes'],[])
        self.assertEqual(resumed['development']['engineering']['components'][0]['native_refs'][0]['object'],'part')
        self.assertEqual(resumed['development']['status']['adoption'],'unadopted')

    def test_general_file_checkpoint_after_lost_ack_does_not_repeat_edit(self):
        from gantry.engineering_workflow import checkout, checkpoint, status
        from pathlib import Path
        base=self.initialize()
        workspace=Path(checkout(self.client,base['id'],self.root/'general','Edit','Continue',
                               ['input.txt'],'admin','start')['workspace'])
        (workspace/'input.txt').write_text('changed')
        real=self.client
        class LostAck:
            def call(self,name,args=None,key=None):
                result=real.call(name,args,key)
                if name=='checkpoint_change': raise ConnectionError()
                return result
        with self.assertRaises(ConnectionError): checkpoint(LostAck(),workspace,'Edited','Candidate only','saved')
        result=checkpoint(real,workspace,'Edited','Candidate only','saved')
        self.assertEqual(status(real,workspace)['state_id'],result['state']['id'])
        self.assertEqual(status(real,workspace)['development']['status']['verification'],'unverified')

    def test_external_capture_cannot_be_deleted_by_unhydrated_checkpoint(self):
        from gantry.engineering_workflow import checkout,capture,checkpoint
        from gantry.integrations.bundle import make_bundle,write_bundle
        base=self.initialize()
        root=checkout(self.client,base['id'],self.root/'external','Import','Review source',
                      ['input.txt','imports/source/'],'admin','start')['workspace']
        bundle=self.root/'bundle'
        write_bundle(bundle,make_bundle('python','source',{'report.json':b'{}'},[]))
        result=capture(self.client,root,bundle,'capture')
        self.assertIn('imports/source/payload/report.json',self.call('get_development_state',{'state_id':result['state']['id']})['manifest'])
        self.fault('restore_required',lambda:checkpoint(self.client,root,'Other edit','Preserve imports','save'))
