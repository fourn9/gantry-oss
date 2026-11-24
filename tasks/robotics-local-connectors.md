# Local robotics connectors

Reviewed engineering workflow: addyosmani/agent-skills at 2686b620fc1fed2e8f60c704839c766b8594c6b6.

1. Run KiCad ERC/DRC on a scratch copy of explicit trusted local inputs. Keep the editable input, selected project/rule files, tool report, version and findings together. A report with findings is a successful capture. Preserve the project's requirement and adoption policies.
2. Read a selected ROS 2/Foxglove MCAP locally. Preserve original bytes and expose recorder-reported channel/statistics metadata without decoding or expanding message chunks. Missing summary fields must stay unknown. Reject truncated records and inconsistent indexed metadata.
3. Transfer native CAD evidence from a customer-owned Windows host via the existing scoped publication path. Support review of saved bytes on the Mac; qualify native execution only on the exact licensed vendor/version. Document unavailable products and prerequisites.
4. Exercise normal CLI capture, integrity checks, publication, stale/scope checks and retrieval. Use a bundled KiCad template and an upstream rosbag2 fixture. Separate actual host activity from contract tests and unpublished local work.

Mac acceptance also covers a native FreeCAD STEP import/save/reopen, the declared input/output schema of a saved ONNX model, and resuming a version-bound MuJoCo integration step. Use CPU-only public or synthetic inputs in a separate ledger, with native verification evidence kept outside this repository.

## Native acceptance evidence

On macOS arm64, in an isolated ledger based on 3e191aebcaaa25f167ad0545cb6dcf053a0f4af2:

- KiCad 10.0.6 ran on its bundled Arduino Pro Mini template. DRC returned 22 violations and 7 unconnected items. ERC returned 40 findings on one sheet. Both returned exit 5 and produced reviewable raw reports.
- FreeCAD 1.1.3 imported a board-only STEP exported by that KiCad installation, saved an FCStd and reopened it. The shape had 1 solid and 40 faces and the measured volume was 448.31365 mm³.
- Read ROS 2's [upstream talker recording](https://github.com/ros2/rosbag2/blob/eaf9712a2b23105eac104d64a6938a40cc5d5c74/rosbag2_py/test/resources/mcap/talker/talker.mcap). There were 3 indexed channels and 20 messages. The independent MCAP 1.6.0 reader decoded the message envelopes and counted 10 each on /rosout and /topic.
- The existing public GitHub reader captured the issue representation of [ros2/rosbag2 PR 1](https://github.com/ros2/rosbag2/pull/1) without using a private account.
- Captured the declared interface of [ONNX Model Zoo MNIST-12](https://github.com/onnx/models/blob/c5cae0f1942c8d7727372c7b1f6b485aa39e4421/validated/vision/classification/mnist/model/mnist-12.onnx). Its SHA-256 matched the upstream LFS pointer. ONNX Runtime 1.32.0 produced a finite 1×10 tensor on CPU from a 1×1×28×28 input. This was an inference smoke test.
- MuJoCo 4.0.1 advanced a synthetic single-hinge model, saved the existing coupled checkpoint at step 100 and restored into a fresh model/data pair. At step 200, qpos, qvel and simulation time matched the uninterrupted run exactly.
- The existing saved-export route captured the installed Autodesk Fusion offline sample archive (19,432 bytes). The desktop API and customer account remained disconnected.
- Nine publications went through the token-authenticated loopback Core API. Reading a newly opened ledger, restoring the final snapshot and replaying the events recovered all 25 payloads byte-for-byte. The final state was unverified and unadopted.
- The Mac preflight reported Windows required or SDK blocked as applicable. No licensed Windows host or private SaaS tenant was qualified.
- Full suite with the local ONNX and simulation dependencies installed: 1,974 tests, 17 skipped, no failures.
