# Local CAD and physical evidence adapter

This path uses the existing Gantry ledger, immutable development states, scoped
changes, artifact storage and Mentor review. Core remains the state authority;
local journals only support recovery. There is no new cloud solver. Customer agents invoke the local CLI or Python functions and use
Gantry's existing authenticated API to publish checkpoints.

## Actual support

| Operation | Support |
| --- | --- |
| CAD read/write | CadQuery 2.8: STEP import, box/cylinder, translation, cut/fuse, STEP export. Declarative JSON, no arbitrary Python execution. |
| Interference | Real static CadQuery solid intersection/distance on explicit pairs in one common frame, millimeters. |
| Strength, tolerance, physical tests | Import external numeric observations, compare against frozen bounds and units, retain raw report and declared conditions. No built-in FEA solver, GD&T solver or test-bench driver. |
| Review | Derived checks in development-state and PR-review context; existing required-check gate refuses Mentor OK when evidence is missing, failed or stale. |
| Adoption | No automatic adoption, fabrication, device commands or physical safety certification. |
| Other CAD vendors | No new Onshape/Fusion/SolidWorks credentialed editing connector. Export STEP or use a separately authorized native tool, then capture its editable source too. |

STEP preserves exchange geometry, not the original feature history. Preserve native
CAD/project files alongside STEP. Solid validity and positive volume do not prove
intended wall thickness, strength, machinability or fit.

## Installation and runnable example

Use the patched Python/installers in [security maintenance](SECURITY-UPDATES.md).
Install optional wheels in a dedicated customer runner environment:

```sh
python -m pip install --only-binary=:all: -c docs/hardware-runtime-constraints.txt 'cadquery>=2.8,<2.9'
python -m pip install .
python examples/hardware_evidence.py /path/to/new-demo-directory
```

The example creates two synthetic solids, records a real collision, imports and
moves one solid, exports it, rechecks clearance and saves both trials into a real
local Gantry ledger. The required strength check deliberately remains unknown.
The example uses the service in-process; production publishing below uses HTTP.
No paid services, customer files or physical hardware are used by the example.

## Edit CAD

```sh
python -m gantry.hardware edit --root workspace --request edit.json --output new-cad-output
```

`edit.json`:

```json
{
  "unit": "mm", "frame": "assembly",
  "steps": [
    {"id":"base","op":"import_step","path":"part.step","sha256":"REPLACE_WITH_INPUT_SHA256"},
    {"id":"part","op":"translate","source":"base","vector":[2,0,0]}
  ],
  "export":["part"]
}
```

Outputs: `part.step` and `cad-operation.json` with exact request, source hashes,
backend version, step volumes, output hashes and limitations. Original inputs are
not overwritten. Only copy chosen outputs back into the scoped candidate workspace.
Record failures using the normal Runner execution log; the edit command does not
publish incomplete native geometry. Native parsing/booleans are local operations;
run them inside the approved Runner/container with time/resource limits for untrusted
CAD. Input/step limits are not a CPU or memory sandbox.

## Freeze acceptance before evaluating

Save `physical-plan.json` in a Gantry development state **before** running the
experiment, then start a change from that state. A plan has version 1, components
and checks. The example script generates a complete interference plan.
A strength check can instead use:

```json
{
  "id":"strength", "scope":"structural", "components":["bracket"], "required":true,
  "inputs":["bracket.step","material.json","solver.py","mesh.json"],
  "report":"stress.json",
  "conditions":{"load_N":100,"fixture":"fixed-base"},
  "evaluator":{"name":"customer-solver","version":"reviewed-1"},
  "environment":{"solver_image":"sha256:YOUR_IMAGE_DIGEST"},
  "criteria":[{"metric":"maximum_stress","unit":"MPa","max":50}]
}
```

Numbers above are schema examples, not recommended engineering limits. Define all
material, load, constraint, mesh/convergence and coverage assumptions with the
responsible engineer. Include their source files, evaluator code and configuration
in `inputs`. Components contain `id`, `role`, `assembly`, and nonempty `paths`;
checks must include all their component input paths. Remaining input completeness
is declared, not discovered or physically certified by Gantry.

A result envelope contains `status` (`completed` or an error status), exact `inputs`
(path -> SHA-256), `conditions`, `evaluator`, `environment`, `measurements`
(metric -> `{value, unit}`), and `limitations` (string list, empty allowed).
Retain native solver output in the same workspace and bind it in `inputs` if it is
an input to the normalized report. Failed solver runs use a non-completed status;
missing or malformed JSON yields unknown. Nonfinite values, absent metrics, unit
mismatches or changed inputs/conditions/tool/environment cannot pass. No implicit
unit conversion or inference of missing observations is performed.

For prototype measurements include unit serial, instrument/calibration identity,
actual hardware configuration and timestamps in conditions. This adapter compares
submitted values; it cannot establish that the instrument or solver actually ran.

## Produce the interference report automatically

```sh
python -m gantry.hardware screen --root workspace --request screen.json \
  --plan workspace/physical-plan.json --check-id clearance --output workspace/collision.json
```

`screen.json` uses the existing `gantry.cad_screen` format: hash-pinned `parts`,
explicit `pairs`, `unit: mm`, `frame`, `clearance`, `overlap_tolerance` (mm³).
The emitted measurement is `violating_pairs` in `count`. Plan conditions must match
unit/frame/clearance/overlap_tolerance/pairs and the part-ID-to-path map exactly.
Evaluator is `{name: gantry.cad-screen, version: "1"}` and environment is
`{cadquery: "2.8.0"}` for the tested runtime. The raw geometric report is embedded.
Outputs must be new files. This covers only the declared pose and pairs; it does
not evaluate continuous motion, flexible hoses or strength.

## Publish into the existing development/review path

```sh
python -m gantry.hardware publish --root workspace \
  --state-id devstate_ID --change-id change_ID --version 1 \
  --plan physical-plan.json --key trial-unique-id \
  --url http://127.0.0.1:8770 --token-file /private/path/agent.token
```

Use HTTPS away from loopback. Tokens belong outside the captured workspace.
The change must authorize modified CAD, reports and operation-log paths. Publishing:

1. Checks the head/version and captures the workspace through the existing API.
2. Requires the plan bytes to equal the plan in the input state; changing acceptance
   requires a separately saved baseline, not silently relaxed limits.
3. Evaluates the captured bytes (not subsequent edits on disk).
4. Preserves unrelated engineering declarations and adds/replaces only checks owned
   by that same frozen plan. Replacing another definition is refused.
5. Creates a paused immutable checkpoint with raw files, compared measurements,
   reasons, unresolved items and hash-bound engineering checks.

Use `get_development_state` to read `engineering.checks` and `review_gaps`, then
`share_change` / `submit_change_review` for the existing review loop. Review sees
these observations as evidence, not as instructions. No model is started by this
adapter itself. Crew bots can read the same state via existing APIs/MCP.

Changing bound CAD/material/configuration/report/plan bytes invalidates the old
check. Old states/results are retained. `status.verification` remains the existing
execution-evaluation axis; scoped physical checks are under `engineering`. Passing
one check does not set global verification or adoption to pass.

The publisher journals exact checkpoint arguments before dispatch under the local
`.gantry/hardware/` directory. After a lost final response, retry with the original
state/change/version and key to recover the same result. A different change head or
reused key with a different intent is rejected. Captured artifacts may remain if
checkpoint authorization/conflict fails. No external computation is replayed.
The [joined workflow](ENGINEERING-WORKFLOW.md) also tracks the local change pointer,
runs external evaluators and carries downstream dependencies into Mentor review.

## References and limits

[CadQuery import/export](https://cadquery.readthedocs.io/en/latest/importexport.html)
and [shape API](https://cadquery.readthedocs.io/en/latest/classreference.html) informed
the implementation. Tested behavior and demonstration outcomes are recorded in
[verification](HARDWARE-VERIFICATION.md). No claim of robot-wide physical correctness
or development speedup follows from these functional tests.
