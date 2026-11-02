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
tasks before claim and at existing fenced action/check boundaries. A running external process
is not forcibly stopped by a requirement edit. Reassess, checkpoint the new requirement references
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
