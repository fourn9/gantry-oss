# Changelog

## Studio structure navigation — 2026-11-06

- Pan product structure by dragging or scrolling, and pinch to zoom around the cursor.
- Inspect components without losing the full hierarchy; resize the sidebar and details.
- The public sample workspace uses the same navigation, without connecting live tools.

This file records changes after v3.3.0. Earlier release notes remain in the
[GitHub releases](https://github.com/fourn9/gantry-oss/releases).

## Unreleased

- Published website/demo source and regression tests under `website/`. In the
  browser-only demo, requests open their selected evidence and pinned comparison;
  CAD/Code navigation retains the request context.

- Studio team onboarding: Sources → Team review → Start. Import selected saved
  organization exports, review and edit role hierarchies, and separately create
  and start a persistent team. No live Notion/Linear/Jira synchronization is implied.
- Customer setup hosts connect once and handle Studio requests with owner-bound
  private journals, exact version checks, and explicit stop/resume recovery. Use
  existing subscription runtimes; no publisher-funded model or API-key fallback.
- Bot experience evaluation now includes generated lessons on isolated held-out
  tasks and selective independent evidence checks. These checks do not establish
  faster real-world engineering.
- Bot completion reports can atomically record explicit experience/action links,
  avoiding a separate bookkeeping inference turn. Preserve same-attempt evidence,
  private memory access, retry safety, and compatibility with existing reports.
- Studio Team and version-bound **Ask a Bot / Assign work**. Answers return to the
  original selection and Inbox; edits return as separate shared candidates.
  Existing customer runtimes execute the work; ordinary comments do not dispatch.
- Acknowledged Bot handoffs preserve saved changes, unfinished context and
  successor dependencies. Read-only Ask also blocks unrelated direct API writes;
  runtime replacement cannot silently reset an active executor.
- Guided project onboarding in Studio and CLI: preview saved-file scope, preserve
  answers and corrections, and open unfinished work. Optional customer-agent
  proposals retain exact source evidence and do not execute or adopt a design.
- Reorganized documentation, examples and historical release records. Updated the
  command-schema reference to include the current registered operations.

## 3.4.0 — Shared workspaces and connected engineering

- Artifact-first Studio with version-bound CAD/code discussions, unfinished sharing,
  saved-workspace import/watch/sync and independent continuation.
- Integrate external/native tool adapters and physical evidence workflows with Studio.
  Preserve fixed baseline acceptance alongside durable publication recovery.
- Streaming larger saved-file captures (10,000 files / 1 GiB), frozen retries and
  explicit stale-head/scope holds. Small browser imports retain atomic limits.
- Human-reviewed member grants, scoped recipient-owned credentials, session enrollment
  and revocation over existing audited principal decisions. No anonymous signup,
  administrator invitation or automatic paid inference.
- Operator provisioning, consistent verified backup/restore and single-host TLS/systemd
  configuration. Bound API request threads. Native vendor/cloud runtime qualification
  remains explicit; see PRODUCT_READINESS_VERIFICATION.md.

### Previously unreleased Bot work included in this version

### Added

- Opt-in paired Bot experience evaluation through isolated Core ledgers and
  normal Bot execution. Frozen inputs/verifier/model settings, private journals,
  independent candidate checks, failure-inclusive reporting and offline report
  regeneration. The synthetic example is not evidence of engineering speedup.

- Opt-in Bot experience planning and outcome reflection, with conditional lessons,
  applicability checks and preserved correction history.
- Persistent Bot/project working notes for commitments, unknowns and next steps.
- Links from recalled experience to recorded actions and their outcomes.
- Selective continuation after watched inputs or task reports change, or a due
  time arrives, within explicit owner standing delegation.
- Explicit recovery of held reflections using saved inference receipts.
- Explicit recovery of confirmed monthly Codex 429 failures during Bot planning
  or actions, preserving completed effects and enforcing a local cooldown.
- Reflection correction receives Core's validation error and the prior rejected
  submission; rejected output does not update learned experience.

### Security and compatibility

- Working context remains scoped to its Bot and owner; peer receipt views redact
  private context. Standing-delegation revocation reaches descendant work.
- Storage is additive. Existing credentials keep their allowlists; autonomous
  continuation and experience inference require explicit configuration.
- No new inference provider, mandatory dependency or publisher telemetry.

### Validation

- New paired evaluation smoke: both real subscription-model arms completed; the
  supplied-experience arm took 69.28 seconds versus 66.25 seconds without it.
  This synthetic single pair did not demonstrate time saving. See
  [comparison evidence and limits](docs/BOT_LEARNING_EVALUATION_VALIDATION.md).

- Earlier Bot-only Python regression: 1,062 invocations, no failures, 8 skips.
  The complete 3.4.0 validation is in `docs/PRODUCT_READINESS_VERIFICATION.md`.
- Real subscription-model checks completed experience selection, tool execution,
  working-note updates, experience/action links, report and outcome reflection.
  A changed-input check recorded a real failure without reusing the previous pass.
  Recovery included operator intervention; learning efficacy and engineering
  speedup are not established.
- See [operation](docs/BOT_CONTINUITY.md) and
  [runtime evidence and limits](docs/BOT_CONTINUITY_VALIDATION.md).
