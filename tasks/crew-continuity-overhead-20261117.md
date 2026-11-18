# Crew continuity correctness and measured overhead

User-authorized scope: preserve truthful evidence, isolate reflection failure,
reduce trace-proven repeat work, then compare independent monthly-model trials.
Workflow: Addy Osmani agent-skills revision 2686b620fc1fed2e8f60c704839c766b8594c6b6;
using-agent-skills, planning, specification, TDD, performance optimization.

## Capability slices and acceptance (before implementation)
1. Reflection: actual file evidence remains bound to saved state hashes. Missing or
   planned file references have an explicit non-evidence representation. No fake
   files, silent evidence deletion, fabricated pass, or relaxed source access.
2. Experiment supervisor: reflection-only hold remains durable and visible but
   cannot abort unrelated development; task/provider failures remain explicit.
3. Context continuity: use existing run receipts to locate avoidable refetch,
   replanning and resume round trips. Reuse only version-checked observations;
   retain fresh authorization, dependencies, verification and reviewer access.
4. Measurement: freeze source, case, endpoint, limits, model and memory before runs.
   Baseline b87787f already contains the corrected uniform ancestry scorer.
   Both arms use the same private unresolved case and historical memory; no prior
   solution/output or other arm's records enter model context. At least two fresh
   trials per arm; interleaved A/B/B/A. Keep failed/time-limited runs in denominator.
   Engineering completion requires actual delegated edits, peer review/integration,
   frozen checks with matching inputs and valid ledger. Reflection completion is
   separately reported; no successful learning claim with unresolved reflections.
   Primary successful completion wall time includes setup, workers and final audit.
   Also report prior strict all-pipeline acceptance and pending reflections.
5. All parent preparation/fix/recovery is separately recorded. Model request time
   includes provider/network latency, not pure thought. Parallel times are unions
   and exclusive partitions, not added as elapsed time. Sleep/clock gaps unknown
   unless measured. No success speed ratio from early failures.

## Boundaries
Private fixtures and outputs stay outside source. No paid fallback, deployment,
physical operation, purchase or formal adoption. Parent can fix infrastructure
before freezing; any mid-run repair invalidates matched comparison and is retained.

## Status
- [ ] Reproduction tests and fixes
- [ ] Actual trace audit and bounded continuity improvement
- [ ] Full tests and source freeze
- [ ] Independent repeated real-model A/B comparison
- [ ] Results, limitations, privacy review and GitHub update
