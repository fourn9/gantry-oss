# Connect a user-owned agent

Gantry runs locally. Your agent application communicates with its stdio MCP bridge, which calls the authenticated HTTP API. Your tools and model subscription remain yours. No Gantry-hosted inference is included.

## 1. Generate a scoped request

Start the server as in README. In the same repository, run:

```sh
.venv/bin/gantry agent-request --name my-agent --profile developer \
  --output-token .gantry/my-agent.token --output-proposal agent-request.json
```

The request contains a token hash, never the token itself. Default expiry is 30 days. `read-only` exposes queries; `developer` additionally exposes permitted changes/work; `reviewer` exposes review submissions and jobs. Profiles do not grant administrator or formal-adoption tools. Core permissions and session delegation are checked independently.

## 2. Activate as the human owner

Inspect `agent-request.json`. Submit it with your owner credential:

```sh
.venv/bin/gantry --token-file .gantry/admin.token call propose --input agent-request.json
```

Use the returned `id` and `version` in subsequent API calls:

1. `submit`: `{"proposal_id":"RETURNED_ID","version":1}`
2. `endorse`: add `"reason":"Reviewed the requested scope and expiry"`.
3. `review_adoption`: add `"verdict":"approve"` and your reason.
4. `commit`: the same proposal ID and version.

For each, save the JSON to a file and use `call OPERATION --input FILE`. These are deliberate owner decisions, not steps for the agent to self-authorize. A returned version other than 1 must be used as returned.

For existing development sessions, include the agent in the owner-configured `actors` using `configure_development`, preserving the intended scope, limits and recipe hashes. Reviewers additionally need the appropriate review-team role. New sessions use `connect_development`. Creating a principal alone does not delegate every project operation.

To revoke access, submit an owner-reviewed update of the principal with `enabled: false`, retaining its other required fields and supplying its current `expected_revision`. Rotating its token hash invalidates the old token. Never post principal configuration or credentials to public issues.

## 3. Generate client configuration

```sh
.venv/bin/gantry agent-config --client claude --profile developer \
  --agent-token-file .gantry/my-agent.token \
  --executable "$PWD/.venv/bin/gantry" --output agent-claude.json
```

The generated configuration contains an absolute token-file path, not its contents. It requires a non-admin agent identity at MCP startup. Owner-only file permissions are required on POSIX.

| Client option | Output | Where to merge it |
|---|---|---|
| `claude` | JSON `mcpServers.gantry` | Claude Code project `.mcp.json` or your selected MCP settings |
| `cursor` | JSON `mcpServers.gantry` | Project `.cursor/mcp.json` or user MCP settings |
| `codex` | TOML `[mcp_servers.gantry]` | Your Codex MCP configuration |
| `generic` | JSON stdio definition | Any compatible stdio MCP client |

Select the matching `--client` and a new `--output` filename. Gantry never overwrites your application settings. Merge the entry rather than replacing unrelated servers. Reload/enable the MCP server in your application. Treat project MCP configurations from untrusted repositories as executable configuration.

Ask the agent to call `identity`, then retrieve the state you delegated. Writes need a stable `idempotency_key`; reuse it only when retrying the same operation and payload. Configuration generation and protocol tests are included; application-specific setup and supported tools may vary across versions.

## Mentor and execution

An external agent can read a review task and submit structured findings through MCP. Automated Mentor/Runner workers are an additional opt-in setup requiring inference configuration, delegated identities, a review team and allowed execution scope. Merely connecting Claude/Cursor/Codex does not start those workers.

The included subscription-backed Codex adapter invokes the installed official CLI under the user's own login and refuses API-key login in that mode. Provider quotas still apply. Other model integrations or API providers use their explicitly configured credentials. Do not assume a flat-rate subscription gives unlimited inference.
