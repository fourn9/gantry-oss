# Persistent residual issues

An issue connects an unresolved report item to later assignments, consultations,
verification and a responsible Bot's decision. It is separate from task status,
formal requirements and human adoption. Completing work never closes an issue.

## Normal path

1. A Bot saves `followups` in its task report, with a purpose, reason, evidence and
   explicit requirement/revision references. Missing formal links stay unlinked.
2. That Bot or its delegated manager uses `issue_open` to promote the saved item.
   Supply the source task, report attempt and follow-up ID, responsible Bot,
   affected saved files, completion conditions, a saved physical-evidence plan
   path and nonempty check IDs. The latter fields are **new Bot declarations**,
   not facts inferred from the old report. Scope and source authority are checked.
3. Assign work with `issue_ids`. Children and read-only consultations inherit the
   links. Handoff preserves them without changing issue ownership. Standing work
   inherits scoped issues from its explicitly watched tasks. The Bot selects work;
   the runtime only executes its recorded assignments.
4. Specialists edit and share changes. A manager integrates the selected versions
   and assigns a `verify` task on the exact candidate. The installed tool writes
   a fresh report; `tool_evidence` automatically publishes its bound results.
5. The responsible Bot or a delegated ancestor manager uses `issue_review` from
   an issue-linked, appropriately scoped task. It selects `working`, `verifying`,
   `deferred`, `reopened` or `resolved` with the current issue version, state,
   reason and saved evidence. This is the Bot's engineering judgment.

`resolved` requires a completed linked verification task in the current issue
cycle, its exact output state, passing frozen checks, current requirement links,
saved report bytes and matching tool/publication receipts. Core re-evaluates the
recorded measurements against the unchanged criteria. A successful exit, a
completed report, an old pass or a manually changed pass label is insufficient.

Evidence references use saved task, state, issue, action, decision or message IDs;
file paths and mutable change IDs are not evidence IDs. The issue stores a scoped
decision, never `formal_adoption` or `product_complete`.

## Reopen and reassess

The old resolution remains attached to its evaluated state. `get_bot_issue`
compares it with the requested state (default: the querying task's current state).
Changed inputs/evidence, requirement revisions, engineering premises or validation
maps return `needs_recheck`; they do not erase the old decision or grant a new pass.

Use `reopened` to require a fresh verification after the reopen event. If requirements
or acceptance changed, first select that saved state in a new assignment. Include
an explicit `reassessment` containing `verification_plan`, `check_ids` and current
`requirement_refs`. It cannot drop existing requirement IDs. The previous contract
is recorded in history, and fresh verification is required. This operation binds
already adopted requirements; it does not approve new normative requirements.

An authorized manager can maintain an issue after its responsible Bot is disabled.
That does not re-enable the Bot, grant it access, or automatically transfer ownership.

## Access and retrieval

The APIs are `open_bot_issue`, `review_bot_issue`, `get_bot_issue` and
`list_bot_issues`; action-loop names are `issue_open`, `issue_review`, `issue` and
`issues`. They use existing authenticated CLI/HTTP/MCP command paths. Existing
restricted credentials need explicit owner delegation of these commands; an
upgrade does not silently expand privileges.

Task context contains bounded summaries of linked and owned issues. Full details
remain available through reads; `issue` supports a JSON `pointer` and `offset`
for bounded runtime retrieval. Issue history is paginated in event order. Reads
respect source-state and requirement-zone access, not just project membership.

Two additive indexed collections hold issues and immutable lifecycle events.
Existing follow-up reports are preserved and point to promoted issues. Existing
records without issue links keep their previous behavior. Rebuild/export/replay
uses the existing event mechanism; no destructive migration is required. Partial
older resolution proofs conservatively require rechecking.

## Limits

This is not a new scheduler or a guarantee that the chosen test proves a design.
Installed tools and authenticated customer-runner reporting remain trusted inputs;
receipts are not remote hardware attestation. CAD, solver fidelity, undeclared
dependencies, physical safety, manufacturing readiness and formal adoption remain
separate. A resolved document/model inconsistency does not resolve the whole product.

There is no dedicated Studio issue editor in this change. API/MCP and the Bot
action loop are implemented; existing task reports remain available in Studio.
