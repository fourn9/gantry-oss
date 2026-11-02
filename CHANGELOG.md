# Changelog

This file records changes after v3.3.0. Earlier release notes remain in the
[GitHub releases](https://github.com/fourn9/gantry-oss/releases).

## Unreleased

### Added

- Opt-in Bot experience planning and outcome reflection, with conditional lessons,
  applicability checks and preserved correction history.
- Persistent Bot/project working notes for commitments, unknowns and next steps.
- Links from recalled experience to recorded actions and their outcomes.
- Selective continuation after watched inputs or task reports change, or a due
  time arrives, within explicit owner standing delegation.
- Explicit recovery of held reflections using saved inference receipts.

### Security and compatibility

- Working context remains scoped to its Bot and owner; peer receipt views redact
  private context. Standing-delegation revocation reaches descendant work.
- Storage is additive. Existing credentials keep their allowlists; autonomous
  continuation and experience inference require explicit configuration.
- No new inference provider, mandatory dependency or publisher telemetry.

### Validation

- Python regression: 865 invocations, no failures, 8 skips; subsequent focused
  verification: 182 passed.
- Real subscription-model checks reached experience selection, tool execution and
  working-note updates. The follow-up report/reflection cycle remains held by
  provider HTTP 429. Learning efficacy and development speedup are not established.
- See [operation](docs/BOT_CONTINUITY.md) and
  [runtime evidence and limits](docs/BOT_CONTINUITY_VALIDATION.md).
