# 2.0.0 — initial public preview

This preview provides the Gantry CLI, HTTP API, stdio MCP bridge, optional UI, Core ledger and Mentor/Runner orchestration. Local development is the supported entry point. Models and external engineering tools are supplied by the user.

## Validation

- Python suite: 249 tests, successful with 3 optional dependency tests skipped in a clean Python 3.12 environment.
- JavaScript review rendering: 7 tests passed.
- Installed wheel: synthetic HTTP capture, immutable checkpoint, sharing, restoration, event verification and replay passed.
- Installed CLI: expiring agent request, owner activation, generated Claude/Cursor/Codex/generic configurations and stdio MCP identity retrieval passed.
- No live model calls in release verification. Worker tests use controlled model fixtures; no claim of live inference quality or development-time improvement is made.

## Known limits

- macOS validation; a Linux CI template is provided but is not activated. Linux and Windows have not been verified by this release run.
- CAD inspection and runtime checkpoint serializers require optional dependencies and a compatible environment. Arbitrary tool process restoration and automatic CAD merging are not provided.
- No independent security audit. Do not expose the default local HTTP server as a public hosted service.
- Agent application UX is not tested in every supported client. Generated configurations use standard stdio MCP, and Core enforces permissions independently.
- Usage metrics are local, optional and manually exported; there is no automatic maintainer data collection.
