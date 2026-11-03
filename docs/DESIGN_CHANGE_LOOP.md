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
  requirement revisions and applicable maps contribute to the identity.
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
