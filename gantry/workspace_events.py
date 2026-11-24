"""Explicit completion signals from enrolled customer tools, confined to a saved file."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from .connection_policy import safe_path, SECRET
from .integrations.mcap_capture import MAGIC
from .model import require
from .project_files import parent_fd


def source_event(kind, path, revision, sha256):
    suffixes = {"fusion-saved": ".f3d", "rosbag-closed": ".mcap"}
    safe_path(path)
    require(kind in suffixes and Path(path).suffix.lower() == suffixes[kind],
            "invalid_input", "Completion event must match the saved file type")
    require(isinstance(revision, str) and re.fullmatch(r"[a-zA-Z0-9_.:/?=%+@&-]{1,256}", revision)
            and not SECRET.search(revision.encode()), "invalid_input", "Safe, immutable source revision required")
    require(isinstance(sha256, str) and re.fullmatch("[0-9a-f]{64}", sha256),
            "invalid_input", "Exact source SHA-256 required")
    return {"kind": kind, "path": path, "source_revision": revision, "sha256": sha256}


def check_saved_bytes(root, event, hashes):
    path = event["path"]
    require(hashes.get(path) == event["sha256"], "stale_basis", "Selected bytes differ from completion event")
    if event["kind"] == "rosbag-closed":
        with parent_fd(root, path) as (parent, name):
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            with os.fdopen(fd, "rb") as bag:
                info = os.fstat(fd)
                require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size >= 2*len(MAGIC)+29,
                        "capture_incomplete", "Closed MCAP file required")
                header = bag.read(len(MAGIC))
                bag.seek(-len(MAGIC)-29, os.SEEK_END)
                footer = bag.read(29+len(MAGIC))
                require(header == MAGIC and footer[:9] == b"\x02"+(20).to_bytes(8,"little") and footer[-len(MAGIC):] == MAGIC,
                        "capture_incomplete", "MCAP completion footer missing")


def event_context(previous, event):
    context = copy.deepcopy(previous)
    receipts = context["environment"].setdefault("saved_source_events", {})
    require(isinstance(receipts, dict), "conflict", "Invalid saved event context")
    existing = receipts.get(event["path"])
    require(existing is None or existing == event, "conflict",
            "This path identifies a different saved version; use a distinct versioned filename")
    receipts[event["path"]] = event
    return context


def receive_events(workspace):
    from .model import Fault
    from .project_connect import locked, private_dir, sync_dir
    binding = workspace.saved()
    outbox = private_dir(workspace.meta / "source-receipts")
    results = []
    with locked(workspace.meta / "source-receipts.lock"):
        for path in sorted(outbox.glob("*.json")):
            if not re.fullmatch("[0-9a-f]{64}", path.stem):
                continue
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                with os.fdopen(fd, "rb") as stream:
                    info = os.fstat(fd)
                    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= 8192
                            and info.st_uid == os.getuid() and not info.st_mode & 0o077,
                            "scope_denied", "Invalid receipt file")
                    raw = stream.read(8193)
                require(hashlib.sha256(raw).hexdigest() == path.stem, "integrity_error", "Changed receipt")
                record = json.loads(raw)
                require(record["work_id"] == binding["work_id"], "stale_basis", "Receipt belongs to another work")
                result = workspace.sync(event=record["event"])
                path.unlink()
                sync_dir(outbox)
            except (Fault, OSError, ValueError, KeyError, TypeError) as exc:
                result = {"status":"held", "error":exc.code if isinstance(exc,Fault) else type(exc).__name__}
            results.append({"receipt":path.stem, **result})
    return results


def follow_events(workspace, interval, iterations):
    import time
    require(1 <= interval <= 3600 and iterations >= 0, "invalid_input", "Invalid polling interval or iterations")
    previous = {}
    count = 0
    while not iterations or count < iterations:
        count += 1
        held = {}
        for result in receive_events(workspace):
            if result["status"] == "held":
                held[result["receipt"]] = result["error"]
                if previous.get(result["receipt"]) == result["error"]:
                    continue
            yield result
        previous = held
        if not iterations or count < iterations:
            time.sleep(interval)
