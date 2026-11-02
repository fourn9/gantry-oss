# Paired experience evaluation: initial validation

Recorded 2026-11-03. This is an actual subscription-model smoke comparison of the
evaluation path, using the public synthetic joint-configuration example. It is
not a robot-development benchmark, physical simulation, or proof of learning efficacy.

## Fixed configuration

- Official Codex ChatGPT login; requested model `gpt-6-astra`, reasoning `low`.
- One pair, seed 42; experience withheld first, supplied second.
- Ten model calls and 360 seconds allowed per arm, including planning/reflection.
- Identical frozen JSON inputs, Python verifier, scope, goal and acceptance.
- Separate Core ledgers, identities, task contexts and workspaces.
- The supplied note is an operator-authored synthetic lesson, explicitly labelled
  as unverified history. It does not contain a measured prior successful trial.
- macOS sandbox, no network access for the project verifier, no API-key inference.

## Observations

| Measure | Experience withheld | Experience supplied |
| --- | ---: | ---: |
| Accepted trials / planned | 1 / 1 | 1 / 1 |
| Total seconds, setup excluded | 66.249 | 69.281 |
| Setup seconds | 0.055 | 0.081 |
| Model calls | 6 | 6 |
| Model-call seconds | 65.50 | 68.53 |
| Remaining measured overhead, seconds | 0.75 | 0.75 |
| Reported input tokens | 89,071 | 95,268 |
| Reported output tokens | 1,179 | 1,454 |
| Failed Bot tool checks | 0 | 0 |
| Repeated identical Bot tool checks | 0 | 0 |

Both arms used the same action order: edit mechanical configuration, edit control
configuration, run `verify`, finish. Each also completed a planning call and an
outcome reflection. The supplied arm recalled the prior note as requiring recheck;
its reflection did not claim that memory caused the outcome.

The independent verifier ran on the initial state, each of two edited states,
and the final state. Results were fail, fail, pass, pass in both arms. The Bot's
own verifier call also passed. Both ledger hash checks succeeded and replay
matched. Saved states remained **unadopted**. Generic evaluation observations
are linked by state/snapshot/evaluator references; this experiment does not turn
the Core state into a formally verified or adopted engineering configuration.

There is **no observed time saving** in this pair. The ratio without/with was
0.956. A single sequential pair cannot separate model variation, order and caching
effects from memory effects. The tiny task is solvable from its current inputs;
the added note did not change the observed work order or prevent a recurring error.
Human effort and per-call monetary cost were not measured. Native provider usage
was recorded, not converted into an invented monetary estimate.

## Verification of the harness

The complete regression suite passed **1,070 invocations in 127.288 seconds**, with
8 environment-dependent skips. Counts include inherited unittest cases. A final
focused run passed 15 tests, including malformed-tool metrics and preserving pinned
model settings across explicit rate-limit recovery. Wheel building succeeded.

Focused regressions cover independent memory/context, a false completion claim,
intermediate failure then success, fresh final verification, model/effort pinning,
provider holds, call limits, metrics after failure, and summary-only CLI output.
An independent review identified missing failure-path metrics, undercounted tool
errors and reused final checks; those were fixed before this model comparison.
A CLI output regression subsequently removed unintended full-report printing.
No model experiment was silently retried or discarded.

Raw inputs, outputs, credentials and ledgers remain in a private local evaluation
directory and are not included in the public repository. The public example and
the [evaluation guide](BOT_LEARNING_EVALUATION.md) allow a new comparison, not
bit-for-bit reproduction of a stochastic provider response.

## What to test next

Use held-out tasks where a selected, evidence-backed prior experience could change
the order of inspection or verification. Freeze that experience and acceptance
before running, include changed-condition cases where it should be rejected, and
run balanced repetitions. Only then evaluate recurring mistakes, elapsed time and
token overhead before introducing automatic lesson promotion or procedure updates.
