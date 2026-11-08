# Bounded Bot working context

Workflow: Addy Osmani agent-skills revision `2686b620fc1fed2e8f60c704839c766b8594c6b6`, debugging, TDD, context engineering and security review. User authorized repairing runtime gaps during real Bot cooperation.

Observed failure: file previews, recalled records and duplicated team/report metadata together exceeded the monthly provider's 500 KB input contract before inference started. Each part had partial limits, but their combination did not.

Acceptance:
- Bound file previews by encoded JSON bytes and selectively retain optional collections; keep their full authorized source in a content-addressed context snapshot.
- Expose omitted counts, original indexes, hashes and retrieval instructions. Missing preview data must not imply absent evidence or satisfied requirements.
- Preserve current task identity, completion, scopes, dependencies and requirement references; preserve project goal/acceptance, active messages and current known limitations.
- Existing scoped context/inspect/read operations remain the retrieval path. Live context may advance; require ID/hash checking rather than assuming a prior array index remains current.
- Do not rewrite any input already submitted to inference. If essential contracts alone exceed the working-context allowance, fail explicitly rather than truncate authority or requirements.
- Verify anonymous large contexts, Unicode/escaped-file accounting, immutable source snapshots and on-demand retrieval, then focused Bot/Crew regression tests.

Scope: context construction, anonymous tests and no private project content in public source. No engineering judgments or acceptance values are changed.

Validation:
- Four new regressions failed before implementation and pass afterward: oversized optional context, encoded file-preview size, immutable source snapshot, and fail-closed handling of an oversized essential contract.
- 125 focused Bot/Crew/context tests pass in 12.290 seconds, including authorized retrieval and cross-project refusal in the existing action-guidance suite.
- Active consultations, issues, children, followups, candidate changes and messages are not trimmed. Only recall/team/report/action/decision previews are bounded.
- Immutable context snapshots add local journal storage per distinct authorized context; they are not uploaded into public source or silently deleted. Native workspace files remain intact. This is bounded model input, not a claim that source evidence disappeared or that context retrieval is free.

Further observed growth: completed child report histories exceeded the context bound at a manager's next attempt. Completed children now retain contracts/output states and all unverified items, with exact latest summary/rationale previews and immutable full-report references; active children are untouched. Anonymous tests reproduce oversized history and verify source preservation.113related tests passed. No model answer or acceptance was synthesized by the reduction.

Aggregate-budget correction acceptance: individually bounded file and historical observation previews must yield to the overall input limit before a task is held. Remove only optional previews, retaining source inventories, retrieval references and explicit omission counts. Preserve current contracts, requirements, active questions, issues, child contracts and all reported unknowns byte-for-byte. Keep newest historical observations when older ones must be omitted. Oversized essential contracts must still fail closed. Test combined optional/essential growth before implementation; preserve already-submitted model inputs.
