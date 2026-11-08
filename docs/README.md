# Documentation

Start with the task you want to perform. Verification reports and implementation plans are separate from setup instructions.

## Use Gantry

| Task | Guide |
| --- | --- |
| Connect Codex, Claude, Cursor or another local agent | [Agent setup](AGENTS.md) |
| Bring an existing project into Studio | [Guided onboarding](GUIDED_ONBOARDING.md) |
| Create persistent Bots from project and organization sources | [Crew setup](CREW_SETUP.md) |
| Navigate artifacts, changes and conversations | [Studio](STUDIO_UI.md) |
| Capture, share, restore and continue saved work | [Connected workspaces](CONNECTED_WORKSPACE.md) |
| Follow the normal development/review loop | [Workflow](WORKFLOW.md) |
| Link requirements to work and evidence | [Requirement traceability](REQUIREMENT_TRACEABILITY.md) |
| Turn results into another correction or test | [Design change loop](DESIGN_CHANGE_LOOP.md) |

## Delegate to Bots

Start with **Bot development**, then choose the extra behavior you need. These guides describe different layers, not separate installation requirements.

| Layer | Guide |
| --- | --- |
| Ask, assign and hand off from Studio | [Studio Bot workflow](STUDIO_BOT_WORKFLOW.md) |
| Independent Crew setup and task execution | [Bot development](BOT_DEVELOPMENT.md) |
| Managers, specialists and peer consultation | [Crew organization](CREW_ORGANIZATION.md) |
| Integrate, verify, recover and carry residual work forward | [Development continuation](CREW_DEVELOPMENT_CONTINUATION.md) |
| Persistent identity, runtime and workspaces | [Persistent Bots](PERSISTENT_BOTS.md) |
| Working memory and selective continuation | [Bot continuity](BOT_CONTINUITY.md) |
| Conditional lessons and outcome reflection | [Bot learning](BOT_LEARNING.md) |
| Compare use of experience under controlled conditions | [Learning evaluation](BOT_LEARNING_EVALUATION.md) |
| Specialist teams in the review service | [Review teams](TEAMS.md) |

## Connect tools and operate a service

| Task | Guide |
| --- | --- |
| Inspect supported capture routes | [External integrations](EXTERNAL-INTEGRATIONS.md) |
| Prepare and verify external writes | [Write plans](EXTERNAL-WRITES.md) |
| Check commercial desktop CAD/ECAD coverage | [Native desktop adapters](NATIVE-DESKTOP.md) |
| Use local CAD checks and external physical evidence | [Hardware adapter](HARDWARE-ADAPTER.md) |
| Combine capture, evaluation and review | [Engineering workflow](ENGINEERING-WORKFLOW.md) |
| Recover execution and expose native-preserving views | [Recovery and tool views](runtime-recovery-and-tool-views.md) |
| Deploy, grant access and back up | [Cloud operations](CLOUD-OPERATIONS.md) · [Advanced administration](ADMIN-AGENTS.md) |
| Maintain runtimes and handle private data | [Security updates](SECURITY-UPDATES.md) · [Privacy](PRIVACY.md) · [Optional feedback](FEEDBACK.md) |

## Reference and evidence

- [Architecture](ARCHITECTURE.md) and [Ledger / Crew responsibilities](SERVICE_SPLIT.md).
- [API contracts](api-contracts.json): generated command schemas for this source revision. The installed runtime's MCP tool listing is the version-specific contract; profiles expose only permitted tools.
- [Verification index](VERIFICATION.md): what was actually exercised, with limits.
- [Release history](RELEASE.md): dated behavior and upgrade notes.
- [Examples](../examples/README.md): choose a demonstration by prerequisites and model usage.
- [Contributing](../CONTRIBUTING.md) and [implementation records](../tasks/README.md).

Supporting configuration: [CI template](ci-workflow.yml) (not active by itself) and [hardware runtime constraints](hardware-runtime-constraints.txt).

- [Persistent Crew issues](CREW_ISSUES.md): responsibility, linked work, verification and state-relative resolution.
