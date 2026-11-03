"""Publish capture bundles through existing immutable, scoped change APIs."""
import base64
import copy
from pathlib import Path
from ..model import canonical, digest, require
from ..requirement_traceability import _subset_refs
from .bundle import read_bundle, read_file
from .transport import parse_json


def publish(client,state_id,change_id,version,bundle_path,key):
    bundle=read_bundle(bundle_path); manifest=bundle['manifest']
    fingerprint=digest([state_id,change_id,version,digest(manifest),getattr(client,'url','local')])
    journal=Path(bundle_path)/('publication-'+digest([getattr(client,'url','local'),key])+'.json')
    if journal.exists():
        saved=parse_json(read_file(journal.parent,journal.name))
        require(saved['fingerprint']==fingerprint,'idempotency_mismatch','Publication key reused for another capture')
        return client.call('checkpoint_change',saved['arguments'],key+':checkpoint')
    before=client.call('get_development_state',{'state_id':state_id}); state=before['state']
    listing=client.call('list_development_states',{'session_id':state['session_id']})
    change=next((c for c in listing['changes'] if c['id']==change_id),None)
    require(change and change['head']==state_id and change['version']==version,'stale_basis','Change head/version changed')
    refs=_subset_refs(state['context'].get('requirement_refs',[]),manifest['requirement_refs'])
    _subset_refs(change.get('requirement_refs',[]),refs)
    session=client.call('development_state',{'session_id':state['session_id']})['session']
    prefix='imports/'+manifest['source_id']+'/'
    files={prefix+'payload/'+name:base64.b64encode(raw).decode() for name,raw in bundle['files'].items()}
    files[prefix+'manifest.json']=base64.b64encode(canonical(manifest).encode()).decode()
    from ..development import in_scope
    require(all(in_scope(p,change['write_scope']) for p in files),'scope_denied','Import paths outside approved write scope')
    request={'files':files,'zone':session['zone'], 'capture_scope':'selected_external_source',
        'source':{'provider':manifest['provider'],'source_id':manifest['source_id'],'capture_hash':digest(manifest)},
        'missing_dependencies':manifest['missing']}
    raw=client.call('capture_artifact',request,key+':raw:'+digest(request))
    # Same-source files absent from the new capture are removed, other project files survive.
    assembled={name:([{'revision_id':part['revision_id'],'path':part['path']} for part in info['chunks']]
                    if 'chunks' in info else [{'revision_id':state['snapshot'],'path':name}])
               for name,info in before['manifest'].items() if not name.startswith(prefix)}
    assembled.update({name:[{'revision_id':raw['revision_id'],'path':name}] for name in files})
    combined=client.call('capture_artifact',{'files':{},'assembled_files':assembled,'zone':session['zone'],
        'capture_scope':'development_state_with_external_capture','missing_dependencies':manifest['missing']},key+':merge:'+digest(assembled))
    context=copy.deepcopy(state['context']); env=context['environment']
    sources=env.setdefault('external_sources',{})
    require(isinstance(sources,dict) and (manifest['source_id'] in sources or len(sources)<100),'acquisition_limit','At most 100 external sources per state')
    sources[manifest['source_id']]={'provider':manifest['provider'],'manifest_path':prefix+'manifest.json',
        'capture_hash':digest(manifest),'requirement_refs':refs,'verification':'unverified',
        'source_revision':manifest['source_revision'],'missing':manifest['missing']}
    # Core checks current change/version and permissions atomically at checkpoint.
    # Stale requirements may be captured as history; existing execution guards still hold them.
    arguments={'change_id':change_id,'version':version,'snapshot':combined['revision_id'],
        'summary':'External source captured: '+manifest['source_id'],
        'rationale':'Preserve original bytes and explicit requirement links for review; no physical pass inferred',
        'unfinished':state['unfinished'],'work_status':'paused','context':context,
        'capture':{'scope':'selected_external_source','missing':manifest['missing']}}
    saved={'fingerprint':fingerprint,'arguments':arguments}
    try:
        import os
        fd=os.open(journal,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as f:
            f.write(canonical(saved));f.flush();os.fsync(f.fileno())
    except FileExistsError:
        require(parse_json(read_file(journal.parent,journal.name))==saved,'idempotency_mismatch','Concurrent publication differs')
    return client.call('checkpoint_change',arguments,key+':checkpoint')
