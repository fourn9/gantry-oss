# Continue from specialist changes

Crew Bots can now integrate shared candidates **during** an action loop, inspect
the exact combined files, run installed tools, save their evidence, and then
continue or delegate verification. This extends the existing state/assignment
model; it does not introduce a scheduler that chooses engineering work.

## Normal path

1. Specialists share candidate changes and report their evidence and unknowns.
2. An integration-authorized Bot inspects those records, then emits `integrate`
   with the pinned input state, exact change IDs/versions and a summary.
3. Core checks scope, versions, conflicts and unchanged assignment premises. The
   worker restores the returned state, verifies its manifest, and retains the old
   workspace. The same task remains running.
4. The Bot reads/edits the combined files and invokes an owner-installed `tool`,
   or returns a waiting report assigning verification against the returned state.
5. Tool output, file checkpoints, declared checks and structured residual work
   return to the Bot. It chooses the next action and reports the observed scope.

The new API is `integrate_bot_task`; the Bot profile also exposes
`get_bot_requirements` and `propose_bot_requirements`. Existing explicitly
restricted principals need those commands delegated by their owner. Upgrading
does not expand an existing credential's allowed commands.

Integration requires an unedited task. Preserve earlier saved edits in a separate
change and assign integration from a chosen baseline. Conflicting candidates and
unsaved local changes are not overwritten. Changes to requirements, constraints
or other assignment premises require a separately selected state/new assignment;
integration cannot silently change an active task's acceptance conditions.
Engineering evidence metadata may advance without changing those premises.

## Tool evidence without manual transcription

Add an optional mapping to the same versioned runtime configuration used by
`gantry-crew bot-worker`. It maps an existing installed tool to its saved plan:

```json
{
  "agent_loop": true,
  "local_tools": {
    "verify_assembly": {
      "argv": ["/absolute/path/to/python", "-B", "checks/assembly.py"],
      "timeout_seconds": 120
    }
  },
  "tool_evidence": {
    "verify_assembly": {"plan_path": "checks/physical-plan.json"}
  }
}
```

This is a configuration fragment, not a complete worker configuration. Use the
existing [runtime setup](CREW_ORGANIZATION.md#enable-an-action-loop-worker) to select
the sandbox/runtime roots and approve the resulting environment manifest. Changing
the mapping changes that manifest. Existing configurations without it retain their
previous manifest hash.

The tool must write the common measurement report described by the existing
[hardware adapter](HARDWARE-ADAPTER.md). The worker checkpoints changed files and
publishes the frozen plan's checks automatically. Receipts bind the tool action,
input state, actual exit code, output artifact, report and input hashes, evaluator,
environment, conditions and requirement revisions.

- Exit zero alone is not a check pass. Thresholds and all declared provenance must
  match. Missing, malformed, stale or mismatched reports remain unknown.
- A failed tool or an old report left unchanged cannot become a fresh pass.
  Automatic capture requires a newly created/rewritten report. A tool preserving
  modification times may conservatively yield unknown; it must publish a fresh
  report. This capture check assumes the installed tool is trusted, not malicious.
- Publication errors return the actual tool result plus the error to the Bot.
  An uncertain publication is reconciled before retry; the tool is not blindly
  re-run. Uncertain external tool effects still require explicit recovery.
- `publish_physical` remains available for explicit report import. Neither route
  certifies a physical model, provides a CAD/CAE solver, or formally adopts a design.

## Requirement discovery and proposed links

`requirements` pages current adopted requirement definitions in the project's
zone. These are available definitions, not an assertion that every requirement
applies to the project. The Bot can emit `propose_requirements` with existing
requirement/revision IDs, a rationale and exact saved source path/hash references.

This creates a separate shared metadata candidate. It does **not** change the
current task, invent normative requirements, or mark a requirement fulfilled.
A delegated manager can inspect the candidate and explicitly assign subsequent
work from that state with the selected requirement references. If there is no
normative definition, the gap remains unlinked until the existing requirement
approval process creates one. Contradictory pinned revisions are rejected.

Onboarding proposals can carry the same `requirement_links`. Studio shows their
source and rationale before the owner opens the first work. Completion rechecks
source hashes and requirement revisions and retains the links in the imported
state. Sharing, executing, satisfying checks and adopting remain separate axes.

## Structured residual work

An optional report `followups` array records:

| Field | Meaning |
| --- | --- |
| `id`, `summary`, `reason` | Stable report-local item and explicit Bot rationale |
| `evidence`, `requirement_refs` | Existing project records and pinned assigned requirements |
| `disposition` | Bot-selected `fix`, `verify`, `consult` or `defer` |
| `assignment_index` | For fix/verify: index of a real assignment in this report |
| `message_id` | For consult: an actual consultation started by this task |

The stored item receives its actual child task ID. Existing hierarchy and scope
checks still apply to that assignment. Deferred work is retained without pretending
it has been dispatched. Child completion means `work_completed_review_required`,
not product completion. Managers decide what the result means.

Task context includes residuals from its assignment descendants with source task,
attempt and state. It is bounded to 100 tasks, 100 recent reports per task and
500 items, with `followups_truncated` when incomplete. Fetch the named child task
or saved report history for details beyond that context; old reports are retained.
Free-text unknowns remain visible, but are not automatically classified or closed.

## Failure and recovery

Correctable final-report errors (for example, waiting without a real assignment
or consultation) are returned to the same Bot while its authority/basis is valid.
The Bot can repair its report or choose another permitted action. These rejected
attempts stay in history. Changed authority, changed premises and unknown outcomes
are not treated as ordinary model correction prompts.

The worker saves request keys before effects and reconciles a final-report receipt
before starting another inference. A lost acknowledgement after successful finish
does not duplicate the report, memory, child tasks or tool execution. Use the
existing worker `--recover-job TASK_ID` path after confirming the earlier worker
has stopped. Intermediate integration similarly preserves the predecessor during
an interrupted workspace switch.

The monthly Codex adapter disables **native Codex tools** while explicitly
permitting schema-defined Gantry JSON actions. The worker executes those actions
and returns their real results. This removes ambiguous instructions without
granting unrestricted shell or file access.

## Verification and limits

Regression tests cover exact-state integration, delegated verification, conflicting
and stale inputs, dirty workspaces, interrupted switches, report correction,
uncertain acknowledgements, scope revocation, evidence freshness, requirement
mapping, hierarchy residuals and ledger replay. See the
[implementation record](../tasks/crew-development-continuation.md).

A private-source smoke exercise used the actual subscription model for lead
continuation and actual sandboxed tools. Previously saved specialist candidates
were imported by a scripted fixture; this was not a new autonomous multi-role
design exercise. One run retained a tool exception as unknown/deferred. After
correcting only the diagnostic wrapper's path, the Bot integrated, regenerated,
checked, corrected a rejected report and finished its assigned static stage.
Physical unknowns and semantic document inconsistencies remained explicit.
These observations establish execution paths, not speedup or manufacturing readiness.

For residual work across multiple tasks, see [persistent issues](CREW_ISSUES.md).
