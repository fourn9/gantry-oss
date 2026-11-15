# Held-out engineering comparison: preliminary result

2026-11-15, frozen source `2beb863cd055df4965ed21974a51cb4b78f4c09e`.
[Protocol](ENGINEERING_COMPARISON_PROTOCOL.md) and
[sanitized observations](engineering-comparison-20261115.json).

**Both arms passed; Gantry was slower in this one small case.** This is an
observation, not an estimate of general robot-development speedup.

A used ordinary files/logs and a subscription model action loop. B used one
subscription-backed Bot with Gantry's saved state, evidence and verification-plan
paths. B did not use Mentor, prior experience, reflection or delegation. The
separate [three-Bot run](ENGINEERING_LIVE_VALIDATION.md) tests coordination, not
this comparison's speed. Do not conflate these two experiments.

Both arms started from byte-identical held-out native STEP/source/report files,
the same immutable evaluator, calibration and acceptance, identical tool recipes
and the same product implementation hash. They ran serially A then B, with
independent output directories and ephemeral model contexts. No answer, history
or intermediate edit was copied between arms. No model tuning used this held-out
parameter case. Both used the existing subscription CLI default with low reasoning;
the resolved model identity was not pinned.

| Measurement | A: files/logs | B: Gantry |
| --- | ---: | ---: |
| Fixed acceptance, real tool binding, final audit | Pass | Pass |
| Total measured wall time | 67.14 s | 104.71 s |
| Model-call time (includes CLI/provider wait) | 65.70 s | 102.90 s |
| Tool time, including final audit | 1.39 s | 1.28 s |
| Remaining harness/record/restore/wait time | 0.055 s | 0.530 s |
| Model calls | 6 | 7 |
| Tools, including final audit | 3 | 3 |
| Input tokens | 118,574 | 227,099 |
| Output tokens | 667 | 1,074 |
| Cached input tokens (subset of input) | 0 | 20,736 |
| Action/model/tool errors | 0 / 0 / 0 | 0 / 0 / 0 |
| Parent interventions after start | 0 | 0 |
| Per-arm automated setup, excluded from measurement | 0.315 s | 0.385 s |

Shared baseline generation took 1.178 seconds once, reported separately. Parent
implementation/setup labor is not captured by these automated setup timings.
There was no deliberate sleep. Host suspension and provider-internal wait are
unknown; per-call monetary cost is not reported by the subscription adapter.

The final audit only ran the fixed verifier over a copy of the submitted files.
It did not rebuild or repair CAD. It required current input hashes and a real
successful tool execution: for B, matching action, output artifact, publication
and report; for A, actual sandbox receipts and report hashes. Both retained
unchanged acceptance and measured all five nominal criteria passing. Neither
formally adopted a design or demonstrated physical hardware performance.

B took 37.57 seconds longer (1.56 times A's wall time). Most of the observed
difference was model-call time, not tool computation or ledger I/O. B chose an
additional explicit verification-plan action; its larger repeated context also
consumed more input tokens. The observation does not isolate how much latency
came from context size, action count, stochastic output or provider scheduling.
Do not turn this single ratio into a general penalty estimate either.

What worked: source-bound evidence, frozen acceptance, actual tool execution,
result recovery and audit all functioned. What did not follow: faster completion
on this small, already-local problem. There was no missing-history discovery or
cross-team handoff for Gantry to save here.

Next measurements should compare staged missing-context/dependency changes and
handoffs, and vary retrieval payload size independently of tool execution. First
measure context/turn reduction against the same evidence and failure-detection
criteria; do not remove provenance or checks just to lower the stopwatch result.
Multiple held-out cases, randomized order and pinned model settings are needed
before making a causal time-saving claim.

No private ledgers, raw model journals, credentials or proprietary project data
are included in the published observations.
