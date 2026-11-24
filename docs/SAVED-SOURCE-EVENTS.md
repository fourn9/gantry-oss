# Receive completed exports in Studio

Use a bound, writable [workspace](CONNECTED_WORKSPACE.md) and a private Gantry token. A producer queues a local receipt for one versioned path. The workstation holding the token processes that receipt. The resulting unshared checkpoint retains the source revision, SHA-256, previous context and requirement references. Each exported revision needs a distinct path. Ordinary edits in neighboring files stay local.

### Autodesk Fusion on macOS

1. Create an export subdirectory within the bound work's write scope. Keep the add-in itself in a separate trusted directory.
2. Copy the [GantrySaved add-in directory](../examples/robotics-events/GantrySaved) there and copy [source_receipts.py](../gantry/source_receipts.py) into it. Put a private `enrollment.json` next to the manifest. Example: `{"workspace":"/absolute/bound-work","exports":"mechanical/exports","data_file_id":"EXACT_FUSION_DATAFILE_ID"}`. Obtain the enrolled design's DataFile.id from Fusion. The add-in registers for exactly that design.
3. Add the folder from Fusion's Scripts and Add-Ins dialog and run the add-in. Save the enrolled standalone design and keep its unmodified version active in the Design workspace until the cloud upload completes. The callback matches the exact cloud version, exports a version-specific F3D, then writes a local receipt. Referenced assemblies and inactive/modified documents are held. Details appear in Fusion's Text Commands log. Stop the add-in to unregister it.

The [Autodesk completion event](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_Application_dataFileComplete.htm) fires after cloud translation. The [export API](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/ExportManager_Sample.htm) creates the archive. This path requires an enrolled, licensed Fusion session for native acceptance.

### ROS 2

On the enrolled workstation, use a sourced ROS 2 environment containing `rclpy`, a `WriteSplitEvent` interface with `node_name`, and Gantry. Start the [receiver](../examples/robotics-events/rosbag_closed.py) on a trusted ROS graph, supplying the recorder's exact advertised event topic and fully qualified node name:

```sh
python examples/robotics-events/rosbag_closed.py --workspace /absolute/bound-work \
  --folder /absolute/bound-work/control/run-015 --topic /your/recorder_event_topic \
  --recorder /your_recorder
```

Only a closed MCAP directly inside the enrolled recording directory is queued. Event topics and last-segment notifications vary by recorder version. Inspect the advertised type with `ros2 topic list -t`. For an application-owned recorder, invoke the same producer directly **after** `writer.close()` returns. This also handles a last segment or a missed notification from a stopped subscriber:

```python
from gantry.source_receipts import enqueue
enqueue("/absolute/bound-work", "rosbag-closed", "control/run-015/segment-0.mcap", "segment-0.mcap")
```

The [ROS message contract](https://docs.ros.org/en/rolling/p/rosbag2_interfaces/msg/WriteSplitEvent.html) identifies the closed file separately from the newly opened file. The stream path checks finalized framing and byte integrity. It does not deserialize messages or establish that a robot test passed.

Runtime check on Apple Silicon: ROS 2 Jazzy, rosbag2 0.26.11 and Cyclone DDS recorded a synthetic string topic on localhost. All eight split/close notifications, including the final close, reached the receiver. After restoration the native ROS reader returned all 75 messages in order. No post-exit catch-up was needed in that run.

### Ingest and review

Run this on the authorized workstation after a save. Add `--follow` to process future receipts until Ctrl+C. The editor and recorder hooks need no Gantry credential.

```sh
gantry --url https://your-gantry.example --token-file /private/gantry.token \
  workspace receive-events --root /absolute/bound-work
```

A successful delivery removes the local receipt. A held receipt remains for inspection and retry and the command returns a failure exit code. Other valid receipts can still be processed. If the operator also enables general-purpose workspace watch, that separate command includes all eligible local edits. Use receipt ingestion alone for event-scoped capture.

An existing producer can deliver directly with `workspace saved-event --event-kind rosbag-closed --event-path control/run-015/segment-0.mcap --source-revision segment-0.mcap --sha256 HEX --root /absolute/bound-work`. The producer must provide the digest of the completed bytes. Review checkpoints in Studio and share when ready. The workspace limit is 10,000 files and 1 GiB total. Full fleet archives exceed this limit.
