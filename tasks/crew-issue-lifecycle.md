# Persistent Crew residual issues

Approved scope: preserve a residual issue across assignments, let responsible Bots
delegate, consult, verify and record a reasoned resolution. Task completion alone
must never resolve an issue. Core validates provenance and authority, not the
engineering choice. Existing human adoption remains separate.

Workflow reference: Addy Osmani agent-skills revision
`2686b620fc1fed2e8f60c704839c766b8594c6b6`; specification, planning, TDD,
incremental implementation, interface design, security and quality review.

## Contract and acceptance

- Promote an actual report follow-up into a stable project-local issue. Preserve
  the source report and requirement references; record the responsible Bot, files,
  completion conditions and required checks as explicit promotion declarations.
  Duplicate promotion returns the same issue without replacing its contract.
- Link real assignments and consultations to issues, inherit links into child
  work, and provide bounded context and paginated history through API and runtime.
- Only the responsible Bot or its delegated manager may change disposition.
  Every change requires the issue version, current task lease and a reason.
- Resolution requires a completed linked verification task, saved evidence and
  passing required checks on the exact files and requirement revisions under
  review. A Bot explicitly judges sufficiency; no automatic engineering verdict.
- Preserve the resolution at its evaluated state. Changed affected files,
  requirements or validation premises return `needs_recheck`, not a new pass.
  Reopening preserves history and requires fresh evidence to resolve again.
- Sharing, issue resolution and execution completion never imply formal adoption
  or whole-product/physical validation. Missing requirements remain explicit.
- Old tasks/reports continue to load. Add indexed record collections and additive
  fields; verify replay, permissions, stale writes and continuation.

## Execution

1. Failing contract/lifecycle tests; implement one API/runtime slice at a time.
2. Independent review of authority, evidence scope and stale-result handling.
3. In a private isolated copy, use distinct real monthly-model Bot contexts for
   an outstanding cross-discipline inconsistency. Save all actions, model receipts,
   changes, verification and issue decisions. Mechanical orchestration is setup,
   not engineering reasoning. No paid API or physical actuation.
4. Run relevant regressions, full checks, package smoke and document evidence.

## Non-goals

No new scheduler, formal requirement approval model, automatic physical proof,
commercial deployment or speedup claim. Private project artifacts and model
journals never enter public source. Original ledgers and files stay unchanged.

## Progress

- [x] Inspect existing continuation, follow-ups, hierarchy and evidence adapters.
- [x] Implement and test persistent issue lifecycle.
- [x] Verify real multi-Bot continuation through resolution.
- [x] Review, regression checks and handoff documentation.

## Delivered

See [the usage and migration contract](../docs/CREW_ISSUES.md).
Added four authenticated APIs and action-loop operations; stable promotion,
versioned disposition, explicit reassessment, evidence-bound resolution and
state-relative applicability. Child work, consultation, executor handoff and
watched standing work retain issue links. Task context is bounded; detailed
records and event-ordered history are retrievable. No Studio issue editor added.

Independent adversarial review covered source ownership, cross-zone disclosure,
read-only tasks, stale/revoked authority, verification provenance, changed
acceptance, history, context bounds and legacy null/partial records. Concrete
findings were fixed. A cross-zone reproduction now rejects direct access and
omits the restricted issue from listing and unrelated task context.

The runtime now also reconciles a prepared but uncommitted claim after a process
restart. It changes the request's runtime/key only if the authoritative task is
still at the exact pending version/attempt; uncertain committed work remains held.

## Verification, 2026-11-08

- Whole Python suite at the implementation checkpoint: 1,803 run, 14 skipped,
  zero failures. The later source-zone regression and final hardening were covered
  by the final relevant suite: 231 passed, including 12 issue-specific tests.
- JavaScript suite: 71 passed.
- Final wheel built, installed in a clean local virtual environment; Crew CLI and
  all four issue API/action schemas available.
- Isolated private experiment: four distinct real monthly-model Bot contexts,
  26 responses and 357.210 seconds, completed a scoped cross-discipline correction
  through actual edits, integration, installed validation and explicit resolution.
- A new process resumed that ledger; two actual Bot contexts reopened, reran
  verification and resolved it using new evidence: eight responses, 95.435 seconds.
- Setup/import, role permissions, acceptance and validator were prepared by the
  operator. Subsequent role actions were model responses, not scripted reasoning.
  Invalid references were rejected and corrected by the models. A diagnostic
  legacy-proof compatibility error was repaired before the successful resumed run.
- Final implementation revalidated the saved resolution proof; ledger hash
  verification and replay matched. Original project file inventories were unchanged.

These timings exclude preparation, implementation and suite runtime. This was a
functional experiment, not a controlled speed comparison or physical certification.
Original project data, credentials, scripts and model journals remain outside this
public source checkout. The final development state remains unadopted and its
whole-product verification remains unverified.
