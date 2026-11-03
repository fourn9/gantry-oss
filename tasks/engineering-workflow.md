# Engineering workflow, outside Bot development

Reference: Addy Osmani agent-skills revision
`2686b620fc1fed2e8f60c704839c766b8594c6b6`. Apply specification,
incremental implementation, TDD, API design, observability, security and review.
This isolated branch preserves unrelated tasks and private projects.

## Contract and order

1. Complete a saved-file / CadQuery roundtrip using existing immutable state APIs.
   Freeze publication requests before dispatch; recover a lost acknowledgement
   without replaying edits, changing the acceptance plan, or overwriting a branch.
2. Extend existing engineering components with explicit native references and
   version-bound dependencies. Preserve source files. Report downstream checks
   requiring reassessment, including when the changed component itself is current.
3. Run a locally authorized physical evaluator against frozen inputs and plan,
   preserve failures/logs, compare results, then publish through the same path.
   Static CAD is the real included evaluator; other physics uses customer tools.
4. Give Mentor a compact engineering dossier: dependencies, changed inputs,
   missing checks, frozen criteria and results. Keep reasoning, review, permission
   and formal adoption separate. Reuse the existing review/correction path.
5. Measure from the first slice: operation, phase, candidate/state, attempt and
   parent, start/pause/resume/end. Distinguish elapsed/overlapping measured time,
   failures, unfinished spans, and unobserved intervals. No retrospective guesses.
6. Ship a single documented CLI path, diagnostics, recovery instructions and
   repeatable anonymous integration tests. Qualify actual runtime vs fixtures.

## Acceptance

- Lost checkpoint acknowledgement recovers the identical state; another change
  head or a reused key with different intent is rejected. Credentials excluded.
- CAD -> harness -> control dependencies retain native IDs and provenance;
  changed geometry invalidates downstream applicability, never historical evidence.
- Frozen plan and interpreter/recipe fingerprint are checked before local launch.
  Input mutation, absent results, failed process and ambiguous interruption cannot
  become a pass; unknown execution is never blindly launched again.
- Published results and impact are visible in real authenticated Mentor context;
  unmet dependencies prevent technical OK. No automatic formal adoption.
- Duration summaries do not add parallel intervals as total elapsed time; restart
  or interrupted spans explicitly retain missing timing and process outcomes.
- End-to-end real CadQuery edit/readback/screen/save/recover/restore; all unit and
  integration tests, CLI packaging and security review. Native commercial products
  remain unverified without licensed environments; no new paid inference.

## Progress

- [x] 1. Durable publication and initial instrumentation
- [x] 2. Cross-tool dependency applicability
- [x] 3. Frozen evaluator execution and result collection
- [x] 4. Engineering review dossier and existing correction path
- [x] 5. Timing summaries and interruption handling
- [x] 6. CLI, doctor, real runtime evidence, docs and final checks

Verification is recorded in `docs/ENGINEERING-WORKFLOW-VERIFICATION.md`.
The scope is implemented and tested locally; licensed native qualification, actual
non-geometric solvers, Mentor quality and development-speed comparisons remain
explicitly unverified. No public release or main-branch integration is implied.

## Review boundaries

No new hosted executor, paid provider, credential forwarding, auto-adoption or
native-vendor qualification. All new writes use existing Core authorization.
Local recipes are explicitly operator-authorized, not a safe arbitrary-code MCP
capability. Requests are frozen before dispatch; uncertain launches require manual
reconciliation and cannot pass. Native IDs and dependencies remain declarations.
Bot organization/reasoning files and the main worktree are untouched.
