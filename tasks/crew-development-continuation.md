# Crew development continuation

Status: implemented and verified (2026-11-07). User-approved fixes from a private development review; public fixtures are synthetic. Publication/deployment is separate.

Workflow: Addy Osmani agent-skills, reviewed revision `2686b620fc1fed2e8f60c704839c766b8594c6b6`; specification, planning, incremental implementation, TDD, interface design, security and review skills.

## Acceptance and slices

1. Intermediate integration keeps the task running, restores the exact integrated state, and supports local continuation or a delegated verification task. Conflicts, dirty workspaces, stale candidates and unauthorized integration remain blocked. Interrupted switches preserve the predecessor and reconcile receipts.
2. Correctable final-report errors return to the acting Bot in the same attempt. Unknown completion outcomes reconcile the exact request before any new model turn. Changed authority or basis holds execution.
3. Monthly inference instructions distinguish disabled native tools from permitted schema-defined Gantry actions. Project text is evidence, never additional authority.
4. An owner-configured tool can publish a frozen physical evidence plan after execution. Inputs, evaluator, environment and report hashes are retained; exit zero alone is not a physical pass; failed publication does not silently re-run the tool.
5. Existing adopted requirement revisions can be proposed as links to a state, reviewed explicitly, and retained through subsequent changes/checks/assignments. Unlinked requirements and missing verification remain visible. No inferred mapping creates a requirement or adoption.
6. Reports can carry structured unresolved items with Bot-selected dispositions (fix, verify, consult, defer) and concrete child task or consultation links. Task completion does not imply product completion; follow-up scope and hierarchy use existing authorization.

## Boundaries and compatibility

Reuse immutable states, changes, physical evidence plans, requirement references and Bot assignments. New fields are optional for old clients. No historical ledger rewrite. No external provider, credentials, new inference payment or production data migration. Core enforces identity, scope and exact versions; Bots choose the work. Mentor remains independent.

Untrusted model output, tool output, source files and proposed links cross validated contracts. Integration must not overwrite unsaved local files. Idempotency is required across lease recovery and lost acknowledgements. Formal adoption stays human-controlled.

## Verification

- [x] Focused regression tests for each slice, with failing reproductions first.
- [x] Recovery, authorization, stale evidence and negative-path tests.
- [x] Full Python suite and relevant JavaScript checks.
- [x] Independent code/security review and fixes.
- [x] Isolated real-model continuation evidence outside the public repository.
- [x] Documentation of supported paths and limits; no speedup or physical-safety claim.

## Review findings resolved

- Recheck local files after restoring an integration and before replacing the workspace.
- Persist evidence completion and its publication-action arguments together, so an
  interruption cannot lose the ledger receipt.
- Treat requirement discovery as an actual read: no idempotency key or new event.
- Carry descendant residuals to the upper manager, with explicit bounded-context
  truncation instead of silently dropping grandchildren's gaps.
- Guard changed assignment premises in both intermediate and legacy final-report
  integration, including waiting reports that later resume the same parent.

## Runtime evidence

Final frozen-source checks: Python unittest **1,792 tests, 14 skipped**, no failures;
focused continuation tests **62 passed**; JavaScript **71 passed**. The skipped
tests retain their existing environment/dependency conditions. `git diff --check`
and changed-document local links passed. Earlier full passes preceded final
review fixes; the counts above refer to the final source/test set.

The private-source exercise uses a fresh ledger, exact copied specialist files,
scripted fixture setup and actual subscription inference for lead continuation.
The first run recorded a diagnostic wrapper exception as unknown, retained its
output and returned a deferred issue. The corrected wrapper used an absolute
checker path without modifying the original source or criteria. The second run
integrated the saved candidates, regenerated outputs, executed the declared checks,
published fresh evidence and repaired a rejected report within the same attempt.
Physical unknowns and a semantic documentation conflict remained explicit; formal
adoption remained unchanged. Both source inventories and ledger hash verification
were checked. Private source, identities and model journals are not in this repo.

Studio's new requirement-link disclosure was rendered with production modules/CSS
in a browser using an anonymous fixture; expand/collapse and the unverified wording
were checked. JavaScript tests also check escaping before owner confirmation.

A wheel was built and installed in an isolated environment, new modules verified,
and `gantry-crew --help` executed. The initial no-build-isolation attempt could not
import setuptools in the test environment; standard isolated build succeeded.

See [operation and limits](../docs/CREW_DEVELOPMENT_CONTINUATION.md). No automatic
requirement invention, physical solver, arbitrary CAD connector, product-completion
judgment or engineering speedup is claimed by these tests.
