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

- [ ] Initial due routine starts without parent-created task or working note.
- [ ] Restart/reconnect does not duplicate work; downtime coalesces to one run.
- [ ] Existing in-flight/held work blocks recurrence without losing its due time.
- [ ] Owner revocation, stale authority and executor identity checks remain effective.
- [ ] Legacy one-shot/event behavior is unchanged; no default extra inference.
- [ ] Returned context explains cadence, next due and last task.
- [ ] Runtime tests distinguish fixture decisions from actual model capability.
- [ ] Tests, documentation, independent review and GitHub CI completed.
