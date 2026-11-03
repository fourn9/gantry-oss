# Product readiness: connect, join, restore, deploy

User authorized completion of the remaining product paths. Preserve existing data
and reuse both the Studio and external-integration implementations. Reference:
Addy Osmani agent-skills 2686b620fc1fed2e8f60c704839c766b8594c6b6
(specification/planning, incremental implementation, TDD, API, security, shipping).

## Acceptance, before implementation

- [x] Combine existing external/native adapters with current Studio; preserve
  baseline-bound physical acceptance and durable publication recovery together.
- [x] A recipient generates a private credential locally and sends only a scoped
  access request. A human owner grants it through existing proposal/approval
  events, adds explicitly selected sessions, and can revoke it. Agents cannot
  grant access, adopt designs, or self-enroll. Expired and wrong-workspace requests
  fail. Retry after partial completion does not duplicate principals or sessions.
- [x] Scoped saved-workspace import/sync supports a bounded larger file set and
  large CAD files through existing chunked artifacts. Freeze bytes before upload,
  checkpoint only after all chunks exist, preserve concurrent-head checks,
  never infer deletion from capture failure. Small browser uploads stay supported.
- [x] Ship a single-host TLS deployment recipe, operator provisioning, health,
  verified backup/restore procedure and rollback instructions. No customer tool
  execution or automatic paid inference on the cloud host.
- [x] Run actual local HTTP two-user import/share/continue, larger synthetic
  capture, native connector contract regressions, package install and privacy
  checks. Keep the public demo static and separate from authenticated storage.

## Completion evidence

Final Python regression: 1,279 invocations, eight optional skips, no failures.
JavaScript: 31 passes. Actual loopback HTTP/CadQuery and installed-wheel checks
passed. Independent security review findings were fixed and regression-tested.
See `docs/PRODUCT_READINESS_VERIFICATION.md` for evidence and limits; no live
licensed CAD qualification, public cloud deployment or speedup is claimed.

## Security and migration

No anonymous sign-up endpoint or implicit privilege grants. Operator controls
workspace provisioning; recipient handles the raw credential. Existing human
approval and session authorization remain authoritative. Requests are untrusted
data; no scripts or arbitrary URLs from requests are executed. Tokens and queued
bytes use private local files; never appear in reports or commits. Changes to
schemas/APIs are additive and old state remains replayable.

## Limits that require external evidence

Licensed native CAD acceptance (especially missing Zuken/Capital SDK contracts),
authenticated customer SaaS acceptance, real customer-scale assemblies and live
cloud operation require environments/accounts not supplied. Do not label contract
tests, synthetic files or deployment configuration as evidence of those outcomes.
Automatic engineering correspondence remains a provenance-bearing proposal;
existing engineering declarations/review are the acceptance path, not filename
guessing or a new assertion of physical correctness.
