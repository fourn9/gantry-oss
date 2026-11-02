"""Explicit native update recipes; no caller-controlled methods, URLs or auth headers."""
import base64
import copy
import math
import re
from urllib.parse import quote, urlencode
from ..model import Fault, canonical, require
from .bundle import safe_file
from .providers import request_for
from .transport import ReadRequest, parse_json, send

TARGETS = {
    ('github','file.update'): {'repository','branch','path'},
    ('github','issue.update'): {'repository','number'},
    ('gitlab','file.update'): {'project','branch','path'},
    ('confluence','page.update'): {'site','page'},
    ('jira','issue.update'): {'site','issue'},
    ('linear','issue.update'): {'issue'},
    ('notion','paragraph.update'): {'block'},
    ('google-drive','metadata.update'): {'file'},
    ('google-sheets','values.update'): {'spreadsheet','range'},
    ('excel','values.update'): {'item','sheet','range'},
    ('sharepoint','metadata.update'): {'drive','item'},
    ('slack','message.update'): {'channel','ts'},
    ('onshape','parameters.update'): {'document','workspace','element','feature'}}
OPERATIONS = {p: {op for provider,op in TARGETS if provider==p} for p,_ in TARGETS}
ATOMIC = {('github','file.update'),('gitlab','file.update'),('confluence','page.update'),
          ('sharepoint','metadata.update'),('onshape','parameters.update')}
TEXT_FIELDS = {'issue.update': {'title','body'}, 'page.update': {'title','storage'},
               'paragraph.update': {'text'}, 'metadata.update': {'name','description'},
               'message.update': {'text'}}


def cell_shape(value):
    m = re.fullmatch(r"(?:[^!]+!)?([A-Z]{1,3})([1-9][0-9]{0,6})(?::([A-Z]{1,3})([1-9][0-9]{0,6}))?", value)
    require(m, 'invalid_input', 'Explicit bounded A1 range required')
    def col(v):
        n=0
        for c in v: n=n*26+ord(c)-64
        return n
    x1,y1=col(m[1]),int(m[2]); x2,y2=col(m[3] or m[1]),int(m[4] or m[2])
    require(x1<=x2<=16384 and y1<=y2<=1048576 and (x2-x1+1)*(y2-y1+1)<=1000,
            'invalid_input','Range must contain 1–1000 cells')
    return y2-y1+1,x2-x1+1


def validate(config, change):
    require(isinstance(config,dict) and isinstance(change,dict),'invalid_input','Target and change objects required')
    pair=(config.get('provider'),config.get('operation'))
    require(all(isinstance(v,str) for v in pair) and pair in TARGETS,'unsupported','Native update operation is not supported')
    require(set(config)==TARGETS[pair]|{'provider','operation'},'invalid_input','Exact native target fields required')
    for key,value in config.items():
        require(isinstance(value,str) and 0<len(value)<=1000 and not any(ord(c)<32 for c in value),
                'invalid_input','Bounded target strings required')
        require('\\' not in value and all(p not in {'','.','..'} for p in value.split('/')),
                'invalid_input','Invalid target identifier')
    require(len(canonical(change).encode())<=1024*1024,'acquisition_limit','Update exceeds 1 MiB')
    p,op=pair
    if p=='github':
        from ..github_connector import validate_repository
        validate_repository(config['repository'])
    if op=='file.update':
        safe_file(config['path'])
        require(not config['path'].startswith('/'),'invalid_input','Relative repository path required')
        require(set(change)=={'content','message'} and isinstance(change['content'],str)
                and isinstance(change['message'],str) and 0<len(change['message'])<=1000,
                'invalid_input','UTF-8 file content and commit message required')
    elif op=='parameters.update':
        for k in ('document','workspace','element'):
            require(re.fullmatch('[a-f0-9]{24}',config[k]),'invalid_input','Onshape document/workspace/element IDs required')
        require(set(change)=={'expressions'} and isinstance(change['expressions'],dict)
                and 1<=len(change['expressions'])<=100,'invalid_input','Named parameter expressions required')
        for k,v in change['expressions'].items():
            require(isinstance(k,str) and 0<len(k)<=200 and isinstance(v,str) and 0<len(v)<=2000,
                    'invalid_input','Bounded parameter ID and expression required')
    elif op=='values.update':
        rows,cols=cell_shape(config['range']); values=change.get('values')
        require(set(change)=={'values'} and isinstance(values,list) and len(values)==rows
                and all(isinstance(r,list) and len(r)==cols for r in values),'invalid_input','Values must fill exactly the target range')
        for row in values:
            for v in row:
                require(type(v) in (str,int,float,bool) and (not isinstance(v,float) or math.isfinite(v)),
                        'invalid_input','Finite scalar cell values required; use empty string to clear')
                if p=='excel' and isinstance(v,str):
                    require(not v.lstrip().startswith(('=','+','-','@')),'invalid_input','Formula-like Excel text is not supported')
    else:
        allowed=TEXT_FIELDS[op]
        if p=='jira': allowed={'summary','description'}
        if p=='linear': allowed={'title','description'}
        if p=='sharepoint': allowed={'name'}
        require(0<len(change) and set(change)<=allowed and all(isinstance(v,str) and len(v)<=50000 for v in change.values()),
                'invalid_input','Only supported text fields may be changed')
        if op=='page.update': require(set(change)=={'title','storage'},'invalid_input','Full title/storage page replacement required')
        if p=='notion': require(len(change['text'])<=2000,'invalid_input','One Notion paragraph update supports at most 2000 characters')
        for k in {'title','summary','name'} & change.keys():
            require(0<len(change[k])<=500,'invalid_input','Nonempty bounded title/name required')
        if 'name' in change:
            require(not any(c in change['name'] for c in '/\\\r\n') and change['name'] not in {'.','..'},'invalid_input','Simple filename required')
    if p=='slack': require(re.fullmatch('[A-Z0-9]+',config['channel']) and re.fullmatch('[0-9]+\\.[0-9]+',config['ts']),
                            'invalid_input','Slack channel and exact message timestamp required')
    # Also validate existing product-specific target schemas through their read recipes.
    read_request(config)
    return pair


def read_request(c):
    p,op=c['provider'],c['operation']; q=lambda key:quote(c[key],safe='')
    if op=='file.update':
        if p=='github':
            base='https://api.github.com/repos/'+c['repository']+'/contents/'+quote(c['path'],safe='/')
            return ReadRequest(base+'?'+urlencode({'ref':c['branch']}),headers={
                'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
        return ReadRequest('https://gitlab.com/api/v4/projects/'+q('project')+'/repository/files/'+q('path')+'?'+urlencode({'ref':c['branch']}))
    if p=='notion': return ReadRequest('https://api.notion.com/v1/blocks/'+q('block'),headers={'Notion-Version':'2022-06-28'})
    if p=='google-drive':
        return ReadRequest('https://www.googleapis.com/drive/v3/files/'+q('file')+'?'+urlencode({'fields':'id,name,description,version,mimeType'}))
    if p=='onshape':
        return ReadRequest('https://cad.onshape.com/api/v9/partstudios/d/'+q('document')+'/w/'+q('workspace')+'/e/'+q('element')+'/features')
    if p=='slack':
        return ReadRequest('https://slack.com/api/conversations.history?'+urlencode({
            'channel':c['channel'],'oldest':c['ts'],'latest':c['ts'],'inclusive':'true','limit':1}))
    cfg={k:v for k,v in c.items() if k!='operation'}
    req=request_for(cfg)
    if p=='google-sheets':
        return ReadRequest(req.url.replace('UNFORMATTED_VALUE','FORMULA'),headers=req.headers)
    return req


def _text_fields(data,fields):
    result={}
    for k in fields:
        value=data.get(k)
        require(value is None or isinstance(value,str),'invalid_response','Text field expected')
        result[k]=value or ''
    return result


def _decode_file(data):
    require(data.get('encoding')=='base64' and isinstance(data.get('content'),str),'invalid_response','Base64 file required')
    try: return base64.b64decode(''.join(data['content'].split()),validate=True).decode('utf-8')
    except (ValueError,UnicodeError): raise Fault('invalid_response','UTF-8 repository content required') from None


def observe(config,change,credential_ref,transport=send):
    validate(config,change)
    try:
        return _observe(config,change,credential_ref,transport)
    except (ValueError,TypeError,KeyError,AttributeError,IndexError,RecursionError):
        raise Fault('invalid_response','Native response does not match the expected object schema') from None


def _observe(config,change,credential_ref,transport):
    validate(config,change); p,op=config['provider'],config['operation']
    response=transport(read_request(config),credential_ref)
    require(isinstance(response.raw,bytes) and len(response.raw)<=2*1024*1024,'acquisition_limit','Write observations are limited to 2 MiB')
    data=parse_json(response.raw)
    require(isinstance(data,dict) and not data.get('errors') and not data.get('error'),'invalid_response','Expected successful object response')
    revision=None; extra={}; desired=copy.deepcopy(change)
    if op=='file.update':
        key='path' if p=='github' else 'file_path'
        require(data.get(key)==config['path'] and (p!='github' or data.get('type')=='file'), 'invalid_response','Requested regular file required')
        revision=data.get('sha') if p=='github' else data.get('last_commit_id')
        require(isinstance(revision,str) and re.fullmatch('[a-f0-9]{40,64}',revision),'invalid_response','File revision required')
        value={'content':_decode_file(data)};desired={'content':change['content']}
    elif p=='github':
        require(data.get('number')==int(config['number']),'invalid_response','Requested issue required')
        value=_text_fields(data,change);revision=data.get('updated_at')
    elif p=='confluence':
        require(str(data.get('id'))==config['page'] and data.get('status')=='current','invalid_response','Published current page required')
        revision=data.get('version',{}).get('number')
        require(type(revision) is int and revision>0,'invalid_response','Page version required')
        value={'title':data['title'],'storage':data['body']['storage']['value']}
    elif p=='jira':
        require(config['issue'] in {data.get('key'),data.get('id')} and isinstance(data.get('fields'),dict),'invalid_response','Requested issue required')
        value={k:data['fields'].get(k) for k in change};revision=data['fields'].get('updated')
        if 'description' in change:
            desired['description']={'version':1,'type':'doc','content':[
                {'type':'paragraph','content':[{'type':'text','text':change['description']}]}] if change['description'] else []}
    elif p=='linear':
        obj=data.get('data',{}).get('issue')
        require(isinstance(obj,dict) and config['issue'] in {obj.get('id'),obj.get('identifier')},'invalid_response','Requested issue required')
        value=_text_fields(obj,change);revision=obj.get('updatedAt');extra['native_id']=obj['id']
    elif p=='notion':
        require(data.get('id','').replace('-','')==config['block'].replace('-','') and data.get('type')=='paragraph'
                and not data.get('archived') and not data.get('in_trash'),'invalid_response','Active paragraph required')
        value={'text':''.join(v.get('plain_text',v.get('text',{}).get('content','')) for v in data['paragraph']['rich_text'])}
        revision=data.get('last_edited_time')
    elif p=='google-drive':
        require(data.get('id')==config['file'],'invalid_response','Requested Drive file required')
        value=_text_fields(data,change);revision=data.get('version')
    elif op=='values.update':
        address=data.get('range') or data.get('address')
        require(isinstance(address,str) and address.rsplit('!',1)[-1]==config['range'].rsplit('!',1)[-1],
                'invalid_response','Requested range response required')
        rows,cols=cell_shape(config['range']);returned=data.get('values',[])
        require(isinstance(returned,list) and len(returned)<=rows and all(isinstance(r,list) and len(r)<=cols for r in returned),
                'invalid_response','Range values exceed requested shape')
        values=[[(returned[r][c] if r<len(returned) and c<len(returned[r]) else '') for c in range(cols)] for r in range(rows)]
        value={'values':values}
        if p=='excel': extra['formulas']=data.get('formulas')
    elif p=='sharepoint':
        require(data.get('id')==config['item'],'invalid_response','Requested drive item required')
        revision=data.get('eTag')
        require(isinstance(revision,str) and 0<len(revision)<=1000 and not any(ord(c)<32 for c in revision),'invalid_response','Valid ETag required')
        value=_text_fields(data,change)
    elif p=='slack':
        messages=data.get('messages',[])
        require(data.get('ok') is True and len(messages)==1 and messages[0].get('ts')==config['ts'],
                'not_found','Exact message not returned')
        msg=messages[0]
        require(not msg.get('blocks') and not msg.get('attachments'),'unsupported','Only plain-text messages can be replaced')
        value={'text':msg.get('text','')};revision=msg.get('edited',{}).get('ts',msg['ts'])
    else: # Onshape
        features=data.get('features',[])
        feature=next((f for f in features if f.get('featureId')==config['feature']),None)
        revision=data.get('sourceMicroversion')
        require(feature and isinstance(revision,str) and re.fullmatch('[a-f0-9]{24}',revision)
                and isinstance(data.get('serializationVersion'),str) and type(data.get('libraryVersion')) is int,
                'invalid_response','Existing feature and serialization/microversion required')
        params=feature.get('parameters',[]);ids=[v.get('parameterId') for v in params]
        require(all(ids.count(k)==1 and isinstance(params[ids.index(k)].get('expression'),str) for k in change['expressions']),
                'unsupported','Only existing expression parameters may be changed')
        value={'expressions':{k:params[ids.index(k)]['expression'] for k in change['expressions']}}
        extra={'feature':feature,'serializationVersion':data['serializationVersion'],'libraryVersion':data['libraryVersion']}
    return {'raw':response.raw,'baseline':{'revision':revision,'value':value,**extra},'desired':desired}


def write_request(config,change,baseline):
    validate(config,change);p,op=config['provider'],config['operation'];req=read_request(config)
    url=req.url.split('?')[0];headers=dict(req.headers);auth=req.auth;method='PATCH';body=copy.deepcopy(change)
    if op=='file.update':
        method='PUT'
        if p=='github': body={'message':change['message'],'content':base64.b64encode(change['content'].encode()).decode(),
                             'branch':config['branch'],'sha':baseline['revision']}
        else: body={'branch':config['branch'],'content':change['content'],'encoding':'text',
                    'commit_message':change['message'],'last_commit_id':baseline['revision']}
    elif p=='confluence':
        method='PUT';body={'id':config['page'],'status':'current','title':change['title'],
            'body':{'representation':'storage','value':change['storage']},'version':{'number':baseline['revision']+1}}
    elif p=='jira':
        method='PUT';body={'fields':copy.deepcopy(change)}
        if 'description' in change:
            body['fields']['description']={'version':1,'type':'doc','content':[
                {'type':'paragraph','content':[{'type':'text','text':change['description']}]}] if change['description'] else []}
    elif p=='linear':
        method='POST';body={'query':'mutation($id:String!,$input:IssueUpdateInput!){issueUpdate(id:$id,input:$input){success issue{id updatedAt}}}',
                            'variables':{'id':baseline['native_id'],'input':change}}
    elif p=='notion': body={'paragraph':{'rich_text':[{'type':'text','text':{'content':change['text']}}] if change['text'] else []}}
    elif p=='google-sheets':
        method='PUT';url+='?valueInputOption=RAW';body={'range':config['range'],'majorDimension':'ROWS','values':change['values']}
    elif p=='sharepoint':headers['If-Match']=baseline['revision']
    elif p=='slack':
        method='POST';url='https://slack.com/api/chat.update';body={'channel':config['channel'],'ts':config['ts'],
            'text':change['text'],'parse':'none','link_names':False,'mrkdwn':False}
    elif p=='onshape':
        method='POST';url+='/featureid/'+quote(config['feature'],safe='');feature=copy.deepcopy(baseline['feature'])
        for param in feature['parameters']:
            if param.get('parameterId') in change['expressions']:param['expression']=change['expressions'][param['parameterId']]
        body={'btType':'BTFeatureDefinitionCall-1406','feature':feature,'sourceMicroversion':baseline['revision'],
              'rejectMicroversionSkew':True,'serializationVersion':baseline['serializationVersion'],'libraryVersion':baseline['libraryVersion']}
    return ReadRequest(url,method,canonical(body).encode(),headers,auth)


def check_response(config,response):
    if not response.raw:
        require(config['provider']=='jira','invalid_response','Missing native write response');return
    data=parse_json(response.raw)
    require(isinstance(data,dict) and not data.get('error') and not data.get('errors'),'remote_error','Native update returned an error')
    p=config['provider']
    if p=='slack':require(data.get('ok') is True,'remote_error','Slack update refused')
    if p=='linear':require(data.get('data',{}).get('issueUpdate',{}).get('success') is True,'remote_error','Linear update refused')
    if p=='onshape':require(not data.get('microversionSkew'),'remote_error','Onshape microversion mismatch')
