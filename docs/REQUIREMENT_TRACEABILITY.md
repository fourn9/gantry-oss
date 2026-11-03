# Requirements across development

Ledger remains the source of versioned requirements and history. Crew Bots decide what
work to do; optional Mentor reviews see the same coverage. No separate requirement store,
model call, paid connection, or physical certification is introduced.

## Define and link

Create/update a managed `requirement` through the existing propose → submit → review → commit
workflow. Its data may include:

```json
{"description":"Reach the target under the specified load",
 "verification_checks":["travel","load"]}
```

The check IDs form the verification plan for that immutable requirement revision.
Capture the committed entry's `id` and `revision_id`. Add to `context` in
`initialize_continuity` or a new `checkpoint_change`:

```json
{"requirement_refs":[{"requirement_id":"motion","revision_id":"rev_FROM_LEDGER"}]}
```

This is a context fragment: retain the existing required requirements, constraints,
decisions, open_questions and environment fields. Only adopted requirement revisions or
ancestors of an adopted revision may be pinned; drafts are not normative requirements.
Old requirements without a verification plan remain valid but unverified.

In `context.environment.engineering.checks`, attach the same `requirement_refs` to each
applicable check. Keep the existing component, scope, required, status, input path/hash and
evidence path/hash fields. Every referenced requirement must belong to the state. Missing
bindings do not count as a pass. Failed and unverified checkpoints can still be shared.
Required checks cannot be removed by setting a check's `required` flag false; the requirement
revision's plan controls coverage. `not_applicable` does not fulfill a planned check: revise
and approve the requirement plan if that scope truly no longer applies.

## Work purpose and execution

`begin_change`, `mentor_propose` (top-level argument) and `assign_bot_task` accept optional
`requirement_refs`. Omission inherits the input state's references. An explicit subset narrows
the work's purpose; `[]` explicitly permits unlinked exploratory work. Crew child assignments
use the same contract. Bot-created change sets preserve their task's selection.
These are purpose links, not evidence that a task fulfills every selected requirement.

Mentor context, Crew task context and `get_development_state` return `requirement_coverage`:

- `met`: all checks in the pinned plan declare pass with applicable file/evidence bindings.
- `unmet`: at least one applicable required check fails.
- `unverified`: missing plan, missing linked check, stale inputs/evidence, or inconclusive result.
- `needs_review`: the adopted requirement advanced or was retracted. `pinned_status` preserves
  the assessment against the earlier requirement; historical evidence is not erased.

Coverage includes check-level gaps and work/purpose links. The work overview is bounded at
100 records per kind using the session index; `work_truncated` marks partial results. Use
existing session work/task APIs for the full history. The overall requirement scope is only
what the state explicitly lists; absence of a requirement is never proof of product completeness.
Free-text `context.requirements` remains explicitly unlinked, not silently matched by an LLM.

Mentor execution checks hold stale requirement contracts; results arriving after a requirement
change remain recorded but invalid for current execution acceptance. Crew checks hold stale
tasks before claim and at existing fenced action/check boundaries. Unsupervised external processes are not stopped by a requirement edit; Gantry Runner uses the
continuation checks described below. Reassess, checkpoint the new requirement references
and assign new work. Existing review fingerprints also include current requirement revisions.

The State tab shows coverage, pinned/current versions, missing checks and work purpose.
Task completion, state verification, requirement coverage and formal human adoption remain
separate. Partial-stage reviews do not certify every product requirement.

## API and compatibility

Use `gantry --token-file TOKEN_FILE call get_development_state --input state.json`, where
state.json contains `{"state_id":"devstate_FROM_LEDGER"}`. CLI, REST and MCP share the same
contracts; writes require the existing idempotency key. No new token is needed.

Old events are unchanged. Optional fields require no destructive migration and replay remains
supported. Old tasks without links stay unlinked. Existing immutable states can acquire links
only through a new checkpoint. Scoped access must cover both pinned and current requirement
zones. Public examples/tests use synthetic files only.

## Limits

Evidence and declared statuses are provided by authorized users/adapters/agents. Hash checks
establish file identity, not whether a test actually proves the engineering claim. Gantry does
not automatically extract all requirements, judge test adequacy, discover physical dependencies,
or prove hardware safety. Changing a requirement reference on a check is a new submitted
assertion, not automatic validation of the old result against a new requirement.

## Complete Adapter → Mentor / Crew path

A physical plan check accepts `requirement_refs` in addition to its existing fields. Declare
these links when saving the plan in the baseline. `hardware screen` copies the exact references
into its measurement report; external solvers must emit that same `requirement_refs` array.
`hardware publish` preserves them in engineering checks and computes requirement coverage.
A report without matching references is retained as unknown, not credited against the linked
requirement. Legacy unlinked plans remain supported. Plan bytes still cannot be changed during
publication. No requirement link is guessed from a matching name or check ID.

Mentor's inferred engineering checks may include requirement_refs from the reviewed state.
Applying the proposal preserves them but initializes the checks as unverified. Review-work
proposals inherit the change's requirement subset; optional top-level requirement_refs may
narrow it. Exploratory changes stay exploratory. Crew consultations and omitted child-task
references inherit the originating task's subset. Explicit child scope remains a Bot decision
within its pinned input state.

Crew's action loop exposes `publish_physical` with `{"plan_path":"physical-plan.json"}`.
It calls the same physical adapter through the Bot's existing fenced `checkpoint_bot_task`
permission, without using a developer/admin credential. Reports must already be in the task's
workspace, within its edit scope; the plan must already be captured in the task's current state.
The adapter captures artifacts and evaluates conditions before Core rechecks the task fence and
scope at checkpoint. Bot checkpoint context may contain updated engineering evidence but may
not replace/remove the state's requirement scope. Use a reassessed state and a new assignment
for changed requirements. The local physical screening command is static geometry screening;
strength/thermal/test-rig measurements still come from explicitly identified external evaluators.

Requirement changes also affect existing completed dependencies and result-reuse matching.
Mentor Runner checks continuation before process launch and on its normal polling loop, requesting
cancellation on stale requirements. This is cooperative process supervision, not an instantaneous
physical emergency stop. Late results remain recorded but are not valid current acceptance.
Crew checks before claims/actions/checkpoints/completion hold stale tasks. Cancel/reassess the
old assignment, create a checkpoint with the new references and review plan, then assign new work.
No result is automatically rebound to the new requirement. No paid model is required for this
handoff; the customer's selected agent still supplies the engineering decisions.

To fulfill a Mentor-inferred check, freeze the physical plan with the same check ID, scope,
components, required flag and requirement references, plus
`source_check: {"submission_id":"review_ID","state_id":"devstate_ID"}` from the inferred
check. The plan must cover its existing input paths. The Adapter then preserves source review
and state provenance while recording the measured result. Without this explicit correspondence
it refuses to overwrite the inferred check. Threshold adequacy remains an engineering review
responsibility; correspondence alone is not certification.

## From coverage to the next change

The [design assessment](DESIGN_CHANGE_LOOP.md) compares the assignment baseline to
its latest state and includes requirement transitions, cumulative edits and affected
checks. It travels through normal Crew/optional Mentor context and saved Bot reports.
Changed causal inputs omitted by a dependency-selected check keep its assessment
unknown even if that check still declares pass. Read the assessment's coverage when
using change-impact context; the standalone state view reports only its directly
bound engineering checks.
