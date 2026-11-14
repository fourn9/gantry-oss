# Crew standing routines

Reference: Addy Osmani agent-skills, reviewed revision
`2686b620fc1fed2e8f60c704839c766b8594c6b6` (using-agent-skills,
test-driven-development, incremental implementation and review).

## Product evidence and scope

Instinct's official https://instinct.com/ describes a personal assistant that
understands ongoing work and can act through permitted tools. Its
https://instinct.com/privacy-policy describes personalized use of interaction
context; it does not disclose an implementable memory or online-learning
architecture. This change is inspired by that experience, not a reproduction
of proprietary internals or a claim of equivalent intelligence.

Existing Crew already stores per-Bot context and experience and executes
hierarchical delegation, watched changes and one-shot due dates. Extend its
existing owner-approved continuation policy with an optional recurring routine.
Bots choose priorities and delegate; Core only persists and enforces authority.
No additional model API subscription, hosted VM, or automatic model training.

## Contract

Optional `routine: {interval_ms, first_due_at}` (UTC epoch milliseconds).
Omission/null disables recurrence, preserving legacy event/one-shot behavior.
One reassessment at or after each due time, even before a first working note.
After enqueue, next due is enqueue time plus interval: missed periods coalesce.
Active/waiting/held work suppresses replacement; authorization is rechecked.
Task records retain scheduled and actual enqueue times. Policy and enqueue are
saved in the same transaction. Status is visible in working-state context.
Customer worker with personal_continuity enabled must be running/polling;
Gantry cannot wake a closed customer application by itself.

## Acceptance

- [x] Initial due routine starts without parent-created task or working note.
- [x] Restart/reconnect does not duplicate work; downtime coalesces to one run.
- [x] Existing in-flight/held work blocks recurrence without losing its due time.
- [x] Owner revocation, stale authority and executor identity checks remain effective.
- [x] Legacy one-shot/event behavior is unchanged; no default extra inference.
- [x] Returned context explains cadence, next due and last task.
- [x] Runtime tests distinguish fixture decisions from actual model capability.
- [ ] GitHub CI completed before merge.

## Validation record

- RED: the first two recurrence tests failed at contract validation (`Unknown field`).
- GREEN: existing continuity suite passed (108 tests at that point); independent
  review subsequently ran 110 tests with no blockers. Five focused routine tests
  passed after adding cadence-removal and timestamp assertions.
- Real Core, SQLite/event replay, runtime leases and Worker execution are used.
  Inference is a labeled fixture: no live-model judgment quality or speedup claim.
- Tested lead -> mechanical manager -> designer and control -> lead completion,
  starting solely from a due owner-approved routine. Child tasks retain standing
  authority; Mentor is not involved.
- Headless security baseline found no findings in the checked Python environment.
- The existing HTTP development-loop example completed with verified event log
  and matching replay. It uses no model calls.
- Independent review found no blockers; optional timestamp/removal coverage added.

## Remaining product limits

A running customer Worker/supervisor is still necessary; no dedicated hosted VM
is provisioned. Native tool capabilities depend on configured adapters. This
extension schedules reassessment, not automatic weight training or proof that
learned experience improves choices. Long-horizon usefulness needs live-model,
role-specific evaluation under the customer's inference arrangement. Autonomous
organization redesign and guaranteed global optimization are not implemented.

Local full suite: 1,923 tests in 222.704 seconds, OK (3 skips). The final
cadence-removal/timestamp additions were also verified in the focused 5-test run.
CI verifies the final revision on Linux/macOS and Python 3.11/3.12.
