# Paired Bot experience evaluation

Approved direction: test whether saved experience changes work order, repeated
mistakes, success and elapsed time before introducing automatic lesson promotion.
Follow Addy Osmani agent-skills revision 2686b620fc1fed2e8f60c704839c766b8594c6b6
(specification, TDD, incremental implementation, security and independent review).

## Scope

An opt-in local Crew CLI runs experience-withheld and experience-supplied arms
using the existing Core, BotWorker and iterative actions. Each arm starts in an
independent ledger/workspace/context. Both use planning and reflection; only prior
experience availability differs. Freeze selected native file bytes, goal, scope,
acceptance, evaluator source, Python environment, model/effort and run limits.
An operator-authored case is executable trusted configuration, not an incoming
document. The initial adapter runs a frozen Python verifier in the existing OS
sandbox, with no network/host-execution fallback. This is not arbitrary CAD support.

Imported notes carry their declared source and limitations. They are hypotheses,
not newly measured historical facts. The supplied example is synthetic and is
not evidence of benefit on actual engineering tasks.

## Acceptance

- Independent Core ledgers and credentials; baseline has no supplied experience;
  no trial receives the other trial's actions, answers or updated memories.
- Pair settings, selected bytes and evaluator are immutable; run order alternates
  across repetitions with a recorded seeded first order. No adaptive tuning.
- Explicit model/effort and identical limits. Monthly subscription only for the
  built-in live path; no key/API fallback or hidden repeat after 429.
- Verifier is outside write scope and rechecked against its frozen bytes. Evaluate
  every saved candidate plus the final state independently of Bot self-report.
- Primary timing includes planning, execution, capture, independent verification,
  reporting and reflection. Setup is separate. Capture calls/tokens (unknown is
  not zero), action order, failed and repeated identical checks, failure codes and
  elapsed times. Human time is unavailable, not inferred from no callbacks.
- Timeouts, holds, failures and interrupted trials remain in the denominator.
  Only matched successful pairs yield time ratios. Never imply statistical proof
  from a small comparison. Hard-killed running trials report incomplete.
- Preserve private ledgers, receipts, file hashes and JSON/Markdown reports. Results
  can be regenerated without inference. No design adoption or live project edits.

## Build order

1. Case validation, frozen inputs, paired report and regression tests.
2. Isolated setup and execution/measurement through existing BotWorker.
3. CLI, anonymous mechanics/control example, real-model smoke comparison, review.

Not included: autonomous memory promotion, weight training, proprietary CAD
integration, paid inference, automatic retries or a claim of faster development.

## Completion evidence

- Implemented isolated setup, frozen case, normal BotWorker calls, independent
  checkpoint/final checks, paired summaries and opt-in Crew CLI.
- TDD: initial three missing-feature failures; focused coverage now includes
  false completion, candidate failure/success, provider holds, limits, failure
  metrics, model pinning and summary-only stdout.
- Independent read-only review found failure-path metrics, tool-error counting
  and final-check reuse issues. All fixed, with failure regressions.
- Full regression: 1,070 invocations / 127.288 seconds / no failures / 8 skips.
  Final focused verification: 15 tests passed. Wheel build passed.
- Real subscription-model pair completed both arms, 66.249 vs 69.281 seconds.
  Same edit/edit/tool/finish order; no observed time saving in this synthetic case.
  Public evidence: docs/BOT_LEARNING_EVALUATION_VALIDATION.md. Private ledgers,
  credentials and model journals are deliberately not included in this repository.
- No storage migration, new API commands, model provider, dependency or automatic
  learning-policy promotion was introduced. Two CLI operations were added.
