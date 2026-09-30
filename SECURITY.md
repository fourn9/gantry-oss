# Security

This is an early release, not an externally audited security product. Use a trusted local machine and synthetic data for initial evaluation. Report vulnerabilities with GitHub's **Report a vulnerability** feature; do not put credentials or exploitable private deployment details in a public issue.

## Boundaries

- The local server binds to loopback by default. Loopback Host checks, origin checks, request limits and authentication are defense in depth, not a sandbox for hostile local processes.
- HTTP clients refuse non-loopback plaintext URLs and redirects. Remote deployments need a TLS reverse proxy, host allowlist, tenant provisioning, backups, monitoring and operational review. Those services are not provisioned by the quick start.
- Agent identities can have expiration, command allowlists, scoped permissions and session participation. MCP profiles further restrict exposed tools; Core is the authorization authority. Do not give agents an owner's token.
- Token files use owner-only filesystem permissions. They are not encrypted by Gantry. Protect the machine and backups; revoke compromised identities through an owner-reviewed principal change (`enabled: false`).
- Runner permission checks are not an operating-system sandbox. Run untrusted code in your own isolated environment, with minimal filesystem/network access and no ambient secrets. Inference or repository content may contain prompt injection.
- The newer `connect` project bridge is a separate, bounded path: exact project capabilities, guarded file access and sandbox-only commands on scratch copies. macOS Seatbelt and Linux bubblewrap backends fail closed if unavailable. Only macOS has been exercised locally. This does not add an OS sandbox to legacy Runner or to a user's independently operated Claude/Codex shell. Same-user processes and the installed runtime remain trusted; this is not a hostile multi-user boundary or a resource-isolated VM.
- Connect never exports an owner token to an agent or client config. Activation is atomic, tokens expire and disconnect revokes them. Commands receive a minimal environment and no network; the optional subscription-backed Mentor uses a distinct, explicitly approved inference route. Generated MCP starts Python in isolated import mode, so a repository cannot shadow the installed `gantry` module through its working directory or `PYTHONPATH`.
- Artifact capture excludes common credential paths and detects some credential patterns. This is not complete secret detection. Inspect what you submit; explicitly supplied artifacts may contain sensitive data.
- Hashes detect mismatches against a trusted reference. A local administrator who controls the complete log and checkpoints can rewrite them. Keep independent trusted backups where needed.
- Review conclusions and model-generated engineering checks are proposals. They do not establish physical compatibility, safety or regulatory compliance. Human formal adoption remains separate.

No third-party security audit or supported public multi-tenant hosting guarantee is claimed. Maintainers handle security reports on a best-effort basis without an SLA.

Use the latest release. See the [publication security review](docs/SECURITY-REVIEW.md) and [2.0.3 connection review](docs/CONNECT-REVIEW.md) for validation and remaining limitations. In particular, isolate mutually untrusted projects into separate ledgers, and do not equate zone-scoped writes with universal per-session read isolation. The optional feedback receiver holds encrypted envelopes only; its offline recipient key and public-facing deployment require separate operator controls.
