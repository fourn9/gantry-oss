# Gantry

An agent-friendly development ledger for robotics hardware and software.

Gantry stores versioned development states, artifacts, changes, evidence and decisions so people and agents can continue from a shared state. It connects to tools you already use through a local CLI, HTTP API and MCP. Mentor reviews a submitted change against recorded context and proposes follow-up work; Core checks permission, versions, dependencies and execution conditions.

**Status: early public release.** Local operation is the supported starting point. Human adoption, agent proposals and execution results remain separate. Gantry does not certify a design's physical safety or operate hardware by default.

## Connect a project

Python 3.11+ on macOS or Linux. No model account is needed to store and retrieve development state.

```sh
git clone https://github.com/fourn9/gantry-oss.git
cd gantry-oss
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/gantry connect /path/to/your/project --client codex \
  --path src/ --path tests/ --write-path src/ \
  --goal "Improve request clamping" \
  --done "Existing boundary tests pass without changing their assertions"
```

Review one permission plan: project, readable/writable files, exact test commands, expiry, goal, completion conditions and limits. Confirm once. Gantry creates the ledger, records the internal owner approvals, saves current files, registers separate developer/reviewer identities and adds only its MCP entry to the selected client's project configuration. It does not change that client's approval or trust settings.

Use `--client claude`, `cursor`, or `generic` for other clients. Without explicit paths, only discovered files are delegated. The default is **work-capable**, displayed before approval. Use `--mode record-only` when you only want to save externally edited files. The current agent can use scoped MCP tools or CLI:

```sh
gantry project status --root /path/to/your/project
# Pass tool arguments using --input file.json and a stable --request-id.
gantry disconnect /path/to/your/project
```

No server or manual principal/proposal sequence is required for this local route. First-time client trust/MCP enablement remains a client decision. See [setup and daily use](docs/AGENTS.md). If no supported command sandbox is available, tests are refused; Gantry never silently runs them unrestricted.

## Continue through review

Read the saved goal and state → edit within scope → checkpoint unfinished work → submit a meaningful milestone → review grounded Mentor findings → correct/test → checkpoint and respond. Agents do not need another owner decision for these delegated steps. Independent candidates can start from the same state in separate workspaces. Sharing and a successful test do not formally adopt a design.

Mentor uses your existing client model through structured prepare/finish tools. This path does not automatically launch another agent and is not an independent-review claim. Optionally choose `--mentor codex-subscription` with `--goal` and `--done` to automatically review submissions using the installed official Codex CLI and your ChatGPT login. The approval plan covers that source-sharing inference route. No API-key fallback or publisher-funded inference account is included; provider limits still apply.

For the legacy HTTP server, web interface, scoped MCP profiles and advanced multi-user administration, see [administrator setup](docs/ADMIN-AGENTS.md). Existing APIs remain supported.

For stopped-worker recovery, native-preserving tool output profiles and the optional
CAD screening command, see [recovery and tool views](docs/runtime-recovery-and-tool-views.md).

Run [the synthetic end-to-end example](examples/connected_project.py) after installation. Its default model responses are marked fixtures; `--live` performs two bounded calls under your subscription. It demonstrates software bounds, not physical robot performance.

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
