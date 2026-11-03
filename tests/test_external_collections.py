import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from gantry.model import Fault
from gantry.integrations.transport import Response
from gantry.integrations.bundle import write_bundle, read_bundle
from gantry.integrations.collections import capture_collection


class CollectionTests(unittest.TestCase):
    def test_notion_nested_pages_preserve_bytes_and_resume_without_repeating(self):
        calls=[]
        def transport(request, ref):
            calls.append(request.url)
            query=parse_qs(urlsplit(request.url).query)
            if '/root/' in request.url and 'start_cursor' not in query:
                data={'results':[{'id':'child','has_children':True}], 'has_more':True,'next_cursor':'next'}
            elif '/root/' in request.url: data={'results':[], 'has_more':False,'next_cursor':None}
            else: data={'results':[{'id':'leaf','has_children':False}], 'has_more':False,'next_cursor':None}
            return Response(json.dumps(data,indent=2).encode(),{})
        config={'provider':'notion','block':'root'}
        b=capture_collection(config,'doc',[],max_requests=1,transport=transport)
        index=json.loads(b['files']['collection.json'])
        self.assertEqual(index['status'],'partial');self.assertEqual(len(index['pending']),2)
        with tempfile.TemporaryDirectory() as tmp:
            write_bundle(Path(tmp)/'page',b)
            done=capture_collection(config,'doc',[],resume=Path(tmp)/'page',transport=transport)
        idx=json.loads(done['files']['collection.json'])
        self.assertEqual(idx['status'],'complete_within_scope')
        self.assertEqual(len(calls),3);self.assertEqual(len(set(calls)),3)
        self.assertEqual(done['files']['pages/0000.json'],b['files']['pages/0000.json'])
        self.assertTrue(all('credential' not in json.dumps(x) for x in idx['pages']))
        self.assertEqual(done['manifest']['verification'],'unverified')

    def test_slack_threads_and_cursor_pages_are_collected(self):
        calls=[]
        def transport(req,ref):
            calls.append(req.url)
            if 'conversations.history' in req.url:
                obj={'ok':True,'messages':[{'ts':'5.0','reply_count':2}], 'has_more':False}
            elif 'cursor=' not in req.url:
                obj={'ok':True,'messages':[{'ts':'5.0'},{'ts':'6.0','thread_ts':'5.0'}],
                     'has_more':True,'response_metadata':{'next_cursor':'second'}}
            else: obj={'ok':True,'messages':[{'ts':'7.0','thread_ts':'5.0'}], 'has_more':False}
            return Response(json.dumps(obj).encode(),{})
        b=capture_collection({'provider':'slack','channel':'C1','oldest':'1.0','latest':'10.0'},
                             'messages',[],transport=transport)
        idx=json.loads(b['files']['collection.json'])
        self.assertEqual(idx['status'],'complete_within_scope');self.assertEqual(len(calls),3)
        self.assertIn('ts=5.0',calls[1]);self.assertIn('cursor=second',calls[2])

    def test_rate_limit_keeps_completed_pages_and_retryable_queue(self):
        count=0
        def transport(req,ref):
            nonlocal count
            count+=1
            if count==2: raise Fault('rate_limited','private remote information')
            return Response(b'{"results":[],"has_more":true,"next_cursor":"next"}',{})
        b=capture_collection({'provider':'notion','block':'root'},'doc',[],transport=transport)
        idx=json.loads(b['files']['collection.json'])
        self.assertEqual(len(idx['pages']),1);self.assertEqual(idx['stopped_reason'],'rate_limited')
        self.assertEqual(len(idx['pending']),1)
        self.assertNotIn('private',json.dumps(idx))

    def test_cursor_cycle_and_depth_limit_are_not_complete(self):
        def cycle(req,ref): return Response(b'{"results":[],"has_more":true,"next_cursor":"loop"}',{})
        b=capture_collection({'provider':'notion','block':'root'},'doc',[],transport=cycle)
        self.assertEqual(json.loads(b['files']['collection.json'])['status'],'partial')
        self.assertIn('cursor_cycle',b['manifest']['missing'])
        def deep(req,ref):return Response(b'{"results":[{"id":"child","has_children":true}],"has_more":false}',{})
        b=capture_collection({'provider':'notion','block':'root'},'doc',[],max_depth=0,transport=deep)
        self.assertIn('depth_limit',b['manifest']['missing'])

    def test_malformed_pages_and_endpoint_escape_do_not_follow_untrusted_links(self):
        for raw in (b'{"results":[{}],"has_more":false}',
                    b'{"results":[],"has_more":true}',
                    b'{"results":[{"id":"../users","has_children":true}],"has_more":false}'):
            calls=[]
            def malformed(req,ref):calls.append(req.url);return Response(raw,{})
            b=capture_collection({'provider':'notion','block':'root'},'doc',[],transport=malformed)
            self.assertEqual(json.loads(b['files']['collection.json'])['status'],'partial')
            self.assertEqual(len(calls),1)

    def test_resume_must_keep_same_scope_and_requirement_links(self):
        def page(req,ref):return Response(b'{"results":[],"has_more":true,"next_cursor":"n"}',{})
        b=capture_collection({'provider':'notion','block':'root'},'doc',[],max_requests=1,transport=page)
        with tempfile.TemporaryDirectory() as tmp:
            write_bundle(Path(tmp)/'cap',b)
            with self.assertRaises(Fault):
                capture_collection({'provider':'notion','block':'different'},'doc',[],resume=Path(tmp)/'cap',transport=page)

    def test_request_limit_does_not_drop_pending_work(self):
        def page(req,ref):return Response(b'{"results":[],"has_more":true,"next_cursor":"n"}',{})
        b=capture_collection({'provider':'notion','block':'root'},'doc',[],max_requests=1,transport=page)
        idx=json.loads(b['files']['collection.json'])
        self.assertEqual(idx['stopped_reason'],'request_limit')
        self.assertEqual(idx['pending'][0]['config']['cursor'],'n')

    def test_resume_queue_must_be_derived_from_captured_pages(self):
        from gantry.integrations.bundle import make_bundle
        def page(req,ref):return Response(b'{"results":[],"has_more":true,"next_cursor":"n"}',{})
        cfg={'provider':'notion','block':'root'}
        b=capture_collection(cfg,'doc',[],max_requests=1,transport=page)
        idx=json.loads(b['files']['collection.json']);idx['pending'][0]['config']['block']='unrelated'
        files={**b['files'],'collection.json':json.dumps(idx).encode()}
        forged=make_bundle('notion','doc',files,[],source=b['manifest']['source'],missing=b['manifest']['missing'])
        with tempfile.TemporaryDirectory() as tmp:
            write_bundle(Path(tmp)/'cap',forged)
            with self.assertRaises(Fault):capture_collection(cfg,'doc',[],resume=Path(tmp)/'cap',transport=page)
