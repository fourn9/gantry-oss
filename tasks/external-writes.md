# Scoped native writes

Addy Osmani agent-skills reviewed revision: 2686b620fc1fed2e8f60c704839c766b8594c6b6.
Apply specification, planning, TDD, incremental implementation, interface design,
security and code review. User authorized local implementation and contract tests;
no live accounts exist. Keep this side branch isolated and do not publish it.

## Objective and acceptance

Extend the read/capture integration slice to explicit native updates of existing
objects. No delete, permissions changes, arbitrary HTTP, bulk edits or remote execution.
API credentials are supplied separately for each invocation, never included in plans.

1. `prepare-write` reads the selected object and saves an immutable plan, exact
   update, source identity, baseline, reason and requirement links. It never writes remotely.
2. `apply-write` requires the exact plan digest, rereads the baseline, uses provider
   concurrency controls where documented, writes once and reads the object back.
   APIs lacking atomic conditions require explicit `--allow-nonatomic` acknowledgement.
3. Durable local journal claims the plan before dispatch. A retry cannot dispatch
   again. Unknown outcomes may only be reconciled by reading; no exactly-once claim
   across devices/independent journals. Concurrent callers serialize per operation.
4. Before/after raw responses, request, observed revision and outcome become a normal
   capture bundle for existing immutable Core publication and requirement context.
   Matching requested fields is write verification, not engineering acceptance/adoption.
5. Failed, unconfirmed, conflict and readback-mismatch outcomes remain distinguishable.
   External content cannot authorize writes; path/host/body bounds and credential
   scanning apply before dispatch as well as to persisted evidence.
6. Native write coverage: GitHub issue and existing repository file; GitLab existing
   repository file; Confluence page; Jira/Linear issue; Notion paragraph; Sheets/Excel
   rectangular values; Drive/SharePoint metadata (not file-body replacement);
   Slack existing message; Onshape existing feature's named parameter expressions.
   The other catalog entries remain explicitly unsupported for native writing.

## Plan / task list

- [x] GitHub file vertical slice: plan, conditional write, verification and durable retry.
- [x] Remaining provider recipes with strict native targets and selected fields.
- [x] CLI + evidence publication roundtrip; no silent pass/adoption.
- [x] Security/negative cases, full tests, build, capability and usage documentation.

## Threat boundaries and limitations

Local operator controls CLI and credential scopes. A checksum detects changes but is
not a user signature or a substitute for provider authorization. No public write endpoint
is added. Provider ACLs remain authoritative; remote content is data, never instructions.
Journal should live on durable owner-controlled storage. Same-user malicious processes
and deliberate copying of plans/journals are outside the local process trust boundary.
No OAuth onboarding, continuous sync or licensed desktop SDK automation in this slice.
No live remote mutation, paid service, customer data or parent checkout change.

Commands: `python -m unittest discover -s tests -p 'test_external*.py' -v`;
`python -m unittest discover -s tests -p 'test_*.py' -q`; `python -m pip wheel . --no-deps --no-build-isolation --wheel-dir /tmp/gantry-native-write-dist`.

## Review findings addressed

- Read-only GraphQL transport now rejects mutations. Native write transport reconstructs
  allowlisted requests rather than accepting arbitrary URLs/methods.
- Partially failed GraphQL/native responses after dispatch are unknown, not assumed
  unapplied. Durable receipts prohibit redispatch and support read-only reconciliation.
- Plans are checked against original observations; server-normalized mismatches are
  retained, not silently labeled verified. Onshape preserves untouched native fields.
- Decoded repository content is screened for configured credential echoes as well as
  known secret patterns. Single-source size bounds protect local journals/bundles.
- CLI output omits raw response/readback bodies. Full evidence stays in owner-only
  capture/journal files for explicitly authorized Core publication.
- Fresh explicit preparations have distinct intent IDs; retries reuse the saved plan.
  No deduplication across independently created plans or journal stores is claimed.

No database migration, parent-checkout change, mandatory dependency or live write.
Native persistence is not engineering acceptance. Core execution authorization is
still the caller's existing work-contract path; this CLI is not a new public write API.

## Final evidence (2026-11-03)

- 18 added tests (17 native-write tests and one real Core evidence/publication test).
  Native fixtures cover all 12 providers / 13 operations, not live tenant acceptance.
- External-integration suite: 34 tests passed.
- Full Python suite: 717 cases, one skipped, no failures (85.163 seconds).
- Wheel built with pip's existing setuptools backend, installed outside this checkout;
  the 17 native-write tests, including CLI prepare/apply/reconcile/export, passed against
  the installed package. `python -m build` was unavailable; no dependency was added.
- Core test retained pinned requirement links and before/after/request evidence while
  requirement coverage remained unverified and adoption remained unadopted. Replay matched.
- Checked stale baselines, permission/conflict refusals, mismatching readback, no-op,
  GraphQL partial errors, crash/lost response, concurrent dispatch, payload/host bounds,
  plan tampering and configured credentials hidden inside base64 repository content.
- Documentation and catalog distinguish metadata-only updates, preflight-only operations,
  unsupported vendor tools and untested live accounts. No remote service was mutated.
- No public push/release or parent-thread merge; package version remains the branch's
  existing 3.3.0 metadata, not a claim that this is the published release artifact.
