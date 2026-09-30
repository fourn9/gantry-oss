import base64
import secrets
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from gantry.client import Client
from gantry.model import Fault
from gantry.service import token_hash
from test_interfaces import InterfaceTests

class BoundaryTests(InterfaceTests):
    def delegate(self):
        token=secrets.token_urlsafe(32)
        proposal=self.client.call('propose',{'title':'Scoped developer','changes':[{'id':'scoped','type':'principal','data':{
            'kind':'agent','permissions':['read','record','propose','work'],'zones':['root'],'token_hash':token_hash(token)}}]})
        args={'proposal_id':proposal['id'],'version':proposal['version']}
        self.client.call('submit',args);self.client.call('endorse',{**args,'reason':'test'})
        self.client.call('review_adoption',{**args,'reason':'test','verdict':'approve'});self.client.call('commit',args)
        return Client(self.url,token)
    def test_scoped_identity_cannot_read_legacy_global_state_or_other_zone_bytes(self):
        client=self.delegate()
        # Owner creates another scope before saving its files.
        p=self.client.call('propose',{'title':'Private zone','changes':[{'id':'private-zone','type':'zone','data':{'owner':'admin'}}]})
        a={'proposal_id':p['id'],'version':p['version']}
        self.client.call('submit',a);self.client.call('endorse',{**a,'reason':'test'})
        self.client.call('review_adoption',{**a,'verdict':'approve','reason':'test'});self.client.call('commit',a)
        artifact=self.client.call('capture_artifact',{'zone':'private-zone','files':{'secret.txt':base64.b64encode(b'secret').decode()}})
        rid=artifact['revision_id']
        for name,args in [('state',{}),('history',{}),('restore_artifact',{'revision_id':rid}),
            ('list_artifact_files',{'revision_id':rid}),('read_artifact_chunk',{'revision_id':rid,'path':'secret.txt','index':0}),
            ('capture_artifact',{'files':{},'assembled_files':{'copied.txt':[{'revision_id':rid,'path':'secret.txt'}]}})]:
            with self.subTest(operation=name),self.assertRaises(Fault) as error:client.call(name,args)
            self.assertEqual(error.exception.code,'unauthorized')
        self.assertEqual(client.call('identity')['id'],'scoped')
    def test_malformed_host_and_invalid_token_before_json(self):
        for host in ['localhost:'+str(self.server.server_port)+'/evil','localhost:'+str(self.server.server_port)+'?x=1']:
            with self.assertRaises(HTTPError) as error:urlopen(Request(self.url+'/health',headers={'Host':host}))
            self.assertEqual(error.exception.code,403)
        with self.assertRaises(HTTPError) as error:urlopen(Request(self.url+'/v1/commands/identity',data=b'not-json',headers={'Content-Type':'application/json','Authorization':'Bearer invalid'}))
        self.assertEqual(error.exception.code,401)
