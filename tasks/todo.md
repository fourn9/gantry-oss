# Implementation checklist

## Bot-owned organization loop

- [x] Record directed consultation, attributed decisions, candidate identity and lessons.
- [x] Wake waiting requesters on replies and preserve stale-context/fence guarantees.
- [x] Add opt-in iterative model actions with scoped context/files/tools and receipts.
- [x] Add proposed organization and atomic owner activation without implicit privileges.
- [x] Verify hierarchy, alternatives, failure/revision, interruption, memory and security.
- [x] Run real subscription smoke separately from deterministic tests; report evidence.
- [x] Review, run regressions/package checks, document operation and limits.

- [x] Remove local review count cap; exercise new and legacy connections.
- [x] Add role profiles, proposal/activation and onboarding contracts.
- [x] Add communication and evidence-backed experience with access controls.
- [x] Connect onboarding and experience to existing review/job execution.
- [x] Expose local CLI/MCP operations and document setup/limits.
- [x] Verify hierarchy, restart, memory, stale inputs, security and replay.
- [x] Run regressions and summarize verified behavior and remaining limits.

## Connection lifetime and test limits

- [x] Compare current Bot foundation with the persistent-agent product boundary.
- [x] Remove default/hard-coded local expiry and test-count caps.
- [x] Add explicit owner renewal retaining existing session/Bot identity and history.
- [x] Verify long idle, thirteen real tests, idempotency, expiry choice and revocation.
- [x] Run regressions and update usage/reference documentation.

## Persistent Bot runtime

- [x] Add permanent organizations/Bots and explicit session-role bindings.
- [x] Retrieve individual and organization experience across authorized sessions.
- [x] Add owner-declared customer runtime, presence and fenced execution.
- [x] Run the durable review/edit/reflection loop automatically through a Bot worker.
- [x] Expose CLI/MCP onboarding, queue, restart and memory paths.
- [x] Test isolation, revocation, concurrency, interruption and fresh-context continuation.
- [x] Document setup, architecture, evidence and limits; run regressions.

## Two independent services

- [x] Record the product decision, customer workflows and responsibility boundaries in `docs/SERVICE_SPLIT.md`.
- [x] Identify current Mentor-job and review-team coupling; distinguish target architecture from v3.0.0 behavior.
- [x] Provide independently usable review-service and Bot-service CLI/MCP entry points and onboarding.
- [x] Separate Bot planning, assignments, peer discussion and candidate integration from Mentor review policy.
- [x] Preserve Core state/scope checks and persistent runtime fences; record workflow and responsible Bot explicitly.
- [x] Implement and verify additive storage, restore and replay without reinterpreting old jobs or extending authority.
- [x] Verify independent execution, saved milestone handoff, interruption and lost-acknowledgement recovery.
- [x] Enforce workflow isolation during recovery, generated background services and MCP onboarding; preserve the legacy compatibility entry point.
- [ ] Optional automatic ownership transfer of in-flight jobs across services (not required to run either service independently).
- [ ] Validate a customer model and native tool bridge on a real engineering task; measure quality and time separately from fixture tests.
