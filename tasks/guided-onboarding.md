# Guided, agent-assisted project onboarding

Approved in the side conversation on 2026-11-03. Isolated from concurrent main
thread changes at 94e49e2. Follow Addy Osmani agent-skills reviewed revision
2686b620fc1fed2e8f60c704839c766b8594c6b6: specification, planning, incremental
implementation, TDD, interface design, frontend, browser testing and security.

## Acceptance contract

- Choose a local folder and review an explicit file scope before upload. Reuse
  credential/path/size policy. No project execution, hidden upload or paid inference.
- Save a resumable onboarding draft with immutable snapshot, owner, authorized
  collaborators, observed file facts, inferred grouping and explicit unknowns.
- Offer a bounded context and structured proposal API/MCP for the customer's
  agent. Validate exact source hashes and keep inference distinct from approval.
- Ask only relevant ambiguous associations; allow unknown/defer. Save answers and
  human corrections, preserve them across new proposals and delta re-inspection;
  changed evidence invalidates applicability rather than erasing past answers.
- Let the user correct components and choose first work, without requiring a
  formal requirements document, organization or agent roster.
- Commit through existing Studio import/continuity, never implicitly share,
  verify or adopt. Subsequent sync/share/independent continuation uses existing APIs.
- Source-service path uses saved authorized snapshots, not arbitrary URL fetching.
  Missing connectors/native parsing have explicit limitations.
- English compact UI, progress/error/retry/resume, accessible controls and narrow
  layout. Artifact views remain the destination, not a dashboard.

## Slices

- [x] Persistent discovery, evidence-bound proposals/answers, completion.
- [x] Local preview/import and agent MCP access.
- [x] Studio guided entry, review/corrections and first work.
- [x] Security, interruption, stale evidence, two-identity continuation tests.
- [x] Browser verification and integration with current main checkout.

## Threat boundaries

Files, filenames and agent output are untrusted data. No eval, shell commands or
automatic URL fetching. Schema/path/content limits before storage; scoped draft
ACL and zone checks on every command. Agent proposals cannot change permissions,
write scope, requirements approval or verification. Saved files/answers are private
ledger data, not telemetry. Archive/retention uses the ledger's existing policy;
do not imply a reversible upload or erasure of append-only history.

## UI contract

Bring project → select and review saved scope → inspect findings and resolve only
important questions → Open first work. Quiet existing Studio styles. Optional
agent handoff is explicit; deterministic grouping is never labelled model reasoning.

## Completion evidence

Integrated into the main implementation checkout on top of 321f779, preserving
its team/cloud/streaming work. Full integrated Python run: 1,295 tests, no failures,
8 skips. Final focused onboarding run after the stable-question instruction fix:
17 tests pass; Studio/onboarding JavaScript: 25 pass. Actual browser and loopback
HTTP handoff evidence is described in docs/GUIDED_ONBOARDING_VERIFICATION.md.
The separate preview server uses the integrated implementation. Existing main
thread server processes were not restarted.
