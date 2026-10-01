"""Authenticated commands. Every mutation is one serialized SQLite transaction."""
import base64
import copy
import hashlib
import json
import secrets
import time
from contextlib import closing
from collections.abc import Mapping
from datetime import datetime

from .model import (Fault, MANAGED, RECORDED, canonical, digest, identifier, impact,
                    policy, require, uid, validate_entry)
from .store import Store
from . import indexed, manifest_store
from .contracts import CONTRACTS, validate


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


from .development import DevelopmentMixin
from .continuity import ContinuityMixin
from .product import ProductMixin
from .autonomy import AutonomyMixin


from .evidence import EvidenceMixin
from .validation_map import ValidationMixin
from .change_review import ChangeReviewMixin
from .mentor_jobs import MentorJobsMixin
from .review_context import ReviewContextMixin
from .connections import ConnectionMixin


class Service(ConnectionMixin, ReviewContextMixin, MentorJobsMixin, ChangeReviewMixin, ValidationMixin, EvidenceMixin, AutonomyMixin, ProductMixin, ContinuityMixin, DevelopmentMixin):
    READS = {"state", "design", "diff", "history", "impact", "open", "reviews", "why",
             "outcomes", "operations", "restore_artifact", "read_artifact_chunk", "verify", "work", "context", "events", "export", "identity", "review_context", "development_state", "mentor_context", "check_execution"}

    def __init__(self, directory, clock=None):
        self.store = Store(directory)
        self.clock = clock or (lambda: time.time_ns() // 1000000)

    READS |= {'get_validation_plan', 'get_evidence_view', 'query_evidence', 'read_artifact_batch', 'list_artifact_files'}
    READS |= {'get_development_state', 'list_development_states'}
    READS |= {'related_review_context','check_mentor_job'}
    READS |= {'get_review_team', 'review_automation_status'}
    READS.add('render_evidence_view')
    READS |= {'get_change_review', 'list_change_reviews'}
    READS |= {'automation_status', 'get_analysis'}
    READS |= {'product_overview', 'project_details', 'session_details', 'get_signal'}
    READS |= {'connection_context', 'inspect_connection', 'connection_review'}

    def bootstrap(self, actor_id="admin", consent_seconds=None, _token=None):
        identifier(actor_id)
        require(actor_id not in {"root", "policy"}, "invalid_input", "Reserved actor ID")
        token = _token if _token is not None else secrets.token_urlsafe(32)
        require(isinstance(token, str) and len(token) >= 32, 'invalid_input', 'Strong initial credential required')
        with closing(self.store.connect()) as con:
            con.execute("BEGIN IMMEDIATE")
            s = self.store.state(con)
            require(s["seq"] == 0, "already_initialized", "Ledger already initialized")
            s["ledger_id"] = uid("ledger")
            effects = [{"table": "meta", "key": "ledger_id", "value": s["ledger_id"]}]
            data = {"kind": "human", "permissions": ["read", "record", "propose", "work", "admin"],
                    "token_hash": token_hash(token), "enabled": True}
            for eid, kind, body in [(actor_id, "principal", data),
                                     ("root", "zone", {"owner": actor_id, "participation": "participating"}),
                                     ("policy", "policy", {"human_approvers": [actor_id],
                                       "arbiter": actor_id, "consent_seconds": consent_seconds})]:
                validate_entry(kind, body)
                e = self._entry(eid, kind, "root", body, None)
                self._save_entry(s, effects, e)
            result = self.store.append(con, s, {"id": actor_id, "kind": "human"}, "bootstrap",
                                       effects, {"actor_id": actor_id}, {"reason": "initialization"},
                                       {"type": "declared", "text": "Initialize ledger"})
            con.commit()
        return {**result, "token": token}

    @staticmethod
    def _put(s, effects, table, key, value):
        effects.append({"table": table, "key": key, "value": copy.deepcopy(value)})
        if table == "meta":
            s[key] = value
        else:
            s.setdefault(table, {})[key] = copy.deepcopy(value)

    @staticmethod
    def _entry(eid, kind, zone, data, previous, **extra):
        return {"id": identifier(eid), "type": kind, "zone": identifier(zone),
                "data": copy.deepcopy(data), "revision_id": uid("rev"),
                "previous_revision": previous, **extra}

    def _save_entry(self, s, effects, entry):
        self._put(s, effects, "entries", entry["id"], entry)
        self._put(s, effects, "revisions", entry["revision_id"], entry)
        if entry["type"] == "principal":
            principal = {"id": entry["id"], **entry["data"]}
            if entry.get("retracted"):
                principal["enabled"] = False
            self._put(s, effects, "principals", entry["id"], principal)

    @staticmethod
    def authenticate(s, token):
        require(isinstance(token, str) and len(token) >= 20, "unauthorized", "Bearer token required")
        h = token_hash(token)
        for actor in s["principals"].values():
            if actor.get("enabled", True) and secrets.compare_digest(h, actor["token_hash"]):
                return actor
        raise Fault("unauthorized", "Invalid or revoked credential")

    @staticmethod
    def allowed(actor, permission):
        require(permission in actor["permissions"] or "admin" in actor["permissions"],
                "unauthorized", "Permission required", permission=permission)

    def _authenticate(self, con, state, token, command):
        require(isinstance(token, str) and 20 <= len(token) <= 4096, 'unauthorized', 'Bearer token required')
        credential = con.execute('SELECT actor FROM credentials WHERE hash=?', (token_hash(token),)).fetchone()
        actor = state['principals'].get(credential[0]) if credential else None
        require(actor and actor.get('enabled', True) and secrets.compare_digest(actor['token_hash'], token_hash(token)),
                'unauthorized', 'Invalid or revoked credential')
        require(actor.get('expires_at') is None or self.clock() < actor['expires_at'], 'unauthorized', 'Credential expired')
        require('allowed_commands' not in actor or command in actor['allowed_commands'], 'unauthorized', 'Command not delegated')
        self.allowed(actor, 'read')
        return actor

    def preflight(self, token, command):
        # Authenticate before accepting a potentially large HTTP upload; the transaction rechecks.
        with closing(self.store.connect()) as con:
            self._authenticate(con, self.store.state(con), token, command)

    @staticmethod
    def zone_write(actor, zone):
        require("admin" in actor["permissions"] or "zones" not in actor or zone in actor["zones"],
                "unauthorized", "Zone write denied", zone=zone)

    def call(self, token, command, args=None, key=None, _acquired=None):
        start = time.monotonic()
        outcome = None
        try:
            return self._call(token, command, args, key, _acquired)
        except Exception as exc:
            outcome = exc.code if isinstance(exc, Fault) else 'failure'
            raise
        finally:
            # Failures in optional statistics must never change transaction results.
            try:
                from .usage_metrics import UsageMetrics
                UsageMetrics(self.store.directory).record(command, outcome, time.monotonic()-start)
            except Exception:
                pass

    def _call(self, token, command, args=None, key=None, _acquired=None):
        args = copy.deepcopy({} if args is None else args)
        require(isinstance(args, dict), "invalid_input", "arguments must be an object")
        require(command in CONTRACTS, "unknown_command", "Unknown command", command=command)
        validate(args, CONTRACTS[command]["schema"])
        if command == 'sync_integration' and _acquired is None:
            return self.sync_github(token, args, key)
        if command == "events" and args.get("wait_ms"):
            wait = args.pop("wait_ms")
            require(isinstance(wait, int) and 0 <= wait <= 25000, "invalid_input", "wait_ms must be 0–25000")
            deadline = time.monotonic() + wait / 1000
            while True:
                result = self._call(token, command, args)
                if result["events"] or time.monotonic() >= deadline:
                    return result
                args["cursor"] = result["cursor"]
                time.sleep(min(0.1, max(0, deadline - time.monotonic())))
        require(not {"actor", "actor_id", "actor_kind"} & args.keys(),
                "invalid_input", "Actor identity comes from authentication")
        method = getattr(self, "cmd_" + command, None)
        require(method is not None, "unknown_command", "Unknown command", command=command)
        readonly = command in self.READS
        if not readonly:
            require(isinstance(key, str) and 1 <= len(key) <= 200, "invalid_input", "Idempotency key required")
        with closing(self.store.connect()) as con:
            con.execute("BEGIN" if readonly else "BEGIN IMMEDIATE")
            s = self.store.state(con)
            if command == "replay":
                self.store.verify(con=con)
                last_seq = con.execute("SELECT COALESCE(MAX(seq),0) FROM events").fetchone()[0]
                s = self.store.state(con, last_seq)
            actor = self._authenticate(con, s, token, command)
            # Legacy aggregate queries predate scoped sessions; fail closed for scoped actors.
            if 'zones' in actor and 'admin' not in actor['permissions']:
                require(command not in {'state','design','diff','history','impact','open','reviews','why',
                    'outcomes','operations','work','context','review_context','export'},
                    'unauthorized', 'This legacy query requires ledger-wide read authority; use scoped development APIs')
                def check_refs(value):
                    if isinstance(value, dict):
                        for child in value.values(): check_refs(child)
                    elif isinstance(value, list):
                        for child in value: check_refs(child)
                    elif isinstance(value, str) and value.startswith('rev_'):
                        entry = s['revisions'].get(value)
                        if entry: self.zone_write(actor, entry.get('zone', 'root'))
                check_refs(args)
            if not readonly:
                cached = con.execute("SELECT * FROM requests WHERE actor=? AND key=?", (actor["id"], key)).fetchone()
                fp = digest({"command": command, "args": args})
                if cached:
                    require(cached["fingerprint"] == fp, "idempotency_mismatch", "Key reused with different input")
                    return manifest_store.unpack(con,json.loads(cached["response"]))
            effects, notices = [], []
            result = (self._apply_sync(s, actor, args, effects, notices, con, _acquired)
                      if command == 'sync_integration' else method(s, actor, args, effects, notices, con))
            if readonly:
                return json.loads(canonical(result))
            if command == 'claim_analysis' and not effects:
                # Polls with no claim are observations, not development events.
                con.execute("INSERT INTO requests VALUES (?,?,?,?)", (actor['id'], key, fp, canonical(manifest_store.pack(con,result))))
                con.commit()
                return result
            intent = args.get("intent", {"type": "declared", "text": command})
            require(isinstance(intent, dict) and intent.get("type") in {"declared", "inferred"},
                    "invalid_input", "Invalid intent")
            if intent["type"] == "inferred":
                require(bool(intent.get("source")) and bool(intent.get("rule")), "invalid_input", "Inferred intent needs source and rule")
            result = self.store.append(con, s, actor, command, effects, result,
                                       args.get("basis", {"seq": s["seq"]}), intent, notices,
                                       request={"key": key, "fingerprint": fp})
            con.execute("INSERT INTO requests VALUES (?,?,?,?)", (actor["id"], key, fp, canonical(manifest_store.pack(con,result))))
            con.commit()
            return result

    @staticmethod
    def _get(s, table, key):
        require(key in s[table], "not_found", "Object not found", id=key)
        return copy.deepcopy(s[table][key])

    def _changes(self, s, actor, changes):
        require(isinstance(changes, list) and 0 < len(changes) <= 200, "invalid_input", "1–200 changes required")
        result, seen = [], set()
        for change in changes:
            require(isinstance(change, dict), "invalid_input", "Change must be an object")
            eid = identifier(change.get("id")); old = s["entries"].get(eid)
            require(eid not in seen, "invalid_input", "Duplicate change target"); seen.add(eid)
            kind, zone = change.get("type"), change.get("zone", "root")
            require(kind in MANAGED, "invalid_input", "Use record for observations and artifacts")
            require(not old or old["type"] == kind, "invalid_input", "Entry type cannot change")
            require((kind != "policy" or eid == "policy") and (eid != "policy" or kind == "policy"),
                    "invalid_input", "Policy must use the reserved policy ID")
            require(eid != "root" or kind == "zone", "invalid_input", "Reserved zone ID")
            require(change.get("expected_revision") == (old or {}).get("revision_id"),
                    "stale_basis", "Expected entry revision does not match", id=eid)
            require(zone in s["entries"] and s["entries"][zone]["type"] == "zone", "invalid_input", "Unknown zone")
            self.zone_write(actor, zone)
            if old:
                self.zone_write(actor, old["zone"])
            validate_entry(kind, change.get("data"))
            entry = self._entry(eid, kind, zone, change["data"], (old or {}).get("revision_id"),
                                retracted=bool(change.get("retracted", False)))
            require(not (eid in {"root", "policy"} and entry["retracted"]), "invalid_input", "Cannot retract root or policy")
            result.append(entry)
        hypothetical = {**s["entries"], **{e["id"]: e for e in result}}
        for entry in hypothetical.values():
            if entry.get("retracted"):
                continue
            d = entry["data"]
            if entry["type"] == "zone":
                for name in (d.get("owner"), d.get("proxy_owner")):
                    if name:
                        require(name in hypothetical and hypothetical[name]["type"] == "principal" and
                                hypothetical[name]["data"].get("enabled", True) and not hypothetical[name].get("retracted"),
                                "invalid_input", "Zone owner must be an enabled principal")
                if d.get("proxy_owner"):
                    require(bool(d.get("proxy_reason")), "invalid_input", "Proxy delegation reason required")
            if entry["type"] == "policy":
                for name in d["human_approvers"]:
                    require(name in hypothetical and hypothetical[name]["type"] == "principal" and
                            hypothetical[name]["data"].get("kind") == "human" and
                            hypothetical[name]["data"].get("enabled", True) and not hypothetical[name].get("retracted"),
                            "invalid_input", "Enabled human approver required")
                arbiter = hypothetical.get(d.get("arbiter"), {})
                require(arbiter.get("type") == "principal" and not arbiter.get("retracted") and
                        arbiter["data"].get("enabled", True), "invalid_input", "Enabled arbiter required")
            if entry["type"] == "relation":
                require(d["source"] in hypothetical and d["target"] in hypothetical,
                        "invalid_input", "Relation endpoint missing")
        # Reject cycles in provenance relations, even within one change set.
        adjacency = {}
        for e in hypothetical.values():
            if e["type"] == "relation" and not e.get("retracted") and e["data"]["kind"] == "derived_from":
                adjacency.setdefault(e["data"]["source"], []).append(e["data"]["target"])
        def visit(node, stack, done):
            require(node not in stack, "invalid_input", "Provenance cycle")
            if node in done: return
            for child in adjacency.get(node, []): visit(child, stack | {node}, done)
            done.add(node)
        done = set()
        for node in adjacency: visit(node, set(), done)
        return result

    def _candidate(self, s, effects, p):
        refs = dict(s["designs"].get(s["head"], {}).get("entries", {}))
        for entry in p["changes"]:
            refs[entry["id"]] = entry["revision_id"]
            self._put(s, effects, "revisions", entry["revision_id"], entry)
        candidate = {"id": uid("design"), "parent": s["head"], "proposal_id": p["id"],
                     "entries": refs, "status": "candidate"}
        self._put(s, effects, "designs", candidate["id"], candidate)
        p["candidate_id"] = candidate["id"]

    def cmd_propose(self, s, actor, a, fx, notices, con):
        self.allowed(actor, "propose")
        require(isinstance(a.get("title"), str) and a["title"].strip(), "invalid_input", "Title required")
        changes = self._changes(s, actor, a.get("changes"))
        p = {"id": uid("proposal"), "title": a["title"], "rationale": a.get("rationale", ""),
             "author": actor["id"], "version": 1, "status": "draft", "changes": changes,
             "impact": impact(s, changes), "reviews": [], "adoptions": [], "invalidations": 0,
             "basis_design": s["head"], "evidence": a.get("evidence", []), "created_at": self.clock()}
        self._candidate(s, fx, p)
        self._put(s, fx, "proposals", p["id"], p)
        return p

    def _editable(self, s, actor, a):
        p = self._get(s, "proposals", a.get("proposal_id"))
        self.allowed(actor, "propose")
        require(p["status"] not in {"committed", "withdrawn"}, "invalid_state", "Proposal is terminal")
        require(actor["id"] == p["author"] or "admin" in actor["permissions"], "unauthorized", "Only proposal author may edit")
        require(a.get("version") == p["version"], "stale_basis", "Proposal version changed")
        return p

    def cmd_amend(self, s, actor, a, fx, n, con):
        p = self._editable(s, actor, a)
        p["changes"] = self._changes(s, actor, a.get("changes"))
        p.update(version=p["version"] + 1, status="draft", impact=impact(s, p["changes"]),
                 title=a.get("title", p["title"]), rationale=a.get("rationale", p["rationale"]),
                 evidence=a.get("evidence", p["evidence"]), basis_design=s["head"])
        self._candidate(s, fx, p)
        self._put(s, fx, "proposals", p["id"], p)
        return p

    def cmd_rebase(self, s, actor, a, fx, n, con):
        p = self._editable(s, actor, a)
        a["changes"] = [{"id": e["id"], "type": e["type"], "zone": e["zone"], "data": e["data"],
                          "retracted": e.get("retracted", False),
                          "expected_revision": s["entries"].get(e["id"], {}).get("revision_id")} for e in p["changes"]]
        return self.cmd_amend(s, actor, a, fx, n, con)

    def _status(self, s, p):
        if p["status"] in {"draft", "committed", "withdrawn"}: return p["status"]
        current = impact(s, p["changes"])
        if current != p["impact"]: return "stale"
        targets = {e["id"] for e in p["changes"]}
        for other in s["proposals"].values():
            if other["id"] != p["id"] and other["status"] not in {"draft", "committed", "withdrawn", "stale"}:
                if targets & {e["id"] for e in other["changes"]}: return "conflict"
        if current["external"]: return "blocked_external"
        return "reviewing"

    def cmd_submit(self, s, actor, a, fx, n, con):
        p = self._editable(s, actor, a)
        require(p["status"] == "draft", "invalid_state", "Only draft can be submitted")
        require(impact(s, p["changes"]) == p["impact"], "stale_basis", "Rebase before submitting")
        period = policy(s).get("consent_seconds")
        require(len(p["impact"]["zones"]) <= 1 or period is not None, "invalid_state", "Consent period not configured")
        p.update(status="reviewing", submitted_at=self.clock(), deadline=self.clock() + (period or 0) * 1000)
        self._put(s, fx, "proposals", p["id"], p)
        return {**p, "status": self._status(s, p)}

    def _review(self, s, actor, a, fx, verdict, human=False):
        p = self._get(s, "proposals", a.get("proposal_id"))
        require(a.get("version") == p["version"], "stale_basis", "Review must target current proposal version")
        require(self._status(s, p) in {"reviewing", "conflict", "blocked_external"}, "invalid_state", "Proposal is not reviewable")
        require(isinstance(a.get("reason"), str) and a["reason"].strip(), "invalid_input", "Review reason required")
        if human:
            require(actor["kind"] == "human" and actor["id"] in policy(s)["human_approvers"],
                    "human_approval_required", "Designated human credential required")
            require(verdict in {"approve", "request_changes", "reject"}, "invalid_input", "Invalid adoption verdict")
        else:
            require(actor["id"] in p["impact"]["owners"].values(), "unauthorized", "Affected owner required")
        collection = "adoptions" if human else "reviews"
        review = {"id": uid("review"), "actor": actor["id"], "version": p["version"],
                  "candidate_id": p["candidate_id"], "verdict": verdict, "reason": a["reason"], "at": self.clock()}
        p[collection].append(review)
        self._put(s, fx, "proposals", p["id"], p)
        return review

    def cmd_endorse(self, s, actor, a, fx, n, con): return self._review(s, actor, a, fx, "endorse")
    def cmd_object(self, s, actor, a, fx, n, con): return self._review(s, actor, a, fx, "object")
    def cmd_retract_review(self, s, actor, a, fx, n, con): return self._review(s, actor, a, fx, "retracted")
    def cmd_review_adoption(self, s, actor, a, fx, n, con): return self._review(s, actor, a, fx, a.get("verdict"), True)

    def cmd_withdraw(self, s, actor, a, fx, n, con):
        p = self._editable(s, actor, a)
        p["status"] = "withdrawn"
        self._put(s, fx, "proposals", p["id"], p)
        return p

    def cmd_commit(self, s, actor, a, fx, n, con):
        self.allowed(actor, "propose")
        p = self._get(s, "proposals", a.get("proposal_id"))
        require(a.get("version") == p["version"], "stale_basis", "Proposal version changed")
        status = self._status(s, p)
        require(status == "reviewing", {"stale": "stale_basis", "conflict": "conflict", "blocked_external": "blocked_external"}.get(status, "invalid_state"),
                "Proposal cannot be committed", status=status)
        for reservation in s["reservations"].values():
            require(not (reservation["proposal_id"] != p["id"] and reservation["expires_at"] > self.clock() and
                         set(reservation["zones"]) & set(p["impact"]["zones"])), "reserved", "Another proposal holds a reservation")
        live = {r["actor"]: r["verdict"] for r in p["reviews"] if r["version"] == p["version"]}
        owners = set(p["impact"]["owners"].values())
        require(not any(live.get(owner) == "object" for owner in owners), "review_pending", "Owner objection remains")
        endorsed = all(live.get(owner) == "endorse" for owner in owners)
        require(endorsed or (len(p["impact"]["zones"]) > 1 and self.clock() >= p["deadline"]),
                "review_pending", "Owner endorsement or consent deadline required")
        adoptions = {r["actor"]: r["verdict"] for r in p["adoptions"] if r["version"] == p["version"] and r["candidate_id"] == p["candidate_id"]}
        require(any(adoptions.get(h) == "approve" for h in policy(s)["human_approvers"])
                and not any(v in {"reject", "request_changes"} for v in adoptions.values()),
                "human_approval_required", "Current candidate needs explicit human approval")
        for e in s["entries"].values():
            if e["type"] == "open_question" and e["data"].get("status", "open") != "resolved":
                blocked = set(e["data"].get("blocking", []))
                require(not blocked & ({p["id"]} | set(p["impact"]["entries"])), "review_pending", "Blocking question remains", question=e["id"])
        candidate = s["designs"][p["candidate_id"]]
        for rid in candidate["entries"].values():
            plan = s["revisions"][rid]
            if plan["type"] == "validation_plan" and plan["data"].get("required") and not plan.get("retracted"):
                results = [e for e in s["entries"].values() if e["type"] == "eval_result" and not e.get("retracted") and
                           e["data"].get("design_revision") == p["candidate_id"] and
                           e["data"].get("validation_plan") == rid]
                require(results and all(e["data"].get("verdict") == "pass" for e in results),
                        "validation_required", "Required evaluation missing or failed", plan=plan["id"])
        decision = {"id": uid("decision"), "type": "decision", "proposal_id": p["id"], "version": p["version"],
                    "candidate_id": p["candidate_id"], "rationale": p["rationale"], "reviews": p["reviews"],
                    "adoptions": p["adoptions"], "impact": p["impact"], "evidence": p["evidence"],
                    "committed_by": actor["id"], "at": self.clock(), "adoption_reason": a.get("reason", "")}
        for entry in p["changes"]:
            # The exact reviewed content/revision is preserved; provenance is in the decision/design.
            self._save_entry(s, fx, entry)
        formal = {"id": uid("design"), "parent": s["head"], "entries": {
            k: e["revision_id"] for k, e in s["entries"].items() if e["type"] in MANAGED},
            "status": "formal", "decision_id": decision["id"], "candidate_id": p["candidate_id"]}
        self._put(s, fx, "designs", formal["id"], formal)
        self._put(s, fx, "meta", "head", formal["id"])
        decision["design_id"] = formal["id"]
        self._put(s, fx, "revisions", decision["id"], decision)
        p.update(status="committed", decision_id=decision["id"])
        self._put(s, fx, "proposals", p["id"], p)
        for other in list(s["proposals"].values()):
            if other["status"] not in {"draft", "committed", "withdrawn", "stale"} and self._status(s, other) == "stale":
                other = copy.deepcopy(other)
                other["status"] = "stale"; other["invalidations"] += 1
                other["needs_scheduling"] = other["invalidations"] >= 2
                self._put(s, fx, "proposals", other["id"], other)
        n.append({"type": "decision_committed", "target": p["id"], "zones": p["impact"]["zones"], "decision_id": decision["id"]})
        return decision

    def cmd_record(self, s, actor, a, fx, n, con):
        self.allowed(actor, "record")
        kind, data, zone = a.get("type"), a.get("data"), a.get("zone", "root")
        require(kind in RECORDED - {"artifact_snapshot"}, "invalid_input", "This type cannot be directly recorded")
        validate_entry(kind, data); self.zone_write(actor, zone)
        require(zone in s["entries"] and s["entries"][zone]["type"] == "zone", "invalid_input", "Unknown zone")
        eid = a.get("id") or uid(kind)
        old = s["entries"].get(eid)
        require(not old or old["type"] == kind, "invalid_input", "Entry type cannot change")
        if old:
            self.zone_write(actor, old["zone"])
            require(a.get("expected_revision") == old["revision_id"], "stale_basis", "Expected revision required")
            require(kind != "configuration", "invalid_input", "Configurations are immutable")
        if kind == "open_question" and data.get("status") == "resolved":
            decision = s["revisions"].get(data.get("decision_id"), {})
            require(decision.get("type") == "decision", "invalid_input", "Resolution decision required")
        for field in ("design_revision", "basis_design_revision"):
            if data.get(field): require(data[field] in s["designs"], "invalid_input", "Unknown design version")
        binding=data.get('design_binding')
        if binding is not None:
            require(isinstance(binding,dict) and binding.get('status') in {'verified_inputs','unverified','invalidated'},
                    'invalid_input','Invalid design input binding')
            bound=data.get('design_revision') if kind=='eval_result' else (data.get('slots',{}).get('design') if kind=='configuration' else None)
            if bound:
                require(binding.get('status')=='verified_inputs' and binding.get('evaluated_design_revision')==bound,
                        'invalid_input','Unverified inputs cannot claim an evaluated design')
                if kind=='eval_result':
                    config=s['revisions'].get(data.get('configuration'),{})
                    require(config.get('type')=='configuration' and config['data'].get('slots',{}).get('design')==bound
                            and config['data'].get('design_binding')==binding,
                            'invalid_input','Evaluation binding must match its immutable configuration')
        if kind == "eval_result":
            data.setdefault("configuration", "unknown")
            data.setdefault("completeness", "unknown" if data["configuration"] == "unknown" else "declared")
            if data.get("validation_plan"):
                require(s["revisions"].get(data["validation_plan"], {}).get("type") == "validation_plan", "invalid_input", "Unknown plan revision")
        if kind in {"eval_result", "incident"}:
            for relation in data.get("decisions", []):
                require(isinstance(relation, dict) and relation.get("relation") in {"evaluates", "associated_with"},
                        "invalid_input", "Decision link must declare relation")
                require(s["revisions"].get(relation.get("id"), {}).get("type") == "decision",
                        "invalid_input", "Unknown decision reference")
        if kind == "development_operation":
            require(data["work_item"] in s["works"], "invalid_input", "Unknown work item")
            for field in ("input_artifact", "output_artifact"):
                if data.get(field):
                    require(s["revisions"].get(data[field], {}).get("type") == "artifact_snapshot",
                            "invalid_input", "Unknown artifact revision")
        if kind == "configuration_observation":
            require(s["entries"].get(data["unit"], {}).get("type") == "unit", "invalid_input", "Unknown unit")
            require(s["revisions"].get(data["configuration"], {}).get("type") == "configuration", "invalid_input", "Configuration revision required")
            self._timestamp(data["occurred_at"])
        if a.get("source_event_id"):
            require(bool(a.get("source_id")), "invalid_input", "source_id required with source_event_id")
            fingerprint = digest({"type": kind, "zone": zone, "data": data})
            for recorded in s["revisions"].values():
                source = recorded.get("source", {})
                if source.get("id") == a["source_id"] and source.get("event_id") == a["source_event_id"]:
                    require(source["fingerprint"] == fingerprint, "idempotency_mismatch", "Source event changed")
                    return recorded
        e = self._entry(eid, kind, zone, data, (old or {}).get("revision_id"), retracted=bool(a.get("retracted", False)))
        if a.get("source_event_id"):
            e["source"] = {"id": a["source_id"], "event_id": a["source_event_id"], "fingerprint": fingerprint}
        self._save_entry(s, fx, e)
        if kind == "eval_result": n.append({"type": "validation_completed", "target": data.get("design_revision", eid), "zones": [zone]})
        return e

    def cmd_capture_artifact(self, s, actor, a, fx, n, con):
        self.allowed(actor, "record"); zone = a.get("zone", "root"); self.zone_write(actor, zone)
        require(zone in s["entries"] and s["entries"][zone]["type"] == "zone", "invalid_input", "Unknown zone")
        files = a.get("files", {}); assembled = a.get("assembled_files", {})
        require(0 < len(files) + len(assembled) <= 10000 and not set(files) & set(assembled),
                "invalid_input", "1–10000 distinct logical files required")
        manifest = self.store.capture(files) if files else {}
        total = sum(info["size"] for info in manifest.values())
        for name, refs in sorted(assembled.items()):
            self.store.safe_name(name)
            parts = []; whole = hashlib.sha256(); size = 0
            for ref in refs:
                self.store.safe_name(ref["path"])
                source = self._get(s, "revisions", ref["revision_id"])
                require(source["type"] == "artifact_snapshot", "invalid_input", "Artifact part reference required")
                info = source["data"]["files"].get(ref["path"])
                require(info is not None and "chunks" not in info, "invalid_input", "Part must reference an ordinary saved file")
                total += info["size"]
                require(total <= 1024 * 1024 * 1024, "invalid_input", "Logical snapshot exceeds 1 GiB")
                raw = self.store.read_blob(info["hash"])
                require(len(raw) == info["size"], "integrity_error", "Part size mismatch")
                whole.update(raw); size += len(raw)
                parts.append({"hash": info["hash"], "size": info["size"], **ref})
            manifest[name] = {"hash": whole.hexdigest(), "size": size, "chunks": parts}
        e = self._entry(uid("artifact"), "artifact_snapshot", zone,
                        {"files": manifest, "capture_scope": a.get("capture_scope", "files_only"),
                         "missing_dependencies": a.get("missing_dependencies", []),
                         "source": a.get("source"), "restorable": True}, None)
        self._save_entry(s, fx, e)
        return e

    def cmd_restore_artifact(self, s, actor, a, fx, n, con):
        e = self._get(s, "revisions", a.get("revision_id"))
        require(e["type"] == "artifact_snapshot", "invalid_input", "Artifact snapshot required")
        if a.get("metadata_only"):
            return {"revision_id": e["revision_id"], "manifest": e["data"]}
        require(not any("chunks" in info for info in e["data"]["files"].values()),
                "stream_required", "Use metadata_only and read_artifact_chunk for this snapshot")
        return {"revision_id": e["revision_id"], "manifest": e["data"], "files": {
            name: base64.b64encode(self.store.read_blob(info["hash"])).decode()
            for name, info in e["data"]["files"].items()}}

    def cmd_read_artifact_chunk(self, s, actor, a, fx, n, con):
        self.store.safe_name(a["path"])
        info = manifest_store.file_info(con,a['revision_id'],a['path'])
        require(info is not None, "not_found", "File not in snapshot")
        parts = self.store.file_parts(info); index = a["index"]
        require(index < len(parts), "invalid_input", "Part index out of range")
        part = parts[index]; raw = self.store.read_blob(part["hash"])
        require(len(raw) == part["size"], "integrity_error", "Artifact part size mismatch")
        return {"revision_id": a["revision_id"], "path": a["path"], "index": index,
                "hash": part["hash"], "size": len(raw), "content": base64.b64encode(raw).decode()}

    def cmd_list_artifact_files(self, s, actor, a, fx, n, con):
        limit = a.get('limit', 100)
        import itertools
        root=con.execute('SELECT root FROM artifact_roots WHERE revision_id=?',(a['revision_id'],)).fetchone()
        require(root is not None,'not_found','Artifact not found')
        rows=list(itertools.islice(manifest_store.Tree(con).items(root[0],a.get('after','')),limit+1))
        return {'files':dict(rows[:limit]),'next':rows[limit-1][0] if len(rows)>limit else None,'revision_id':a['revision_id']}

    def cmd_read_artifact_batch(self, s, actor, a, fx, n, con):
        size = 0
        for part in a['parts']:
            self.store.safe_name(part['path'])
            info=manifest_store.file_info(con,a['revision_id'],part['path'])
            require(info is not None,'not_found','File not in snapshot')
            parts=self.store.file_parts(info)
            require(part['index'] < len(parts), 'invalid_input', 'Part index out of range')
            size += parts[part['index']]['size']
        require(size <= 8*1024*1024, 'batch_too_large', 'Batch exceeds 8 MiB')
        return {'parts': [self.cmd_read_artifact_chunk(s, actor, {'revision_id': a['revision_id'], **p}, fx,n,con)
                          for p in a['parts']]}

    @staticmethod
    def _redact(value):
        if isinstance(value, Mapping): return {k: Service._redact(v) for k, v in value.items() if k != "token_hash"}
        if isinstance(value, list): return [Service._redact(v) for v in value]
        return value

    def cmd_state(self, s, actor, a, fx, n, con):
        if "as_of_seq" in a:
            require(a["as_of_seq"] <= s["seq"], "invalid_input", "Future seq requested")
            s = self.store.state(con, a["as_of_seq"])
        return self._redact({"ledger_id": s["ledger_id"], "seq": s["seq"], "cursor": s["seq"],
                             "head": s["head"], "entries": s["entries"], "units": self._units(s),
                             "proposals": {k: {**v, "status": self._status(s, v)} for k, v in s["proposals"].items()}})

    def cmd_design(self, s, actor, a, fx, n, con):
        design = self._get(s, "designs", a.get("design_id") or s["head"])
        return self._redact({**design, "contents": {k: s["revisions"][rid] for k, rid in design["entries"].items()}})

    def cmd_identity(self, s, actor, a, fx, n, con):
        return self._redact(actor)

    def cmd_review_context(self, s, actor, a, fx, n, con):
        p = self._get(s, "proposals", a.get("proposal_id"))
        candidate = s["designs"][p["candidate_id"]]
        base = s["designs"].get(candidate.get("parent"), {}).get("entries", {})
        candidate_contents = {key: s["revisions"][rid] for key, rid in candidate["entries"].items()}
        changes = [{"id": e["id"], "before": s["revisions"].get(base.get(e["id"])), "after": e}
                   for e in p["changes"]]
        design_ids = {p["candidate_id"], s["revisions"].get(p.get("decision_id"), {}).get("design_id")}
        design_ids.discard(None)
        works = [w for w in s["works"].values() if w.get("proposal_id") == p["id"]]
        work_ids = {w["id"] for w in works}
        results = [e for e in s["entries"].values() if e["type"] in {"eval_result", "incident"} and
                   e["data"].get("design_revision") in design_ids and not e.get("retracted")]
        questions = [e for e in s["entries"].values() if e["type"] == "open_question" and not e.get("retracted") and
                     set(e["data"].get("blocking", [])) & ({p["id"]} | set(p["impact"]["entries"]))]
        versions, seen_candidates = [], set()
        for row in con.execute("SELECT body FROM events ORDER BY seq"):
            event = manifest_store.unpack(con,json.loads(row[0]))
            result = event["payload"].get("result", {})
            cid = result.get("candidate_id")
            if result.get("id") == p["id"] and cid and cid not in seen_candidates:
                seen_candidates.add(cid)
                versions.append({"candidate_id": cid, "version": result["version"],
                                 "title": result["title"], "rationale": result.get("rationale", ""),
                                 "actor": event["actor_id"], "recorded_at": event["recorded_at"],
                                 "seq": event["seq"], "parent": s["designs"][cid].get("parent")})
        # Earlier failed attempts belong to this proposal's history, but must not
        # become evidence that the current candidate passed its required checks.
        version_by_design = {v["candidate_id"]: v["version"] for v in versions}
        past_ids = set(version_by_design) - design_ids
        historical_results = [{**e, "source_candidate_version": version_by_design[e["data"]["design_revision"]]}
                              for e in s["entries"].values()
                              if e["type"] in {"eval_result", "incident"} and not e.get("retracted")
                              and e["data"].get("design_revision") in past_ids]
        historical_results.sort(key=lambda e: (e["source_candidate_version"], e["data"].get("occurred_at", ""), e["id"]))
        unbound_results=[e for e in s['entries'].values() if e['type']=='eval_result' and not e.get('retracted')
                         and not e['data'].get('design_revision') and
                         (e['data'].get('proposal_id')==p['id'] or e['data'].get('work_item') in work_ids or
                          e['data'].get('basis_design_revision') in version_by_design)]
        unbound_results.sort(key=lambda e:(e['data'].get('occurred_at',''),e['id']))
        results.sort(key=lambda e: (e["data"].get("occurred_at", ""), e["id"]))
        return self._redact({"seq": s["seq"], "proposal": {**p, "status": self._status(s, p)},
                            "candidate": candidate, "candidate_contents": candidate_contents,
                            "candidate_versions": versions,
                            "discussions": self._discussion_entries(s, {p['id']} | work_ids | set(version_by_design), con),
                            "changes": changes, "results": results, "historical_results": historical_results, "unbound_results":unbound_results,"questions": questions,
                            "works": works, "evidence": [{"id": rid, "entry": s["revisions"].get(rid),
                                'superseded_by':(s['entries'].get(s['revisions'].get(rid,{}).get('id'),{}).get('revision_id')
                                                 if s['entries'].get(s['revisions'].get(rid,{}).get('id'),{}).get('revision_id')!=rid else None)} for rid in p["evidence"]],
                            "operations": [e for e in s["revisions"].values() if e.get("type") == "development_operation" and
                                           e["data"].get("work_item") in work_ids],
                            "can_owner_review": actor["id"] in p["impact"]["owners"].values(),
                            "can_human_review": actor["kind"] == "human" and actor["id"] in policy(s)["human_approvers"]})

    def cmd_diff(self, s, actor, a, fx, n, con):
        left = self._get(s, "designs", a.get("before"))["entries"] if a.get("before") else {}
        right = self._get(s, "designs", a.get("after"))["entries"]
        return self._redact({"changes": [{"id": k, "before": s["revisions"].get(left.get(k)),
                                           "after": s["revisions"].get(right.get(k))}
                                          for k in sorted(set(left) | set(right)) if left.get(k) != right.get(k)]})

    def cmd_history(self, s, actor, a, fx, n, con):
        start, limit = a.get("after_seq", 0), min(max(int(a.get("limit", 100)), 1), 500)
        rows = con.execute("SELECT body FROM events WHERE seq>? ORDER BY seq LIMIT ?", (start, limit)).fetchall()
        events = [manifest_store.unpack(con,json.loads(row[0])) for row in rows]
        return {"events": self._redact(events), "cursor": events[-1]["seq"] if events else start}

    def cmd_impact(self, s, actor, a, fx, n, con):
        p = self._get(s, "proposals", a.get("proposal_id"))
        return {**impact(s, p["changes"]), "seq": s["seq"]}

    def cmd_open(self, s, actor, a, fx, n, con):
        return {"items": [e for e in s["entries"].values() if e["type"] == "open_question" and
                           not e.get("retracted") and e["data"].get("status", "open") != "resolved" and
                           (not a.get("zone") or e["zone"] == a["zone"]) and
                           (not a.get("due_before") or e["data"].get("due_at", "9999") <= a["due_before"])]}

    def cmd_reviews(self, s, actor, a, fx, n, con):
        return self._redact({"items": [{**p, "status": self._status(s, p)} for p in s["proposals"].values()
                                       if p["status"] not in {"draft", "withdrawn", "committed"} and
                                       (actor["id"] in p["impact"]["owners"].values() or actor["id"] in policy(s)["human_approvers"])]})

    def cmd_operations(self, s, actor, a, fx, n, con):
        return {"items": [e for e in s["revisions"].values() if e.get("type") == "development_operation" and
                          (not a.get("work_item") or e["data"].get("work_item") == a["work_item"])]}

    def cmd_verify(self, s, actor, a, fx, n, con): return self.store.verify(a.get("checkpoint"), con)

    def cmd_replay(self, s, actor, a, fx, n, con):
        self.allowed(actor, "admin")
        self.store.verify(con=con)
        rebuilt = self.store.state(con, s["seq"])
        matched = canonical(rebuilt) == canonical(self.store.state(con))
        indexed.rebuild(con, rebuilt, canonical)
        return {"matched": matched, "repaired": not matched, "state_hash": digest(rebuilt), "replayed_events": s["seq"]}

    @staticmethod
    def _timestamp(value):
        try:
            stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
            require(stamp.tzinfo is not None, "invalid_input", "Timestamp must include timezone")
            return stamp.timestamp()
        except (AttributeError, ValueError) as exc:
            raise Fault("invalid_input", "Invalid RFC3339 timestamp") from exc

    def _units(self, s):
        units = {}
        for unit in s["entries"].values():
            if unit["type"] != "unit" or unit.get("retracted"): continue
            observations = [e for e in s["entries"].values() if e["type"] == "configuration_observation" and
                            e["data"]["unit"] == unit["id"] and not e.get("retracted")]
            by_source = {}
            for e in observations:
                source, ts = e["data"]["source"], self._timestamp(e["data"]["occurred_at"])
                selected = by_source.get(source, [])
                if not selected or ts > self._timestamp(selected[0]["data"]["occurred_at"]): by_source[source] = [e]
                elif ts == self._timestamp(selected[0]["data"]["occurred_at"]): selected.append(e)
            latest = [e for group in by_source.values() for e in group]
            configs = {e["data"]["configuration"] for e in latest}
            approved = unit["data"].get("configuration")
            units[unit["id"]] = {"approved_configuration": approved, "observations": latest,
                                  "ambiguous": len(configs) > 1, "unknown": not latest,
                                  "matches_approved": len(configs) == 1 and approved in configs,
                                  "observed_configuration": next(iter(configs)) if len(configs) == 1 else None}
        return units

    def cmd_why(self, s, actor, a, fx, n, con):
        root = a.get("id"); limit = min(int(a.get("max_depth", 8)), 30)
        require(root in s["entries"] or root in s["revisions"] or root in s["designs"] or root in s["proposals"],
                "not_found", "Unknown provenance target")
        graph = {}
        def edge(source, target, kind):
            if target: graph.setdefault(source, []).append({"target": target, "kind": kind})
        for eid, e in s["entries"].items(): edge(eid, e["revision_id"], "current_revision")
        for rid, e in s["revisions"].items():
            edge(rid, e.get("previous_revision"), "previous_revision")
            if e.get("type") == "decision":
                edge(rid, e["proposal_id"], "proposal")
                for evidence in e.get("evidence", []): edge(rid, evidence, "basis")
            if e.get("type") == "relation" and not e.get("retracted") and e["data"]["kind"] == "derived_from":
                edge(e["data"]["source"], e["data"]["target"], "derived_from")
        for p in s["proposals"].values():
            edge(p["candidate_id"], p["id"], "proposal")
            edge(p["id"], p.get("basis_design"), "basis_design")
            for evidence in p.get("evidence", []): edge(p["id"], evidence, "basis")
            if p.get("decision_id"):
                for e in p["changes"]: edge(e["revision_id"], p["decision_id"], "adopted_by")
        for did, design in s["designs"].items(): edge(did, design.get("decision_id"), "decision")
        paths, pending, truncated = [], [(root, [], {root})], False
        while pending:
            current, path, visited = pending.pop(0)
            if len(path) >= limit:
                truncated = truncated or bool(graph.get(current)); paths.append(path); continue
            edges = [e for e in graph.get(current, []) if e["target"] not in visited]
            if not edges: paths.append(path)
            for item in edges:
                pending.append((item["target"], path + [{"source": current, **item}], visited | {item["target"]}))
            require(len(paths) + len(pending) <= 2000, "query_limit", "Provenance query too broad")
        return {"id": root, "paths": paths, "truncated": truncated, "no_basis": paths == [[]]}

    def cmd_outcomes(self, s, actor, a, fx, n, con):
        d = self._get(s, "revisions", a.get("decision_id"))
        require(d.get("type") == "decision", "invalid_input", "Decision required")
        items = []
        for e in s["entries"].values():
            if e["type"] not in {"eval_result", "incident"} or e.get("retracted"): continue
            links = [link for link in e["data"].get("decisions", []) if link["id"] == d["id"]]
            if e["data"].get("design_revision") in {d["candidate_id"], d["design_id"]}:
                links.append({"id": d["id"], "relation": "associated_with", "intent": "inferred", "basis": "same_design_revision"})
            if links: items.append({"entry": e, "links": links})
        return {"decision_id": d["id"], "items": items}

    def cmd_resolve_conflict(self, s, actor, a, fx, n, con):
        require(actor["id"] == policy(s).get("arbiter"), "unauthorized", "Configured arbiter required")
        require(bool(a.get("reason")), "invalid_input", "Resolution reason required")
        winner = self._get(s, "proposals", a.get("proposal_id"))
        require(self._status(s, winner) == "conflict", "invalid_state", "No conflict to resolve")
        targets = {e["id"] for e in winner["changes"]}
        withdrawn = []
        for p in list(s["proposals"].values()):
            if p["id"] != winner["id"] and p["status"] not in {"draft", "committed", "withdrawn"} and targets & {e["id"] for e in p["changes"]}:
                p = copy.deepcopy(p); p.update(status="withdrawn", resolution={"reason": a["reason"], "arbiter": actor["id"], "winner": winner["id"]})
                self._put(s, fx, "proposals", p["id"], p); withdrawn.append(p["id"])
        return {"selected": winner["id"], "withdrawn": withdrawn, "approval_required": True}

    def cmd_reserve(self, s, actor, a, fx, n, con):
        require(actor["id"] == policy(s).get("arbiter"), "unauthorized", "Configured arbiter required")
        p = self._get(s, "proposals", a.get("proposal_id"))
        require(p["status"] not in {"committed", "withdrawn"}, "invalid_state", "Terminal proposal")
        duration = a.get("seconds", 300)
        require(isinstance(duration, int) and 1 <= duration <= 3600, "invalid_input", "Reservation duration 1–3600 seconds")
        zones = impact(s, p["changes"])["zones"]
        for r in s["reservations"].values():
            require(r["expires_at"] <= self.clock() or not set(zones) & set(r["zones"]), "reserved", "Overlapping reservation exists")
        r = {"id": uid("reservation"), "proposal_id": p["id"], "zones": zones, "expires_at": self.clock() + duration * 1000,
             "reason": a.get("reason", ""), "actor": actor["id"]}
        self._put(s, fx, "reservations", r["id"], r)
        return r

    def cmd_release_reservation(self, s, actor, a, fx, n, con):
        require(actor["id"] == policy(s).get("arbiter"), "unauthorized", "Configured arbiter required")
        r = self._get(s, "reservations", a.get("reservation_id")); r["expires_at"] = self.clock()
        self._put(s, fx, "reservations", r["id"], r)
        return r

    def _work_ready(self, s, w):
        for dep in w.get("dependencies", []):
            source = s["works"].get(dep["work_id"])
            if not source: return False
            if dep.get("condition", "done_required") == "done_required":
                if source["status"] != "done": return False
            else:
                pub = s["publications"].get(dep.get("publication_id"))
                if not pub or pub.get("work_id") != source["id"]: return False
        return True

    def cmd_create_work(self, s, actor, a, fx, n, con):
        self.allowed(actor, "work")
        zone = a.get("zone", "root"); self.zone_write(actor, zone)
        require(s["entries"].get(zone, {}).get("type") == "zone", "invalid_input", "Unknown zone")
        require(bool(a.get("title")) and bool(a.get("completion_condition")), "invalid_input", "Title and completion condition required")
        if a.get("design_id"): require(a["design_id"] in s["designs"], "invalid_input", "Unknown design")
        if a.get("proposal_id"): require(a["proposal_id"] in s["proposals"], "invalid_input", "Unknown proposal")
        for dep in a.get("dependencies", []):
            require(dep.get("work_id") in s["works"], "invalid_input", "Unknown dependency")
            require(dep.get("condition", "done_required") in {"done_required", "published_candidate_allowed"},
                    "invalid_input", "Invalid dependency condition")
        reviewer = a.get("reviewer", actor["id"])
        require(reviewer in s["principals"], "invalid_input", "Unknown reviewer")
        w = {"id": uid("work"), "version": 1, "title": a["title"], "zone": zone, "author": actor["id"],
             "completion_condition": a["completion_condition"], "design_id": a.get("design_id", s["head"]),
             "proposal_id": a.get("proposal_id"), "dependencies": a.get("dependencies", []),
             "inputs": a.get("inputs", []), "reviewer": reviewer, "status": "ready", "claim": None,
             "results": [], "needs_reassessment": False}
        if not self._work_ready(s, w): w["status"] = "blocked"
        self._put(s, fx, "works", w["id"], w)
        return w

    def _work_get(self, s, actor, a):
        self.allowed(actor, "work")
        w = self._get(s, "works", a.get("work_id")); self.zone_write(actor, w["zone"])
        require(a.get("version") == w["version"], "stale_basis", "Work version changed")
        return w

    def _work_save(self, s, fx, w):
        w["version"] += 1
        self._put(s, fx, "works", w["id"], w)
        return w

    def _lease(self, w, actor):
        claim = w.get("claim")
        require(claim and claim["actor"] == actor["id"] and claim["expires_at"] > self.clock(),
                "claim_expired", "Active work claim required")

    def cmd_claim_work(self, s, actor, a, fx, n, con):
        w = self._work_get(s, actor, a)
        require(w["status"] not in {"done", "cancelled", "submitted"} and self._work_ready(s, w), "invalid_state", "Work not ready")
        require(not w.get("manual_block"), "invalid_state", "Work explicitly blocked")
        require(not w["claim"] or w["claim"]["expires_at"] <= self.clock(), "already_claimed", "Work already claimed")
        seconds = a.get("seconds", 300)
        require(isinstance(seconds, int) and 1 <= seconds <= 3600, "invalid_input", "Claim duration 1–3600 seconds")
        w.update(status="in_progress", claim={"actor": actor["id"], "expires_at": self.clock() + seconds * 1000})
        return self._work_save(s, fx, w)

    def cmd_renew_claim(self, s, actor, a, fx, n, con):
        w = self._work_get(s, actor, a); self._lease(w, actor)
        seconds = a.get("seconds", 300)
        require(isinstance(seconds, int) and 1 <= seconds <= 3600, "invalid_input", "Claim duration 1–3600 seconds")
        w["claim"]["expires_at"] = self.clock() + seconds * 1000
        return self._work_save(s, fx, w)

    def cmd_handoff_work(self, s, actor, a, fx, n, con):
        w = self._work_get(s, actor, a); self._lease(w, actor)
        require(bool(a.get("notes")), "invalid_input", "Handoff notes required")
        w.update(status="ready", claim=None, handoff={"from": actor["id"], "notes": a["notes"], "at": self.clock()})
        n.append({"type": "handoff_requested", "target": w["id"], "zones": [w["zone"]]})
        return self._work_save(s, fx, w)

    def cmd_submit_work(self, s, actor, a, fx, n, con):
        w = self._work_get(s, actor, a); self._lease(w, actor)
        require(w["status"] == "in_progress" and not w["needs_reassessment"], "invalid_state", "Work requires reassessment or is not active")
        require(isinstance(a.get("results"), list) and a["results"], "invalid_input", "Result references required")
        for rid in a["results"]: require(rid in s["revisions"] or rid in s["designs"], "invalid_input", "Unknown result")
        w.update(status="submitted", results=a["results"], submission_notes=a.get("notes", ""))
        return self._work_save(s, fx, w)

    def cmd_complete_work(self, s, actor, a, fx, n, con):
        w = self._work_get(s, actor, a)
        require(actor["id"] == w["reviewer"], "unauthorized", "Work reviewer required")
        require(w["status"] == "submitted" and w.get("claim") and w["claim"]["expires_at"] > self.clock(),
                "claim_expired", "Submitted work needs a current claim")
        require(not w["needs_reassessment"] and bool(a.get("reason")), "invalid_state", "Reason and resolved basis required")
        w.update(status="done", completed_at=self.clock(), completion_reason=a["reason"])
        result = self._work_save(s, fx, w)
        for downstream in list(s["works"].values()):
            if downstream["status"] == "blocked" and not downstream.get("manual_block") and self._work_ready(s, downstream):
                downstream = copy.deepcopy(downstream); downstream["status"] = "ready"
                self._work_save(s, fx, downstream)
                n.append({"type": "work_ready", "target": downstream["id"], "zones": [downstream["zone"]]})
        return result

    def _manage_work(self, s, actor, a):
        w = self._work_get(s, actor, a)
        require(w["status"] not in {"done", "cancelled"}, "invalid_state", "Work is terminal")
        require(actor["id"] in {w["author"], w["reviewer"], (w.get("claim") or {}).get("actor")} or "admin" in actor["permissions"],
                "unauthorized", "Work participant required")
        return w

    def cmd_block_work(self, s, actor, a, fx, n, con):
        w = self._manage_work(s, actor, a)
        require(bool(a.get("reason")), "invalid_input", "Block reason required")
        w.update(status="blocked", manual_block=a["reason"], claim=None)
        return self._work_save(s, fx, w)

    def cmd_resume_work(self, s, actor, a, fx, n, con):
        w = self._manage_work(s, actor, a)
        require(w["status"] == "blocked" and self._work_ready(s, w), "invalid_state", "Dependencies not ready")
        w.update(status="ready", manual_block=None, claim=None)
        return self._work_save(s, fx, w)

    def cmd_cancel_work(self, s, actor, a, fx, n, con):
        w = self._manage_work(s, actor, a)
        require(bool(a.get("reason")), "invalid_input", "Cancellation reason required")
        w.update(status="cancelled", cancellation_reason=a["reason"], claim=None)
        return self._work_save(s, fx, w)

    def cmd_work(self, s, actor, a, fx, n, con):
        return self._get(s, "works", a["work_id"]) if a.get("work_id") else {"items": list(s["works"].values())}

    def cmd_context(self, s, actor, a, fx, n, con):
        w = self._get(s, "works", a.get("work_id"))
        p = s["proposals"].get(w.get("proposal_id"))
        d = s["designs"].get(w.get("design_id"))
        if a.get('view', 'full') == 'focused':
            from .focused_context import build_focused_context
            return self._redact(build_focused_context(self, s, actor, a, w, p, d, fx, n, con))
        require(not {'entry_ids', 'discussion_limit', 'before_discussion_seq'} & a.keys(),
                'invalid_input', 'Focused options require view=focused')
        return self._redact({"work": w, "proposal": p, "design": d,
                            "contents": {k: s["revisions"][rid] for k, rid in (d or {}).get("entries", {}).items()},
                            "discussions": self._discussion_entries(s, {w['id'], w.get('proposal_id'), w.get('design_id')} - {None}, con),
                            "questions": self.cmd_open(s, actor, {"zone": w["zone"]}, fx, n, con)["items"],
                            "operations": self.cmd_operations(s, actor, {"work_item": w["id"]}, fx, n, con)["items"]})

    @staticmethod
    def _discussion_entries(s, targets, con):
        entries = {e['revision_id']: e for e in s['entries'].values()
                   if e.get('type') == 'discussion_entry' and not e.get('retracted')
                   and e['data'].get('target') in targets}
        items = []
        for row in con.execute('SELECT body FROM events ORDER BY seq'):
            event = manifest_store.unpack(con,json.loads(row[0])); rid = event['payload'].get('result', {}).get('revision_id')
            if rid in entries:
                items.append({**entries[rid], 'actor': event['actor_id'],
                              'recorded_at': event['recorded_at'], 'seq': event['seq']})
        return items

    def cmd_discuss(self, s, actor, a, fx, n, con):
        target = a.get("target")
        require(target in s["proposals"] or target in s["works"] or target in s["designs"], "invalid_input", "Discussion target required")
        require(bool(a.get("body")), "invalid_input", "Discussion body required")
        evidence = a.get('evidence', [])
        for rid in evidence:
            require(rid in s['revisions'] or rid in s['designs'], 'invalid_input', 'Unknown evidence revision')
        if a.get('reply_to'):
            reply = s['entries'].get(a['reply_to'], {})
            require(reply.get('type') == 'discussion_entry' and reply['data']['target'] == target,
                    'invalid_input', 'Reply must reference a discussion on this target')
        design_id = (s['proposals'][target]['candidate_id'] if target in s['proposals']
                     else s['works'][target].get('design_id') if target in s['works'] else target)
        return self.cmd_record(s, actor, {"type": "discussion_entry", "zone": a.get("zone", "root"),
                               "data": {"target": target, "body": a["body"], "author": actor["id"],
                                        "reply_to": a.get("reply_to"), "basis": a.get("basis", {}),
                                        "evidence": evidence, "design_revision": design_id}}, fx, n, con)

    def cmd_create_improvement(self, s, actor, a, fx, n, con):
        evidence = self._get(s, "revisions", a.get("result_id"))
        require(evidence["type"] in {"eval_result", "incident"}, "invalid_input", "Result or incident required")
        p = self.cmd_propose(s, actor, {**a, "evidence": [evidence["revision_id"]]}, fx, n, con)
        w = self.cmd_create_work(s, actor, {"title": a["title"], "completion_condition": a.get("completion_condition", "Submit improvement candidate"),
                    "zone": a.get("zone", "root"), "design_id": p["candidate_id"], "proposal_id": p["id"]}, fx, n, con)
        return {"proposal": p, "work": w}

    def cmd_publish_candidate(self, s, actor, a, fx, n, con):
        p = self._editable(s, actor, a)
        if a.get("work_id"): require(a["work_id"] in s["works"], "invalid_input", "Unknown work")
        pub = {"id": uid("publication"), "proposal_id": p["id"], "version": p["version"],
               "design_id": p["candidate_id"], "zones": p["impact"]["zones"], "entries": p["impact"]["entries"],
               "work_id": a.get("work_id"), "at": self.clock()}
        previous = [v for v in s["publications"].values() if v["proposal_id"] == p["id"]]
        self._put(s, fx, "publications", pub["id"], pub)
        n.append({"type": "candidate_published", "target": p["id"], "publication_id": pub["id"],
                  "zones": pub["zones"], "entries": pub["entries"]})
        for w in list(s["works"].values()):
            relevant = [dep for dep in w.get("dependencies", []) if dep.get("publication_id") in {v["id"] for v in previous}]
            if relevant:
                w = copy.deepcopy(w); w["needs_reassessment"] = True
                w["basis_update"] = {"publication_id": pub["id"], "previous": [dep["publication_id"] for dep in relevant]}
                self._work_save(s, fx, w)
                n.append({"type": "basis_changed", "target": w["id"], "zones": [w["zone"]],
                          "old": w["basis_update"]["previous"], "new": pub["id"]})
        return pub

    def cmd_reconcile_work_basis(self, s, actor, a, fx, n, con):
        w = self._manage_work(s, actor, a)
        require(w["needs_reassessment"], "invalid_state", "No reassessment pending")
        require(a.get("action") in {"keep", "switch"} and bool(a.get("reason")), "invalid_input", "Choose keep/switch and record reason")
        if a["action"] == "switch":
            pub = self._get(s, "publications", a.get("publication_id"))
            require(pub["id"] == w["basis_update"]["publication_id"], "stale_basis", "Expected updated publication")
            for dep in w["dependencies"]:
                if dep.get("publication_id") in w["basis_update"]["previous"]: dep["publication_id"] = pub["id"]
            w["results"] = []
            if w["status"] == "submitted": w["status"] = "in_progress"
        w.update(needs_reassessment=False, basis_resolution={"action": a["action"], "reason": a["reason"], "at": self.clock()})
        return self._work_save(s, fx, w)

    def cmd_subscribe(self, s, actor, a, fx, n, con):
        require(any(a.get(k) for k in ("targets", "zones", "types")), "invalid_input", "Subscription filter required")
        cursor = a.get("cursor", s["seq"])
        require(0 <= cursor <= s["seq"], "cursor_expired", "Resync from state cursor")
        sub = {"id": uid("subscription"), "actor": actor["id"], "targets": a.get("targets", []),
               "zones": a.get("zones", []), "types": a.get("types", []), "active": True, "start_seq": cursor}
        self._put(s, fx, "subscriptions", sub["id"], sub)
        return {**sub, "cursor": cursor, "head": s["head"]}

    def cmd_unsubscribe(self, s, actor, a, fx, n, con):
        sub = self._get(s, "subscriptions", a.get("subscription_id"))
        require(sub["actor"] == actor["id"], "unauthorized", "Subscription belongs to another actor")
        sub["active"] = False
        self._put(s, fx, "subscriptions", sub["id"], sub)
        return sub

    def cmd_events(self, s, actor, a, fx, n, con):
        cursor = a.get("cursor", 0)
        require(isinstance(cursor, int) and 0 <= cursor <= s["seq"], "cursor_expired", "Resync from state cursor")
        limit = min(max(int(a.get("limit", 100)), 1), 500)
        subs = [sub for sub in s["subscriptions"].values() if sub["active"] and sub["actor"] == actor["id"]]
        rows = con.execute("SELECT body FROM events WHERE seq>? ORDER BY seq LIMIT ?", (cursor, limit)).fetchall()
        items = []
        owned_works = {w["id"] for w in s["works"].values() if actor["id"] in {w["author"], w["reviewer"], (w.get("claim") or {}).get("actor")}}
        for row in rows:
            event = manifest_store.unpack(con,json.loads(row[0])); cursor = event["seq"]
            for index, notice in enumerate(event["payload"].get("notices", [])):
                selected = notice["target"] in owned_works
                for sub in subs:
                    selected = selected or (event["seq"] > sub["start_seq"] and
                        (not sub["targets"] or notice["target"] in sub["targets"] or bool(set(sub["targets"]) & set(notice.get("entries", [])))) and
                        (not sub["zones"] or bool(set(sub["zones"]) & set(notice.get("zones", [])))) and
                        (not sub["types"] or notice["type"] in sub["types"]))
                if selected:
                    items.append({"event_id": event["event_id"] + ":" + str(index), "source_event_id": event["event_id"],
                                  "seq": event["seq"], "recorded_at": event["recorded_at"], **notice})
        return {"events": items, "cursor": cursor, "head_seq": s["seq"], "has_more": cursor < s["seq"]}

    def cmd_export(self, s, actor, a, fx, n, con):
        self.allowed(actor, "admin")
        self.store.verify(con=con)
        events = [manifest_store.unpack(con,json.loads(row[0])) for row in con.execute("SELECT body FROM events ORDER BY seq")]
        infos = [info for e in s["revisions"].values() if e.get("type") == "artifact_snapshot"
                 for info in e["data"]["files"].values()]
        hashes = {part["hash"] for info in infos for part in self.store.file_parts(info)}
        blobs = {h: base64.b64encode(self.store.read_blob(h)).decode() for h in sorted(hashes)}
        return {"format": "gantry-backup-v2" if any("chunks" in info for info in infos) else "gantry-backup-v1", "events": events, "blobs": blobs,
                "projection_hash": digest(s), "checkpoint": {"ledger_id": s["ledger_id"], "seq": s["seq"], "hash": events[-1]["hash"]}}
