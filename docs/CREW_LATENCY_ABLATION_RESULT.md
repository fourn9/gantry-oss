# Crew latency ablation: preliminary real-model results

Measured 2026-11-16. [Protocol](CREW_LATENCY_ABLATION_PROTOCOL.md),
[all 16 sanitized observations](crew-latency-ablation-20261116.json).
Experiment implementation: `9cd451c22a1679b36dda6ef0bad5fa0747815668`.

## Finding

Removing one model round trip for verification planning and tool dispatch was
faster in all four paired cases: 6.35–12.76 seconds, with a median paired
reduction of 7.63 seconds (10.89%). Both the verification plan and actual tool
execution/evidence remained independently recorded. This supports a narrow causal
mechanism: one avoidable model turn contributed latency in this workflow.

It does **not** establish that large context was the principal cause of historical
long-running development. Description compression produced a small observed
reduction; lossless duplicate references reduced tokens but did not reduce elapsed
time. It does not measure learning, delegation, or whole-project development speed.

## Task and controls

Four new initial parameter combinations of one anonymous CAD/software fixture:
edit a carrier position and command target, generate native STEP geometry, and
verify their consistency against an immutable calibration and evaluator. The
software component is an 80-step discrete position filter, not a robot dynamics
simulation. The five fixed predicates were:

- nominal overlap <= 0.001 mm3;
- nominal clearance >= 1 mm;
- carrier center between 11 and 20 mm;
- CAD/source position error <= 0.01 mm;
- final software/CAD position error <= 0.01 mm.

Each case had four byte-identical starting copies, independent ledgers/workspaces,
and fresh ephemeral model contexts. No answers or previous attempts were provided
across runs. Four conditions ran serially in the predetermined cyclic Latin-square
order. The cases are parameter variants, not independent engineering domains.

Model: explicit `gpt-6-astra`, low reasoning, official Codex CLI 0.154.0 with an
existing ChatGPT subscription; no paid API fallback. Python 3.12.15 and the native
headless Open CASCADE backend were fixed. Per-run source, evaluator, authority,
package and runtime checks passed. All 16 ran without mid-experiment code changes,
parent solution suggestions, harness retries, restart interventions, or discarded failures.
The equal observation ceiling was 1,800 seconds per sample; no sample reached it.

## Results

Times include input transformation, inference, edits, real tools, Core recording,
restoration, and the final independent audit. Setup is separate below. A faster
failure would not count as a speedup; all 16 samples were accepted.

| Condition | Accepted | Model calls per run | Median elapsed | Median paired change | Median paired input-token change |
|---|---:|---:|---:|---:|---:|
| Baseline | 4/4 | 7 | 69.73 s | — | — |
| Plan/tool combined response | 4/4 | 6 | 62.38 s | -7.63 s / -10.89% | -15.29% |
| Shorter action descriptions | 4/4 | 7 | 67.43 s | -2.09 s / -3.00% | -5.68% |
| Exact duplicate references | 4/4 | 7 | 71.12 s | +1.67 s / +2.41% | -10.38% |

The median paired change compares the treatment with baseline **within each case**;
it is not the subtraction of the two independently calculated column medians.
`compact_schema` is the internal label for description compression: exact action
schemas and capabilities were preserved, not removed or loaded dynamically.

| Case | Baseline | Plan/tool | Short descriptions | Duplicate references |
|---|---:|---:|---:|---:|
| 0 | 69.82 s | 57.07 s | 67.33 s | 69.84 s |
| 1 | 69.64 s | 63.29 s | 69.49 s | 69.78 s |
| 2 | 70.81 s | 62.92 s | 65.11 s | 75.77 s |
| 3 | 69.21 s | 61.84 s | 67.52 s | 72.41 s |

There were no action, tool, or model errors. Every run made one explicit observation
retrieval; compression did not cause extra retrieval calls in this sample. The
combined action was actually selected in all four treatment runs; no unused
feature is credited with the reduction.

## Where the time went

Across all 16 samples: 1,081.84 seconds measured (18.03 minutes).

- Model-call intervals: 1,052.56 seconds (97.30%). These include CLI/network/provider
  waiting and input transformation; they are **not** pure model thinking time.
- Actual tools, including independent final audits: 21.14 seconds (1.95%).
- Remaining harness, recording, restoration and wait: 8.14 seconds (0.75%).

The usual action sequence was observe, two edits, build, plan verification,
verification tool, finish. Fusion combined the plan and verification dispatch into
one response while retaining separate plan/tool receipts. Median baseline plan
response time was 12.08 seconds; the fused response was 12.52 seconds. Ordinary
baseline tool-request responses had a median of 7.60 seconds. This is consistent
with eliminating a request round trip, rather than accelerating CAD calculation.
These per-action medians are descriptive, not an additive timing proof.

Four-case fixture preparation took 8.24 seconds; isolated per-run setup totaled
1.98 seconds. These do not include development of the experiment itself, regression
checks, model-availability preflights, or report preparation. That preparation labor
was not comprehensively timed, so it is not claimed as saved development time.

All inference receipts reported usage: 108 calls, 3,344,026 input tokens and 16,646
output tokens. Per-call monetary cost is not reported by the subscription route.
Provider-reported cached input tokens totaled 338,688 and varied across runs:
baseline 103,680; plan/tool 34,560; descriptions 96,768; references 103,680. Fresh
contexts do not disable provider prefix caching. This and remote scheduling remain
uncontrolled factors despite rotated order. No deliberate sleeps were inserted;
host sleep and provider wait cannot be separately quantified. Wall/monotonic totals
differed by less than 0.007 seconds per sample, but this is not a sleep instrumentation
claim.

## Evidence and parent involvement

All runs passed fresh, read-only final audits against actual linked tool receipts,
unchanged evaluator/calibration inputs, and the exact submitted file hashes. The
auditor did not build or repair CAD for the Bot. All 16 event chains verified and
replayed to matching state. None was formally adopted.

All 108 saved model inputs were audited against their treatment. All 28 deduplicated
inputs reconstructed the original context exactly. Description treatment preserved
all non-guide context and exact schemas; optional field enumeration order was
normalized during audit because canonical saved JSON sorts schema property keys.
No unique failures or constraints were summarized away.

The parent prepared the fixture, acceptance, authority, implementation, tests and
schedule; fixed a pre-run measurement bug where a held provider error could evade
the experiment stop rule; launched and monitored the experiment; then audited and
summarized it. Bots chose the parameter edits and tool use. No parent engineering
answer, repair, restart, or semantic intervention occurred during the measured runs.
Raw journals/configurations remain private; public observations are allowlisted
aggregates, fixture hashes, action names and evidence flags, not credentials or
model conversations.

## Decision and next checks

Keep these treatments opt-in. The best supported next production candidate is
plan/tool response fusion, subject to multi-Bot and interruption testing across more
real tasks. Existing focused tests cover stale basis, missing input, lost plan/tool
acknowledgements, and uncertain tool effects; ambiguous effects remain held.

Do not roll out duplicate references as a latency optimization on this evidence.
They saved input tokens, but all four elapsed results were equal or slower. Small
numbers of cases, output variation, provider scheduling/cache and the reference
representation prevent attributing that slowdown to a single cause.

Shorter descriptions were faster in all four cases, but the median improvement was
only 2.09 seconds. It needs more varied tasks and repeated runs before claiming a
reliable general latency benefit or removing operation guidance.

The next experiment should test plan/tool fusion in an actual multi-Bot
handoff/replanning workflow, then a separate batching experiment for independent
edits. Preserve intermediate evidence, stale-input checks and uncertain-effect
recovery. No general 100x or whole-robot development speedup is established.

Validation: local Python regression ran 1,981 tests with 3 skips; the final harness
stop-rule slice passed 4 focused tests; 124 Node tests passed. The experiment code
commit passed all four GitHub CI matrix jobs (Linux/macOS, Python 3.11/3.12).
