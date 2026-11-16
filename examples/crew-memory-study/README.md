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
Subscription/provider failures stop without silent retry or parent recovery.

Time categories describe operation intent. A model interval includes CLI,
network and provider waiting; it is not a measurement of hidden reasoning.
Parallel durations are reported as both accumulated spans and interval unions.
Rework remains unknown until linked to an actual failure and correction; negative
fixtures or repeated reads are not automatically waste. Host sleep is unknown.
`wall_seconds` includes workers and final engineering audit; setup and later
report generation/integrity checks should also be reported separately. Keep
private raw logs, tokens, artifacts and source-derived fixtures out of GitHub.

The initial study uses a strict stop-on-held policy, including reflection holds.
The product normally isolates a held reflection and can continue unrelated work.
Do not describe this study-wide stop as product-wide failure. The report retains
those stopped trials and separates an explicitly recovered continuation.

Final auditing permits evidence published on a verified same-session ancestor
only when the recorded check, current evaluated inputs, report hashes and actual
execution provenance still match. An unrelated notes update does not invalidate
an otherwise unchanged check. Read the preliminary [report](REPORT.md) for the
original scoring defect, uniform rescoring, and limits of the evidence.
