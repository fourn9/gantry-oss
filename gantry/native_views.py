"""Adapter-side selective JSON projection. Native source bytes remain untouched."""
import json
from .adapters import artifact_file_parts
from .model import require


def json_view(client,state_id,subject_id,revision_id,path,profile,fields,key):
    """fields: ordered name/pointer/unit/frame/time_basis mappings, explicitly configured.
    JSON Pointer indexes choose only needed fields. Missing fields are unknown,
    never zero; the adapter does not claim to understand unprovided CAD semantics.
    """
    manifest=client.call('restore_artifact',{'revision_id':revision_id,'metadata_only':True})['manifest']
    info=manifest['files'].get(path);require(info is not None,'not_found','Source file missing')
    require(info['size']<=16*1024*1024,'invalid_input','JSON projection source exceeds 16 MiB; provide a bounded native extractor')
    source=json.loads(b''.join(artifact_file_parts(client,revision_id,path,info)))
    values=[];missing=[]
    for spec in fields:
        pointer=spec['pointer'];require(pointer=='' or pointer.startswith('/'),'invalid_input','JSON Pointer required')
        value=source;classification='derived'
        try:
            for part in pointer.split('/')[1:] if pointer else []:
                part=part.replace('~1','/').replace('~0','~')
                if isinstance(value,list):
                    require(part.isdigit(),'invalid_input','Array pointer must be a nonnegative index');value=value[int(part)]
                else:value=value[part]
        except (KeyError,IndexError,TypeError):value=None;classification='unknown';missing.append(spec['name'])
        values.append({'name':spec['name'],'value':value,'classification':classification,'source_index':0,
            'method':'JSON Pointer '+pointer,**{k:spec[k] for k in ('unit','frame','time_basis') if k in spec}})
    return client.call('record_evidence_view',{'state_id':state_id,'subject_id':subject_id,'profile':profile,
        'extractor':'gantry.json-pointer.v1','sources':[{'revision_id':revision_id,'path':path,'sha256':info['hash'],'locator':'JSON Pointer entries in field methods'}],
        'fields':values,'missing':missing},key)


def upload_runtime_checkpoint(client,folder,receipt,key,zone='root'):
    from .runner import capture_tree
    from .model import digest
    from pathlib import Path
    manifest=json.loads((Path(folder)/'manifest.json').read_text())
    require(digest(manifest)==receipt['manifest_sha256'],'integrity_error','Checkpoint receipt differs')
    snapshot,gaps=capture_tree(client,folder,key,zone)
    require(not gaps,'capture_incomplete','Checkpoint upload incomplete')
    return {'artifact_revision':snapshot['revision_id'],'manifest_sha256':receipt['manifest_sha256'],
        'binding':receipt['binding'],'storage':'bytes_saved','resume_validation':'not_checked_by_upload'}
