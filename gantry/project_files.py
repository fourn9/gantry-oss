"""Descriptor-relative workspace access; no symlink or hardlink following."""
import base64
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import secrets
import stat

from .model import require, Fault
from .connection_policy import safe_path, covered, clean_bytes, MAX_FILE, MAX_TOTAL, MAX_FILES


@contextmanager
def parent_fd(root, name):
    safe_path(name)
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in name.split('/')[:-1]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd); fd = nxt
        yield fd, name.split('/')[-1]
    finally:
        os.close(fd)


def read_file(root, name):
    with parent_fd(root, name) as (parent, leaf):
        fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
                    'scope_denied', 'Only ordinary nonlinked files can be read')
            require(before.st_size <= MAX_FILE, 'capture_incomplete', 'File exceeds 16 MiB')
            with os.fdopen(fd, 'rb', closefd=False) as f: raw = f.read(MAX_FILE+1)
            after = os.fstat(fd)
            require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns),
                    'stale_basis', 'File changed during capture')
            return clean_bytes(raw)
        finally: os.close(fd)


def write_file(root, name, raw, expected_hash):
    clean_bytes(raw)
    with parent_fd(root, name) as (parent, leaf):
        try: old = read_file(root, name); current = hashlib.sha256(old).hexdigest()
        except FileNotFoundError: current = 'absent'
        require(current == expected_hash, 'stale_basis', 'File changed; reread before editing')
        temp = '.gantry-edit-' + secrets.token_hex(12)
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        try:
            with os.fdopen(fd, 'wb') as f: f.write(raw); f.flush(); os.fsync(f.fileno())
            os.replace(temp, leaf, src_dir_fd=parent, dst_dir_fd=parent); os.fsync(parent)
        finally:
            try: os.unlink(temp, dir_fd=parent)
            except FileNotFoundError: pass


def inventory(root, scopes=None):
    root = Path(root); payload = {}; missing = []; total = 0
    for directory, folders, files in os.walk(root, followlinks=False):
        folders.sort(); files.sort()
        for name in list(folders):
            path = Path(directory)/name; rel = path.relative_to(root).as_posix()
            try: safe_path(rel)
            except Fault:
                missing.append({'path': rel, 'reason': 'excluded_directory'}); folders.remove(name); continue
            if path.is_symlink(): missing.append({'path': rel, 'reason': 'symlink'}); folders.remove(name)
        for name in files:
            rel = (Path(directory)/name).relative_to(root).as_posix()
            try:
                safe_path(rel)
                if scopes is not None and not covered(rel, scopes): continue
                raw = read_file(root, rel)
            except (Fault, OSError) as exc:
                missing.append({'path': rel, 'reason': exc.code if isinstance(exc, Fault) else 'unsafe_or_unreadable'})
                continue
            total += len(raw)
            require(total <= MAX_TOTAL and len(payload) < MAX_FILES, 'capture_incomplete', 'Narrow the project scope (32 MiB / 1000 files)')
            payload[rel] = base64.b64encode(raw).decode()
    require(payload, 'capture_incomplete', 'No readable project files')
    hashes = {p: hashlib.sha256(base64.b64decode(v)).hexdigest() for p, v in payload.items()}
    return payload, hashes, missing
