# Design change → evidence → next change

Gantry now places a cumulative, version-bound design assessment on the normal
Crew task input, each action-loop refresh, the returned Bot report, and optional
Mentor context/review. Bots choose corrections and tests; Core records those choices
and checks identities, versions, scopes and evidence bindings. Crew does not need
Mentor to execute development work.

## Assessment contract

Read-only operation, also available in the Bot/read-only MCP profiles:

```json
{"baseline_state_id":"devstate_BASE","state_id":"devstate_CURRENT"}
```

```sh
gantry call get_design_assessment --input comparison.json
```

The two states must belong to the same session and be accessible to the caller.
The response contains:

- `id`: digest of the complete assessment before preview clipping; current
  requirement revisions, applicable maps and engineering evidence contribute to the identity.
  Retrieval-only evidence query watermarks are excluded, so unrelated ledger writes
  do not change the assessment identity.
- `changes`: cumulative path/hash changes from the assignment baseline, including
  earlier checkpoints, not only the most recent edit.
- `impact`: declared hierarchy/component/check-input effects and traversal of
  explicit, state-bound dependency/geometry maps, when available.
- `requirements.items`: current coverage, previous coverage, pinned/current
  requirement revisions, linked checks and evidence.
- `checks`, `open_checks`: failed, missing, stale, removed or changed checks and
  unbound changed dependency inputs. A selected check cannot reuse an old pass
  merely because its check ID is unchanged.
- `gaps`: unknown mappings, unmapped changes, capture omissions and unmet coverage.
- `partial`: previews over 96 KiB are reduced, including nested evidence. Counts
  and compact unresolved summaries remain; a partial assessment cannot obtain a
  Mentor OK. Retrieve source states/checks via `get_development_state` and native
  views via `query_evidence`; narrow the work scope for a complete review.

Missing maps stay explicit. Maps are not inferred from filenames or copied from
another state. A map whose source hash differs from the claimed state's manifest
is inapplicable; sources not captured in that state need an explicit binding before
being treated as applicable. Multiple maps are ambiguous, not resolved by random
ID ordering. Adding a map invalidates older Mentor review input fingerprints.
Engineering component IDs and hierarchy subject IDs remain separate namespaces.

Requirement coverage is **relative to declared criteria**. `met` does not certify
all dependencies, all physics, or product safety. The broader assessment can remain
`needs_review` while a particular static requirement is met. Valid reasoned
`not_applicable` engineering checks retain their previous semantics, but do not
fulfill a check explicitly required by a requirement revision.

## Development path

1. Capture existing native files, editable source, configuration and requirements.
2. Start a change/task from an immutable state. The task fixes its purpose,
   dependencies and editable scope.
3. Read its assessment. Choose an edit, a tool test, a consultation or a blocker.
4. Crew records brokered intermediate edits, failures, tool outputs and snapshots.
5. Run the customer-approved tool in the scratch sandbox. Tool success alone is
   not requirement evidence.
6. Use `publish_physical` to capture reports against `physical-plan.json`, including
   exact inputs, requirement references, conditions, environment and numerical
   criteria. The adapter updates the engineering context and coverage.
7. The next model turn receives the refreshed assessment. Finish or continue based
   on the actual result. Returned reports preserve the assessment at that time.
8. Start new work from the saved candidate. A dependency change makes earlier
   evidence inapplicable until the relevant combination is evaluated again.

Experience planning receives the same assessment and bounded current source
previews, instead of requiring a plan from hashes and historical memories alone.
No extra inference call is added by this change. This is not proof that experience
caused better engineering choices.

## Frozen acceptance and compatibility

`hardware.publish` pins the acceptance plan to the change's `base_state`;
`hardware.publish_bot` pins it to the task's `state_id`. Editing and checkpointing
weaker criteria cannot rebaseline acceptance in the same work item. Reassess a new
plan in a new state and start new work to intentionally change criteria. A stale
plan holds a Bot task for explicit reassessment rather than blindly retrying it.
Authorized raw declarations remain submitted evidence, not independent measurements.

No database migration or historical rewriting is required. Existing reports simply
lack the new assessment field; old files, states and measurements remain available.
Existing scoped credentials may need this new read command added if their allowlist
is frozen. Existing Bot operations include the embedded assessment automatically.

Virtual environments are now included in the exact read-only sandbox runtime
manifest. This fixes native CAD imports from an approved venv. An existing runtime
whose manifest changes must be reapproved with `configure_bot_runtime`; the harness
never falls back to unrestricted host execution. Use a dedicated tool venv containing
only approved dependencies, not credentials or private project files.

## Run the native example

From a source checkout with Gantry and CadQuery installed in the same Python venv:

```sh
PYTHONPATH=. python examples/design-change-loop/run.py \
  --output /absolute/new/private-demo-directory \
  --model YOUR_CODEX_MODEL --reasoning-effort low
```

The directory must be new. The example uses the official Codex CLI's existing
ChatGPT login; it refuses API-key fallback. It creates a separate loopback Core,
credentials, project, Bot and journals. Nothing is adopted or physically operated.
The operator supplies the anonymous fixture and requirements. The real model chooses
CAD parameter/control edits, runs real CadQuery, publishes results and reports its
limitations. A second fresh task restores the result after a calibration change.

Keep the output directory private: it contains credentials, model inputs and journals.
Only the anonymized example source and [verification summary](DESIGN_CHANGE_LOOP_VERIFICATION.md)
belong in the source repository.

This example validates static B-rep interference and a simple CAD/control interface.
It does not run strength, thermal, dynamic, tolerance, prototype or commercial CAD
validation. Such tools must submit their actual measurements through the same
version-bound evidence path; Gantry cannot make an unavailable solver or license exist.


## Derived engineering evidence

`get_design_assessment` also returns `engineering_evidence.version = 1`, with
`mode = "state_comparison"`. It derives observations from existing state-bound
`evidence_views`; it creates no records and does not replace original files or
engineering declarations. `intent_prediction_supported = false`: proposed changes
are not treated as measurements of a state that does not exist.

`fields` groups declared correspondence by hierarchy subject, profile and field
name. Each before/after observation preserves its classification, method, units,
frame, time basis and exact source revision/path/hash/locator. Its
`provenance.request` contains `get_evidence_view` arguments for the original field.
Statuses are `changed`, `unchanged`, `unknown`, or `conflict`. Missing observations
remain unknown, rather than implying physical addition/removal. Numeric `delta`
is after minus before only for finite scalars with identical units, frames and
time bases. No implicit unit or coordinate conversion occurs. Contradictory
applicable views remain conflicts; ordering or recency does not elect a truth.

Source identity must match both the artifact and the claimed state's manifest.
An older artifact may remain retrievable while being inapplicable to this state.
Stale-source, dimension, capture and conflicting-observation problems contribute
explicit assessment gaps. Projects without optional evidence views keep their
existing check-status behavior, with the absence reported inside the section.

`impacts` names targets in the **engineering_component** namespace, independently
of field subjects in the **hierarchy** namespace. Each entry names changed input
paths, a representative declared prerequisite-to-dependent route, baseline/current
state references and associated check IDs. This is potential impact through saved
bindings, not a physical risk prediction. `check_obligations` references the
existing assessed check status, reasons and evidence; field differences cannot
upgrade verification. Existing reports, frozen criteria, requirement coverage and
adoption rules remain authoritative.

Each side scans at most 30 evidence views and 200 fields. `coverage.before` and
`coverage.after` expose `query_evidence` request/next_request arguments, including
an `as_of_seq` watermark for repeatable discovery. The projection retains at most
30 entries per list, at most 10 edges in a representative path, and 24 KiB overall.
Oversized field values are omitted with a source request. Scan, traversal and
presentation limits set `coverage.partial`, the assessment's `partial`, and a gap;
coverage counts describe the scanned projection, not an exhaustive project count.
Use the source requests and `get_development_state` for complete original data.

The projection source fingerprint covers the scanned views and derived rows before
presentation clipping; it does not imply coverage beyond the reported scan bounds.
Pagination watermarks are scoped to each state’s source views, so unrelated ledger
writes do not invalidate an in-flight assessment.
