# Studio team control acceptance — 2026-11-05

This extends the [initial setup acceptance](CREW_SETUP_ACCEPTANCE.md). That earlier
document describes the CLI and actual-model baseline. The current change connects
the same operations to Studio through a customer-owned persistent setup host.

## Verified in a browser

An isolated, anonymous local fixture ran the actual HTTP server, Core, setup host
and BotWorker. Only the inference responses were synthetic. No paid model or real
engineering tool was invoked.

1. Opened initial team setup for a saved project, entered organization notes, and
   saved Sources. The UI reached Team review with no worker execution.
2. Requested Suggest team. The registered customer host produced a proposal and
   inactive preparation. Studio displayed two roles with their reporting hierarchy.
3. Expanded the specialist role, changed its mission and saved it. The old runtime
   approval disappeared; Prepare runtime was required before Create team.
4. Created the exact revised team. Both roles were configured and offline; execution
   remained a separate Start action.
5. Started the team. Both runtimes became online and the first task completed through
   the actual worker path with synthetic reasoning.
6. Stopped both workers, then resumed them through Studio. Both reconnected. Core
   retained two Bots and exactly one completed first task; no duplicate task appeared.
7. Replayed the ledger. Its projection matched the stored state.

The saved API receipts show successful analyze, prepare, activate, start, stop and
start operations. Screenshots and the anonymous local evidence are kept outside the
public source repository. Layout was checked at 320, 768, 1024 and 1440 CSS pixels;
the document did not overflow horizontally. Role editing worked at 320 pixels.

## Contract and recovery checks

- Owner/project isolation; no setup-host capability in Bot or Mentor profiles.
- Exact proposal, preparation, configuration, session and host-instance checks.
- One active operation per host/setup; bounded owner records; no jobs on page open.
- Unknown HTTP outcomes replay the same intent. Unknown provider outcomes require
  the original private receipt and do not trigger another inference automatically.
- Existing Bot credentials, runtime configuration and memory are reused unchanged.
- Explicit Stop fences shared owned Bot runtimes across their project references.
  Failed-start rollback preserves an existing shared worker.
- Partial startup rolls back newly started workers. Lost stop acknowledgements
  preserve ownership and recovery. Expired worker instances can be explicitly resumed.
- Changed execution settings cannot be silently applied to an old Start approval.
  Explicit stop-only reconciliation preserves the first task and original receipt;
  cancellation cannot finish while relevant runtime leases are active.
- Unsaved role edits block approving an older proposal. Navigation cannot inject a
  late response into another project. Dynamic source/proposal content is escaped.

Independent review found and resolved issues in stale approval handling, lifecycle
idempotency, worker stop/restart and uncertain-result recovery. No required findings
remained in its final focused review.

## Limits

The browser run demonstrates functional wiring, not the quality of a proposed
organization, autonomous engineering, physical correctness, or development speedup.
Actual-model validation from the earlier baseline is not claimed as a fresh model
run of this UI. No new external service account, credential or paid API was used.

Customer setup still requires a one-time local connection and installed tools.
The host runs in the foreground unless the customer configures a supervisor.
Notion/Linear/Jira imports are selected saved exports, not live OAuth synchronization.
Loss of the private journal requires explicit recovery, not credential regeneration.
No deployment or GitHub publication is part of this change.

## Reproduce

Verification results: Python full regression **1,721 tests, OK, 8 skipped**;
browser JavaScript **57 passed**; a subsequent shared-worker stop regression and
all **17 focused host tests** passed; wheel build and current-module inclusion passed;
`git diff --check` passed. The supported test environment used Python 3.12.

An earlier full run exposed eager CLI imports in the new host parser; those imports
were made lazy and the interface regressions passed. A subsequent run had two
intermittent failures in the existing learning-transfer tests; both passed isolated
rechecks and the final full suite passed. Their intermittent cause remains a test
reliability follow-up, not a diagnosed fix or evidence of learning performance.

```sh
python -m unittest discover -s tests -q
node --test tests/*.mjs
python -m pip wheel . --no-deps --no-build-isolation --wheel-dir /tmp/gantry-wheel
```

Focused test modules: `test_crew_setup_jobs`, `test_crew_setup_host`,
`test_crew_setup`, `test_crew_setup_client`, `test_studio_crew_control_web.mjs`.
Use the supported Python version (3.11+) for both the runner and subprocesses.
