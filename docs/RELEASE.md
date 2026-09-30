# Gantry 2.0.3 — scoped project connection

Connect an existing local project with one reviewed delegation. `gantry connect .` combines saved-file discovery, the existing approval audit chain, a project zone, development state and client MCP setup. Work-capable and record-only connections are explicit. Existing low-level APIs remain supported.

The connected agent can read/edit within scope, run exact approved commands in a sandbox, checkpoint, submit to Mentor, apply a current review's proposed correction, save results and resume. Independent candidates and provisional assumptions are recorded separately from formal adoption. Mentor can use the current client model or an explicitly selected official Codex subscription adapter; no maintainer-funded inference is used.

Validation and limits are in [the connection review](CONNECT-REVIEW.md). macOS command execution and four installed MCP configurations were exercised; GUI permission dialogs, arbitrary CAD runtimes and Linux execution are not claimed as qualified. The bridge does not automatically start or continue arbitrary user agents, nor sandbox their direct host operations.

The change adds event-backed connection and operation records. Existing events, artifacts, principal policies and feedback consent remain unchanged. `connect` does not silently extend old agent permissions or import old private ledgers. Back up data before upgrading; once new connection events exist, older readers that do not recognize them cannot replay that ledger. See [the agent guide](AGENTS.md) for setup, limits, interruption and revocation.
