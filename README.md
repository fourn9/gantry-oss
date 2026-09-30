# Gantry

An agent-friendly development ledger for robotics hardware and software.

Gantry stores versioned development states, artifacts, changes, evidence and decisions so people and agents can continue from a shared state. It connects to tools you already use through a local CLI, HTTP API and MCP. Mentor reviews a submitted change against recorded context and proposes follow-up work; Core checks permission, versions, dependencies and execution conditions.

**Status: early public release.** Local operation is the supported starting point. Human adoption, agent proposals and execution results remain separate. Gantry does not certify a design's physical safety or operate hardware by default.

## Start locally

Python 3.11+ on macOS or Linux. No model account is needed to store and retrieve development state.

```sh
git clone https://github.com/fourn9/gantry-oss.git
cd gantry-oss
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/gantry init --data .gantry
.venv/bin/gantry serve --data .gantry
```

The API and optional UI are at `http://127.0.0.1:8765`. Initialization creates `.gantry/admin.token`; keep it private and use it only for owner administration. The browser asks for this token. Do not expose this local server directly to the Internet.

In another terminal:

```sh
printf '{}\n' | .venv/bin/gantry --token-file .gantry/admin.token call identity
.venv/bin/python examples/development_loop.py
```

The example uses a temporary ledger and synthetic gripper files. It captures a baseline, checkpoints an unverified change, shares it, restores it into another directory and verifies the event history. It does not contact a model or prove physical performance.

## Connect your agent

Use a dedicated, expiring identity with one of three MCP profiles: `read-only`, `developer`, or `reviewer`. Owner credentials and formal-adoption tools are not given to agents. Generate configuration for Claude Code, Cursor, Codex, or a compatible stdio MCP client:

```sh
.venv/bin/gantry agent-request --name my-agent --profile developer \
  --output-token .gantry/my-agent.token --output-proposal agent-request.json
```

The token is **inactive until the owner reviews and commits its principal proposal**. See [agent setup](docs/AGENTS.md) for the complete activation and configuration steps. Installing the MCP configuration alone does not grant execution permission.

You supply your agent subscription or inference credentials. Gantry has no bundled paid inference account and makes no model calls on install or server startup. Provider limits and billing still apply when you explicitly configure a worker. General MCP connectivity is supported; identical capabilities in every agent application are not guaranteed.

## What is included

- Immutable artifact snapshots and development states, with content hashes and restoration.
- Independent change sets, checkpoints, integration conflict checks and explicit unknown compatibility.
- Version-bound evaluations: passing an old combination does not approve a new one.
- Review submissions, specialist reports, Mentor proposals, engineering-check suggestions and outcome tracking.
- Work contracts, authorization, leases, execution limits and resumable runner journals.
- Saved-file and Git capture, GitHub issue/PR/CI ingestion, and an optional web interface.
- An append-only event history, replay and backup/export.

CAD inspection and runtime simulation checkpoints are optional adapters. Install their dependencies separately and declare what is captured. Gantry is not a universal CAD editor, simulator, fleet monitor or deployment system.

See [architecture and boundaries](docs/ARCHITECTURE.md), [workflow](docs/WORKFLOW.md), [privacy](docs/PRIVACY.md) and [security](SECURITY.md).

## Help improve Gantry

Report bugs, propose adapters, discuss workflows and contribute tests through GitHub issues and pull requests. Share a **minimal synthetic example**, not confidential CAD, source, logs or credentials.

On first initialization, choose no feedback (default), statistics, or statistics plus explicitly selected diagnostics. Noninteractive initialization defaults to off. Nothing is sent in the background. Every encrypted upload requires preview confirmation. See [encrypted feedback](docs/FEEDBACK.md) for the optional extra, recipient setup and receiver deployment. A public receiver is not bundled or preconfigured.

```sh
.venv/bin/gantry usage enable --data .gantry
.venv/bin/gantry usage export --data .gantry --output usage-preview.json
# Inspect the JSON before choosing whether to share it.
.venv/bin/gantry usage disable --data .gantry
```

## Development

```sh
python3 -m pip install ".[feedback]"
python3 -m unittest discover -s tests -p 'test_*.py' -q
node --test tests/test_review_web.mjs
```

Core tests use the standard library. Optional NumPy and CAD tests skip when dependencies are absent. Use `GANTRY_CAD_PYTHON` to select a separate CadQuery interpreter. See [contributing](CONTRIBUTING.md).

## License

MIT. The published source, including Core and Mentor orchestration, may be used, modified and redistributed under [LICENSE](LICENSE). Third-party tools and models have their own licenses and terms.
