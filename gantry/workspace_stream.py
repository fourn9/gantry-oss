"""Bounded, scoped disk staging for larger Studio workspaces; no tool execution."""
import hashlib
import os
from pathlib import Path
import shutil
import stat
from .connection_policy import safe_path, covered, SECRET
from .project_files import parent_fd
from .project_connect import private_dir,save,load,sync_dir
from .model import Fault, require, digest

MAX_FILES=10000
MAX_TOTAL=1024**3
BLOCK=1024**2


def inspect(root,scopes,destination=None,selected=None,_prepared=False):
    """Hash all scoped bytes; optionally freeze selected files in a new private tree."""
    require(scopes and len(scopes)<=12000,'invalid_input','Explicit bounded scope required')
    for scope in scopes:safe_path(scope,True)
    root=Path(root);hashes={};missing=[];total=0
    if destination is not None:
        destination=Path(destination)
        if _prepared:
            require(destination.is_dir() and not destination.is_symlink() and not any(destination.iterdir()),
                    'conflict','Prepared staging directory must be empty')
        else:
            require(not destination.exists() and not destination.is_symlink(),'conflict','Staging destination already exists')
            private_dir(destination)
    def unreadable(exc):
        raise Fault('capture_incomplete','Cannot enumerate scoped workspace') from exc
    for directory,folders,files in os.walk(root,followlinks=False,onerror=unreadable):
        folders.sort();files.sort()
        for name in list(folders):
            path=Path(directory)/name;rel=path.relative_to(root).as_posix()
            try:safe_path(rel)
            except Fault:
                folders.remove(name);missing.append({'path':rel,'reason':'excluded_directory'});continue
            relevant=any(s==rel or s.startswith(rel+'/') or (s.endswith('/') and rel.startswith(s)) for s in scopes)
            if not relevant:folders.remove(name);continue
            require(not path.is_symlink(),'capture_incomplete','Linked directory in workspace scope')
        for name in files:
            rel=(Path(directory)/name).relative_to(root).as_posix()
            # Test coverage before safe_path so a secret in an unselected sibling is not ingested.
            if not any(rel==s or (s.endswith('/') and rel.startswith(s)) for s in scopes):continue
            output=None
            try:
                safe_path(rel)
                with parent_fd(root,rel) as (parent,leaf):
                    fd=os.open(leaf,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
                    with os.fdopen(fd,'rb') as source:
                        before=os.fstat(source.fileno())
                        require(stat.S_ISREG(before.st_mode) and before.st_nlink==1,'capture_incomplete','Only regular unlinked files may be captured')
                        require(len(hashes)<MAX_FILES and total+before.st_size<=MAX_TOTAL,'capture_incomplete','Workspace limit: 10000 files / 1 GiB')
                        if destination is not None and (selected is None or rel in selected):
                            p=destination/rel;private_dir(p.parent)
                            output=p.open('xb');os.chmod(p,0o600)
                        h=hashlib.sha256();tail=b'';size=0
                        for block in iter(lambda:source.read(BLOCK),b''):
                            size+=len(block)
                            require(size<=before.st_size and total+size<=MAX_TOTAL,'capture_incomplete','File grew during capture')
                            require(not SECRET.search(tail+block),'capture_incomplete','Potential credential in scoped file; capture stopped')
                            tail=block[-512:];h.update(block)
                            if output:output.write(block)
                        after=os.fstat(source.fileno())
                        require((before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==
                                (after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns) and size==before.st_size,
                                'capture_incomplete','File changed during capture')
                        hashes[rel]=h.hexdigest();total+=size
                        if output:output.flush();os.fsync(output.fileno())
            except (OSError,Fault) as exc:
                raise Fault('capture_incomplete','Scoped capture failed; no files treated as deleted',{'path':rel}) from exc
            finally:
                if output:output.close()
    require(hashes,'capture_incomplete','No readable scoped files')
    return hashes,missing


def freeze(root,scopes,expected,destination,selected=None):
    destination=Path(destination).absolute();private_dir(destination.parent)
    sync_dir(destination.parent.parent)
    require(not destination.exists() and not destination.is_symlink(),'conflict','Staging destination already exists')
    stage={'directory':str(destination),'device':None,'inode':None}
    journal=destination.parent/('.'+destination.name+'.json')
    require(not journal.exists() and not journal.is_symlink(),'conflict','Capture journal already exists')
    # Persist before writing any source bytes. A crash before the workspace's
    # pending request is saved can then be recovered under its operation lock.
    save(journal,stage)
    try:
        destination.mkdir(mode=0o700)
        sync_dir(destination.parent)
        info=destination.stat();stage.update(device=info.st_dev,inode=info.st_ino);save(journal,stage)
        hashes,missing=inspect(root,scopes,destination,selected,_prepared=True)
        require(hashes==expected,'capture_incomplete','Workspace changed while freezing; retry from current state')
        again,_=inspect(root,scopes)
        require(again==expected,'capture_incomplete','Workspace is still changing; no checkpoint published')
        for directory,_,_ in os.walk(destination,topdown=False):sync_dir(directory)
        return {**stage,'hashes':{p:h for p,h in hashes.items() if selected is None or p in selected}}
    except BaseException:
        try:cleanup(destination.parent.parent,stage)
        except (OSError,Fault):pass  # Keep the durable capture intent for retry.
        raise


def cleanup(meta,stage):
    """Delete only this client's frozen directory after durable acknowledgement."""
    parent=Path(meta).absolute()/'uploads';directory=Path(stage['directory'])
    require(directory.parent==parent and directory.name.startswith(('workspace-sync_','workspace-import_')),
            'scope_denied','Cleanup target is not a workspace staging directory')
    require(not parent.is_symlink() and not directory.is_symlink(),'scope_denied','Linked staging cannot be removed')
    journal=parent/('.'+directory.name+'.json')
    if journal.exists() or journal.is_symlink():
        intent=load(journal)
        require(all(intent.get(k)==stage.get(k) for k in ('directory','device','inode')),
                'scope_denied','Capture journal differs from staging identity')
    if directory.exists():
        info=directory.stat();owner=parent.stat()
        require(info.st_uid==owner.st_uid==os.getuid() and not (info.st_mode|owner.st_mode)&0o077
                and stat.S_ISDIR(info.st_mode),'scope_denied','Staging ownership or private permissions changed')
        if stage.get('inode') is None:
            # Only an empty directory can precede the identity journal. Never
            # recursively delete unidentified bytes after an interrupted mkdir.
            require(journal.is_file(),'scope_denied','Missing capture intent')
            directory.rmdir()
        else:
            require((info.st_dev,info.st_ino)==(stage.get('device'),stage.get('inode')),
                    'scope_denied','Staging filesystem identity changed')
            require(shutil.rmtree.avoids_symlink_attacks,'unsupported','Safe staging cleanup unavailable on this platform')
            shutil.rmtree(directory)
        sync_dir(parent)
    if journal.exists():journal.unlink();sync_dir(parent)


def recover_staging(meta,kind,protected=()):
    """Called under the sync/import lock; never discard an active outbox stage."""
    require(kind in {'workspace-sync','workspace-import'},'invalid_input','Unknown capture kind')
    parent=Path(meta).absolute()/'uploads'
    require(not parent.is_symlink(),'scope_denied','Linked staging root')
    protected={s['directory'] for s in protected if s}
    for journal in sorted(parent.glob('.'+kind+'_*.json')):
        stage=load(journal)
        require(journal.name=='.'+Path(stage['directory']).name+'.json','scope_denied','Capture journal path mismatch')
        if stage['directory'] not in protected:cleanup(meta,stage)


def upload(client,stage,base,expected,key,zone):
    """Replay immutable chunks, then construct one complete manifest from leaf refs."""
    from .adapters import capture_saved_files
    refs={}
    if base:
        for path,info in base['manifest'].items():
            if path in expected and path not in stage['hashes']:
                refs[path]=([{'revision_id':c['revision_id'],'path':c['path']} for c in info['chunks']]
                    if 'chunks' in info else [{'revision_id':base['snapshot'],'path':path}])
    if stage['hashes']:
        actual,_=inspect(stage['directory'],list(stage['hashes']))
        require(actual==stage['hashes'],'integrity_error','Queued bytes changed; do not retry a different payload')
        for item in capture_saved_files(client,stage['directory'],list(stage['hashes']),key,zone):
            for path,info in item['data']['files'].items():
                refs[path]=([{'revision_id':c['revision_id'],'path':c['path']} for c in info['chunks']]
                    if 'chunks' in info else [{'revision_id':item['revision_id'],'path':path}])
    result=client.call('capture_artifact',{'files':{},'assembled_files':refs,'zone':zone,
        'capture_scope':'scoped saved files frozen before upload',
        'missing_dependencies':['unsaved edits','native operation history','environment not verified']},key+':assembly:'+digest(refs))
    require({p:i['hash'] for p,i in result['data']['files'].items()}==expected,'integrity_error','Published manifest differs from frozen input')
    return result['revision_id']
