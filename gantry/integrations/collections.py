"""Bounded, resumable acquisition of related records; no atomic snapshot claim."""
import time
from ..model import Fault, require, canonical, digest
from .bundle import make_bundle, read_bundle
from .providers import fetch, request_for
from .transport import send, parse_json


def _successors(config, data, depth):
    provider=config['provider']; tasks=[]
    rows=data.get('results' if provider=='notion' else 'messages')
    require(isinstance(rows,list) and len(rows)<=1000,'invalid_response','Bounded page items required')
    more=data.get('has_more',False)
    require(type(more) is bool,'invalid_response','Boolean pagination flag required')
    cursor=data.get('next_cursor') if provider=='notion' else data.get('response_metadata',{}).get('next_cursor')
    require(not more or bool(cursor),'invalid_response','Pagination cursor missing')
    if cursor:
        tasks.append({'config':{**config,'cursor':cursor},'depth':depth})
    for row in rows:
        require(isinstance(row,dict),'invalid_response','Object item required')
        if provider=='notion':
            require(isinstance(row.get('id'),str) and type(row.get('has_children')) is bool,
                    'invalid_response','Block identity/child status required')
            if row['has_children']:
                tasks.append({'config':{'provider':provider,'block':row['id']},'depth':depth+1})
        elif 'thread_ts' not in config:
            replies=row.get('reply_count',0)
            require(type(replies) is int and replies>=0,'invalid_response','Reply count required')
            if replies:
                task={k:v for k,v in config.items() if k!='cursor'}
                task['thread_ts']=row.get('ts');tasks.append({'config':task,'depth':depth+1})
    for task in tasks: request_for(task['config'])  # Do not follow remote URLs.
    return tasks


def _advance(pending,seen,gaps,task,successors):
    pending.remove(task);seen.add(digest(task['config']))
    queued={digest(t['config']) for t in pending}
    for nxt in successors:
        k=digest(nxt['config'])
        if k in seen: gaps.append('cursor_cycle')
        elif k not in queued: pending.append(nxt);queued.add(k)


def _validate_resume(scope,index,files):
    pending=[{'config':scope,'depth':0}];seen=set();gaps=[]
    require(len(index['pages'])==len(files),'integrity_error','Unexpected collection files')
    for i,page in enumerate(index['pages']):
        require(isinstance(page,dict) and page.get('file')==f'pages/{i:04d}.json',
                'integrity_error','Unexpected collection page order')
        task={'config':page['config'],'depth':page['depth']}
        require(task in pending,'scope_denied','Page is outside the captured traversal')
        data=parse_json(files[page['file']])
        require(isinstance(data,dict),'invalid_response','Captured page must be an object')
        _advance(pending,seen,gaps,task,_successors(task['config'],data,task['depth']))
    require(pending==index['pending'] and seen==set(index['visited']) and set(gaps)==set(index['gaps']),
            'integrity_error','Pending work differs from recorded page relationships')


def capture_collection(config,source_id,refs,*,max_requests=20,max_depth=6,resume=None,transport=send):
    request_for(config)
    require(config['provider'] in {'notion','slack'},'unsupported','Related capture supports Notion and Slack')
    require('cursor' not in config,'invalid_input','Start a related capture at its root; use resume for continuation')
    require(type(max_requests) is int and 1<=max_requests<=90 and type(max_depth) is int and 0<=max_depth<=12,
            'invalid_input','Use 1–90 requests and depth 0–12 per acquisition')
    scope={k:v for k,v in config.items() if k!='credential_ref'}
    if config['provider']=='slack' and 'thread_ts' not in config:
        require({'oldest','latest'}<=config.keys(),'invalid_input','Explicit Slack time window required for related capture')
    files={};pages=[];pending=[{'config':scope,'depth':0}];seen=set();gaps=[]
    if resume:
        bundle=read_bundle(resume);index=parse_json(bundle['files'].get('collection.json',b''))
        require(isinstance(index,dict) and index.get('version')==1 and index.get('scope')==scope
                and bundle['manifest']['source_id']==source_id and bundle['manifest']['requirement_refs']==refs,
                'stale_basis','Resume scope, source or requirements differ')
        files={k:v for k,v in bundle['files'].items() if k!='collection.json'}
        pages=index['pages'];pending=index['pending'];seen=set(index['visited']);gaps=index['gaps']
        require(isinstance(pages,list) and isinstance(pending,list) and len(pending)<=1000
                and isinstance(gaps,list) and len(files)<=90,'invalid_input','Invalid saved collection')
        # Local captures are user controlled too: constrain every pending task to the root authority.
        for task in pending:
            require(isinstance(task,dict) and set(task)=={'config','depth'} and type(task['depth']) is int
                    and 0<=task['depth']<=13,'invalid_input','Invalid pending task')
            c=task['config'];request_for(c)
            require(c['provider']==scope['provider'] and 'credential_ref' not in c,'scope_denied','Resume authority changed')
            if c['provider']=='slack':
                require(all(c.get(k)==v for k,v in scope.items() if k!='thread_ts') and
                        ('thread_ts' not in scope or c.get('thread_ts')==scope['thread_ts']),
                        'scope_denied','Resume channel/window changed')
        _validate_resume(scope,index,files)
    started=time.monotonic();used=0;reason=None;size=sum(map(len,files.values()))
    while pending:
        if used>=max_requests: reason='request_limit';break
        if len(files)>=90 or size>=28*1024*1024: reason='capture_limit';break
        if time.monotonic()-started>=300: reason='acquisition_deadline';break
        eligible=next((i for i,t in enumerate(pending) if t['depth']<=max_depth),None)
        if eligible is None: reason='depth_limit';break
        task=pending[eligible];key=digest(task['config'])
        if key in seen:
            pending.pop(eligible);gaps.append('cursor_cycle');continue
        used+=1
        try:
            cfg={**task['config'],**({'credential_ref':config['credential_ref']} if 'credential_ref' in config else {})}
            captured=fetch(cfg,transport);raw=captured['raw'];data=captured['view']
            successors=_successors(task['config'],data,task['depth'])
            require(len(pending)+len(successors)<=1000 and
                    len(canonical(pending+successors))+len(canonical(pages))<1024*1024,
                    'acquisition_limit','Pending collection is too large')
            if size+len(raw)>28*1024*1024: reason='capture_limit';break
        except Fault as exc:
            # Remote error text/URLs are deliberately excluded from the resumable journal.
            reason=exc.code if exc.code in {'rate_limited','remote_unavailable','credential_missing','not_found',
                'acquisition_limit','invalid_response','invalid_input','scope_denied','remote_error'} else 'acquisition_failed'
            break
        except (KeyError,ValueError,TypeError,AttributeError):
            reason='invalid_response';break
        name=f'pages/{len(files):04d}.json';files[name]=raw;size+=len(raw)
        pages.append({'file':name,'config':task['config'],'depth':task['depth'],
                      'source_revision':captured['source_revision']})
        _advance(pending,seen,gaps,task,successors)
    status='partial' if pending or gaps else 'complete_within_scope'
    index={'version':1,'scope':scope,'status':status,'pages':pages,'pending':pending,
           'visited':sorted(seen),'gaps':sorted(set(gaps)),'stopped_reason':reason}
    files['collection.json']=canonical(index).encode()
    missing=['No cross-request atomic snapshot','Attachments and linked documents not downloaded',
             'Earlier revisions and comments outside selected scope not captured']+index['gaps']
    if reason: missing.append(reason)
    return make_bundle(config['provider'],source_id,files,refs,
        source={'collection_scope':scope,'capture_status':status},missing=missing)
