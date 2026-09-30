# Development workflow

1. An owner captures an existing workspace (`capture-workspace`), creates a development session (`connect_development`) and sets delegated actors, scope, execution limits and allowed recipes. Earlier history that was not imported stays explicitly missing.
2. `initialize_continuity` creates a state with design hierarchy, requirements, constraints, decisions, open questions and environment. An agent reads `get_development_state` and starts `begin_change` from that state.
3. Save intermediate work with `checkpoint-workspace`, including rationale, unfinished items and acquisition gaps. Share with `share_change` before verification if useful.
4. Another authorized actor restores it with `restore-development-state`, inspects its context, and continues from a new change. Independent changes can be combined with `integrate_changes`; conflicts and unknown compatibility are explicit.
5. Submit a pinned candidate with `submit_change_review`. A configured review team/worker records specialist reports, coordinator findings and proposed next work. Read the proposed scope and evidence before delegating execution.
6. Core checks a contract before execution. The customer-controlled runner invokes a registered recipe or delegated developer job, journals progress and returns results. Retry uses stable idempotency keys; an uncertain invocation may require operator reconciliation.
7. Record evaluations for their actual input state and scope. Use `propose_state_adoption` only when an owner is ready for formal adoption, through the usual proposal/review/commit process.

Inspect `gantry --help` and `docs/api-contracts.json` for exact current CLI and API parameters. CLI calls use JSON files via `call OPERATION --input FILE`; MCP tool calls wrap payloads in `arguments` and require a stable `idempotency_key` for writes.

Export a ledger with `gantry --token-file .gantry/admin.token export --output backup.json`; restore to a new, empty location with `gantry restore-backup --data restored-ledger --input backup.json`. Backups contain project data and require private storage. File restoration does not guarantee that proprietary CAD dependencies, credentials or an interrupted simulator process are available.

For a runnable minimal capture/share/restore path, use `examples/development_loop.py`. For complete contract/review scenarios, see `tests/test_development.py`, `tests/test_continuity.py` and `tests/test_mentor_jobs.py`. Model responses in those tests are fixtures; they do not prove live inference quality.
