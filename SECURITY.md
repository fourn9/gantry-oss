# Security

This is an early release, not an externally audited security product. Use a trusted local machine and synthetic data for initial evaluation. Report vulnerabilities with GitHub's **Report a vulnerability** feature; do not put credentials or exploitable private deployment details in a public issue.

## Boundaries

- The local server binds to loopback by default. Loopback Host checks, origin checks, request limits and authentication are defense in depth, not a sandbox for hostile local processes.
- HTTP clients refuse non-loopback plaintext URLs and redirects. Remote deployments need a TLS reverse proxy, host allowlist, tenant provisioning, backups, monitoring and operational review. Those services are not provisioned by the quick start.
- Agent identities can have expiration, command allowlists, scoped permissions and session participation. MCP profiles further restrict exposed tools; Core is the authorization authority. Do not give agents an owner's token.
- Token files use owner-only filesystem permissions. They are not encrypted by Gantry. Protect the machine and backups; revoke compromised identities through an owner-reviewed principal change (`enabled: false`).
- Runner permission checks are not an operating-system sandbox. Run untrusted code in your own isolated environment, with minimal filesystem/network access and no ambient secrets. Inference or repository content may contain prompt injection.
- Artifact capture excludes common credential paths and detects some credential patterns. This is not complete secret detection. Inspect what you submit; explicitly supplied artifacts may contain sensitive data.
- Hashes detect mismatches against a trusted reference. A local administrator who controls the complete log and checkpoints can rewrite them. Keep independent trusted backups where needed.
- Review conclusions and model-generated engineering checks are proposals. They do not establish physical compatibility, safety or regulatory compliance. Human formal adoption remains separate.

No third-party security audit or supported public multi-tenant hosting guarantee is claimed. Maintainers handle security reports on a best-effort basis without an SLA.

Use 2.0.2 or later. For the latest fixes and validation, see [SECURITY-REVIEW.md](docs/SECURITY-REVIEW.md). In particular, isolate mutually untrusted projects into separate ledgers, and do not equate zone-scoped writes with universal per-session read isolation. The optional feedback receiver holds encrypted envelopes only; its offline recipient key and public-facing deployment require separate operator controls.
