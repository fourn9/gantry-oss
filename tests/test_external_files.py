import hashlib
import io
import json
import unittest
from unittest.mock import patch
from gantry.model import Fault
from gantry.integrations.transport import Response
from gantry.integrations.files import capture_file, download_sharepoint


class CloudFileTests(unittest.TestCase):
    def google_meta(self, raw=b'native file', version='7'):
        return {'id':'file1','name':'part.step','mimeType':'application/octet-stream','version':version,
                'size':str(len(raw)),'md5Checksum':hashlib.md5(raw).hexdigest(),'capabilities':{'canDownload':True}}

    def test_google_binary_preserved_and_version_bracketed(self):
        raw=b'native file';calls=[]
        def transport(req,ref):
            calls.append(req.url)
            return Response(raw if 'alt=media' in req.url else json.dumps(self.google_meta()).encode(),{})
        b=capture_file({'provider':'google-drive','file':'file1'},'part',[],transport=transport)
        self.assertEqual(b['files']['content.bin'],raw)
        self.assertEqual(b['manifest']['source_revision'],'7')
        self.assertEqual(len(calls),3);self.assertEqual(calls[0],calls[2])
        self.assertEqual(b['manifest']['verification'],'unverified')

    def test_google_remote_change_or_checksum_mismatch_fails(self):
        for change in ('version','checksum','size','identity'):
            calls=[]
            def transport(req,ref):
                calls.append(req.url);meta=self.google_meta()
                if 'alt=media' in req.url:return Response(b'native file',{})
                if change=='version' and len(calls)==3:meta['version']='8'
                if change=='checksum':meta['md5Checksum']='0'*32
                if change=='size':meta['size']='999'
                if change=='identity':meta['id']='different'
                return Response(json.dumps(meta).encode(),{})
            with self.subTest(change=change),self.assertRaises(Fault):
                capture_file({'provider':'google-drive','file':'file1'},'part',[],transport=transport)

    def test_google_native_document_and_download_denial_not_treated_as_blob(self):
        for override in ({'mimeType':'application/vnd.google-apps.document'}, {'capabilities':{'canDownload':False}}):
            def transport(req,ref):return Response(json.dumps({**self.google_meta(),**override}).encode(),{})
            with self.assertRaises(Fault):capture_file({'provider':'google-drive','file':'file1'},'part',[],transport=transport)

    def test_sharepoint_content_url_is_ephemeral_and_does_not_receive_credentials(self):
        raw=b'CAD original';signed='https://tenant.sharepoint.com/sites/team/file?tempauth=private-value'
        def transport(req,ref):
            meta={'id':'part','name':'board.native','size':len(raw),'file':{'mimeType':'application/octet-stream'},
                  'eTag':'tag1','@microsoft.graph.downloadUrl':signed}
            return Response(json.dumps(meta).encode(),{})
        def downloader(url,host):
            self.assertEqual(host,'tenant.sharepoint.com');self.assertEqual(url,signed)
            return raw
        b=capture_file({'provider':'sharepoint','drive':'d','item':'part','download_host':'tenant.sharepoint.com',
                        'credential_ref':'GANTRY_CONNECTOR_TEST'},'part',[],transport=transport,downloader=downloader)
        self.assertEqual(b['files']['content.bin'],raw)
        self.assertNotIn(b'private-value',b''.join(b['files'].values()))
        self.assertNotIn('downloadUrl',json.dumps(b['manifest']))

    def test_sharepoint_stale_version_does_not_publish_mixed_capture(self):
        n=0
        def transport(req,ref):
            nonlocal n;n+=1
            return Response(json.dumps({'id':'part','name':'x','size':1,'file':{},'eTag':str(n),
                '@microsoft.graph.downloadUrl':'https://tenant.sharepoint.com/file'}).encode(),{})
        with self.assertRaises(Fault):capture_file({'provider':'sharepoint','drive':'d','item':'part',
            'download_host':'tenant.sharepoint.com'},'part',[],transport=transport,downloader=lambda *a:b'x')

    def test_download_rejects_host_escape_credentials_redirects_and_private_dns(self):
        for url in ['http://tenant.sharepoint.com/file','https://tenant.sharepoint.com.evil.test/file',
                    'https://user:pass@tenant.sharepoint.com/file','https://tenant.sharepoint.com:444/file',
                    'https://tenant.sharepoint.com/file#fragment']:
            with self.subTest(url=url),self.assertRaises(Fault):download_sharepoint(url,'tenant.sharepoint.com')
        with patch('gantry.integrations.files.socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]):
            with self.assertRaises(Fault):download_sharepoint('https://tenant.sharepoint.com/file','tenant.sharepoint.com')

    def test_download_no_auth_no_redirect_and_bounded_bytes(self):
        class Reply(io.BytesIO):
            status=200
        with patch('gantry.integrations.files.socket.getaddrinfo',return_value=[(2,1,6,'',('8.8.8.8',443))]), \
             patch('gantry.integrations.files.PinnedDownload') as connect:
            c=connect.return_value;c.getresponse.return_value=Reply(b'xyz')
            self.assertEqual(download_sharepoint('https://tenant.sharepoint.com/file?sig=private','tenant.sharepoint.com'),b'xyz')
            kwargs=c.request.call_args.kwargs
            self.assertNotIn('Authorization',kwargs['headers'])
            self.assertEqual(connect.call_args.args[1],'8.8.8.8')
            c.getresponse.return_value=Reply(b'xyz');c.getresponse.return_value.status=302
            with self.assertRaises(Fault) as e:download_sharepoint('https://tenant.sharepoint.com/file?sig=private','tenant.sharepoint.com')
            self.assertNotIn('private',str(e.exception))
            c.getresponse.return_value=Reply(b'xyz')
            with patch('gantry.integrations.files.MAX_RESPONSE',2),self.assertRaises(Fault):
                download_sharepoint('https://tenant.sharepoint.com/file','tenant.sharepoint.com')
