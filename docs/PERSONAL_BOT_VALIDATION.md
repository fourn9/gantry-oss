# Personal Bot work-cycle validation

Observation: 2026-11-17 (Japan), anonymous scalar calibration fixture.
Base: `3e191ae` plus the personal-Bot working changes in this branch. This report
is not a measurement of a different branch's concurrent performance work.

## What actually ran

Two independent customer-model contexts, `maintainer` and `reviewer`, used the
existing official Codex CLI / ChatGPT-login backend. CLI default model, low
reasoning effort; exact resolved model ID was not recorded by this backend.
Native model tools were disabled; Gantry executed the requested scoped actions.
`evaluate.py` ran as an actual sandboxed process. No CAD, robot or hardware was
simulated by a mocked response; this example is deliberately a **scalar fixture**,
not a CAD or robot validation.

The setup supplied three files, frozen acceptance, role profiles, a human report
preference, one initial assignment and standing continuation authority. It did
not supply the corrective offset, proposed model outputs or prewritten lessons.
The intended lifecycle was described in onboarding; this is an instructed
functional observation, not a test of discovering an unknown workflow.

| Stage | Observed behavior |
| --- | --- |
| Initial work | Maintainer created a task-linked responsibility, read the saved inputs, edited controller offset and ran the real evaluator. |
| First result | Evaluator reported measured=5, corrected=3, absolute_error=0, passed=true. The shared candidate changed only controller.json. |
| Reflection | Bot-authored conditional procedure lessons were stored through the existing reflection path. |
| Planned restart | Worker instances closed and Core reopened. No new task, memory, repair or answer was inserted. |
| Continuation | Existing standing authority and changed responsibility/feedback enqueued the next task; the Bot retrieved its prior task/report/candidate. |
| Continued work | Maintainer integrated the previous candidate and evaluated the exact combined state. |
| Peer check | Maintainer requested a memory-specific check; reviewer inspected actual records and ran evaluate independently. |
| Disposition | Maintainer inspected the returned evidence, resolved the consultation, recorded a scoped preferred procedure, explicitly completed its responsibility and reflected. |

The human preference (metrics before recommendations, unknown physical behavior
separate) was reflected in the final reports. Shared/finished work did not become
formal design adoption. Core verification and replay both matched.

## Parent intervention

- Setup: fixture/acceptance, roles, delegated scope, installed tool, report
  preference, one initial task, standing authority and observation window.
- Planned operational intervention: close/reopen both workers and Core after the
  first task and its reflection. This tests durable continuation, not a crash
  during an uncertain tool effect.
- After setup: no parent-authored repair value, task selection, peer answer,
  model-output rewrite, manual recovery or memory insertion. The automatic
  continuation and its consultation tasks came from the product/Bot paths.
- No solution comparison or speed-up control group was run.

## Cost and limits observed

| Measurement | Result |
| --- | ---: |
| Wall time, including setup, model calls, checks, records, waiting and restart | 419.66 s |
| First cycle including reflection | 75.23 s |
| Maintainer model calls / elapsed model time | 24 / 322.70 s |
| Reviewer model calls / elapsed model time | 10 / 160.53 s |
| Model action responses | 25 |
| Learning-plan and reflection responses | 9 |
| Reported input tokens | 1,077,842 |
| Reported cached input tokens (subset of input) | 48,512 |
| Reported output tokens | 11,003 |
| Actual evaluator executions | 3 |
| Manual recovery / runtime errors | 0 / 0 |
| Automatic learning replans caused by arriving shared experience | 2 |

Model time overlaps across Bots and must not be summed as wall time. Tokens are
provider receipts, not a separate API invoice or a price estimate. No API-key
fallback was used. The small arithmetic task does not justify this cost by itself;
the point was exercising the complete continuation and learning path. This
observation **does not establish faster engineering or monotonically better Bots**.

The fixture polls every 0.5 seconds: of 1,529 recorded events at replay, 732 were
runtime heartbeats and 678 continuation polls. That cadence exposes bookkeeping
volume; it is not a production throughput benchmark. Repeated broad context and
peer-history reads also need separate efficiency work. Preserve these costs in
future comparisons rather than reporting only evaluator time.

## Verification scope

Final source verification on 2026-11-17: all 32 focused tests passed. The full
suite ran 1,997 tests in 239.240 seconds with no failures and 3 skips. An isolated
wheel build and installed-package imports, Core bootstrap and replay passed.
`gantry.security_check` reported no findings against the repository's dated
baseline; this is not a comprehensive current-vulnerability or penetration audit.

Core/Worker regression tests cover task-linked closure, priority changes, due
wake/restart, handed-off tasks, held-work suppression, chronological pagination,
changed-input replan, scoped human feedback/withdrawal, stale prepared actions,
legacy credentials/plans, independent procedure checks, retirement, peer privacy
and replay. In the deterministic whole-worker procedure test, decisions are
explicitly fixture choices but sandbox execution is real.

After the real-model observation, migration hardening (legacy plan feedback pins,
capability-filtered action advertising) and explicit priority changes were added.
Those final changes are covered by regression tests; the live observation above
is not represented as an exact run of every final source byte or as a live test
of priority selection.

## Reproduce

Use Python >=3.11 and a customer ChatGPT-authenticated Codex CLI. From this checkout:

```sh
PYTHONPATH=. python examples/personal_bot_cycle.py \
  --output /absolute/private/new-observation-directory --seconds 1500
```

`--model` can pin an available model. The observation is opt-in and consumes the
customer's allowance. The output directory must be new and outside this source
repository; it contains ledger, tokens, model inputs, action receipts, timeline
and final state. Do not publish it. The source example contains anonymous inputs
only. `--seconds` bounds this observation, not ordinary product execution.

The live run demonstrates subsequent memory retrieval/rechecking and procedure
selection. Reuse of that newly preferred procedure on a later held-out problem
was not demonstrated; the deterministic Worker test covers the later-use path.

Further evidence needed: a held-out second engineering problem, larger concurrent
responsibilities, long-lived memory consolidation, and role-specific quality/cost
comparisons. Task/project feedback is implemented; inferred organizational habits
and Studio controls are not added in this change.
