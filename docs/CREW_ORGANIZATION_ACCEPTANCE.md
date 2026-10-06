# Crew organization acceptance — 2026-10-06

This experiment extended the v3.0.0 source; no public release or hosted deployment
was performed. The package was 3.0.0 during the experiment; the project owner
designated this implementation v3.1 (3.1.0) on 2026-10-07. No private robot project
was used.

## What was exercised

A fresh anonymous project contained geometry.json, control.json and a fixed
Python evaluator. Initial reach and software limit were both 1. The objective was
to choose a reach between 2 and 3, match the software limit, and minimize reach².
The evaluator and acceptance conditions were not editable by Bots.

The owner configured five persistent identities: an integration lead, hardware
and software managers, and one specialist under each manager. The owner supplied
scope, hierarchy, objective and tool installation only. No parent-generated
candidate answer, chosen winner or intermediate assignment was supplied.

The successful real subscription run used separate Codex contexts and actual Core
transactions, restored workspaces and sandboxed evaluator processes:

1. The lead proposed two isolated alternatives, reach 2 and reach 3.
2. Each department manager delegated each alternative to its specialist.
3. Specialists edited their permitted files; managers collected their reports.
4. The lead requested separate integrations with exact change IDs and versions.
5. Managers delegated checks on each integrated state to specialists.
6. Both actual processes exited 0. Outputs were (reach=2, limit=2, score=4) and
   (reach=3, limit=3, score=9); both reported match=true and feasible=true.
7. The lead recorded a selection of reach 2 with evidence, the alternative,
   rationale and explicit limits. It then completed its assignment.

Technical selection did not adopt a design or silently move the original baseline.
The selected state is identified in the decision's target-state references. The
lead relied on delegated reports; it did not independently rerun their checks.

## Results and costs

| Observation | Result |
| --- | --- |
| Persistent Bots | 5 |
| Saved tasks | 15, all completed |
| Real model turns | 33 completed; no injected answers |
| Saved action receipts | 33 |
| Saved candidate changes | 4 |
| Saved states | 11 in this run |
| Attributed selection | 1, authored by the integration Bot |
| Saved provisional experience | 24 records, including task reports |
| Parent engineering interventions | 0 during the loop |
| Mentor jobs | 0 |
| Provider | Official Codex CLI, existing ChatGPT login; CLI default model |
| Reported provider input tokens | 831,065 (includes provider-reported cached input) |
| Reported cached input tokens | 34,560 |
| Reported output tokens | 11,331 |
| Reported reasoning output tokens | 532 |
| Observed elapsed time | 356.55 seconds, including inference, tools, persistence and waiting |
| Final task / ledger verification | completed / valid |
| Formal adoption / physical verification | neither performed |

This is a small functional exercise, **not evidence of faster robot development**.
The token cost and roughly six-minute run for a tiny fixture are material overhead.
Model default was not pinned, and there was no matched baseline comparison. No
publisher API key or paid API fallback was used; provider subscription quotas apply.

## Failed attempts and fixes

Two earlier isolated runs remained waiting/held; they are not counted as successes.

- The first exposed missing assignment enum values in model onboarding. Bots guessed
  unsupported kinds, then consulted peers about the API. The action loop now sends
  authoritative argument schemas and precise error paths.
- Both earlier attempts ended with provider timeouts/runtime lease expiration. In
  the second, the event log has a 1,131.39-second gap between its last heartbeat and
  the first hold. This is consistent with host suspension, not proof of its cause.
  Reported monotonic elapsed times were 389.15 and 263.75 seconds respectively and
  do not represent full wall-clock duration across that gap. The successful run
  kept the Mac awake for the experiment. Expired work was not marked complete.
- The successful run initially cited tool-action IDs in a decision, which the older
  evidence validator rejected. The Bot revised its evidence to accepted task IDs
  by itself. Current code also accepts same-project action/decision references;
  regression tests cover this extension without accepting arbitrary IDs.

The successful run saved a source manifest with SHA-256
`4b6d4e8d8f3e849892f27a8b4292ebe9b2262bb4268886625a0f82b984b7b56d`.
After that process had imported its code, narrowly scoped fixes added atomic source
fencing for stop/team actions, removed duplicate final checkpoints and bound action
receipts to the latest checkpoint plus workspace fingerprints. Those changes are
covered by the final regression suite; the 356.55-second observation is not a
second live run of those later fixes. Private receipts, credentials, run manifests
and failed-run logs remain outside the public repository.

## Verification of the final code

- Python 3.12: 546 test cases, 538 passed, 8 optional-environment skips,
  no failures, 74.702 seconds. This includes inherited compatibility cases, not
  546 distinct new behaviors.
- Existing UI suite: 7 passed.
- All 191 registered API input contracts match the generated reference.
- Wheel built and installed without extra runtime dependencies in a fresh temporary
  virtual environment. Both gantry-crew and gantry-ledger help/contract imports passed.
- Separate-context adversarial review found actionable bugs in stale effects,
  capture zone, uncertain-ack recovery, provider-input replay, unanswered questions
  and unbounded historical prompts. Each was fixed and exercised by a regression.
  No remaining reproduced issue was reported in that review. It is not a formal
  security audit or a proof of absence of vulnerabilities. A second model review
  was offered but not run.

| Acceptance path | Evidence type |
| --- | --- |
| Hierarchy, delegated work, independent candidates, exact-state checks, selection | real subscription fixture |
| Consult → peer task → reply → requester resumes → question resolution → memory | deterministic inference, real Core/worker transactions |
| Actual sandbox failure → edit → successful recheck | real processes, deterministic action choices |
| Lost committed/uncommitted request response without duplicate consultation | injected transport faults and actual recovery |
| Provider receipt reuse after interruption | injected provider interruption and exact-input assertion |
| Stale completion/cancellation and unauthorized scope blocked | race/security regression tests |
| Proposed team, owner-only atomic activation and rollback | real Core transactions in tests |
| Replay and compatibility with old Bot/Mentor routes | regression suite |

## Remaining boundaries

Native CAD/firmware automation, physical validity, arbitrary process-memory
restoration, optimal organization design and measured development speed require
separate evaluation. Provider failures and uncertain local effects can still
require explicit recovery. A final integration conflict is held rather than
silently rebased. Each persistent Bot has one active worker; separate Bots, not
multiple concurrent owners of one identity, provide parallelism. Memory changes
onboarding context; model weights are not automatically trained.
