# Three-Bot memory study

Run an existing, unfinished engineering task from identical frozen inputs. The
lead delegates to two specialists, inspects their evidence and integrates their
changes. This is an experiment harness, not a new product dispatcher.

Supply a private case JSON using the contract validated by `load_case` in
`run.py`: explicit base64 files and SHA-256 manifest, goal and fixed acceptance,
three roles and write scopes, frozen Python verifier, dependencies, and sourced
historical observations. `required_worker_bots` makes genuine specialist edits,
lead retrieval and integration part of acceptance. An engineering pass alone is
insufficient. The final verifier and evidence plan must be read-only.

```sh
PYTHONPATH=. python examples/crew-memory-study/run.py \
  --case /private/frozen-case.json --condition cold \
  --output /private/new-run --model YOUR_SUBSCRIPTION_MODEL --seconds 1800
```

`cold` and `recall` both run learning and reflection. Only imported prior notes
differ. Their original provenance and uncertainty must be retained. Both arms
may still contain existing project knowledge in files. Use fresh independent
contexts and do not transfer newly generated solutions between arms. The
observation window belongs to this experiment, not a product execution limit.

The runner saves raw calls, task records, memory uses, action intervals, restored
state, final independent evaluation, workflow audit, and ledger verification.
Task and shared provider failures stop without silent retry or parent recovery. A held reflection remains visible and pending but does not stop unrelated development.

Time categories describe operation intent. A model interval includes CLI,
network and provider waiting; it is not a measurement of hidden reasoning.
Parallel durations are reported as both accumulated spans and interval unions.
Rework remains unknown until linked to an actual failure and correction; negative
fixtures or repeated reads are not automatically waste. Host sleep is unknown.
`wall_seconds` includes workers, final engineering audit and integrity checks.
For comparisons, use the common wrapper window including setup and all final
checks; record post-run analysis separately. Keep
private raw logs, tokens, artifacts and source-derived fixtures out of GitHub.

The original study at b87787f used a strict stop-on-held policy, including
reflection holds. The current supervisor isolates those holds, matching product
behavior. It records each unchanged hold once rather than flooding the timeline.
`development_accepted` requires completed delegated work, peer review/integration,
actual verification and ledger integrity. `accepted` additionally requires every
reflection to complete. Pending learning is never described as learned experience.
The historical report retains stopped trials and a separate recovered continuation.

Final auditing permits evidence published on a verified same-session ancestor
only when the recorded check, current evaluated inputs, report hashes and actual
execution provenance still match. An unrelated notes update does not invalidate
an otherwise unchanged check. Read the preliminary [report](REPORT.md) for the
original scoring defect, uniform rescoring, and limits of the evidence.

## Frozen implementation comparison

Use `gantry.crew_continuity_comparison.score_run` for every arm, followed by
`compare`. Supply a common `execution-window.json` captured immediately before
`run` and after it returns (including setup, final audit, verify and replay). The
common scorer applies the same engineering criteria to old and new records, even
when one implementation stores reflection-only holds in `errors` and the other
in `reflection_warnings`. The after-setup observation limit includes all final
checks in both arms. Successful completion time includes setup as well.

Freeze source revisions, input/case hashes, model and effort, tools, imported
memories, acceptance and scorer before independent repeated runs. Keep failures
and timeouts; early stops are not faster completion. At least two repetitions per
arm are a preliminary check only. Do not transfer answers between contexts.
Model activity labels describe observable requests, including provider latency;
they do not measure internal reasoning. Actual editing/verification leaf spans
and reflection requests are separate. Parallel unions cannot be added as wall time.
