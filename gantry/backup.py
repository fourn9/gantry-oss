"""Offline restore into an empty data directory, with verified artifacts."""
import base64
import hashlib
from contextlib import closing
from .model import canonical, digest, empty_state, project, require
from .store import Store
from . import indexed


def restore_backup(directory, bundle):
    require(bundle.get("format") in {"gantry-backup-v1", "gantry-backup-v2"}, "invalid_input", "Unknown backup format")
    events, blobs = bundle.get("events"), bundle.get("blobs", {})
    require(isinstance(events, list) and events, "invalid_input", "Backup events required")
    s, prev, ledger = empty_state(), "0" * 64, events[0]["ledger_id"]
    for seq, e in enumerate(events, 1):
        body = dict(e); h = body.pop("hash", None)
        require(e["seq"] == seq and e["ledger_id"] == ledger and e["prev_hash"] == prev and digest(body) == h,
                "integrity_error", "Invalid backup event", seq=seq)
        project(s, e); prev = h
    require(digest(s) == bundle.get("projection_hash"), "integrity_error", "Backup projection mismatch")
    cp = bundle.get("checkpoint", {})
    require(cp == {"ledger_id": ledger, "seq": len(events), "hash": prev}, "integrity_error", "Backup checkpoint mismatch")
    raw_blobs = {}
    for e in s["revisions"].values():
        if e.get("type") != "artifact_snapshot": continue
        for name, info in e["data"]["files"].items():
            Store.safe_name(name); whole = hashlib.sha256(); size = 0
            for part in Store.file_parts(info):
                h = part["hash"]
                require(h in blobs, "artifact_missing", "Backup lacks a referenced blob", hash=h)
                raw = base64.b64decode(blobs[h], validate=True)
                require(hashlib.sha256(raw).hexdigest() == h and len(raw) == part["size"], "integrity_error", "Invalid backup artifact")
                raw_blobs[h] = raw; whole.update(raw); size += len(raw)
            require(whole.hexdigest() == info["hash"] and size == info["size"], "integrity_error", "Invalid assembled backup file")
    store = Store(directory)
    with closing(store.connect()) as con:
        con.execute("BEGIN IMMEDIATE")
        require(con.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0, "already_initialized", "Restore destination must be empty")
        for raw in raw_blobs.values(): store.put_blob(raw)
        for e in events:
            con.execute("INSERT INTO events VALUES (?,?)", (e["seq"], canonical(e)))
            request = e["payload"].get("request")
            if request:
                response = {**e["payload"]["result"], "event_id": e["event_id"], "seq": e["seq"]}
                con.execute("INSERT INTO requests VALUES (?,?,?,?)",
                            (e["actor_id"], request["key"], request["fingerprint"], canonical(response)))
        indexed.rebuild(con, s, canonical)
        con.commit()
    return {"restored_events": len(events), "restored_blobs": len(raw_blobs), "checkpoint": cp}
