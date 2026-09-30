"""Capture externally saved CAD/code files. No editor automation or command execution."""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil
import tempfile
import time
from .model import digest, require, uid
from .store import Store


def files_payload(root, names):
    root = Path(root).resolve()
    result = {}
    for name in names:
        Store.safe_name(name)
        p = root / name
        require(not p.is_symlink() and p.resolve().is_relative_to(root), "invalid_input", "Symlink/path escape denied")
        before = p.stat()
        require(before.st_size <= 32 * 1024 * 1024, "invalid_input", "File exceeds capture limit")
        raw = p.read_bytes(); after = p.stat()
        require((before.st_size, before.st_mtime_ns, before.st_ino) == (after.st_size, after.st_mtime_ns, after.st_ino),
                "capture_incomplete", "File changed during capture; retry after save completes")
        result[name] = base64.b64encode(raw).decode()
    return result


def capture_saved_files(client, root, names, key, zone="root", source=None,
                        capture_scope="saved_regular_files", missing_dependencies=None):
    """Bounded uploads. Return complete logical snapshots, excluding intermediate parts.

    A failed/mutated upload may leave immutable parts, but never publishes that
    file's assembly. Retrying identical bytes with the same key is idempotent.
    The caller must retain the returned list: each snapshot is independently dated.
    """
    root = Path(root).resolve(); results = []; pending = {}; size = 0
    common = {"zone": zone, "source": source or {}, "capture_scope": capture_scope,
              "missing_dependencies": missing_dependencies or []}
    def upload(payload, suffix):
        args = {**common, **payload}
        return client.call("capture_artifact", args, key + ":" + suffix + ":" + digest(args))
    def flush():
        nonlocal pending, size
        if pending:
            results.append(upload({"files": pending}, "files")); pending = {}; size = 0
    for name in sorted(set(names)):
        Store.safe_name(name); path = root / name
        require(not path.is_symlink() and path.resolve().is_relative_to(root), "invalid_input", "Symlink/path escape denied")
        before = path.stat()
        require(path.is_file() and before.st_size <= 1024**3, "invalid_input", "Regular file up to 1 GiB required")
        parts = []; whole = hashlib.sha256(); read_size = 0
        with path.open("rb") as f:
            if before.st_size <= 32 * 1024**2:
                raw = f.read(32 * 1024**2 + 1); read_size = len(raw)
            else:
                flush()
                while True:
                    raw = f.read(16 * 1024**2)
                    if not raw: break
                    read_size += len(raw)
                    require(read_size <= before.st_size, "capture_incomplete", "File grew during capture")
                    whole.update(raw)
                    part_name = "parts/" + str(len(parts))
                    part = upload({"files": {part_name: base64.b64encode(raw).decode()}}, "part")
                    parts.append({"revision_id": part["revision_id"], "path": part_name})
        after = path.stat()
        require((before.st_size, before.st_mtime_ns, before.st_ino) == (after.st_size, after.st_mtime_ns, after.st_ino)
                and read_size == before.st_size, "capture_incomplete", "File changed during capture")
        if parts:
            result = upload({"files": {}, "assembled_files": {name: parts}}, "assembly")
            require(result["data"]["files"][name]["hash"] == whole.hexdigest(), "integrity_error", "Uploaded assembly mismatch")
            results.append(result)
        else:
            if size + read_size > 48 * 1024**2 or len(pending) >= 1000: flush()
            pending[name] = base64.b64encode(raw).decode(); size += read_size
    flush()
    return results


def artifact_file_parts(client, revision_id, name, info):
    """Yield bounded verified bytes; full hash is checked on iterator exhaustion."""
    Store.safe_name(name); whole = hashlib.sha256(); size = 0
    for index, expected in enumerate(Store.file_parts(info)):
        result = client.call("read_artifact_chunk", {"revision_id": revision_id, "path": name, "index": index})
        raw = base64.b64decode(result["content"], validate=True)
        require(len(raw) == expected["size"] and hashlib.sha256(raw).hexdigest() == expected["hash"],
                "integrity_error", "Downloaded artifact part mismatch")
        whole.update(raw); size += len(raw)
        yield raw
    require(size == info["size"] and whole.hexdigest() == info["hash"], "integrity_error", "Downloaded complete file mismatch")


def restore_files(client, revision_id, destination, cache_dir=None):
    result = client.call("restore_artifact", {"revision_id": revision_id, "metadata_only": True})
    target = Path(destination).absolute()
    require(not target.exists() and not target.is_symlink(), "invalid_input", "Restore destination must not exist")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".gantry-restore-", dir=target.parent))
    try:
        from .artifact_cache import restore_manifest
        namespace = hashlib.sha256(client.url.encode()).hexdigest()[:16] if hasattr(client, 'url') else 'local'
        cache = (Path(cache_dir) if cache_dir else target.parent / '.gantry-cache') / namespace
        stats = restore_manifest(client, revision_id, result['manifest']['files'], staging, cache)
        require(not target.exists() and not target.is_symlink(), "invalid_input", "Restore destination appeared during download")
        staging.rename(target)
    finally:
        if staging.exists(): shutil.rmtree(staging)
    return {"destination": str(target), "files": len(result["manifest"]["files"]), "transfer": stats}


def capture_git(client, repository, work_id, zone="root", base=None):
    root = Path(repository).resolve()
    def git(*args):
        proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
        require(proc.returncode == 0, "adapter_error", proc.stderr.decode(errors="replace")[:2000])
        return proc.stdout
    head = git("rev-parse", "--verify", "HEAD").decode().strip()
    files = {}
    for record in git("ls-tree", "-rz", "--full-tree", head).split(b"\0"):
        if not record: continue
        meta, path = record.split(b"\t", 1); mode, kind, obj = meta.split()
        name = path.decode("utf-8"); Store.safe_name(name)
        require(mode in {b"100644", b"100755"} and kind == b"blob", "capture_incomplete", "Symlink/submodule requires explicit capture support")
        files[name] = base64.b64encode(git("cat-file", "blob", obj.decode())).decode()
    content_key = "git:" + digest({"head": head, "path": str(root), "zone": zone})
    key = "git-operation:" + digest({"work": work_id, "head": head, "path": str(root), "base": base, "zone": zone})
    diff = git("diff", "--no-ext-diff", "--no-textconv", base, head, "--").decode(errors="replace") if base else None
    artifact = client.call("capture_artifact", {"zone": zone, "files": files,
        "source": {"adapter": "git", "commit": head, "repository": str(root)}, "capture_scope": "committed_regular_files"}, content_key + ":artifact")
    version = client.call("record", {"type": "software_version", "zone": zone,
        "source_id": str(root) + ":" + zone, "source_event_id": head,
        "data": {"git_sha": head, "repository": str(root), "artifact": artifact["revision_id"]}}, content_key + ":version")
    operation = client.call("record", {"type": "development_operation", "zone": zone,
        "data": {"work_item": work_id, "tool": "git", "status": "success", "capture_scope": "committed_diff",
                 "base": base, "head": head, "diff": diff, "output_artifact": artifact["revision_id"],
                 "missing_history": ["uncommitted edits", "individual editor/tool calls"]}}, key + ":operation")
    return {"artifact": artifact, "software_version": version, "operation": operation}


def watch_saved_files(client, root, names, work_id, zone, journal, interval=2, once=False):
    """Durable outbox for saved CATPart/CATProduct/STEP/code files.

    Unsaved edits and feature operations are explicitly outside capture scope.
    """
    path = Path(journal)
    state = json.loads(path.read_text()) if path.exists() else {"previous": None, "fingerprint": None, "pending": None}
    binding = {"root": str(Path(root).resolve()), "files": sorted(names), "work_id": work_id, "zone": zone}
    require(not path.exists() or state.get("binding") == binding,
            "invalid_input", "Journal belongs to another capture configuration; use a separate journal")
    state["binding"] = binding
    def persist():
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        with open(tmp, "w") as f:
            os.chmod(tmp, 0o600); json.dump(state, f); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    while True:
        if not state["pending"]:
            payload = files_payload(root, names); fp = digest(payload)
            if fp != state["fingerprint"]:
                state["pending"] = {"key": uid("capture"), "files": payload, "fingerprint": fp, "at": time.time()}
                persist()
        if state["pending"]:
            p = state["pending"]
            artifact = client.call("capture_artifact", {"zone": zone, "files": p["files"],
                "source": {"adapter": "saved-file-watcher", "root": str(Path(root).resolve())},
                "capture_scope": "saved_files_only"}, p["key"] + ":artifact")
            data = {"work_item": work_id, "tool": "saved-file-watcher", "status": "success",
                    "capture_scope": "before_after_saved_files", "output_artifact": artifact["revision_id"],
                    "observed_at": p["at"], "missing_history": ["unsaved edits", "CAD feature operations", "tool failures"]}
            if state["previous"]: data["input_artifact"] = state["previous"]
            client.call("record", {"type": "development_operation", "zone": zone, "data": data}, p["key"] + ":operation")
            state.update(previous=artifact["revision_id"], fingerprint=p["fingerprint"], pending=None)
            persist()
        if once: return {"artifact_revision": state["previous"], "journal": str(path)}
        time.sleep(interval)
