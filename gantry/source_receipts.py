"""Completion receipt writer shared with the opt-in macOS/Linux producer hooks.

Uses only the Python standard library so the same file can run inside Fusion.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile


def enrolled_path(root, relative):
    root = Path(root).resolve(strict=True)
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts or any(p.startswith(".") for p in relative.parts):
        raise ValueError("Select a relative export inside the enrolled workspace")
    path = root / relative
    if path.parent.resolve(strict=True) != path.parent or path.is_symlink():
        raise ValueError("Linked completion path")
    meta = root / ".gantry"
    binding = meta / "studio-workspace.json"
    if meta.is_symlink() or binding.is_symlink():
        raise ValueError("Linked workspace binding")
    with binding.open() as stream:
        saved = json.load(stream)
    if saved["root"] != str(root) or not any(
        relative.as_posix() == scope or scope.endswith("/") and relative.as_posix().startswith(scope)
        for scope in saved["write_scope"]
    ):
        raise ValueError("File outside bound write scope")
    return path, saved["work_id"]


def enqueue(root, kind, relative, revision):
    relative = Path(relative)
    path, work_id = enrolled_path(root, relative)
    meta = Path(root).resolve(strict=True) / ".gantry"
    if kind not in {"fusion-saved", "rosbag-closed"}:
        raise ValueError("Invalid completion kind")
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not 0 < info.st_size <= 1024**3:
            raise ValueError("Expected an ordinary saved file of at most 1 GiB")
        h = hashlib.sha256()
        size = 0
        for block in iter(lambda: stream.read(1024**2), b""):
            size += len(block)
            if size > info.st_size:
                raise ValueError("File grew during completion")
            h.update(block)
        checksum = h.hexdigest()
        after = os.fstat(fd)
        if (info.st_size, info.st_ctime_ns) != (after.st_size, after.st_ctime_ns):
            raise ValueError("File changed while reading completion")
    receipt = {"work_id": work_id, "event": {"kind": kind, "path": relative.as_posix(),
               "source_revision": revision, "sha256": checksum}}
    raw = json.dumps(receipt, sort_keys=True).encode()
    if len(raw) > 8192:
        raise ValueError("Oversized receipt")
    outbox = meta / "source-receipts"
    outbox.mkdir(mode=0o700, exist_ok=True)
    if outbox.is_symlink() or outbox.stat().st_uid != os.getuid() or outbox.stat().st_mode & 0o077:
        raise ValueError("Use an owner-only receipt directory")
    fd, tmp = tempfile.mkstemp(dir=outbox, prefix=".writing-")
    dest = outbox / (hashlib.sha256(raw).hexdigest() + ".json")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, dest)
        directory = os.open(outbox, os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(tmp).unlink(missing_ok=True)
    return dest
