"""Canonical representation and deterministic projection. No clock or I/O."""
import copy
import hashlib
import json
import re
import uuid
from collections.abc import Mapping


class Fault(Exception):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code, self.message, self.details = code, message, details or {}

    def as_dict(self):
        return {"code": self.code, "message": self.message, "details": self.details}


def require(condition, code, message, **details):
    if not condition:
        raise Fault(code, message, details)


def _not_json(value):
    raise TypeError(type(value).__name__)


def canonical(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False,
                          default=lambda v: dict(v) if isinstance(v, Mapping) else _not_json(v))
    except (ValueError, TypeError) as exc:
        raise Fault("invalid_input", "JSON must contain finite, serializable values") from exc


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def uid(prefix):
    return prefix + "_" + uuid.uuid4().hex


def identifier(value):
    require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", value),
            "invalid_input", "Invalid identifier")
    return value


TABLES = ("entries", "revisions", "proposals", "designs", "works", "publications",
          "subscriptions", "reservations", "principals")
DEVELOPMENT_TABLES = ("dev_sessions", "dev_contracts", "dev_executions", "dev_milestones", "dev_steps")
DEVELOPMENT_TABLES += ("dev_states", "dev_changes", "dev_shares", "dev_evaluations", "dev_restores", "dev_reflections")
DEVELOPMENT_TABLES += ("product_projects", "product_integrations", "product_signals", "product_uploads",
                       "product_sessions", "product_notes", "product_workers")
DEVELOPMENT_TABLES += ("automation_policies", "analysis_runs", "signal_assessments")
DEVELOPMENT_TABLES += ("evidence_views", "validation_maps", "validation_plans")
DEVELOPMENT_TABLES += ("review_teams", "change_reviews", "review_heads", "review_responses", "review_lessons")
DEVELOPMENT_TABLES += ("review_automation", "mentor_jobs")
DEVELOPMENT_TABLES += ('agent_connections', 'connection_operations')
DEVELOPMENT_TABLES += ('team_proposals', 'team_messages', 'bot_memories')
DEVELOPMENT_TABLES += ('organizations', 'persistent_bots', 'bot_bindings', 'bot_runtimes', 'organization_memories')
DEVELOPMENT_TABLES += ('bot_projects', 'bot_tasks', 'bot_task_messages')
DEVELOPMENT_TABLES += ('bot_decisions', 'bot_actions', 'bot_team_proposals')
MANAGED = {"goal", "requirement", "design_document", "subsystem", "part_spec", "bom",
           "validation_plan", "unit", "zone", "interface", "policy", "principal", "relation"}
RECORDED = {"hardware_rev", "software_version", "checkpoint", "calibration", "configuration",
            "configuration_observation", "eval_result", "incident", "open_question",
            "discussion_entry", "development_operation", "artifact_snapshot"}
RELATIONS = {"depends_on", "implements", "uses_interface", "derived_from", "evaluates",
             "associated_with", "supersedes"}


def empty_state():
    return {**{k: {} for k in TABLES}, "head": None, "seq": 0, "ledger_id": None}


def project(state, event):
    require(event["schema_version"] == 1, "unsupported_schema", "Unknown event schema")
    require(event["event_type"] in {"bootstrap", "command"}, "unsupported_schema", "Unknown event type")
    for effect in event["payload"]["effects"]:
        if effect["table"] == "meta":
            require(effect["key"] in {"head", "ledger_id"}, "invalid_event", "Invalid meta effect")
            state[effect["key"]] = copy.deepcopy(effect["value"])
        else:
            require(effect["table"] in TABLES + DEVELOPMENT_TABLES, "invalid_event", "Invalid effect table")
            state.setdefault(effect["table"], {})[effect["key"]] = copy.deepcopy(effect["value"])
    state["seq"] = event["seq"]
    return state


def validate_entry(kind, data):
    require(kind in MANAGED | RECORDED, "invalid_input", "Unknown entry type", type=kind)
    require(isinstance(data, dict), "invalid_input", "Entry data must be an object")
    canonical(data)
    if kind == "zone":
        require(data.get("participation", "participating") in {"participating", "external"},
                "invalid_input", "Invalid zone participation")
        if data.get("participation") != "external":
            identifier(data.get("owner"))
    elif kind == "principal":
        require(data.get("kind") in {"human", "agent", "service"}, "invalid_input", "Invalid principal kind")
        require(isinstance(data.get("permissions"), list), "invalid_input", "permissions is required")
        require(set(data["permissions"]) <= {"read", "record", "propose", "work", "admin"},
                "invalid_input", "Unknown permission")
        require(re.fullmatch(r"[a-f0-9]{64}", data.get("token_hash", "")), "invalid_input", "token_hash required")
        if 'allowed_commands' in data:
            require(isinstance(data['allowed_commands'], list) and
                    all(isinstance(x, str) and re.fullmatch(r'[a-z_]+', x) for x in data['allowed_commands']),
                    'invalid_input', 'allowed_commands must be command names')
        if 'expires_at' in data:
            require(type(data['expires_at']) is int and data['expires_at'] > 0,
                    'invalid_input', 'expires_at must be an epoch millisecond integer')
    elif kind == "policy":
        require(isinstance(data.get("human_approvers"), list) and data["human_approvers"],
                "invalid_input", "At least one human approver is required")
        period = data.get("consent_seconds")
        require(period is None or (isinstance(period, int) and not isinstance(period, bool) and period > 0),
                "invalid_input", "consent_seconds must be positive or null")
    elif kind == "relation":
        require(data.get("kind") in RELATIONS, "invalid_input", "Unknown relation")
        identifier(data.get("source")); identifier(data.get("target"))
    elif kind == "configuration":
        require(isinstance(data.get("slots"), dict), "invalid_input", "Configuration slots required")
    elif kind == "configuration_observation":
        for field in ("unit", "source", "configuration", "occurred_at"):
            require(bool(data.get(field)), "invalid_input", field + " is required")
    elif kind == "eval_result":
        require(bool(data.get("run_id")), "invalid_input", "run_id is required")
        require(data.get("verdict", "unknown") in {"pass", "fail", "unknown"},
                "invalid_input", "Invalid evaluation verdict")
    elif kind == "validation_plan":
        require(isinstance(data.get("required", False), bool), "invalid_input", "required must be boolean")
    elif kind == "development_operation":
        for field in ("work_item", "tool", "status", "capture_scope"):
            require(bool(data.get(field)), "invalid_input", field + " is required")
        require(data["status"] in {"success", "failed", "unknown", "cancelled"},
                "invalid_input", "Invalid operation status")


def policy(state):
    entry = state["entries"].get("policy")
    require(entry is not None, "invalid_state", "Missing policy")
    return entry["data"]


def impact(state, changes, limit=10000):
    """Use the union of the pre/post graph, including removed dependencies."""
    before = state["entries"]
    after = copy.deepcopy(before)
    changed = set()
    for change in changes:
        eid = change["id"]
        changed.add(eid)
        old = after.get(eid, {})
        after[eid] = {"id": eid, "type": change.get("type", old.get("type")),
                      "zone": change.get("zone", old.get("zone", "root")),
                      "data": change.get("data", {}), "revision_id": change.get("revision_id")}
    graphs = [before, after]
    affected, paths = set(changed), {key: [key] for key in changed}
    edges = set()
    for graph in graphs:
        for eid, entry in graph.items():
            if entry.get("type") == "relation" and not entry.get("retracted"):
                d = entry["data"]
                if d.get("kind") in {"depends_on", "implements", "uses_interface"}:
                    edges.add((d["target"], d["source"], eid))
                    if eid in changed:
                        for node in (d["source"], d["target"]):
                            affected.add(node); paths[node] = [eid, node]
    pending = list(sorted(affected))
    while pending:
        node = pending.pop(0)
        for target, source, relation in sorted(edges):
            if target == node and source not in affected:
                affected.add(source); paths[source] = paths[node] + [relation, source]
                pending.append(source)
        require(len(affected) <= limit, "impact_limit", "Impact exploration limit reached")
    zones = set()
    basis = {}
    for graph in graphs:
        for eid in affected:
            entry = graph.get(eid)
            if entry:
                zones.add(entry["zone"])
                if entry["type"] == "interface":
                    zones.update(entry["data"].get("zones", []))
    for eid in affected:
        basis[eid] = before.get(eid, {}).get("revision_id")
    # Bind all impact-bearing relations reachable from the read set.
    for target, source, relation in edges:
        if target in affected or source in affected:
            basis[relation] = before.get(relation, {}).get("revision_id")
    # A downstream edit also reads its upstream prerequisites. Keep this read set
    # separate from impact so it does not invent upstream approval obligations.
    reads, pending = set(affected), list(sorted(affected))
    while pending:
        node = pending.pop()
        for target, source, relation in sorted(edges):
            if source == node:
                basis[relation] = before.get(relation, {}).get("revision_id")
                basis[target] = before.get(target, {}).get("revision_id")
                if target not in reads:
                    reads.add(target); pending.append(target)
        require(len(reads) <= limit, "impact_limit", "Prerequisite exploration limit reached")
    basis["policy"] = before.get("policy", {}).get("revision_id")
    owners, external = {}, []
    for zone in sorted(zones):
        z = before.get(zone)
        require(z is not None and z["type"] == "zone", "invalid_input", "Unknown zone", zone=zone)
        basis[zone] = z["revision_id"]
        d = z["data"]
        if d.get("participation") == "external" and not d.get("proxy_owner"):
            external.append(zone)
        else:
            owner = d.get("proxy_owner") or d.get("owner")
            owners[zone] = owner
            basis[owner] = before.get(owner, {}).get("revision_id")
    return {"entries": sorted(affected), "zones": sorted(zones), "owners": owners,
            "external": external, "basis": basis, "paths": paths}
