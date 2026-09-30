# Security review — 2.0.1

Scope: targeted source review and regression/negative testing of Core authentication, scoped reads, HTTP/MCP boundaries, artifact references, feedback consent, encryption and receiver storage. This is a maintainer review, not an independent penetration test or certification.

## Findings and changes

| Finding | Change | Boundary / residual risk |
|---|---|---|
| Legacy aggregate reads and low-level artifact references could expose records beyond a zone-scoped identity | Scoped actors are denied legacy aggregate queries; submitted artifact revision references are zone-checked, including assembly | Unscoped principals retain ledger-wide authority. A zone is shared read trust; strict per-file/per-session confidentiality and a full authorization audit are not claimed. Separate mutually untrusted projects into separate ledgers. |
| HTTP accepted large bodies before authenticating | Indexed credential, expiry and command checks before body processing; transactional checks still repeat | Trusted local deployment only by default; edge rate/concurrency/body controls are required for hosted deployment. |
| Malformed/duplicate Host and credential headers and unbounded MCP lines | Tightened Host parsing, unique authorization header, bounded MCP messages | OS-user processes and explicitly trusted local MCP clients remain inside the trust boundary. |
| Request paths and exception traces could disclose diagnostic contents | Core HTTP logs only method/status; generic internal errors | Runner and external tool logs can still contain sensitive data. |
| Metrics directory symlinks and consent handling | Reject symlinked consent/metrics roots; private file permissions | Same-user malicious processes can still access/edit local files. Full disk encryption is an OS responsibility. |
| Feedback needed explicit sharing scope and recipient confidentiality | First-run opt-in, selected logs, redacted plaintext preview, exact-byte confirmation, libsodium sealed boxes, invitation-authenticated receiver | Redaction is incomplete; recipient can read plaintext offline; sender identity is not cryptographically authenticated. |

## What remains

- Local ledgers, previews and private keys are not encrypted at rest by Gantry. Use disk encryption, dedicated accounts, restricted backups and an appropriate key manager.
- Runner recipe checks are not an OS sandbox. External agents and engineering tools require their own isolation and credential scope. Prompt injection remains possible in retrieved material and diagnostic reports.
- The feedback receiver has tested size, retention, capacity, authentication and no-download boundaries. Public TLS termination, distributed abuse resistance, operational alerting and managed storage are deployment responsibilities. No production cloud deployment has been tested in this release.
- No full audit of every business API, dependency combination, browser client or OS has been completed. Do not describe this release as enterprise-hardened or universally safe for proprietary engineering assets.
- Users remain in control of agent/provider costs and data sent to their configured providers. Encryption of maintainer feedback does not protect data independently supplied to a model provider.

## Cryptography references

Feedback uses the maintained [PyNaCl SealedBox API](https://pynacl.readthedocs.io/en/latest/public/#nacl-public-sealedbox), not a custom encryption primitive. Sealed boxes provide recipient confidentiality and ciphertext integrity without proof of sender identity. Data minimization and separate key custody follow [OWASP cryptographic storage guidance](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html). No cryptographic security level beyond those library guarantees is claimed.
