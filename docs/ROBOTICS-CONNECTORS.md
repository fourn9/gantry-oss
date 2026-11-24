# Connecting a robot development workspace

Start with the original design or recording that a colleague needs to reproduce a result. These commands create private local bundles. A second, explicit operation publishes the bundle into a scoped Gantry change.

| Priority | Source | Operator action | Evidence available in Gantry |
|---|---|---|---|
| 1 | KiCad | Run ERC on a saved schematic or DRC on a saved board | Editable source, selected project/rule files, raw JSON report, KiCad version, finding counts and source revision |
| 1 | ROS 2 and Foxglove | Select an MCAP recording from rosbag2, a local export or the recording owner | Original recording, indexed topics and encodings, recorder counts and time range when present |
| 1 | GitHub | Pull one issue or PR by repository and number | Provider response, update marker, explicit gaps. The existing GitHub PR connector also handles diffs and checks |
| 2 | Autodesk Fusion | Capture a selected saved F3D archive using the existing `capture --provider fusion360` command | Native archive bytes. Desktop session edits require a separate live connection |
| 2 | Mechanical CAD to Mac FreeCAD | Export STEP in the originating CAD system, then import/save/reopen locally | STEP bytes, a static native FCStd shape, FreeCAD version, face/solid counts and volume |
| 2 | ONNX | Capture one saved protobuf model | Model bytes, declared tensor inputs/outputs, shape, element type, opsets and hash |
| 2 | MuJoCo | At a completed step call the existing coupled serializer, then publish the selected checkpoint files | Runtime and model binding, declared subsystem state and explicitly supplied evaluation files |
| 3 | Windows vendor CAD | Use the licensed Windows host and publish through Gantry. On the Mac, use a neutral export when one is available | Exact native operations and limitations are in the [desktop driver guide](NATIVE-DESKTOP.md) |

Priority reflects dependencies in a mixed hardware/software project. Team-specific cloud accounts, organization workspaces and robot fleets need their own targets and credentials.

## Install and capture

From this checkout with Python 3.11 or later, run `python -m pip install .` in a virtual environment. Use `python -m pip install '.[onnx]'` for the ONNX parser. Optionally supply `--requirements requirements.json` to any capture command. Use a new output directory for each capture.

```sh
gantry-integrations check-kicad --root ./electronics --document board.kicad_pcb \
  --executable /Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli \
  --source-id main-board --output ./captures/board-01
gantry-integrations check-kicad --root ./electronics --document board.kicad_sch \
  --dependency power.kicad_sch --executable /absolute/path/to/kicad-cli \
  --source-id board-erc --output ./captures/erc-01
gantry-integrations capture-mcap --root ./bags --path run.mcap \
  --source-id sensor-bag --output ./captures/bag-01
gantry-integrations capture-step --root ./exports --path bracket.step \
  --freecad-app /Applications/FreeCAD.app --source-id bracket --output ./captures/shape-01
gantry-integrations capture-onnx --root ./models --path perception.onnx \
  --source-id perception --output ./captures/model-01
gantry-integrations inspect --bundle ./captures/bag-01
```

KiCad and FreeCAD run as local operator commands on **trusted** selected projects and installed applications. Both use scratch copies, fixed native operations and a private temporary settings directory. Native tools run with the local OS user's permissions. There is no new remotely callable command runner. For outside or untrusted designs, run native tools in a disposable VM and import reviewed saved files. Use the absolute path to the actual KiCad installation. Hierarchical sheets and local design libraries must be selected explicitly. KiCad's installed libraries, severity settings, waived rules and unstaged dependencies affect findings. Inspect the raw report before making an engineering decision.

A FreeCAD import stores a single static shape. Source feature history, editable vendor parameters, assembly mates and external references require the originating CAD environment. The Mac path uses the FreeCAD application's bundled Python. The reader closes and reopens its own scratch FCStd and compares face count, solid count and volume. This checks the transfer at that scope.

MCAP preserves encoded payloads. It reads bounded record headers and summary metadata without decoding messages or expanding chunks. A recorder that omits statistics or channels yields missing data. Timestamps are recorder log-time nanoseconds, with the recording's clock semantics. Streaming DDS, Foxglove cloud synchronization and dataset-wide bag playback are separate capabilities. For ONNX, external weights are not followed, and model interfaces can include unknown or symbolic dimensions. Store evaluation evidence separately against the exact model hash.

For MuJoCo, use `gantry.checkpoint.capture_coupled`, `save_bundle`, `load_bundle` and `restore_coupled` with a caller-defined model/environment binding. Capture the model, saved manifest, **each** state/array file and selected evaluation results with `gantry-integrations capture --provider mujoco --root ... --path ...`. The existing serializer is for its supported integration state and driver fields. New driver types and other mutable model fields require explicit coverage.

## Publish and read back

```sh
gantry-integrations publish --bundle ./captures/board-01 \
  --url https://your-gantry.example --token-file /private/gantry.token \
  --state-id STATE_ID --change-id CHANGE_ID --version 1 --key board-01
```

The change must allow `imports/main-board/`. After publication, use the returned state ID to read the versioned manifest or restore files. Check the [immutable publication contract](EXTERNAL-INTEGRATIONS.md#publish-into-a-development-change) for retry, version and requirement handling. Inputs remain subject to the existing 16 MiB per-file and 32 MiB per-bundle limits. Full fleet recordings and large model weights need a large-artifact transport before this route can preserve them.

## Completed Fusion saves and ROS 2 recordings

The [source event guide](SAVED-SOURCE-EVENTS.md) connects a completed export or
recording to one bound Studio work item. Its workspace transport supports up to
1 GiB across the workspace and checkpoints the selected artifact only.

## Use Windows CAD from a Mac

1. For immediate geometry handoff, obtain a STEP export of the selected vendor design. Run `capture-step` on the Mac. A native CATPart, SLDPRT or Creo part and a STEP export carry different editing capabilities.
2. For native parameter changes, run `gantry-native doctor` on the intended Windows installation. It reports the installed COM class registrations visible to that Python where applicable. It never starts an editor, opens a document or checks out a license. On macOS the report identifies operations requiring a Windows host.
3. On the customer-controlled host, install `.[native-windows]`, open a disposable licensed document and follow the product-specific inspect, prepare, apply and readback path. Operate that Windows desktop from macOS with the [Microsoft Windows App](https://learn.microsoft.com/en-us/windows-app/get-started-connect-devices-desktops-apps?pivots=remote-pc). Publish only the selected evidence through the authenticated HTTPS Gantry endpoint.
4. SOLIDWORKS, Creo and CATIA V5 have narrow parameter drivers. SOLIDWORKS Electrical handles a project metadata field. Altium and Allegro use editor scripts with different save guarantees. Zuken E3.series and Siemens Capital need version/module-specific SDK contracts and drivers. A working Windows host alone cannot activate these two entries.

Check the exact product year, CPU/OS, graphics driver, add-in, license and USB requirements with the vendor before using a VM on Apple Silicon. For example, SOLIDWORKS lists x86_64 processors, particular hypervisor versions and graphics requirements in its [system requirements](https://www.solidworks.com/support/system-requirements).

Protocol references: [KiCad CLI](https://docs.kicad.org/10.0/en/cli/cli.html), [MCAP](https://mcap.dev/spec), [ONNX serialization](https://onnx.ai/onnx/api/serialization.html), [MuJoCo simulation](https://mujoco.readthedocs.io/en/stable/programming/simulation.html).
