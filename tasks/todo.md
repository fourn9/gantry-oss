# Implementation checklist

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
