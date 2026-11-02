"""Product-specific read recipes. Identifiers are data; no arbitrary endpoint API."""
import re
from urllib.parse import quote, urlencode
from ..model import require, canonical
from .transport import ReadRequest, parse_json, send, MAX_RESPONSE

FIELDS = {
 'github':({'repository','number'}, {'kind'}),
 'gitlab':({'project','commit'},set()),
 'confluence':({'site','page'},set()),
 'jira':({'site','issue'},set()),
 'linear':({'issue'},set()),
 'notion':({'block'}, {'cursor'}),
 'google-drive':({'file'}, {'format'}),
 'google-sheets':({'spreadsheet','range'},set()),
 'excel':({'item','sheet','range'},set()),
 'sharepoint':({'drive','item'},set()),
 'onshape':({'document','microversion','element'},set()),
 'slack':({'channel'}, {'cursor','oldest','latest'})}
COMMON = {'provider','credential_ref'}
MISSING = {
 'github':['comments','repository files; use existing GitHub connector for PR diff and checks'],
 'gitlab':['repository contents','commit diff and pipelines'],
 'confluence':['attachments','child pages','earlier revisions'],
 'jira':['comments beyond returned page','attachments','issue history'],
 'linear':['comments','attachments','related issues'],
 'notion':['nested blocks','attachments','earlier revisions'],
 'google-drive':['original native document; captured representation is an export','comments','earlier revisions'],
 'google-sheets':['cells outside requested range','formulas and formats','atomic remote revision'],
 'excel':['cells outside requested range','workbook binary','atomic remote revision'],
 'sharepoint':['document bytes; metadata only (download redirects not followed)','earlier revisions'],
 'onshape':['native editable document','assembly context','material validity and measurement uncertainty'],
 'slack':['thread replies','attachments','messages outside requested window']}


def request_for(config):
    require(isinstance(config,dict),'invalid_input','Configuration object required')
    p=config.get('provider'); require(p in FIELDS,'unsupported','No native API reader for this provider; use saved exports')
    required,optional=FIELDS[p]
    require(required<=config.keys() and not config.keys()-(COMMON|required|optional),
            'invalid_input','Missing or unknown provider fields')
    for k,v in config.items():
        require(isinstance(v,str) and 0<len(v)<=1000 and not any(ord(c)<32 for c in v),
                'invalid_input','Configuration values must be bounded nonempty strings')
    def v(key):
        value=config[key]
        require(not any(x in {'.','..',''} for x in value.split('/')) and '\\' not in value
                and ('/' not in value or (p=='gitlab' and key=='project')), 'invalid_input','Invalid object identifier')
        return quote(value,safe='')
    def site():
        require(re.fullmatch('[a-z0-9][a-z0-9-]{0,62}',config['site']), 'invalid_input','Atlassian tenant slug required')
        return 'https://'+config['site']+'.atlassian.net'
    if p=='github':
        from ..github_connector import validate_repository
        repo=validate_repository(config['repository']); kind=config.get('kind','issue')
        require(kind in {'issue','pull_request'} and config['number'].isdigit() and int(config['number'])>0,
                'invalid_input','Positive issue or PR number required')
        return ReadRequest('https://api.github.com/repos/'+repo+('/pulls/' if kind=='pull_request' else '/issues/')+v('number'),
            headers={'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
    if p=='gitlab':
        require(re.fullmatch('[a-fA-F0-9]{40,64}',config['commit']), 'invalid_input','Immutable commit SHA required')
        return ReadRequest('https://gitlab.com/api/v4/projects/'+v('project')+'/repository/commits/'+v('commit'))
    if p=='confluence': return ReadRequest(site()+'/wiki/api/v2/pages/'+v('page')+'?body-format=storage',auth='basic')
    if p=='jira': return ReadRequest(site()+'/rest/api/3/issue/'+v('issue'),auth='basic')
    if p=='linear':
        query='query($id:String!){issue(id:$id){id identifier title description updatedAt url state{id name} cycle{id name} team{id name}}}'
        return ReadRequest('https://api.linear.app/graphql','POST',canonical({'query':query,'variables':{'id':config['issue']}}).encode(),auth='raw')
    if p=='notion':
        query={'page_size':100}
        if 'cursor' in config: query['start_cursor']=config['cursor']
        return ReadRequest('https://api.notion.com/v1/blocks/'+v('block')+'/children?'+urlencode(query),
            headers={'Notion-Version':'2022-06-28'})
    if p=='google-drive':
        mime=config.get('format','text/plain')
        require(mime in {'text/plain','text/csv','application/pdf',
                         'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                         'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'},'invalid_input','Unsupported export format')
        return ReadRequest('https://www.googleapis.com/drive/v3/files/'+v('file')+'/export?'+urlencode({'mimeType':mime}))
    if p=='google-sheets':
        return ReadRequest('https://sheets.googleapis.com/v4/spreadsheets/'+v('spreadsheet')+'/values/'+v('range')+'?valueRenderOption=UNFORMATTED_VALUE')
    if p=='excel':
        require(re.fullmatch(r'[A-Z]{1,3}[1-9][0-9]{0,6}(?::[A-Z]{1,3}[1-9][0-9]{0,6})?',config['range']), 'invalid_input','Bounded A1 cell range required')
        return ReadRequest('https://graph.microsoft.com/v1.0/me/drive/items/'+v('item')+'/workbook/worksheets/'+v('sheet')+"/range(address='"+config['range']+"')")
    if p=='sharepoint':
        fields='id,name,eTag,cTag,size,lastModifiedDateTime,webUrl,file,sharepointIds'
        return ReadRequest('https://graph.microsoft.com/v1.0/drives/'+v('drive')+'/items/'+v('item')+'?'+urlencode({'$select':fields}))
    if p=='onshape':
        for k in ('document','microversion','element'):
            require(re.fullmatch('[a-fA-F0-9]{24}',config[k]), 'invalid_input','Onshape immutable IDs required')
        return ReadRequest('https://cad.onshape.com/api/partstudios/d/'+v('document')+'/m/'+v('microversion')+'/e/'+v('element')+'/massproperties')
    query={'channel':config['channel'],'limit':100}
    query.update({k:config[k] for k in ('cursor','oldest','latest') if k in config})
    return ReadRequest('https://slack.com/api/conversations.history?'+urlencode(query))


def fetch(config, transport=send):
    req=request_for(config); p=config['provider']
    response=transport(req,config.get('credential_ref'))
    require(isinstance(response.raw,bytes) and len(response.raw)<=MAX_RESPONSE,'acquisition_limit','Invalid bounded response')
    missing=list(MISSING[p]); revision=None; continuation=None
    if p=='google-drive':
        view={}; missing.append('atomic remote revision')
    else:
        data=parse_json(response.raw)
        require(isinstance(data,dict),'invalid_response','Expected object response')
        require(not data.get('error') and not data.get('errors'),'remote_error','Provider returned an error; remote text not persisted')
        if p=='linear':
            require(isinstance(data.get('data'),dict) and isinstance(data['data'].get('issue'),dict), 'not_found','Issue not returned')
            revision=data['data']['issue'].get('updatedAt')
        elif p=='slack': require(data.get('ok') is True,'remote_error','Slack refused the read')
        elif p=='notion': require(isinstance(data.get('results'),list),'invalid_response','Block list required')
        elif p in {'google-sheets','excel'}: require('range' in data or 'address' in data,'invalid_response','Range response required')
        elif p=='confluence':
            require(str(data.get('id'))==config['page'] and isinstance(data.get('body'),dict), 'invalid_response','Requested page body not returned')
            revision=data.get('version',{}).get('number')
        elif p=='jira':
            require(config['issue'] in {data.get('id'),data.get('key')} and isinstance(data.get('fields'),dict), 'invalid_response','Requested issue not returned')
            revision=data.get('fields',{}).get('updated')
        elif p=='gitlab':
            require(data.get('id','').lower()==config['commit'].lower(),'stale_basis','Commit identity mismatch')
            revision=data['id']
        elif p=='onshape':
            require(isinstance(data.get('bodies'),dict), 'invalid_response','Mass-properties body map required')
            revision=config['microversion']
        elif p=='sharepoint':
            require(data.get('id')==config['item'],'invalid_response','Requested drive item not returned')
            revision=data.get('eTag')
        elif p=='github':
            require(data.get('number')==int(config['number']),'invalid_response','Requested issue/PR not returned')
            revision=data.get('updated_at')
        continuation=data.get('next_cursor') or data.get('response_metadata',{}).get('next_cursor')
        if continuation or data.get('has_more') or data.get('@odata.nextLink') or 'rel="next"' in response.headers.get('link',''):
            missing.append('additional page(s); request explicit cursor separately')
        view=data
    if revision is None and 'atomic remote revision' not in missing: missing.append('atomic remote revision')
    # Acquisition configuration excludes any credential reference, and never copies a response URL.
    return {'provider':p,'source':{k:v for k,v in config.items() if k not in {'credential_ref','provider'}},
        'raw':response.raw,'view':view,'missing':missing,'source_revision':str(revision) if revision is not None else None,
        'revision_semantics':'provider_marker_not_cross_request_transaction', 'continuation':continuation}
