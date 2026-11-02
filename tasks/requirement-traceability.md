# Requirement traceability

Reference workflow: Addy Osmani agent-skills, revision 2686b620fc1fed2e8f60c704839c766b8594c6b6; specification, TDD, interface design, security and review.

Reuse managed requirement revisions, immutable development states, engineering checks,
changes, Mentor contracts and Crew tasks. No second requirement database or destructive migration.
Optional pinned requirement_refs identify the adopted requirement revision; legacy free text
remains unlinked. Requirement data.verification_checks fixes required check IDs. Checks bind
requirement_refs and existing immutable inputs/evidence. Satisfaction is a derived declaration,
not certification, task completion or adoption. Missing plans/bindings never imply success.
Current requirement changes/retractions make previous evidence needs_review; historical pinned
assessment stays available. Work may explicitly select a subset (including empty exploration).
Core checks reference integrity; Bots retain decisions about engineering priorities.

Acceptance: partial pass, absent evidence, stale files and requirement revision changes cannot
be reported as current satisfaction; legacy data and replay preserved; unauthorized references
rejected; API, Mentor and Crew expose gaps; UI escapes content and shows explicit unlinked work.
Tests use anonymous synthetic fixtures, not customer CAD or physical validation.

## Implementation and validation

Implemented additive requirement_refs on states, changes, Mentor proposals and Crew tasks;
required check IDs live on managed requirement revisions. API/UI expose per-requirement gaps,
pinned/current assessments and indexed bounded work-purpose links. Mentor execution checks
and Crew fenced checks hold changed requirement baselines. Review fingerprints include current
requirement revisions. No database migration, inference invocation or private data import.

Validation on 2026-11-02:
- Full Python regression: 606 tests, 1 skipped, no failures (80.604 s).
- Final targeted requirement tests after adding scoped-access coverage and avoiding repeated
  lineage validation: 9 passed. Covers adopted-lineage integrity, partial pass, stale files,
  changed requirements, legacy integration/replay, exploration, Mentor conditions and Crew
  context/fenced execution/access control.
- JavaScript review + requirement rendering: 9 passed, including escaping and historical/current distinction.
- git diff --check passed. Static review checked reference integrity, adoption separation,
  immutable history, scoped access and bounded work queries.

Tests use synthetic declarations and saved files; no real robot or CAD measurement was certified.
The new UI component was checked by rendering tests, not a production browser deployment.
Feature is on feature/requirement-traceability; no public release or live ledger migration performed.
