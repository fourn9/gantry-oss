# Changelog

This file records changes after v3.3.0. Earlier release notes remain in the
[GitHub releases](https://github.com/fourn9/gantry-oss/releases).

## Unreleased

### Added

- Opt-in paired Bot experience evaluation through isolated Core ledgers and
  normal Bot execution. Frozen inputs/verifier/model settings, private journals,
  independent candidate checks, failure-inclusive reporting and offline report
  regeneration. The synthetic example is not evidence of engineering speedup.

- Opt-in Bot experience planning and outcome reflection, with conditional lessons,
  applicability checks and preserved correction history.
- Persistent Bot/project working notes for commitments, unknowns and next steps.
- Links from recalled experience to recorded actions and their outcomes.
- Selective continuation after watched inputs or task reports change, or a due
  time arrives, within explicit owner standing delegation.
- Explicit recovery of held reflections using saved inference receipts.
- Explicit recovery of confirmed monthly Codex 429 failures during Bot planning
  or actions, preserving completed effects and enforcing a local cooldown.
- Reflection correction receives Core's validation error and the prior rejected
  submission; rejected output does not update learned experience.

### Security and compatibility

- Working context remains scoped to its Bot and owner; peer receipt views redact
  private context. Standing-delegation revocation reaches descendant work.
- Storage is additive. Existing credentials keep their allowlists; autonomous
  continuation and experience inference require explicit configuration.
- No new inference provider, mandatory dependency or publisher telemetry.

### Validation

- New paired evaluation smoke: both real subscription-model arms completed; the
  supplied-experience arm took 69.28 seconds versus 66.25 seconds without it.
  This synthetic single pair did not demonstrate time saving. See
  [comparison evidence and limits](docs/BOT_LEARNING_EVALUATION_VALIDATION.md).

- Final Python regression: 1,062 invocations, no failures, 8 skips.
- Real subscription-model checks completed experience selection, tool execution,
  working-note updates, experience/action links, report and outcome reflection.
  A changed-input check recorded a real failure without reusing the previous pass.
  Recovery included operator intervention; learning efficacy and engineering
  speedup are not established.
- See [operation](docs/BOT_CONTINUITY.md) and
  [runtime evidence and limits](docs/BOT_CONTINUITY_VALIDATION.md).
