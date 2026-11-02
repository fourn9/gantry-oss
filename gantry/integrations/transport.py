"""Bounded HTTPS transport for locally invoked, fixed SaaS read recipes."""
import base64
import json
import re
import time
from dataclasses import dataclass, field
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler
from ..github_connector import NoRedirect, credential
from ..model import Fault, require

MAX_RESPONSE = 8 * 1024 * 1024
HOSTS = {'api.github.com','gitlab.com','api.linear.app','api.notion.com','www.googleapis.com',
         'sheets.googleapis.com','graph.microsoft.com','slack.com','cad.onshape.com'}


@dataclass(frozen=True)
class ReadRequest:
    url: str
    method: str = 'GET'
    body: bytes | None = None
    headers: dict = field(default_factory=dict)
    auth: str = 'bearer'


@dataclass(frozen=True)
class Response:
    raw: bytes
    headers: dict


def parse_json(raw):
    try:
        def reject(value): raise ValueError('Non-finite number')
        return json.loads(raw, parse_constant=reject)
    except (ValueError, UnicodeError):
        raise Fault('invalid_response','Remote response is not strict JSON') from None


def validate_target(url):
    try:
        p=urlsplit(url); port=p.port
    except ValueError: raise Fault('scope_denied','Invalid SaaS endpoint') from None
    require(p.scheme=='https' and port in (None,443) and not p.username and not p.password
            and not p.fragment and (p.hostname in HOSTS or
            re.fullmatch(r'[a-z0-9][a-z0-9-]{0,62}\.atlassian\.net',p.hostname or '')),
            'scope_denied','Only fixed public SaaS endpoints are supported')


def send(request, credential_ref):
    validate_target(request.url)
    require(request.method in {'GET','POST'} and (request.method!='POST' or
            request.url=='https://api.linear.app/graphql'), 'scope_denied','Read recipe required')
    if request.method == 'POST':
        query = parse_json(request.body).get('query', '').strip()
        require(query.startswith('query') and 'mutation' not in query,
                'scope_denied', 'Read transport rejects GraphQL mutations')
    return _exchange(request, credential_ref)


def send_write(config, change, baseline, credential_ref):
    # Rebuild a fixed provider recipe; callers cannot submit an arbitrary URL/method.
    from .write_recipes import write_request
    require(bool(credential_ref), 'credential_missing', 'Explicit write credential reference required')
    request = write_request(config, change, baseline)
    validate_target(request.url)
    return _exchange(request, credential_ref)


def _exchange(request, credential_ref):
    token=credential(credential_ref)
    require(token or urlsplit(request.url).hostname=='api.github.com', 'credential_missing','Credential reference required')
    headers={'Accept':'application/json','User-Agent':'Gantry-integrations/1',**request.headers}
    if token:
        require(token not in request.url and token.encode() not in (request.body or b''),
                'credential_detected','Configured credential found in request data')
        if request.auth=='basic': value='Basic '+base64.b64encode(token.encode()).decode()
        elif request.auth=='raw': value=token
        else: value='Bearer '+token
        headers['Authorization']=value
    if request.body is not None: headers.setdefault('Content-Type','application/json')
    opener=build_opener(ProxyHandler({}),NoRedirect())
    try:
        deadline=time.monotonic()+30
        with opener.open(Request(request.url,data=request.body,method=request.method,headers=headers),timeout=15) as result:
            chunks=[];size=0
            while True:
                require(time.monotonic()<deadline,'acquisition_limit','Acquisition deadline reached')
                block=result.read1(min(65536,MAX_RESPONSE+1-size))
                if not block: break
                size+=len(block);require(size<=MAX_RESPONSE,'acquisition_limit','Response exceeds 8 MiB');chunks.append(block)
            raw=b''.join(chunks)
            if token:
                require(token.encode() not in raw and headers['Authorization'].split(' ',1)[-1].encode() not in raw,
                        'credential_detected','Response contains a configured credential; not captured')
            # Never save cookies, download URLs or authorization headers.
            kept={k.lower():result.headers[k] for k in ('ETag','Last-Modified','Content-Type') if k in result.headers}
            if 'rel="next"' in result.headers.get('Link',''): kept['link']='rel="next"'
            return Response(raw,kept)
    except HTTPError as exc:
        code='rate_limited' if exc.code==429 else 'remote_http_'+str(exc.code)
        raise Fault(code,'Remote request refused; check credential scope or retry later') from None
    except (URLError,OSError,TimeoutError):
        raise Fault('remote_unavailable','Remote request failed; no response body or credentials logged') from None
