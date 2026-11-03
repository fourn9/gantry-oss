"""Selected cloud file bytes with revision checks and credential-isolated download."""
import hashlib
import http.client
import ipaddress
import re
import socket
import ssl
import time
from urllib.parse import urlencode, urlsplit
from ..model import Fault, require, canonical
from .bundle import make_bundle
from .providers import request_for
from .transport import ReadRequest, MAX_RESPONSE, send, parse_json


class PinnedDownload(http.client.HTTPSConnection):
    """Connect only to a checked IP while verifying TLS against the tenant hostname."""
    def __init__(self,host,address):
        super().__init__(host,443,timeout=15,context=ssl.create_default_context())
        self.address=address

    def connect(self):
        sock=socket.create_connection((self.address,443),timeout=self.timeout)
        try:self.sock=self._context.wrap_socket(sock,server_hostname=self.host)
        except BaseException:sock.close();raise


def download_sharepoint(url,host):
    require(isinstance(host,str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,62}\.sharepoint\.com',host),
            'scope_denied','Explicit tenant.sharepoint.com content host required')
    require(isinstance(url,str) and 0<len(url)<=12000 and all(32<ord(c)<127 for c in url),
            'scope_denied','Invalid signed content URL')
    try:target=urlsplit(url);port=target.port
    except ValueError:raise Fault('scope_denied','Invalid content location') from None
    require(target.scheme=='https' and target.hostname==host and port in {None,443}
            and not target.username and not target.password and not target.fragment,
            'scope_denied','Content location differs from the configured tenant')
    connection=None;deadline=time.monotonic()+30
    try:
        addresses={entry[4][0] for entry in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)}
        require(addresses and all(ipaddress.ip_address(a).is_global for a in addresses),
                'scope_denied','Content host did not resolve exclusively to public addresses')
        require(time.monotonic()<deadline,'acquisition_limit','Content acquisition deadline reached')
        connection=PinnedDownload(host,sorted(addresses)[0])
        # Preauthenticated URL: never send the Graph bearer token, cookies or a Referer.
        connection.request('GET',target.path+('?' + target.query if target.query else ''),
                           headers={'Accept':'application/octet-stream','User-Agent':'Gantry-integrations/1'})
        response=connection.getresponse()
        require(response.status==200,'remote_http_error','Content download refused; redirects are not followed')
        chunks=[];size=0
        while True:
            require(time.monotonic()<deadline,'acquisition_limit','Content acquisition deadline reached')
            block=response.read1(min(65536,MAX_RESPONSE+1-size))
            if not block:break
            size+=len(block);require(size<=MAX_RESPONSE,'acquisition_limit','Content exceeds 8 MiB')
            chunks.append(block)
        return b''.join(chunks)
    except (OSError,ValueError,http.client.HTTPException):
        raise Fault('remote_unavailable','Content acquisition failed; signed URLs are not logged') from None
    finally:
        if connection:connection.close()


def _metadata(response,provider,identity):
    require(isinstance(response.raw,bytes) and len(response.raw)<=MAX_RESPONSE,
            'acquisition_limit','Bounded metadata required')
    data=parse_json(response.raw)
    require(isinstance(data,dict) and data.get('id')==identity and not data.get('error'),
            'invalid_response','Requested file metadata not returned')
    if provider=='google-drive':
        keys=('id','name','mimeType','size','version','md5Checksum','capabilities','trashed')
        require(isinstance(data.get('mimeType'),str) and not data['mimeType'].startswith('application/vnd.google-apps.')
                and not data.get('trashed'),'unsupported','Select a non-trashed blob file; use pull for Google document export')
        require(isinstance(data.get('capabilities'),dict) and data['capabilities'].get('canDownload') is True,
                'scope_denied','Provider does not allow downloading this file')
        marker=data.get('version')
    else:
        keys=('id','name','eTag','cTag','size','lastModifiedDateTime','file')
        require(isinstance(data.get('file'),dict),'unsupported','A file item is required')
        marker=data.get('eTag')
    require(isinstance(marker,str) and 0<len(marker)<=1000,'invalid_response','File revision marker required')
    size=data.get('size')
    require((type(size) is int or isinstance(size,str) and re.fullmatch(r'[0-9]{1,12}',size))
            and 0<=int(size)<=MAX_RESPONSE,'acquisition_limit','Bounded file size required (8 MiB maximum)')
    # Signed URLs and unselected metadata never enter persisted evidence.
    return {k:data[k] for k in keys if k in data},marker,data.get('@microsoft.graph.downloadUrl')


def capture_file(config,source_id,refs,*,transport=send,downloader=download_sharepoint):
    require(isinstance(config,dict) and config.get('provider') in {'google-drive','sharepoint'},
            'unsupported','File content capture supports Google Drive and SharePoint')
    provider=config['provider'];host=config.get('download_host')
    base={k:v for k,v in config.items() if k!='download_host'}
    req=request_for(base)
    if provider=='google-drive':
        require('download_host' not in config and 'format' not in config,'invalid_input','Blob capture does not accept export options')
        url=req.url.split('/export?',1)[0]
        fields='id,name,mimeType,size,version,md5Checksum,capabilities(canDownload),trashed'
        req=ReadRequest(url+'?'+urlencode({'fields':fields,'supportsAllDrives':'true'}))
        identity=config['file']
    else:
        require(isinstance(host,str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,62}\.sharepoint\.com',host),
                'scope_denied','Configure the expected SharePoint content host before download')
        url=req.url.split('?',1)[0];identity=config['item']
        fields='id,name,eTag,cTag,size,lastModifiedDateTime,file,@microsoft.graph.downloadUrl'
        req=ReadRequest(url+'?'+urlencode({'$select':fields}))
    ref=config.get('credential_ref')
    before,marker,location=_metadata(transport(req,ref),provider,identity)
    # Source: Drive files.get alt=media / Graph driveItem @microsoft.graph.downloadUrl.
    if provider=='google-drive':
        raw=transport(ReadRequest(url+'?alt=media&supportsAllDrives=true'),ref).raw
    else:
        raw=downloader(location,host)
    require(isinstance(raw,bytes) and len(raw)==int(before['size']) and len(raw)<=MAX_RESPONSE,
            'integrity_error','Downloaded bytes do not match the declared size')
    after,next_marker,_=_metadata(transport(req,ref),provider,identity)
    require(before==after and marker==next_marker,'stale_basis','File changed during acquisition; no mixed snapshot saved')
    if provider=='google-drive' and before.get('md5Checksum'):
        require(hashlib.md5(raw,usedforsecurity=False).hexdigest()==before['md5Checksum'],
                'integrity_error','Provider file checksum differs from captured content')
    return make_bundle(provider,source_id,{'content.bin':raw,
        'metadata-before.json':canonical(before).encode(),'metadata-after.json':canonical(after).encode()},refs,
        source={**{k:v for k,v in config.items() if k not in {'provider','credential_ref'}},
                'capture_mode':'file_content','revision_semantics':'before_after_marker_check_not_atomic_transaction'},
        source_revision=marker,missing=['Earlier revisions and dependent files not captured',
            'Selected metadata only; ephemeral content credentials excluded','Native application restore not verified'])
