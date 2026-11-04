# Project and organization onboarding into persistent Crew

## Objective and authorization
Connect existing project import to evidence-based organization proposals, persistent
Bot identities, explicit owner delegation and customer-owned runtimes. User approved
implementation on 2026-11-05. Use Addy Osmani agent-skills revision
2686b620fc1fed2e8f60c704839c766b8594c6b6: specification, planning, incremental
implementation, API design, TDD, security, frontend and independent review.

## Contract
- Existing project state and selected organizational exports are separate sources.
  Notion Markdown, Linear/Jira CSV, generic CSV/JSON/text and safe XLSX provide
  evidence; they never grant authority. Preserve original bytes and exact provenance.
  No live OAuth/sync claims, fetching source URLs, macros or spreadsheet evaluation.
- A saved setup pins session/state, organization version and selected source hashes.
  An agent proposes organization profile, hierarchical roles, rationale, evidence,
  responsibility, consultation/reporting conventions, scopes and uncertainties.
  Submitting a proposal cannot create credentials or enable execution.
- Owner reviews/corrects the proposal, then explicitly maps roles to dedicated agent
  principals. Existing membership, organization/Bot/project bindings and queue are
  reused. New credentials stay on the customer device; only hashes are submitted.
- Existing organization identities and memories are reused without silently editing
  their profiles. Project bindings remain separate. Stale/foreign evidence and
  authority expansion are rejected; activation is atomic and retry-safe.
- Setup is resumable. Runtime readiness reports actual offline/unconfigured/ready
  status. A CLI prepares private per-Bot worker configurations, owner approves their
  exact environment, then existing bot-worker runs them. No project execution on
  import or proposal. First work is an explicit owner action; managers then delegate.
- Compact English Studio entry from Team, sources/review/readiness, with CLI/MCP
  equivalent commands. Preserve project-only onboarding as a valid partial use.

## Verification
Anonymous fixtures only. Test malformed spreadsheet/XML/ZIP, source truncation,
secrets, provenance, unauthorized proposal/activation, hierarchy, stale state,
atomic rollback, retry, reuse of organization identity, offline runtime and actual
worker continuation. Record a subscription-model smoke separately from fixture
reasoning. No speedup or native tool connection claims from these tests.

## Slices
- [x] Source parsers and bounded evidence views.
- [x] Saved proposal and owner activation over existing models.
- [x] Customer inference, private runtime preparation and CLI/MCP.
- [x] Studio flow and existing onboarding handoff.
- [x] Acceptance, independent review, usage documentation.

## Data and privacy
Additive `crew_setups` projection, replay-compatible; no existing state rewritten.
Selected exports may contain personal data: preview scope and preserve existing
private-ledger storage policy; no telemetry/public fixtures. Source text and model
output are untrusted. Scoped reads, strict schemas, size limits and hash checks.
No model-generated commands, credential grants or external URLs are executed.

## Implementation and review
- Added bounded source views and a `crew_setups` projection over existing project,
  organization, membership, Bot and task models; additive replay only.
- Added `crew-setup` CLI, existing MCP profiles and compact Studio handoff.
- Independent review found dedicated-principal reuse and split spreadsheet secret
  detection gaps. Both were fixed with regression tests before completion.
- Full-suite checking found eager CLI imports affected legacy command paths. Made
  the heavy setup dependency lazy; HTTP/CLI/MCP equivalence passed again.
- Actual subscription inference completed proposal, lead work and conditional
  memory creation after an initial reflection citation hold. Added explicit eligible
  evidence IDs without weakening validation. Anonymous receipts stay private.
- See docs/CREW_SETUP.md and docs/CREW_SETUP_ACCEPTANCE.md for workflow, evidence
  boundaries and final verification. Live service synchronization is not included.

## Final checks
Python: 1,670 tests, OK (8 skipped). JavaScript: 49 passed. Wheel built and assets
verified; diff check clean. Two transient failures in earlier full-suite runs are
recorded as undiagnosed test-reliability follow-ups in the acceptance report; final
isolated suite and focused repeats passed. This implementation is local, not a new
public release.
