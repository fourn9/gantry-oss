# Initial Crew onboarding acceptance — 2026-11-05

This is the original CLI/model baseline. The subsequent Studio-controlled host
implementation and its current boundaries are documented in
[Studio team control acceptance](STUDIO_CREW_ACCEPTANCE.md).

## Scope

Connect saved project state and selected organizational exports to a proposed
hierarchy, persistent Bot identities, customer runtimes, first work and learning.
Reuse the existing membership, project, Bot, task and memory models. `crew_setups`
is an additive replayed projection; old ledgers and Bot memories are not rewritten.

## Verified paths

- Source bytes are retained separately from editable project files. Evidence is
  pinned to hashes and row/cell/text locations. Truncation and unavailable content
  are explicit. Malformed XML/ZIP, spreadsheet macros, source credentials, oversized
  expansion and foreign evidence are rejected. No source link is fetched.
- Import and model proposals do not grant permissions or start work. Owner activation
  checks the exact proposal, saved project/organization versions, hierarchy, scopes
  and dedicated agent identities. Reusing an existing organization preserves Bot
  profiles, versions and memory. A credential cannot silently represent another Bot.
- CLI preparation creates private customer credential/config files. Unknown server
  responses reuse exact requests; input changes require fresh review. Existing Bot
  runtimes are reused without replacement. The owner token is not a worker token.
- Actual worker presence gates first work. Core supplies the role rationale and
  source evidence to the worker. A deterministic end-to-end reasoning fixture uses
  the real worker/Core path for manager delegation, a specialist edit and a restarted
  manager collecting the report. No Mentor execution is involved.
- English Studio provides source preview, proposal/hierarchy/evidence, existing-agent
  mapping and readiness. Project-only onboarding remains available. UI tests cover
  escaping, stale responses, same-intent retries and offline/owner guards.

## Actual customer-model check

Two isolated anonymous fixtures used the existing official Codex subscription
adapter with no API-key fallback. Each supplied a saved two-file project, a role
CSV and a short workflow document. The owner explicitly requested a two-role team
and a first task limited to explaining saved constraints and unknowns. This tests
source-to-organization execution, not unconstrained organization optimization.

| Run | Observation |
| --- | --- |
| Initial | Organization proposal and lead Bot task completed. Reflection was held because the model cited an assessment ID that was not eligible observation evidence. |
| After narrow guidance fix | Organization proposal, lead Bot task and reflection completed. One conditional memory was saved. Replay matched the saved state. |

The fix exposes a bounded list of visible eligible evidence IDs and explains that
nested assessment IDs are not observation citations. It does not weaken validation
or automatically retry model calls. The original held attempt is preserved.

The successful run took approximately 78 seconds from proposal inference through
worker execution and reflection. There is no baseline comparison and no speedup
claim. Both runs used the CLI's default model; the provider receipt labels it
`CLI default`, so an exact model snapshot was not independently established.

Private model receipts, original failed/successful attempts, tokens and ledgers
remain outside the source repository. Public tests use anonymous fixtures and
synthetic inference; they are not evidence of engineering correctness.

## Remaining boundaries

- Notion, Linear and Jira input is selected exported files, not live OAuth or sync.
- CSV/XLSX columns are evidence for inference, not a trusted permission schema.
  Safe XLSX tables are supported; legacy XLS, images, macros and embedded objects
  require an appropriate text/table export.
- Browser analysis uses the connected customer agent or CLI. Model calls are not
  started merely by opening a page. New credentials are prepared privately by CLI.
- Customer workers still need installed tools and explicit startup. There is no
  new hosted runtime, arbitrary CAD connector, automatic VM provisioning or paid
  model service in this change.
- The real-model check executed the lead's bounded planning task. Multi-Bot
  delegation was tested with deterministic inference, not claimed as a live
  multi-model engineering or physical validation trial.
- Creating persistent identities and saving a conditional memory does not prove
  improved future decisions, an optimal organization or reduced development time.

## Final verification results

- Python full regression: **1,670 tests, OK, 8 skipped**, final isolated run.
- Browser JavaScript tests: **49 passed**.
- Wheel built successfully; onboarding Python modules and browser assets are present.
- `git diff --check` passed.

Two earlier full-suite runs each had one transient failure in existing tests:
`test_worker_uses_plan_reflects_and_next_fresh_context_changes_order` and
`test_actual_http_disconnect_reconnect_keeps_one_execution`. Both passed isolated
checks; the learning case also passed 200 repeated attempts. The final full suite
passed. The intermittent failure cause is **not established**; this is retained as
a test-reliability follow-up, not reported as a diagnosed/fixed product defect.

## Reproduce functional verification

Use the project's supported Python environment and run:

```sh
PYTHONPATH=tests python -m unittest test_crew_sources test_crew_setup test_crew_setup_client -q
PYTHONPATH=tests python -m unittest discover -s tests -q
node --test tests/*.mjs
python -m pip wheel --no-deps --no-build-isolation . -w /tmp/gantry-wheel
```

For a customer-model check, follow [Crew setup](CREW_SETUP.md) with a disposable
anonymous project and private journals. Start with no external tools and a bounded
planning task. Retain any held attempt; use the existing explicit recovery workflow
rather than deleting journals or repeating an uncertain provider call.
