import base64
from concurrent.futures import ThreadPoolExecutor
import json
import secrets
import tempfile
import unittest

from gantry.model import Fault, canonical
from gantry.service import Service, token_hash


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.now = 1000000
        self.svc = Service(self.temp.name, clock=lambda: self.now)
        self.token = self.svc.bootstrap(consent_seconds=3600)["token"]

    def tearDown(self): self.temp.cleanup()

    def call(self, name, args=None, token=None, key=None):
        return self.svc.call(token or self.token, name, args or {}, key or secrets.token_hex(12))

    def proposal(self, eid="hand", data=None):
        old = self.call("state")["entries"].get(eid)
        return self.call("propose", {"title": "指の設計変更", "rationale": "把持機能の改善",
                         "changes": [{"id": eid, "type": "subsystem", "zone": "root", "data": data or {"length_mm": 80},
                                      "expected_revision": (old or {}).get("revision_id")}]})

    def approve(self, p):
        a = {"proposal_id": p["id"], "version": p["version"], "reason": "構成と根拠を確認"}
        self.call("endorse", a)
        self.call("review_adoption", {**a, "verdict": "approve"})

    def commit(self, p): return self.call("commit", {"proposal_id": p["id"], "version": p["version"]})
    def submit(self, p): return self.call("submit", {"proposal_id": p["id"], "version": p["version"]})

    def assertFault(self, code, fn):
        with self.assertRaises(Fault) as caught: fn()
        self.assertEqual(caught.exception.code, code)

    def test_end_to_end_two_revisions(self):
        p = self.proposal(); self.submit(p)
        self.assertNotIn("hand", self.call("state")["entries"])
        self.approve(p); d = self.commit(p)
        first = self.call("state")["head"]
        self.assertEqual(self.call("design")["contents"]["hand"]["data"]["length_mm"], 80)
        p2 = self.proposal(data={"length_mm": 85}); self.submit(p2); self.approve(p2); self.commit(p2)
        self.assertEqual(self.call("design", {"design_id": first})["contents"]["hand"]["data"]["length_mm"], 80)
        self.assertTrue(self.call("verify")["valid"])
        self.assertTrue(self.call("replay")["matched"])
        self.assertTrue(any(e["payload"]["command"] == "commit" for e in self.call("history")["events"]))

    def test_no_human_no_commit(self):
        p = self.proposal(); self.submit(p)
        self.call("endorse", {"proposal_id": p["id"], "version": 1, "reason": "ok"})
        self.assertFault("human_approval_required", lambda: self.commit(p))

    def test_review_preserves_previous_trial_without_using_it_as_current_evidence(self):
        p = self.proposal()
        for verdict in ["fail", "pass"]:
            self.call("record", {"type": "eval_result", "data": {
                "run_id": "old-" + verdict, "design_revision": p["candidate_id"], "verdict": verdict}})
        other = self.proposal(eid="other")
        self.call("record", {"type": "eval_result", "data": {
            "run_id": "unrelated", "design_revision": other["candidate_id"], "verdict": "pass"}})
        amended = self.call("amend", {"proposal_id": p["id"], "version": 1,
            "changes": [{"id": "hand", "type": "subsystem", "data": {"length_mm": 90}}]})
        context = self.call("review_context", {"proposal_id": p["id"]})
        self.assertEqual(context["results"], [])
        self.assertEqual({r["data"]["run_id"] for r in context["historical_results"]}, {"old-fail", "old-pass"})
        self.assertTrue(all(r["source_candidate_version"] == 1 for r in context["historical_results"]))
        self.call("record", {"type": "eval_result", "data": {
            "run_id": "current", "design_revision": amended["candidate_id"], "verdict": "fail"}})
        context = self.call("review_context", {"proposal_id": p["id"]})
        self.assertEqual([r["data"]["run_id"] for r in context["results"]], ["current"])
        self.assertEqual(len(context["historical_results"]), 2)

    def test_agent_cannot_impersonate_human(self):
        secret = secrets.token_urlsafe(32)
        p = self.call("propose", {"title": "Add agent", "changes": [{"id": "agent", "type": "principal", "data": {
            "kind": "agent", "permissions": ["read", "record", "propose", "work"], "token_hash": token_hash(secret)}}]})
        self.submit(p); self.approve(p); self.commit(p)
        p = self.proposal(); self.submit(p)
        self.assertFault("human_approval_required", lambda: self.call("review_adoption", {
            "proposal_id": p["id"], "version": 1, "reason": "yes", "verdict": "approve"}, token=secret))
        self.assertFault("invalid_input", lambda: self.call("state", {"actor_id": "admin"}, token=secret))
        self.assertNotIn("token_hash", canonical(self.call("state")))

    def test_record_cannot_bypass_approval(self):
        self.assertFault("invalid_input", lambda: self.call("record", {"type": "subsystem", "id": "hand", "data": {}}))
        self.call("record", {"type": "software_version", "data": {"git_sha": "a" * 40}})
        self.assertIsNone(self.call("state")["head"])

    def test_amend_invalidates_approval(self):
        p = self.proposal(); self.submit(p); self.approve(p)
        p = self.call("amend", {"proposal_id": p["id"], "version": 1,
                     "changes": [{"id": "hand", "type": "subsystem", "data": {"length_mm": 90}}]})
        self.submit(p)
        self.call("endorse", {"proposal_id": p["id"], "version": 2, "reason": "ok"})
        self.assertFault("human_approval_required", lambda: self.commit(p))

    def test_conflicting_proposals_cannot_commit(self):
        p = self.proposal(); q = self.proposal(data={"length_mm": 99})
        self.submit(p); self.submit(q); self.approve(p)
        self.assertFault("conflict", lambda: self.commit(p))
        self.call("withdraw", {"proposal_id": q["id"], "version": 1})
        self.commit(p)

    def test_idempotency_and_concurrent_commit(self):
        p = self.proposal(); self.submit(p); self.approve(p)
        args = {"proposal_id": p["id"], "version": 1}
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.call("commit", args, key="same"), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertFault("idempotency_mismatch", lambda: self.call("commit", {**args, "version": 2}, key="same"))

    def test_restore_artifact_and_detect_corruption(self):
        raw = b"test CAD bytes\x00\x01"
        a = self.call("capture_artifact", {"files": {"part.CATPart": base64.b64encode(raw).decode()}})
        restored = self.call("restore_artifact", {"revision_id": a["revision_id"]})
        self.assertEqual(base64.b64decode(restored["files"]["part.CATPart"]), raw)
        h = a["data"]["files"]["part.CATPart"]["hash"]
        (self.svc.store.blobs / h).write_bytes(b"corrupt")
        self.assertFault("integrity_error", lambda: self.call("restore_artifact", {"revision_id": a["revision_id"]}))
        self.assertFault("invalid_input", lambda: self.call("capture_artifact", {"files": {"../oops": "YQ=="}}))

    def test_tamper_and_truncate(self):
        self.proposal()
        cp = self.call("verify")
        with self.svc.store.connect() as con: con.execute("DELETE FROM events WHERE seq=?", (cp["seq"],))
        self.assertFault("integrity_error", lambda: self.svc.store.verify(cp))


if __name__ == "__main__": unittest.main()
