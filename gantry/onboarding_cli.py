"""Scoped local onboarding; previews never write local state or contact Gantry."""
from pathlib import Path
from .model import require,uid


def add_parser(sub):
    p=sub.add_parser('onboard',help='Inspect an existing project and open guided setup')
    p.add_argument('action',choices=['start','resume','finish','refresh','analyze'])
    p.add_argument('--root',default='.')
    p.add_argument('--path',action='append',dest='paths',help='Explicit saved file or directory scope')
    p.add_argument('--name')
    p.add_argument('--goal',default='')
    p.add_argument('--actor',action='append',default=[])
    p.add_argument('--apply',action='store_true',help='Save the previewed sources in Gantry')
    p.add_argument('--onboarding-id')
    p.add_argument('--backend',choices=['codex-subscription','customer-command'])
    p.add_argument('--inference-config',help='Approved customer command and executable hash JSON')
    p.add_argument('--journal',help='Private inference attempt directory')
    p.add_argument('--title',default='Share current progress')
    p.add_argument('--purpose',default='Share saved work and continue from known inputs')


def run(client,a):
    from .workspace import scan,save,load,locked,Workspace
    if a.action=='analyze':
        require(a.onboarding_id and a.backend and a.journal,'invalid_input','Select --onboarding-id, --backend and --journal explicitly')
        from .onboarding_agent import analyze
        if a.backend=='codex-subscription':
            from .monthly_codex import infer_monthly
            infer=infer_monthly
        else:
            import json
            from .bot_worker import infer_command
            require(a.inference_config,'invalid_input','Select --inference-config')
            config=json.loads(Path(a.inference_config).read_text())
            infer=lambda context,schema,directory:infer_command(config,context,schema,directory)
        return analyze(client,a.onboarding_id,a.journal,infer)
    if a.action in {'resume','finish'}:
        require(a.onboarding_id,'invalid_input','Provide --onboarding-id')
        d=client.call('get_onboarding',{'onboarding_id':a.onboarding_id})
        if a.action=='resume':return d
        d=client.call('complete_onboarding',{'onboarding_id':d['id'],'version':d['version'],
            'title':a.title,'purpose':a.purpose},'onboard-finish:'+d['id']+':'+str(d['version']))
        return {'onboarding':d,'next':'Use workspace attach in the original directory, or workspace continue in a new directory.'}
    require(a.paths,'invalid_input','Select --path scopes before inspecting the local project')
    files,hashes,missing=scan(a.root,a.paths)
    preview={'files':list(hashes),'hashes':hashes,'missing':missing,'sent':False,'executed':False}
    if not a.apply:return preview
    require(files is not None,'capture_incomplete','Guided setup currently supports ordinary files up to 16 MiB each / 32 MiB total; narrow --path or use workspace import for large snapshots')
    if a.action=='start':require(a.name and a.name.strip(),'invalid_input','Provide --name')
    else:require(a.onboarding_id,'invalid_input','Provide --onboarding-id')
    w=Workspace(client,a.root)
    with locked(w.meta/'onboarding.lock'):
        journal=w.meta/('onboarding-'+a.action+'.json')
        intent={'endpoint':w.endpoint,'name':a.name,'goal':a.goal,'paths':a.paths,'actors':a.actor,'id':a.onboarding_id}
        if journal.exists():
            pending=load(journal)
            if pending.get('result') and a.action=='refresh':pending=None
            else:require(pending['intent']==intent,'conflict','This folder has a different setup journal; resume that setup first')
        else:pending=None
        if pending is None:
            _,second,_=scan(a.root,a.paths)
            require(hashes==second,'capture_incomplete','Files changed during capture; retry after saving')
            if a.action=='start':args={'name':a.name,'goal':a.goal,'files':files,'actors':a.actor,
                'missing':['Only saved selected scope; unsaved edits and earlier operations not captured']+[m['reason']+':'+m['path'] for m in missing]}
            else:
                d=client.call('get_onboarding',{'onboarding_id':a.onboarding_id})
                args={'onboarding_id':d['id'],'version':d['version'],'files':files}
            pending={'intent':intent,'args':args,'key':uid('onboarding-upload')};save(journal,pending)
        if not pending.get('result'):
            d=client.call('start_onboarding' if a.action=='start' else 'refresh_onboarding',pending['args'],pending['key'])
            pending['result']={'id':d['id'],'snapshot':d['snapshot'],'version':d['version']};pending.pop('args');save(journal,pending)
        return {**pending['result'],'sent':True,'executed':False,
                'open':client.url+'/#studio-start/'+pending['result']['id'] if hasattr(client,'url') else pending['result']['id']}
