from concurrent.futures import ThreadPoolExecutor
import secrets
import unittest
import test_service as fixtures


class CollaborationTests(unittest.TestCase):
    setUp = fixtures.LedgerTests.setUp
    tearDown = fixtures.LedgerTests.tearDown
    call = fixtures.LedgerTests.call
    proposal = fixtures.LedgerTests.proposal
    approve = fixtures.LedgerTests.approve
    commit = fixtures.LedgerTests.commit
    submit = fixtures.LedgerTests.submit
    assertFault = fixtures.LedgerTests.assertFault

    def work(self, **extra):
        return self.call("create_work", {"title": "ハンド変更", "completion_condition": "設計を提出", **extra})

    def test_published_candidate_enables_parallel_work_and_notifies(self):
        p = self.proposal()
        up = self.work(proposal_id=p["id"])
        sub = self.call("subscribe", {"targets": [p["id"]]})
        pub = self.call("publish_candidate", {"proposal_id": p["id"], "version": 1, "work_id": up["id"]})
        down = self.work(dependencies=[{"work_id": up["id"], "condition": "published_candidate_allowed", "publication_id": pub["id"]}])
        down = self.call("claim_work", {"work_id": down["id"], "version": 1})
        self.assertEqual(down["status"], "in_progress")
        p = self.call("amend", {"proposal_id": p["id"], "version": 1, "changes": [{"id": "hand", "type": "subsystem", "data": {"length_mm": 90}}]})
        pub2 = self.call("publish_candidate", {"proposal_id": p["id"], "version": 2, "work_id": up["id"]})
        down = self.call("work", {"work_id": down["id"]})
        self.assertTrue(down["needs_reassessment"])
        self.assertEqual(down["dependencies"][0]["publication_id"], pub["id"])
        down = self.call("reconcile_work_basis", {"work_id": down["id"], "version": down["version"],
                        "action": "switch", "publication_id": pub2["id"], "reason": "新しい質量で計算"})
        self.assertFalse(down["needs_reassessment"])
        events = self.call("events", {"cursor": sub["cursor"]})
        self.assertIn("basis_changed", [e["type"] for e in events["events"]])
        self.assertEqual(len({e["event_id"] for e in events["events"]}), len(events["events"]))
        self.assertEqual(self.call("events", {"cursor": sub["cursor"]}), events)
        self.assertIsNone(self.call("state")["head"])

    def test_work_claim_race_and_expiry(self):
        w = self.work()
        def claim(_):
            try: return self.call("claim_work", {"work_id": w["id"], "version": 1, "seconds": 1})
            except Exception as e: return e
        with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(claim, range(2)))
        self.assertEqual(sum(isinstance(r, dict) for r in results), 1)
        w = next(r for r in results if isinstance(r, dict)); self.now += 1001
        self.assertFault("claim_expired", lambda: self.call("submit_work", {"work_id": w["id"], "version": w["version"], "results": []}))

    def test_subscribe_from_snapshot_does_not_lose_intervening_publication(self):
        p = self.proposal()
        cursor = self.call("state")["cursor"]
        pub = self.call("publish_candidate", {"proposal_id": p["id"], "version": 1})
        subscription = self.call("subscribe", {"targets": [p["id"]], "cursor": cursor})
        notifications = self.call("events", {"cursor": subscription["cursor"]})
        self.assertIn(pub["id"], [e.get("publication_id") for e in notifications["events"]])

    def test_handoff_and_default_dependency_wait(self):
        up = self.work()
        down = self.work(dependencies=[{"work_id": up["id"]}])
        self.assertEqual(down["status"], "blocked")
        self.assertFault("invalid_state", lambda: self.call("claim_work", {"work_id": down["id"], "version": 1}))
        up = self.call("claim_work", {"work_id": up["id"], "version": 1})
        up = self.call("handoff_work", {"work_id": up["id"], "version": up["version"], "notes": "指長変更済み、較正は未実施"})
        self.assertEqual(up["status"], "ready")
        self.assertIn("較正", self.call("context", {"work_id": up["id"]})["work"]["handoff"]["notes"])

    def test_observations_do_not_rewind_on_late_arrival(self):
        p = self.call("propose", {"title": "個体", "changes": [{"id": "unit1", "type": "unit", "data": {"serial": "001"}}]})
        self.submit(p); self.approve(p); self.commit(p)
        c1 = self.call("record", {"type": "configuration", "data": {"slots": {"hand": "unknown"}}})
        c2 = self.call("record", {"type": "configuration", "data": {"slots": {"hand": "not_applicable"}}})
        for c, ts in [(c2, "2026-09-14T12:00:00Z"), (c1, "2026-09-13T12:00:00Z")]:
            self.call("record", {"type": "configuration_observation", "data": {"unit": "unit1", "source": "robot",
                       "configuration": c["revision_id"], "occurred_at": ts}})
        self.assertEqual(self.call("state")["units"]["unit1"]["observed_configuration"], c2["revision_id"])

    def test_result_deduplication_and_outcomes(self):
        p = self.proposal(); self.submit(p); self.approve(p); d = self.commit(p)
        a = {"type": "eval_result", "source_id": "CI", "source_event_id": "run-1", "data": {
             "run_id": "run-1", "design_revision": d["design_id"], "decisions": [{"id": d["id"], "relation": "evaluates"}]}}
        first = self.call("record", a); second = self.call("record", a)
        self.assertEqual(first["revision_id"], second["revision_id"])
        self.assertEqual(len(self.call("outcomes", {"decision_id": d["id"]})["items"]), 1)
        self.assertEqual(first["data"]["configuration"], "unknown")
        why = self.call("why", {"id": "hand"})
        self.assertTrue(any(len(path) >= 3 for path in why["paths"]))


if __name__ == "__main__": unittest.main()
