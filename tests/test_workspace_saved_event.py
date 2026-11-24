import hashlib
import unittest
from gantry.model import Fault
from gantry.source_receipts import enqueue, enrolled_path
from gantry.workspace_events import source_event, receive_events
import test_workspace_client as fixtures


class SavedEventTests(unittest.TestCase):
    setUp = fixtures.WorkspaceClientTests.setUp
    tearDown = fixtures.WorkspaceClientTests.tearDown
    workspace = fixtures.WorkspaceClientTests.workspace
    imported = fixtures.WorkspaceClientTests.imported
    call = fixtures.WorkspaceClientTests.call
    artifact = fixtures.WorkspaceClientTests.artifact
    connect = fixtures.WorkspaceClientTests.connect
    policy = fixtures.WorkspaceClientTests.policy

    def test_scoped_save_is_idempotent_and_retains_context(self):
        workspace, initial = self.workspace()
        path = "mechanical/arm-v4.f3d"
        raw = b"opaque external archive"
        (workspace.root / path).write_bytes(raw)
        (workspace.root / "control/main.py").write_text("private unsaved-to-ledger work")
        event = source_event("fusion-saved", path, "design:4", hashlib.sha256(raw).hexdigest())
        first = workspace.sync(event=event)
        self.assertEqual(first["status"], "captured")
        again = workspace.sync(event=event)
        self.assertEqual(again["state_id"], first["state_id"])
        view = self.call("get_development_state", {"state_id": first["state_id"]})
        self.assertEqual(view["manifest"][path]["hash"], event["sha256"])
        self.assertEqual(view["state"]["context"]["environment"]["saved_source_events"][path], event)
        self.assertEqual(view["state"]["context"]["requirements"], ["Travel 10 mm"])
        self.assertEqual(view["status"]["adoption"], "unadopted")
        self.assertEqual(view["status"]["verification"], "unverified")
        self.assertEqual([item["path"] for item in workspace.status()["changes"]], ["control/main.py"])

    def test_rejects_stale_bytes_outside_scope_and_unclosed_bag(self):
        workspace, initial = self.workspace()
        with self.assertRaises(ValueError):
            enrolled_path(workspace.root,"outside-work.f3d")
        path = "control/run.mcap"
        raw = b"unfinished"
        (workspace.root / path).write_bytes(raw)
        event = source_event("rosbag-closed", path, "run-1", hashlib.sha256(raw).hexdigest())
        for bad in [event, {**event, "sha256": "0" * 64}, {**event, "path": "elsewhere.mcap"}]:
            with self.assertRaises(Fault):
                workspace.sync(event=bad)
        self.assertEqual(workspace.status()["state_id"], initial["state"]["id"])

    def test_large_stream_preserves_baseline_and_uses_one_receipt(self):
        from gantry.integrations.mcap_capture import MAGIC
        from gantry.continuity_adapter import restore_development_state
        workspace, initial = self.workspace()
        path = "control/record-001.mcap"
        # Synthetic footer for transport testing. Codec validation uses upstream bags.
        data = MAGIC + bytes(17 * 1024**2) + b"\x02" + (20).to_bytes(8,"little") + bytes(20) + MAGIC
        (workspace.root / path).write_bytes(data)
        receipt = enqueue(workspace.root, "rosbag-closed", path, "record-001")
        self.assertEqual(receipt,enqueue(workspace.root, "rosbag-closed", path, "record-001"))
        result, = receive_events(workspace)
        self.assertEqual(result["status"], "captured")
        self.assertFalse(receipt.exists())
        view = self.call("get_development_state", {"state_id": result["state_id"]})
        self.assertEqual(view["manifest"][path]["size"],len(data))
        self.assertIn("chunks",view["manifest"][path])
        restored=restore_development_state(self.client,result["state_id"],self.root/"back","verify-recording")
        from pathlib import Path
        self.assertEqual((Path(restored["workspace"])/path).read_bytes(),data)
        self.assertIn("mechanical/part.step",view["manifest"])

    def test_queue_holds_changed_bytes_and_still_delivers_independent_receipt(self):
        workspace, initial = self.workspace()
        path = "mechanical/work.f3d"
        other = "mechanical/approved.f3d"
        for name in [path,other]:
            (workspace.root / name).write_bytes(b"v1")
            enqueue(workspace.root,"fusion-saved",name,"v1")
        (workspace.root / path).write_bytes(b"v2")
        rows = receive_events(workspace)
        self.assertCountEqual([row["status"] for row in rows],["held","captured"])
        self.assertEqual(receive_events(workspace)[0]["error"],"stale_basis")
