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

## Follow-up: complete operational handoff

Acceptance: frozen physical plans carry explicit requirement revisions into reports/checkpoints;
missing/mismatched report requirement bindings cannot pass. CAD screening emits these bindings.
Mentor's review-work and inferred checks retain the explicit requirement subset. Crew child tasks,
consultations and checkpoints retain scope. Requirement changes hold delegated work; recorded
historical results remain available. A new state/assignment after reassessment can resume.
Validate using real local CAD screening plus synthetic report/identity fixtures; no paid inference,
commercial CAD connection, public release or customer ledger mutation is implied.

### Follow-up outcome (2026-11-02)

Completed operational handoff:
- Physical plans/reports/checkpoints retain pinned requirement references. Missing/mismatched
  report bindings remain unknown. Mentor-inferred checks can be explicitly mapped by frozen
  source_check provenance, without overwriting unrelated check definitions.
- Review-work preserves the change subset; inferred checks preserve their own explicit links.
  Pending/reviewed stale submissions hold until a reassessed checkpoint is submitted.
- Crew child assignments, consultations and checkpoints retain purpose. publish_physical uses
  Bot-scoped credentials and fenced checkpointing; no developer/admin capability is added.
  Its context update is restricted to engineering evidence, not goals/constraints/environment.
- Runner checks continuation before launch and while polling. Late results remain invalid for
  current acceptance. Result reuse and completed dependency checks include requirement identity.

Evidence:
- Full regression: 682 Python tests, 1 skipped, no failures, 85.610 seconds.
- Final focused suite after pending-review and Bot context hardening: 76 cases passed,
  including inherited regression cases (not 76 new independent scenarios).
- JS review/requirement rendering: 9 passed. Registered/documented schemas match; diff check clean.
- Real CadQuery STEP geometry screening → report → Adapter checkpoint → requirement coverage
  → Mentor context ran locally. Travel passed while absent load evidence stayed unverified.
- Real Python child process ran, then was cancelled by Runner after requirement revision changed;
  its result was retained invalid. Crew scoped adapter publication, stale hold, new assignment
  resume, consultation/child scope, and replay were exercised against the real Core.
- Review/model answers and non-geometric measurements were deterministic synthetic fixtures.
  No production LLM reasoning, commercial CAD license, physical strength certification, live
  customer project, browser deployment, or public release is claimed.

Reproduce with the project's optional CAD runtime installed:
  python -m unittest discover -s tests -p test_requirement_handoff.py -q
  python -m unittest discover -s tests -p 'test_*.py' -q
  node --test tests/test_requirements_web.mjs tests/test_review_web.mjs

## v3.3.0 release verification (2026-11-02)

- Final Python regression after all guards: 683 cases, one skipped, no failures,
  85.169 seconds. Nine JavaScript tests passed.
- Built wheel, installed it outside the checkout, verified version/imports and
  hardware CLI. The offline runtime security baseline reported no findings.
- Inspected package layout: only Gantry code/static assets and distribution metadata;
  no databases, project data, tokens, logs or private keys. Source privacy/credential
  pattern scan found only existing negative-test private-key header fixtures.
- pip-audit checked all 50 pinned optional CAD/runtime packages without skipped
  packages or known vulnerabilities. No dependency versions changed in this update.
- Public release metadata is v3.3.0. No hosted deployment or customer ledger mutation.
