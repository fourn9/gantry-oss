# Explicit stopped-timeout recovery

Workflow reference: Addy Osmani agent-skills `2686b620fc1fed2e8f60c704839c766b8594c6b6`; using-agent-skills, debugging, TDD and security review. User authorized fixing execution gaps in Bot collaboration.

Problem: a locally timed-out Codex process is stopped, but its journal remains `started`. Explicit Bot recovery accepts only an answer-free 429, leaving a known timeout unrecoverable through that path.

Acceptance:
- Record timeout only after the child is confirmed stopped; preserve input, schema, model settings and process identity.
- Explicit retry accepts that recorded timeout only while its PID is stopped and no saved answer or completed/partial agent response exists.
- Archive the old invocation and preserve context/settings; retry remains opt-in.
- Unknown started invocations, missing identities, live PIDs, malformed journals and unrelated failures remain held. No engineering work or external effects are repeated automatically.
- Test RED before implementation, then timeout and existing monthly/Bot recovery regressions.

Scope: monthly adapter/recovery and anonymous tests only. Existing old `started` journals are not automatically migrated; operators must separately reconcile their unknown outcome.

Validation completed:
- Before the fix, four new tests produced one failure and one error: no stopped-timeout receipt and no permitted explicit retry.
- After the fix, timeout, monthly adapter and Bot inference-recovery regressions passed: 207 tests in 19.749 seconds. This includes a real Core/worker recovery flow with deterministic inference, exact pending-input reuse, no replay of a completed read action and matching ledger replay.
- Unconfirmed adapter stop, live/missing PID, saved/partial/completed response, malformed/missing events and unrelated failures remain held.
- No live inference or engineering behavior was exercised by these tests. No new dependency or automatic retry policy was added.
