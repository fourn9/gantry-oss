# Opt-in safe Bot recovery

Source workflow: Addy Osmani agent-skills revision
`2686b620fc1fed2e8f60c704839c766b8594c6b6`; read using-agent-skills,
spec-driven-development, planning-and-task-breakdown, test-driven-development,
incremental-implementation, security-and-hardening and code-review-and-quality.
The existing user approval covers this bounded change. Other task plans remain intact.

## Acceptance before implementation

- Absent `recovery_policy` preserves explicit-only recovery. An explicit policy has
  integer `max_attempts` from 1 to 3 and `cooldown_seconds` from 1 to 86400, belongs
  to `bot_development`, and participates in the owner-approved environment hash.
- A held/running task with the original journal can resume a saved completed
  inference or retry a known stopped, answer-free monthly timeout/429 after a
  fresh runtime fence and cooldown. Existing Core recovery checks remain final.
- Task-attempt recovery counts and cooldown survive worker restarts. Reserve a
  count before calling recovery, so a lost acknowledgement cannot create an
  unlimited retry loop. A service restart renews the fence; a bounded restart
  request is recorded before exiting the worker loop.
- Live or missing process identities, unknown outcomes, in-flight local tool/edit
  effects, changed requirements/dependencies/authority and changed environment
  remain held. Completed prior actions are not repeated. No automatic recovery
  applies to legacy Mentor work, reflection jobs, or arbitrary external commands.
- Recovery metadata records only count, time, status/reason and fence digest;
  task/model content and credentials are not copied into public files or logs.

## Plan and verification

1. Write a deterministic real-Core lifecycle test that fails because held work
   never recovers automatically. Include an already completed read action.
2. Implement one narrow gate using existing monthly and task-recovery helpers;
   keep the default off and renew fences through the existing service boundary.
3. Add adversarial lifecycle coverage for unknown effects, live PID, changed
   environment/authority, cooldown and attempt exhaustion; review the diff.

Files: `gantry/bot_worker.py`, `gantry/bot_auto_recovery.py`,
`tests/test_bot_auto_recovery.py`, this task record. No Core, action-runtime or
monthly adapter changes. Python standard library; use existing `Fault`, `require`
and `persist` conventions. Focused command:
`python3.12 -m unittest discover -s tests -p 'test_bot_auto_recovery.py' -v`.
The local `.venv` is absent and the host `python3` is 3.9; final regression uses
the parent's existing Python 3.12 environment. Full suite belongs to parent review:
`python3.12 -m unittest discover -s tests -p 'test_*.py' -q`.

Trust boundaries: owner-approved config, private durable journals, authenticated
Core, subprocess identity. Recovery never authorizes new scope. Anonymous fixture
reasoning proves lifecycle mechanics only; no live model, sleep/resume reliability,
engineering quality, or paid API use is claimed.

## Evidence

- RED: before implementation, two lifecycle tests failed because held work stayed
  `explicit_recovery_required` after restart and the recovery policy did not alter
  the environment hash. GREEN after the minimal gate.
- Additional RED regressions caught malformed/negative/bool retry counters,
  failed rate-limit receipts lacking PID, late answer evidence and missing
  recovery timing. Fixed in the automatic gate without changing Core or monthly
  retry helpers. Automatic recovery now also has payload-free timing spans.
- Deterministic Core tests cover stopped timeout recovery, preserved inference
  input, one completed read action, saved-response reuse after simulated lease
  expiry, new/old fence checks, unchanged authority, stale dependency requirement,
  429 backoff, persisted cooldown, 1- and 3-attempt caps across service restarts,
  unknown/live-process/tool/edit holds, environment approval, malformed counters,
  symlink refusal, and service exit after one recorded restart request.
- Final focused regression: 233 tests passed in 26.080 seconds across
  `test_bot_auto_recovery` (17 new cases), `test_monthly_timeout_recovery`,
  `test_bot_inference_recovery` and `test_persistent_bots`. `git diff --check`
  passed. Full-suite/build validation is owned by the parent integration review.
- These are anonymous local Core/SQLite/worker lifecycle tests. No live Codex CLI,
  paid API, host suspend/resume, launchd/systemd deployment or production recovery
  was exercised; no recovery was enabled for an existing customer runtime.

## Deliberate limits

The owner must approve the changed environment manifest before use. The service
supervisor must be installed already for unattended restarts; an interactive
worker exits with `runtime_reconnect_required` and needs to be restarted. No new
in-process restart loop was added. The initial cooldown begins when held work is
first observed, and the provider's 429 backoff is an additional lower bound.

Only the pending-inference journal boundary qualifies. Monthly adapter retries
need a stopped PID and answer-free evidence; completed inference receipts can be
reused. Existing action receipts awaiting reconciliation, partially edited output,
previously armed retries, reflections and legacy workflow remain explicit-only.
The attempt allowance is reserved before Core recovery; a crash or unexpected
transport/authority error can consume it without progress and leave the task held.
This intentionally prefers a visible hold over an unbounded or ambiguous retry.
Metadata is private and bounded to one small task-attempt status/counter record;
the existing timing implementation adds one local span per attempted recovery.
