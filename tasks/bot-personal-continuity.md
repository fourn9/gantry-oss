# Personal Bot continuity

Approved direction: persistent role, experience-informed action, correction and
event-based continuation. Addy Osmani agent-skills reference:
2686b620fc1fed2e8f60c704839c766b8594c6b6. Extend the existing learning branch.
This is not a model-training or measured-speedup claim. Preserve private data.

## Capability map and build order

1. working-context: one versioned Bot/project working note, backed by canonical
   project/state/task references; commitments, next steps and explicit watch conditions.
   Fenced Bot updates and automatic report references; no duplicate design truth.
2. experience-actions: link recalled lessons to actual action receipts and reasons;
   ordered procedural lessons and outcome reflection reuse existing memory storage.
   Correction links retain old evidence. No learned permission or acceptance changes.
3. responsibility-wake: owner-approved standing scope, completion conditions and
   dependencies; Bot-defined watched files/tasks or one-shot due time. A worker
   materializes one ordinary reassessment task when relevant inputs change. Bot
   reasoning chooses actions, consultation and delegation. No semantic dispatcher.
4. runtime-validation: context and schema integration, durable pending reflection,
   safe retry behavior, real-model exercise separately from deterministic regression.

## Contracts and safeguards

Working notes belong to one persistent Bot and project. Profile and project goal
remain owner-controlled. Notes contain hypotheses, not authoritative requirements.
Source access, bindings, task/runtime fences and optimistic versions are checked.
Watched tasks must belong to the same project; paths must exist in the source
manifest. Working notes do not themselves grant permission to create new work.
Continuation requires separate human standing delegation; no model can enable it.
Changed delegation invalidates queued/running continuation work. Changes are
coalesced while a prior wake task is pending/running/waiting/held. Unknown effects
are never blindly retried. Polling with no relevant changes makes no model call.

No new inference vendor, dependency, cloud worker, telemetry, native CAD automation
or release. Existing configurations remain opt-in. No model-weight training.
One-shot deadlines use UTC epoch milliseconds, not local wall-clock strings.

## Acceptance and tasks

- [x] A fresh task/context sees the same Bot's working note and canonical project
      state, with pending commitments; another Bot cannot write it or read private notes.
- [x] Stale updates, forged references, revoked bindings and expanded scope fail.
- [x] Actual action receipts link a chosen lesson to work and subsequent reflection;
      fabricated/other-task actions fail. Old corrected lessons remain historical.
- [x] A relevant change/due time creates exactly one authorized task; no change
      causes no inference. Another change during running work remains available.
- [x] Disabling/reconfiguring standing delegation stops stale work; no permission
      or formal adoption is inferred from memory or completion.
- [x] Worker and MCP paths expose the same contracts; restart and acknowledgement
      loss preserve effects. Reflection failure is visible without losing pending work.
- [x] Regressions, replay, schema and package checks pass. Record live successes
      and provider failures separately; do not claim learning efficacy from fixtures.

Tests: `PYTHONPATH=tests ../gantry-security-env-20261024/bin/python -m unittest
test_bot_continuity test_bot_learning -q`; full discovery after integration.
Primary modules: bot_continuity.py/contracts, bot_wake.py, existing learning and
worker/action-loop hooks. Use stdlib and current transactional record/index patterns.

## Outcome

Implemented and regression-verified. See [validation](../docs/BOT_CONTINUITY_VALIDATION.md).
A real subscription model completed work and saved a procedure after a manual
evidence-contract fix; a fresh follow-up was held by provider HTTP 429. Its input
and journal remain preserved. Real multi-cycle learning efficacy remains unproven.
