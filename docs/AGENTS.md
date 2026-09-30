# Connect and work with your agent

Install Gantry in a Python 3.11+ environment. Keep that environment installed while a client uses its generated MCP command.

```sh
gantry connect . --client claude \
  --path src/ --path tests/ --write-path src/ \
  --goal "Correct the simulated controller's bounds" \
  --done "Boundary tests pass without changing the tests" \
  --constraint "Keep the existing public interface" \
  --hold "An actuator requirement needs changing"
```

Substitute `codex`, `cursor`, or `generic`. Read the permission plan and answer one `y/N` prompt. Default lifetime is one hour, maximum eight hours. The displayed limits are three reviews, ten test attempts and three alternative branches. These are exploration limits, not engineering acceptance criteria.

The simple `gantry connect .` also works. Its generic goal is modest: save an unadopted candidate with evidence and remaining questions. Supply a meaningful goal and completion conditions for useful autonomous continuation. **Work-capable is the default**; record-only must be selected explicitly.

Detection reads saved files and filenames; it does not execute repository scripts, hooks or package installation. Git presence, CAD files, Python/tests and possible XML models are observations, not proof of a working toolchain. Replace a detected Python unittest command with an exact, owner-reviewed command:

```sh
gantry connect . --test-command 'test=["/absolute/path/to/python","-B","verify.py"]'
```

The executable must be inside the approved read-only runtime. Unsupported CAD/tool runtimes need a separately reviewed adapter. Commands have a 60-second default timeout (Core accepts at most 300 seconds). Tests run on a scratch copy and never silently apply generated files to the project.

## Approval and recovery

An agent can run `gantry connect . --prepare` without activating a token. The owner can rerun the same command interactively or use `--approve EXACT_PREVIEW_HASH` after reviewing it. There is no blanket `--yes`. Unattended approval still requires the local owner credential; an agent capability cannot call approval APIs.

Activation saves the existing propose/submit/endorse/human approval/commit events, session membership, baseline and continuity state in one SQLite transaction. Failure rolls back activation and leaves the request pending. A retry uses the same keys. A client-config conflict leaves an explicit connected-but-client-setup-pending state: fix the conflicting entry and rerun without a second Gantry approval. Existing client entries are not silently replaced.

If the workspace or requested scope changes after preview, cancel with `gantry disconnect .` and review a new plan. Expiry never extends silently. A lost owner credential requires a private backup. Disconnect revokes developer and Mentor credentials before removing local token files; history remains.

## Client setup

| Client | Managed entry | User action |
|---|---|---|
| Claude Code | `.mcp.json`, `mcpServers.gantry_project` | Approve the project MCP server once |
| Codex CLI/app | `.codex/config.toml`, `mcp_servers.gantry_project` | Trust the project and enable/reload MCP as supported by the client |
| Cursor | `.cursor/mcp.json`, `mcpServers.gantry_project` | Enable the project MCP server |
| Other MCP clients | `.gantry/mcp.json` | Import the generated stdio entry |

Configuration contains an interpreter and project path, never a token value. Gantry changes no host approval policies, trust lists or shell permissions. Active clients may need one reload; Gantry cannot force arbitrary clients to reload or continue themselves.

Official references: [Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli), [Codex project trust](https://learn.chatgpt.com/docs/config-file/config-basic), [Claude Code MCP](https://code.claude.com/docs/en/mcp). Host permission prompts are separate from Gantry delegation.

## Daily tools

| MCP tool / `gantry project` action | Purpose |
|---|---|
| `project_status` / `status` | Goal, constraints, completion/hold conditions, state and permission plan |
| `project_read` / `read` | Approved file bytes (base64) and hash |
| `project_edit` / `edit` | Replace a UTF-8 file using its expected hash; `absent` creates a permitted new file |
| `project_test` / `test` | Run a named sandboxed command, recording inputs and result |
| `project_checkpoint` / `checkpoint` | Save approved bytes, rationale and unfinished items; no adoption |
| `project_submit` / `submit` | Share a checkpoint and request a meaningful PR-style review |
| `project_mentor_prepare` / `mentor-prepare` | Supply saved context and an output schema to the user's model |
| `project_mentor_finish` / `mentor-finish` | Save that model's findings under the delegated reviewer identity |
| `project_review` / `review` | Retrieve findings, evidence and current applicability |
| `project_respond` / `respond` | Link corrected state and explanations back to findings |
| `project_branch` / `branch` | Restore an isolated candidate from a common saved baseline |
| `project_assumption` / `assumption` | Record a provisional assumption, scope, evidence, dependencies and adoption blocker |

Normal delegated operations do not ask the owner again. Use stable `request_id` values for MCP writes, or CLI `--request-id` with JSON `--input FILE` (or `-` for stdin). Begin again with `project_status` after interruption. Only scoped tools are exposed: they cannot modify principals, policies, goals, expiry or adoption.

Use `branch` on read/edit/test/checkpoint/submit/respond to work in an alternative's isolated workspace. Branches share a baseline, not edits. No automatic winning-candidate selection or merge is claimed. Formal integration/adoption needs a human decision through existing administration APIs.

Example edit: `{"path":"src/control.py","expected_hash":"HASH_FROM_READ","content":"...","request_id":"edit-1"}`. Test: `{"command":"test","request_id":"test-1"}`. Checkpoint: `{"expected_state":"STATE_FROM_STATUS","summary":"Clamp corrected","rationale":"Address lower-bound finding","unfinished":["Physical integration"],"request_id":"checkpoint-1"}`.

For a review-driven edit/test, add `"from_review":"SUBMISSION_ID"`. Core checks that the review still applies to the current candidate and, for edits, that the path is one of its proposed finding paths as well as inside the delegated write scope. Read-only acceptance files must still match the approved baseline before tests run; editing tests externally requires a new reviewed baseline.

## Mentor and continuation

Default: prepare → the user's current model returns structured findings → finish. Separate credentials prevent a reviewer token from editing or adopting; they do not prove independent reasoning when one client handles both roles.

For automatic submitted-milestone review, approve `--mentor codex-subscription --goal ... --done ...`. The existing official CLI adapter checks ChatGPT login, disables inference tools and refuses API-key fallback. Source context uses that explicitly approved user-provider route. Installation and ordinary recording make no model calls; Gantry maintainers pay no inference charges.

The running user agent chooses and performs follow-up work. Gantry does not automatically launch/continue arbitrary Claude or Cursor sessions. Idle/stopped clients, host approval and provider quota can stop continuation; saved state remains available. An uncertain inference/process is never blindly retried. Inspect private operation/review journals before a deliberate new attempt.

Test observations are bound to actual input hashes and included in matching reviews. New combinations do not inherit a physical pass. Assumptions stay open questions and block canonical state adoption until resolved through the existing explicit workflow. Investigate agent-resolvable unknowns; bundle genuinely user-owned decisions and continue independent work within scope.

## Security boundary

The capability scopes this project's Core calls and Gantry bridge. File operations reject traversal, symlinks, hardlinks, private paths and known secret patterns. Commands use macOS Seatbelt or Linux bubblewrap, a scratch copy, no host environment credentials, no network and no project/hardware writes. Failed/missing sandbox setup has no unrestricted fallback. Only macOS has live platform acceptance evidence in this change; Linux needs qualification.

These controls **do not sandbox a separately operated agent, shell or CAD app**. A process with full access to the same OS account can read/modify local files, including the ledger. Trust the host and installed runtimes; use host controls or a dedicated OS/VM account for stronger separation. Never give agents the owner token. Secret detection is best-effort. Connect supports 1,000 files / 32 MiB total / 16 MiB per file; larger assemblies use the existing chunked artifact adapters.

Internal approvals and HTTP/MCP administration: [administrator guide](ADMIN-AGENTS.md).
