"""Verified chunk cache, scoped by endpoint. Never hard-link mutable workspaces."""
import base64
import hashlib
import os
import tempfile
from pathlib import Path
from .model import require
from .store import Store


def restore_manifest(client, revision, files, target, cache):
    cache = Path(cache); cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    require(not cache.is_symlink(), 'invalid_input', 'Cache cannot be a symlink')
    stats = {'downloaded_bytes': 0, 'downloaded_parts': 0, 'reused_parts': 0, 'requests': 0}
    pending = []; size = 0
    def valid(part):
        path = cache/part['hash']
        return path.is_file() and not path.is_symlink() and path.stat().st_size == part['size'] and hashlib.sha256(path.read_bytes()).hexdigest() == part['hash']
    def flush():
        nonlocal pending, size
        if not pending: return
        specs = [{'path': name, 'index': i} for name, i, _ in pending]
        if len(pending) == 1 and size > 8*1024*1024:
            replies = [client.call('read_artifact_chunk', {'revision_id':revision, **specs[0]})]
        else:
            replies = client.call('read_artifact_batch', {'revision_id':revision, 'parts':specs})['parts']
        stats['requests'] += 1
        require(len(replies)==len(pending), 'integrity_error', 'Incomplete batch')
        for (name, i, info), reply in zip(pending, replies):
            require(reply['path']==name and reply['index']==i and reply['revision_id']==revision,
                    'integrity_error', 'Batch binding mismatch')
            raw = base64.b64decode(reply['content'], validate=True)
            require(len(raw)==info['size'] and hashlib.sha256(raw).hexdigest()==info['hash'], 'integrity_error', 'Corrupt part')
            fd,tmp=tempfile.mkstemp(dir=cache)
            try:
                with os.fdopen(fd,'wb') as f: f.write(raw); f.flush(); os.fsync(f.fileno())
                os.replace(tmp,cache/info['hash'])
            finally:
                if os.path.exists(tmp): os.unlink(tmp)
            stats['downloaded_bytes'] += len(raw); stats['downloaded_parts'] += 1
        pending=[]; size=0
    for name, info in files.items():
        Store.safe_name(name)
        for i,part in enumerate(Store.file_parts(info)):
            require(len(part['hash'])==64 and all(c in '0123456789abcdef' for c in part['hash']), 'integrity_error', 'Invalid hash')
            if valid(part): stats['reused_parts'] += 1; continue
            if len(pending)>=64 or size+part['size']>8*1024*1024: flush()
            pending.append((name,i,part)); size+=part['size']
    flush()
    for name,info in files.items():
        path=Path(target)/name; path.parent.mkdir(parents=True,exist_ok=True)
        whole=hashlib.sha256(); count=0
        with open(path,'xb') as out:
            for part in Store.file_parts(info):
                require(valid(part),'integrity_error','Cache changed during restore')
                raw=(cache/part['hash']).read_bytes(); whole.update(raw);count+=len(raw);out.write(raw)
        require(count==info['size'] and whole.hexdigest()==info['hash'],'integrity_error','Restored file mismatch')
    return stats
