# Experience learning: measured overhead

Workflow: Addy Osmani agent-skills, revision
`2686b620fc1fed2e8f60c704839c766b8594c6b6`; performance optimization,
test-driven development, incremental implementation, interface and security review.

## Evidence and objective

The private, preserved eight-run transfer study had four successes per arm and
one edit per successful task. Experience did not avoid a failed attempt. Total
time was 291.97 s without experience and 360.26 s with experience. Three additional
`experience_use` model turns consumed 39.06 s. Planning and reflection also grew.
These are observed timings, not a causal attribution of the entire time gap.
Both arms used Gantry and both ran planning/reflection. The tasks exposed the rules
in their acceptance materials, so they cannot establish a learning advantage.

Current planning already receives file previews. Do not describe that existing
feature as a new improvement. Preserve planning, reflection, acceptance checks,
evidence provenance, and authority/version enforcement.

## Change and acceptance criteria

Allow a Bot to include explicit experience/action links in its existing completion
report. Save those links and the report atomically, using the same checks as the
standalone `record_bot_learning_use` API. Prefer this route in the action guide.
The standalone API and old reports remain valid. No inferred claim of memory use.

- Same-attempt actions, planned non-rejected memories, current access and fence
  are required; unknown/foreign evidence cannot finish the task.
- An invalid batch leaves neither partial links nor a completed task.
- Response loss/recovery does not duplicate links, reports or model calls.
- Reflection receives the exact links; sharing/completion is not formal adoption.
- The worker can edit/read, finish with links, and reflect without an extra
  bookkeeping inference turn.
- Fresh controlled subscription-model comparison includes all calls, recording,
  verification, reflection, timeouts and failures. Keep original inputs/verifier,
  model and effort fixed and isolate each trial. Report speed and correctness
  separately; do not use historical timings as the fresh control arm.

## Validation plan

1. Preserve and aggregate historical phase/action/token measurements privately.
2. Write real-Core regression tests and confirm failure before implementation.
3. Implement the additive report contract and run targeted tests.
4. Freeze original and changed code, predeclare counterbalanced live trials using
   the existing monthly Codex login (no API-key fallback).
5. Review integrity/privacy and run the relevant broader regression suite.
6. Document measured results and remaining limits, without private case content.

## Implementation verification

- A new report-with-receipts test first failed because the field was unsupported.
- Review then caught disclosure through shared reports/raw finish receipts. A
  reproducing privacy test failed before fixing the read boundary. Shared reports
  now omit receipts; executor/owner-only records and reflection retain them.
- Reflection's bounded receipt page was increased to 40, matching the maximum
  report batch. Older history is still explicitly paginated.
- Seven added regression cases cover atomicity, evidence/fence constraints,
  private views, full-batch reflection, empty/null compatibility, and an edit plus
  checkpoint with lost completion acknowledgement and no extra inference turn.
- Targeted learning-completion suite: 53 invocations including inherited tests;
  iterative-runtime suite: 86. Full Python suite: 1,409 invocations, 1,401 passes
  and 8 pre-existing environment-dependent skips (162.132 s).
- Independent read-only review approved the corrected implementation. No new
  dependency, authority expansion, ledger migration or paid API was introduced.
- Initial performance prototype was stopped after its active trial completed,
  due to the privacy defect. Its three completed outcomes and five unstarted
  slots remain in private records. Corrected code receives a separate frozen,
  counterbalanced comparison; do not pool the prototype outcomes with it.

## Corrected-snapshot live result

Four fresh pairs using the same imported experience: both paths accepted 4/4.
Mean full-session time 112.50 s → 99.07 s (11.9% lower); model calls 24 → 20;
input tokens 445,095 → 359,654 (19.2% lower). Every pair was faster. Actual
edit/tool links and reflection were retained in all eight verified ledgers.
Setup was measured separately (0.134/0.132 s summed per variant).

This measures receipt overhead, not a demonstrated advantage of experience over
no experience, autonomous lesson acquisition, or robot-development speed. Provider
latency/cache and limited fixed code checks constrain interpretation. Full method
and limitations: [validation](../docs/BOT_LEARNING_EFFICIENCY_VALIDATION.md).
