# Gantry 2.0.1 — consent and security boundaries

- First-run feedback choice: off (default), statistics, or statistics plus selected diagnostics. Noninteractive startup defaults to off; existing installations can configure it explicitly.
- Plaintext preview, best-effort redaction and exact SHA-256 confirmation before each encrypted export/upload. Revoking consent prevents future packages.
- Optional PyNaCl sealed-box encryption; a separate invitation-authenticated opaque receiver with bounded requests/storage, automatic 30-day expiry and no decryption key or public download endpoint.
- TLS proxy/systemd deployment templates. No publicly hosted receiver or default recipient is configured.
- Hardened scoped artifact references, legacy aggregate reads, HTTP authentication before large uploads, header handling, MCP message bounds and diagnostic logging.

## Validation

Python suite: 268 tests successful, 3 optional dependency skips. UI: 7 tests successful. Synthetic capture/share/restore and local encrypted HTTP upload/decryption verified. Negative tests cover tampering, consent withdrawal, wrong recipients, cross-zone artifacts, bad hosts, invalid credentials, oversized requests, capacity and rate limits.

Known-vulnerability check for the tested feedback dependencies (PyNaCl 1.6.2, cffi 2.1.1, pycparser 3.0) reported no known vulnerabilities at release preparation. This is not a security guarantee. No live inference or real engineering/customer data was used.

## Upgrade notes

Install the updated checkout or release wheel; use the `feedback` extra for encryption. Existing installations do not silently enable sharing. Zone-scoped agents must use delegated development/review APIs instead of legacy whole-ledger queries. Unscoped principals still have ledger-wide read authority. See `docs/SECURITY-REVIEW.md` for remaining boundaries.

Early public preview: not independently audited, not an OS sandbox, no native encryption at rest, no claim of strict per-session artifact confidentiality within one zone. Use separate ledgers for mutually untrusted projects. Feedback receiver deployment, domain, offline key custody, backups and edge abuse controls remain the operator's responsibility.
