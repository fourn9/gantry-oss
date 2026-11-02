# Bot experiential learning

Workflow: Addy Osmani agent-skills at 2686b620fc1fed2e8f60c704839c766b8594c6b6.
User-authorized extension of persistent customer-owned Bots; preserve prior work.

## Objective and boundary
Make experience change a Bot's explicit plan, then retain evidence about whether
that use helped. This is a bounded learning loop, not a claim of parity with any
commercial personal agent or of physical competence. No model training, paid API,
new cloud runtime, silent permission/profile change, or public release is required.
Each existing Bot (specialist or manager) uses its customer inference backend.
Core checks provenance and access; Bots choose methods, ordering and collaborators.

## Capability map / implementation order
1. experience-recall: reuse bot_memories and authorized organization sharing; rank
   older experience by task text, paths and requirement identity; show changes,
   contradictions, replacement links and reported utility separately. Bounded,
   paginated scan with explicit coverage; never call lexical matches semantic proof.
2. learning-contract: frozen planning packet → Bot applies/rechecks/rejects memories
   → ordered steps and consultations. Save citations and rationale. Closed-loop
   outcome reflection creates incremental conditional lessons and helpful/harmful/
   unknown feedback. Keep raw history; inferred preferences do not override policy.
3. learning-runtime: opt-in experience_learning in approved customer worker config.
   Before work, invoke the same Bot backend for a structured plan. After an actual
   report, Core queues a durable reflection; worker processes it before more work.
   Persist exact model inputs/receipts and retry idempotently after transport loss.
4. evaluation: anonymous multi-episode fixtures; compare no memory and remembered
   plans, changed premises, unknown information, revoked access, concurrency/replay.
   Real-model evidence is reported separately from deterministic contract tests.

## Contracts
Existing memory records remain authoritative. New indexed records hold frozen
plans and pending/completed reflections; no old history is rewritten. New APIs
are available through the existing CLI/HTTP/MCP Bot profile. Existing credentials
do not gain commands silently. Existing workers remain unchanged until opted in.

Memory includes source state/paths/hashes, pinned requirements, applicability,
strategy, exceptions, limitations and cited observations. Retrieval never grants
authority or marks design verification passed. Changed/contradicted/superseded
experience cannot be marked directly applicable without fresh reassessment.
Reported helpfulness is not causal proof or a calibrated probability of success.

Acceptance:
- [x] Old relevant memory is recalled outside the recent-30 window; unrelated
      text, inaccessible sources and stale applicability cannot silently win.
- [x] Plan explicitly records apply/recheck/reject, changed steps and unknowns.
- [x] Reported failure/success feeds a durable reflection and conditional lesson.
- [x] Next fresh Bot context includes that lesson and evidence-backed feedback.
- [x] Source revocation, changed requirement/environment and concurrent updates
      preserve access, stale-basis and replay invariants.
- [x] Interrupted inference/response retries do not duplicate plans or lessons.
- [x] Default workers, Mentor and existing data remain compatible.

Structure: gantry/bot_learning*.py, existing worker/Core integration,
tests/test_bot_learning*.py, docs/BOT_LEARNING.md. Python unittest integration
tests use the real Core and fixtures from test_bot_development. Keep small helpers
and separate retrieval from inference lifecycle. No new mandatory dependency.

Commands (project Python with optional CAD runtime):
  python -m unittest discover -s tests -p 'test_bot_learning*.py' -q
  python -m unittest discover -s tests -p 'test_*.py' -q
  node --test tests/test_requirements_web.mjs tests/test_review_web.mjs
  git diff --check

## Research applied
- Reflexion (2023), https://arxiv.org/abs/2303.11366: feedback to conditional
  text experience between trials; do not infer weight training.
- ACE (ICLR 2026), https://arxiv.org/abs/2510.04618: itemized incremental updates
  and explicit helpful/harmful feedback; preserve source details instead of
  rewriting one growing summary. This implementation is not an ACE reproduction.
- MemRL (2026), https://arxiv.org/abs/2601.03192: relevance and downstream utility
  are different signals. Use transparent reported counts here, not unvalidated
  Q-values or claimed reinforcement-learning convergence.
- LongMemEval (ICLR 2025), https://arxiv.org/abs/2410.10813: test updates, temporal
  validity, cross-session use and abstention, not just recall. Engineering behavior
  needs additional evaluation; this is not a LongMemEval benchmark score.
- A-MEM (NeurIPS 2025), https://arxiv.org/abs/2502.12110: linked structured memories
  motivate explicit replacement/contradiction references with access checks.

No source code from these projects is imported. Paper results do not establish
Gantry performance. Commercial product descriptions do not establish parity.

- Anthropic, Scaling Misuse Detection with Self-Assessment (2026-10-16),
  https://safeguards.anthropic.com/2026/self-assessment/: structured short
  post-action self-assessment motivates a separate reported signal. This research
  is about misuse detection, not experiential learning. Shared actor/assessor
  blind spots mean self-ratings cannot verify a design or lesson. Their trained,
  cache-reusing compute result does not predict our separate-call overhead.
  Keep assessment text private under the same access rules as task records.

## Validation record
Initial tests failed with missing APIs before implementation (TDD). Added explicit
recall, planning, result-linked reflection and opt-in customer runtime paths.
The context-hash transfer omission discovered by a regression test was repaired;
no missing context was treated as valid in the interim (it required recheck).
Anonymous real-model API smoke succeeded once; a later stricter test rejected an
invalid apply decision. The final helper-path retest stopped at provider HTTP 429
after planning; pending reflection and private journals were preserved. Full
real-model retest on the final source remains pending; no speedup claim.
Security review: authenticated original executor writes; owner may inspect;
source binding/reassignment/revocation checks; scoped memories; versioned inputs;
no authority changes from preferences; output bounds and safe idempotent retries.
No dependency, paid API, publisher telemetry or public deployment was added.

Final local checks (2026-11-03):
- Python discovery: 759 invocations, 758 passed, 1 existing skip; this count includes
  inherited regression cases. The new learning class adds 16 specific scenarios.
- Web regression: 9 passed.
- Fresh-tree wheel: 85 Gantry files; every packaged path and byte matched source.
- Schema snapshot updated; whitespace checks passed.
At that implementation checkpoint, no GitHub push/tag/release or live customer
configuration change had been made. Subsequent continuity work and runtime
evidence are recorded in [continuity validation](../docs/BOT_CONTINUITY_VALIDATION.md).
