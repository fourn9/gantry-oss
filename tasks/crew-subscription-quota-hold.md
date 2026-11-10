# Subscription quota hold and explicit recovery

Status: implemented and locally verified. Workflow: Addy Osmani agent-skills 2686b620fc1fed2e8f60c704839c766b8594c6b6 (TDD, observability, performance).

Problem: the official monthly CLI can terminate with a usage-limit error without an HTTP 429 code. It is currently reported as provider_failed; the safe recovery parser cannot recognize that known, answer-free terminal outcome.

Acceptance:
- Recognize usage exhaustion only from a terminal turn.failed provider event with no answer/agent message and a stopped recorded process.
- Return a specific provider_usage_limited fault; do not infer a reset timestamp from locale-dependent prose or start a paid fallback.
- Preserve ordinary 429 cooldown and unknown/live/partial-result holds.
- Automatic recovery never retries subscription exhaustion, even after its local cooldown; owner retry allowance is not consumed.
- An explicit retry request may archive and arm this known stopped inference after the operator has confirmed allowance is restored. Preserve context/schema/model settings and completed action receipts.
- Tests must fail before implementation; include actual-shaped CLI response, no-repeat behavior, explicit recovery, negative response/live-process cases and real-Core automatic-hold integration.

No UI/library migration, provider change, monthly cap bypass or alteration of private engineering decisions. Product behavior changes are outside the already-stopped measurement window.

Validation: the new classification and explicit-retry regressions failed before the fix. The full unittest suite passed: 1,907 tests, 14 existing skips (1,893 passed). Real-Core deterministic tests confirm automatic quota holds and explicit recovery preserve input and completed read receipts. These tests do not establish renewed live provider availability.

Review: correctness, journal integrity, provider-event provenance, stopped-process checks, bounded parsing and no automatic quota retry were reviewed. Late response evidence after a cached quota receipt is rechecked and covered by regression tests. No new dependencies, paid fallback, public customer fixtures or credentials were introduced. Localized/unrecognized provider errors intentionally remain held.
