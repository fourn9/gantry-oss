# Data views, recovery and CAD execution

This change extends existing native artifact storage, selective evidence views,
review jobs and local journals. It does not introduce a new agent organization,
purchase model usage, adopt designs, or modify historical artifacts.

## Native data and tool-specific views

Gantry already saves native artifact bytes and source-bound `evidence_views`.
`native_views.json_view` extracts selected JSON fields; it does not replace the
native document. A view identifies the development state, stable subject, source
revision/path/hash, extractor, classification, unit, frame, time basis and gaps.
Capture is bounded by the connector's coverage and delegated paths. It does not
claim every external service field, unsaved editor operation or credential was captured.

`render_evidence_view` adds a read-only, explicit JSON output profile. For example:

```json
{
  "view_id": "VIEW_ID",
  "state_id": "STATE_ID",
  "profile": {
    "id": "simulation-position",
    "version": 1,
    "fields": [
      {"source": "position", "target": "/body/position", "unit": "m", "frame": "body"}
    ]
  }
}
```

Call with `gantry call render_evidence_view --input profile.json`, HTTP, or the
general MCP read profile. The result contains data, profile hash, original source
references, conversion provenance, omitted fields and unknown values. No artifact
is overwritten. Known length/time/angle/mass units can be converted; unknown
units, coordinate/time transforms and mismatched state IDs fail closed. Output
paths describe JSON objects, not a vendor CAD schema. Editable CAD topology,
electrical net semantics and tool-specific importers still require adapters.

## Reconnect a user-agent review

The normal scoped project path exposes `project_mentor_recover` in MCP and:

```sh
gantry project mentor-recover --root . --input recovery.json
```

```json
{"submission_id":"REVIEW_ID","reason":"The previous reviewer process has stopped"}
```

This renews an expired lease only if the development state, delegation and review
evidence still apply. The original model input and saved answer remain unchanged.
Then use `mentor-prepare`/`mentor-finish` to continue. A valid existing lease needs
normal continuation, not recovery. An uncertain model call is not automatically
reissued. Existing subscription receipts remain reusable. Revoked/expired access
is never extended by recovery. Recovery provenance is recorded in Core and in the
private review journal; successful response retries do not create a second review.

## Recover a team worker

The configured `mentor-worker` still runs the specialist, coordinator, developer
and reflection jobs. To reconcile a stopped worker, retain its private journal
and use the **same delegated principal**:

```sh
gantry --url https://YOUR-GANTRY --token-file /private/worker.token \
  recover-mentor-job --job-id JOB_ID --journal /private/jobs \
  --confirm-stopped "Previous worker and child processes have stopped"

gantry mentor-worker --config /private/worker.json --journal /private/jobs --iterations 1
```

Recovery rotates the job fence and coordinator lease, checks current version,
permissions, evidence, execution scope/conflicts and automation conditions, and
retains prior failures and completed specialist reports. Replaying an ambiguous
Core acknowledgement uses the saved idempotency key. Recovery of a reserved run
does not charge another execution slot; a deliberately new model attempt charges
the existing inference-job allowance.

- Saved model output, applied edits and finished verification are reused.
- Unknown model outcome: inspect the provider journal and confirm termination;
  add `--retry-inference` to authorize a new attempt in a **new** provider journal.
  Completed model receipts cannot be discarded using this switch.
- Unknown verifier outcome: add `--collect-interrupted-verification` to save the
  partial workspace as **unverified**, with an unknown interrupted outcome and
  exit code -1. It does not rerun the verifier or infer a pass.
- A live local worker lock or known live child process prevents recovery.
- Changed premises or delegation require a fresh submission. No stale answer is
  rebound to new geometry. New policy/role assignment is outside this operation.

This supports a replacement process using the same private journal and identity,
not automatic credential transfer to another principal or arbitrary app startup.
Keep journal backups private: they contain project context and output. Do not
upload them as feedback. Old journals without PIDs need an explicit termination
assertion. This is application-level reconciliation, not an OS process sandbox.

## Common CAD screening path

The optional CadQuery runtime can run a fixed-pose screen using:

```sh
python -m gantry.cad_screen --root /approved/snapshot \
  --request screen.json --output new-screen-result.json
```

```json
{
  "parts": [
    {"id":"body","path":"body.step","sha256":"ACTUAL_SHA256"},
    {"id":"bracket","path":"bracket.step","sha256":"ACTUAL_SHA256"}
  ],
  "pairs": [["body","bracket"]],
  "clearance": 0.5,
  "overlap_tolerance": 0.000001,
  "unit": "mm",
  "frame": "assembly"
}
```

Register this exact command through the existing Runner recipe/delegation path;
the command does not itself grant execution permission or contact a cloud service.
It verifies STEP hashes, computes one numeric bounding box per part, prunes only
separated pairs and performs exact distance/intersection checks for the remainder.
The result records request/source hashes, backend version, pair coverage,
calculation counts and import/bounds/check/total times. It is saved by the normal
Runner artifact capture. Native length units/frame remain explicit declarations.

Existing motion evaluators can call `gantry.cad_screen.capture_bounds(world)`
**after constructing each pose**, then reuse the returned immutable numbers for
that pose's pair loop. Construct a new snapshot after a shape/pose change.
No mutable global shape cache or CadQuery monkey patch is installed. Replacing
an old evaluator is an explicit, versioned change and needs a parity check.
Unmodified third-party scripts do not automatically receive this optimization.

The adapter covers explicit pairs in one pose, not continuous motion, physical
compatibility, material intent, electrical behavior or manufacturing readiness.
Previously required checks and exclusions must not change during optimization.

## Verification

Regression tests exercise HTTP/service restart, lost acknowledgements, expired
leases, old-worker fencing, changed inputs, active-process refusal, explicit
inference retries, incomplete verification collection, scoped project MCP
continuation, native-preserving views and real STEP collision checks when the
optional CAD runtime is installed. Model responses in these tests are fixtures;
workspace edits, subprocess verification, Core persistence and HTTP are real.
No end-to-end development speedup or live-model quality is inferred from them.

No destructive schema migration is required. Old journals remain readable; new
fields are additive. Restart existing servers/workers to load the changed code.
