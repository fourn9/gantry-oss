# Bot inference recovery

Use Addy Osmani agent-skills at reviewed revision
`2686b620fc1fed2e8f60c704839c766b8594c6b6`: debugging, specification,
test-driven development and code/security review.

## Problem and scope

A monthly Codex invocation can terminate with HTTP 429, leave no answer, and
keep the Bot held. Independent Bot recovery currently rejects retry-inference,
so an operator must archive provider files by hand. Completed actions must never
be repeated to recover the next model call. Provider availability is outside
Gantry's control; this change does not buy credits or switch to a paid API.

## Acceptance

- Classify a terminal, answer-free Codex 429 separately from an unknown outcome.
- Repeated polling makes no new inference request. Explicit recovery enforces a
  local exponential cooldown (not a prediction of the provider's reset time).
- `--recover-job --retry-inference --confirm-stopped` archives only the failed
  planning/action inference; exact inputs, completed actions and receipts survive.
- Live processes, unknown outcomes and changed task authority remain blocked.
- Reflection rejection preserves Core's error and the rejected answer; an explicit
  correction provides both to the model without weakening evidence validation.
- Include planning inference in the existing process-liveness recovery check.
- Test recovery after a completed action and after a failed planning call;
  prove the action is not repeated and inputs are unchanged.
- Run the held real-model task through report/reflection, then a changed-input
  task. Report provider holds separately if real inference remains unavailable.
- Publish only anonymous summaries, source and tests; keep model journals private.

## Verification

Implementation: additive private provider journal states; no ledger migration,
new dependency, permission grant, background retry, or paid fallback.

Regression tests reproduced the original classification/retry defect, missing-PID
and reflection unknown-outcome gaps, and absent validation feedback before fixes.
Focused recovery/continuity/learning tests pass. Final suite: 1,062 invocations,
no failures, 8 skips; wheel built. Independent review's two required guards were
fixed and re-reviewed. The original held real-model task completed without
repeating its tool; rejected reflection was corrected through the product path;
a changed-input real-model task detected the mismatch and completed reflection.
Anonymous runtime results and limits are in `docs/BOT_CONTINUITY_VALIDATION.md`.
