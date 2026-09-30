# Development workflow

## Normal local development

1. `gantry connect . --client codex --goal ... --done ...` discovers saved files and proposes a scoped permission plan. Select read/write paths and test commands. The owner approves once; Core records the existing approval chain internally. `record-only` is an explicit alternative, not the development default.
2. The connected agent starts with `project_status`. It gets goal, completion/hold conditions, fixed constraints, saved state and product-owned continuation instructions. It performs scoped reads/edits/tests without another owner decision.
3. `project_checkpoint` records a milestone with rationale and unfinished work. `project_submit` shares it and creates an immutable PR-style review. Missing verification is allowed; sharing never adopts a design.
4. Mentor consumes that saved context through prepare/finish tools, using the user's model. An explicitly configured subscription adapter can review automatically. The resulting findings name exact evidence, concrete proposed changes and completion checks. Core rejects invalid evidence or a stale review.
5. The user agent reads findings, edits through the scoped bridge, runs approved tests, checkpoints and responds. The result and actual input hashes are retained. Repeated proposals/tests/branches stop at the delegated limits; no arbitrary agent is automatically launched by this bridge.
6. `project_branch` creates independent alternatives from a common baseline. `project_assumption` records provisional assumptions and their adoption blockers. Investigate agent-owned unknowns; ask the owner for decisions that change goals, fixed constraints, authority or formal adoption. Continue independent work while those decisions wait.
7. After interruption, `project_status` retrieves the current state and `project_review` retrieves saved findings. Ambiguous process/inference outcomes require journal inspection; the bridge does not blindly replay execution. `gantry disconnect .` immediately revokes both agent identities and preserves history.

Use [the agent guide](AGENTS.md) and [the synthetic connect/review/correct/restart example](../examples/connected_project.py). CLI arguments go in JSON files; MCP tools have direct JSON schemas and stable `request_id` fields. Client host approvals remain separate.

## Advanced low-level APIs (unchanged)

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
