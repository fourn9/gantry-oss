"""SQLite event log, disposable projection, and content addressed artifacts."""
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import sqlite3
import time
from contextlib import closing

from . import indexed, manifest_store
from .model import canonical, digest, empty_state, project, require, uid, Fault


class Store:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.blobs = self.directory / "blobs"
        self.blobs.mkdir(exist_ok=True, mode=0o700)
        self.db = self.directory / "ledger.sqlite3"
        with closing(self.connect()) as con:
            con.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS projection(id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS requests(actor TEXT, key TEXT, fingerprint TEXT, response TEXT,
                                                   PRIMARY KEY(actor,key));
                CREATE TABLE IF NOT EXISTS credentials(hash TEXT PRIMARY KEY, actor TEXT NOT NULL);
            ''')
            indexed.schema(con)
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT body FROM projection WHERE id=1").fetchone()
            if row and json.loads(row[0]).get('_indexed') != 2:
                self.verify(con=con)
                count = con.execute('SELECT COUNT(*) FROM events').fetchone()[0]
                indexed.rebuild(con, self.state(con, count), canonical)
            con.commit()
        os.chmod(self.db, 0o600)

    def connect(self):
        con = sqlite3.connect(str(self.db), timeout=30, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA synchronous=FULL")
        return con

    def state(self, con, as_of=None):
        if as_of is None:
            row = con.execute("SELECT body FROM projection WHERE id=1").fetchone()
            if row:
                meta = json.loads(row[0])
                return indexed.load(con, meta) if meta.get("_indexed") else meta
        result = empty_state()
        query, args = "SELECT body FROM events", ()
        if as_of is not None:
            require(isinstance(as_of, int) and as_of >= 0, "invalid_input", "Invalid seq")
            query += " WHERE seq <= ?"; args = (as_of,)
        for row in con.execute(query + " ORDER BY seq", args):
            project(result, manifest_store.unpack(con,json.loads(row[0])))
        return result

    def append(self, con, state, actor, command, effects, result, basis, intent, notices=None, request=None):
        last = con.execute("SELECT body FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        previous = json.loads(last[0]) if last else None
        if previous and previous.get('_gantry_storage')==1: previous=previous['value']
        event = {"schema_version": 1, "event_id": uid("evt"), "ledger_id": state["ledger_id"],
                 "seq": state["seq"] + 1, "event_type": "bootstrap" if previous is None else "command",
                 "actor_id": actor["id"], "actor_kind": actor["kind"],
                 "recorded_at": time.time_ns() // 1000000, "basis": basis, "intent": intent,
                 "prev_hash": previous["hash"] if previous else "0" * 64,
                 "payload": {"command": command, "effects": effects, "result": result,
                             "notices": notices or []}}
        if request is not None:
            event["payload"]["request"] = request
        event["hash"] = digest(event)
        con.execute("INSERT INTO events VALUES (?,?)", (event["seq"], canonical(manifest_store.pack(con,event))))
        project(state, event)
        row = con.execute('SELECT body FROM projection WHERE id=1').fetchone()
        if not row or json.loads(row[0]).get('_indexed') != 2:
            indexed.rebuild(con, state, canonical)
        else:
            for effect in effects:
                if effect['table'] != 'meta':
                    indexed.put(con, effect['table'], effect['key'], effect['value'], canonical)
            con.execute('INSERT OR REPLACE INTO projection VALUES (1,?)', (canonical(indexed.header(state)),))
        return {**result, "event_id": event["event_id"], "seq": event["seq"]}

    def verify(self, checkpoint=None, con=None):
        if con is None:
            with closing(self.connect()) as connection:
                return self.verify(checkpoint, connection)
        events = [manifest_store.unpack(con,json.loads(r[0])) for r in con.execute("SELECT body FROM events ORDER BY seq")]
        prev, ledger = "0" * 64, None
        for seq, e in enumerate(events, 1):
            body = dict(e); actual = body.pop("hash", None)
            require(e.get("seq") == seq and e.get("prev_hash") == prev and digest(body) == actual,
                    "integrity_error", "Event chain mismatch", seq=seq)
            require(e.get("schema_version") == 1, "unsupported_schema", "Unknown schema", seq=seq)
            ledger = ledger or e.get("ledger_id")
            require(e.get("ledger_id") == ledger, "integrity_error", "Ledger ID changed", seq=seq)
            prev = actual
        if checkpoint:
            n = checkpoint.get("seq", -1)
            require(isinstance(n, int) and 1 <= n <= len(events), "integrity_error", "Checkpoint missing or truncated")
            require(checkpoint.get("ledger_id") == ledger and checkpoint.get("hash") == events[n-1]["hash"],
                    "integrity_error", "Trusted checkpoint mismatch")
        return {"valid": True, "ledger_id": ledger, "seq": len(events), "hash": prev}

    def put_blob(self, raw):
        require(len(raw) <= 32 * 1024 * 1024, "invalid_input", "File exceeds 32 MiB limit")
        h = hashlib.sha256(raw).hexdigest()
        path = self.blobs / h
        if not path.exists():
            tmp = self.blobs / (".tmp-" + secrets.token_hex(12))
            with open(tmp, "xb") as f:
                os.chmod(tmp, 0o600); f.write(raw); f.flush(); os.fsync(f.fileno())
            os.replace(tmp, path)
        require(hashlib.sha256(path.read_bytes()).hexdigest() == h, "integrity_error", "Corrupt blob", hash=h)
        return h

    def read_blob(self, h):
        require(isinstance(h, str) and len(h) == 64 and all(c in "0123456789abcdef" for c in h),
                "invalid_input", "Invalid blob hash")
        path = self.blobs / h
        require(path.is_file(), "artifact_missing", "Artifact is unavailable", hash=h)
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == h, "integrity_error", "Artifact hash mismatch", hash=h)
        return raw

    @staticmethod
    def safe_name(name):
        require(isinstance(name, str) and name and "\\" not in name and "\x00" not in name,
                "invalid_input", "Invalid artifact filename")
        p = PurePosixPath(name)
        require(not p.is_absolute() and all(x not in {"..", ".", ""} for x in name.split("/"))
                and ":" not in name, "invalid_input", "Unsafe artifact filename")
        return name

    def capture(self, files):
        require(isinstance(files, dict) and 0 < len(files) <= 1000, "invalid_input", "1–1000 files required")
        manifest = {}
        total = 0
        for name, content in sorted(files.items()):
            self.safe_name(name)
            try:
                raw = base64.b64decode(content, validate=True)
            except (ValueError, TypeError) as exc:
                raise Fault("invalid_input", "File contents must be base64") from exc
            total += len(raw)
            require(total <= 64 * 1024 * 1024, "invalid_input", "Snapshot exceeds 64 MiB")
            manifest[name] = {"hash": self.put_blob(raw), "size": len(raw)}
        return manifest

    @staticmethod
    def file_parts(info):
        return info.get("chunks", [info])

    def verified_parts(self, info):
        whole = hashlib.sha256(); size = 0
        for part in self.file_parts(info):
            raw = self.read_blob(part["hash"])
            require(len(raw) == part["size"], "integrity_error", "Artifact part size mismatch")
            whole.update(raw); size += len(raw)
            yield raw
        require(size == info["size"] and whole.hexdigest() == info["hash"],
                "integrity_error", "Assembled artifact mismatch")
