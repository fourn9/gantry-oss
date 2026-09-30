# Publication and security review — 2.0.2

Date: 2026-09-30. This is a maintainer review with local tests, not an independent penetration test, certification or exhaustive source audit. The supported starting point remains a trusted local machine.

This records the 2.0.2 publication review. The additional scoped project bridge introduced in 2.0.3 is covered by [its separate review](CONNECT-REVIEW.md); the legacy Runner limitations below still apply.

## Changes

- Git capture now rejects common sensitive tracked filenames and credential patterns before uploading any snapshot. The check also covers removed text in a requested historical diff. Snapshot size/file-count limits apply, and a diff base must resolve to a commit rather than a Git option. Detection remains best-effort: binary secrets and arbitrary credential formats are not guaranteed to be detected. Explicit artifact APIs still require the caller to inspect their contents.
- Direct Python API GitHub synchronization now performs the indexed expiration and command-scope checks before fetching or returning an idempotent cached response. HTTP already performed this preflight; the direct service entry point now uses the same checks. Transactional authorization still repeats before changes are committed.
- Feedback uploads only report success if the receiver receipt matches the exact encrypted envelope sent. A syntactically valid receipt for a different envelope is rejected. This does not independently prove long-term storage or deletion by the recipient.

These changes require no database migration or consent reset. Existing sharing consent is never expanded.

## Evidence

- Python suite: 271 cases, 268 passed and 3 skipped for optional dependencies. The added regressions exercise committed sensitive files, secrets removed in a diff, invalid diff bases, expired/restricted identities on cached and fresh synchronization, and an incorrect receiver receipt. The existing real local encrypted upload/decrypt test also passes.
- JavaScript suite: 7 passed.
- Static analysis with Bandit reported 23 low and 1 medium finding. The medium SQL-construction finding was reviewed: column names are selected from a fixed allowlist and user values are bound parameters. The low findings concern intentional subprocess execution, PATH-resolved executables and optional metrics error handling. They do not remove the need to isolate tools and trust the installed executables.
- The secret scanner's five candidates in the reviewed checkout were synthetic negative-test fixtures, not operational credentials. Release review also covers tracked history, filenames, package contents and published metadata. Pattern-based scanning cannot guarantee the absence of every secret format.
- Known-vulnerability lookup for the tested optional runtime dependencies, PyNaCl 1.6.2, cffi 2.1.1 and pycparser 3.0, reported no known vulnerabilities. This excludes operating-system packages, user-supplied engineering tools and other dependency versions.
- The distribution contains project source and static UI assets, with its MIT license. No third-party binaries, fonts or model weights are bundled. External tools and models are separately installed and subject to their own terms.

## Remaining release boundaries

- Runner is not an OS sandbox. An authorized recipe or external agent can use the OS account's capabilities. Use isolated environments and scoped credentials for untrusted code or models. Retrieved content can carry prompt injection.
- Local data, token files and recipient private keys are protected by filesystem permissions, not native encryption at rest. Use OS disk encryption and appropriate backup/key custody controls.
- Zones are shared read boundaries, not strict per-session secrecy. Use separate ledgers for mutually untrusted projects. Unscoped identities have broad ledger access by design.
- The optional feedback server has no default hosted endpoint. Sharing is off by default and every upload requires confirmation. Redaction is incomplete; the configured recipient can decrypt selected logs. Public TLS, edge abuse controls, monitoring and key custody must be configured and reviewed before operating an Internet-facing receiver.
- GitHub Actions is not active in this release. `docs/ci-workflow.yml` is a template; the tests above ran locally on macOS. Linux execution, enforced remote checks, branch protection, signed release attestations and an independent security audit remain outstanding.
- Checksums published beside a wheel detect accidental mismatches, but are not independent protection against a compromised release account.
- The MIT license permits copying, modification and commercial redistribution; it is not a secrecy mechanism. No trademark clearance or patent/ownership opinion is supplied by this technical review.

See [Security](../SECURITY.md) and [feedback privacy](PRIVACY.md). Report vulnerabilities privately through GitHub's vulnerability reporting feature.
