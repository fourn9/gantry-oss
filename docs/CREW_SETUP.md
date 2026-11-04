# Set up Crew from existing project and organization evidence

`gantry crew-setup` connects an existing saved project state to a persistent Bot
organization. `gantry-crew crew-setup` provides the same commands. Start with the
session and state IDs shown by Studio or the existing project onboarding flow.
Project-only onboarding remains valid; a team is optional.

Organization exports are separate from the project's editable files. Supported
inputs include Notion Markdown exports, Linear/Jira CSV exports, generic text,
CSV/JSON, and bounded XLSX tables. These are **saved exports**, with original bytes,
hashes, record locations and parsing limitations retained. There is no live OAuth
connection or continuous synchronization. Gantry does not fetch links, run macros,
evaluate spreadsheet formulas, or certify native engineering files through import.

## Which source to start with

Use sources together, rather than requiring one system to describe everything:

| Source | Useful evidence | What it does not establish |
| --- | --- | --- |
| Saved project state | Actual files, requirements, unresolved conditions and editable scope | The organization's reporting hierarchy |
| Notion Markdown/text export | Design principles, team procedures, responsibilities and past decisions | Current execution permissions |
| Linear/Jira CSV export | Issues, assignees, status and outstanding work | A manager relationship from issue assignment alone |
| CSV/XLSX role table | Explicit departments, roles, responsibilities and reporting relationships | An automatically authorized Bot account |

A useful initial role table has `role`, `reports_to`, `responsibility`, `scope`,
`report_when`, and `consult_with` columns. These are recommended descriptions, not
a required schema. Original column names and values are preserved. A missing
organization chart is acceptable: use owner notes and project evidence, then review
the inferred organization and its unknowns. Do not map every named employee or
issue assignee to a new Bot without reviewing the intended responsibility.

Selected exports become part of the project's authorized context. Reusing an
organization also includes its current organization profile and Bot role profiles
in this setup context; it does not import other projects' files or memories. Select
only organizational material appropriate for this project's participants.

Studio exposes **Team → Initial team setup**, also offered after project import.
Its normal path is **Sources → Team review → Start**. With a customer setup host
connected once, the owner can request a proposal, edit roles, create the reviewed
team, and start/stop workers entirely from Studio. Opening the page does not invoke
a model. Private credentials are prepared by that customer's host, never in the
browser. See [Studio onboarding](STUDIO_CREW_ONBOARDING.md) for connection and recovery.
The individual CLI steps below remain available for existing integrations.

## Preview and save selected evidence

Use the owner's existing Gantry URL and private token file through `--url` and
`--token-file`, or the existing `GANTRY_URL` and `GANTRY_TOKEN_FILE` settings. Keep
all operation journals, token files, runtime templates and configuration outside
source repositories in a private customer directory.

```sh
gantry crew-setup start \
  --session-id SESSION_ID --state-id STATE_ID --name 'Assembly team' \
  --root /customer/exports \
  --source notion=team.md --source spreadsheet=roles.xlsx \
  --notes 'Review the suggested reporting structure and tool limitations'
```

The default preview reads only the named saved files and reports hashes, sizes,
record counts and limitations. It makes no server or model call and writes no
journal. Repeat the exact command with `--apply --journal /customer/private/upload`
to preserve and upload the reviewed bytes. Select at most 30 files, 16 MiB each
and 32 MiB total. Omitting `--source` is supported when the project state and owner
notes are sufficient evidence. Add `--organization-id ID` to reuse an organization.

The upload returns `setup_id`. Uploading cannot create principals, activate Bots,
enable execution or start work. Repeating the same upload with its journal resumes
the saved request. Changed input requires a new journal and a fresh source review.

## Analyze, inspect and correct

Choose the customer inference route explicitly:

```sh
gantry crew-setup analyze --setup-id SETUP_ID \
  --backend codex-subscription --journal /customer/private/analysis
gantry crew-setup review --setup-id SETUP_ID
```

The subscription adapter uses the customer's existing official Codex CLI login and
refuses API-key fallback. Alternatively, select `--backend customer-command
--inference-config /customer/private/inference.json`. That private JSON must contain
the installed customer's exact `command` argument array and `executable_hash`
(SHA-256 of the executable). The existing bridge receives JSON `{context, schema}`
on stdin and returns the requested JSON on stdout. A customer bridge is trusted
local software; Gantry does not turn it into an OS sandbox.

Analysis includes the saved project state evidence, selected source records,
current organization and Bots, allowed scope and explicit limitations. The proposal
contains profiles, reporting hierarchy, responsibilities, rationale with evidence
IDs, scopes, uncertainties and a first planning task. An inferred organization is
a suggestion for owner review. Source statements never grant authority.

Review the complete proposal in Studio or `review`. Existing organization profiles
and existing Bot names, profiles and hierarchy must be preserved when reused;
separate reviewed organization updates handle changes to those identities. To save
owner corrections, put the corrected **proposal content** in a private JSON file:

```sh
gantry crew-setup propose --setup-id SETUP_ID \
  --proposal /customer/private/corrected-proposal.json \
  --journal /customer/private/correction
```

This submits the same validated proposal contract without invoking a model. It
still does not create credentials or grant permissions. Re-run `review` to obtain
the exact current proposal hash. `resume` is an alias for this read-only view.

## Prepare private worker files and approve the team

Create a private runtime template using your actual installed tool configuration.
A minimal template enables the existing Crew model/tool workflow with no external
tool commands:

```json
{
  "name": "Customer Crew runtime",
  "tools": [],
  "local_tools": {}
}
```

For installed tools, preserve the existing worker fields `local_tools`,
`tool_runtime`, `sandbox`, `cad_python`, `verification` and
`environment_definition` as applicable. External commands must be supplied and
reviewed by the customer. See [Crew organization](CREW_ORGANIZATION.md) and
[Persistent Bots](PERSISTENT_BOTS.md). For the customer-command backend, include
its exact `command` and `executable_hash` in the runtime template as well.

The template must not contain a token, token path, server URL or Bot ID. The setup
adds `workflow: bot_development`, `agent_loop: true`, `experience_learning: true`,
`learning_mode: selective` and `personal_continuity: true`. It preserves the supplied
tool declarations and rejects conflicting workflow settings. Make template,
inference and mapping files owner-only (`chmod 600`); new journals use mode 700
and private files mode 600.

```sh
gantry crew-setup prepare --setup-id SETUP_ID \
  --backend codex-subscription \
  --runtime-template /customer/private/runtime-template.json \
  --journal /customer/private/runtimes
```

Preparation returns the proposal hash, runtime plan hash, role/principal mappings,
credential **hash** requests, proposed configuration and public environment
manifests. New Bot credentials are created with the existing recipient-owned
membership request mechanism. Their raw values stay in local token files. They
are inactive until owner activation. The owner token is never placed in worker
configuration. Preparation itself grants no permissions.

Review both the proposal and role mappings, then approve the exact proposal:

```sh
gantry crew-setup activate --setup-id SETUP_ID \
  --journal /customer/private/runtimes --approve EXACT_PROPOSAL_HASH
```

Core atomically activates the reviewed organization, dedicated principals and
project bindings. The client then creates per-Bot configuration files from the
actual activation result. It does not start workers or enable project execution.

An existing principal requires `--bindings` pointing to a private JSON list such
as `[{"role_id":"lead","principal_id":"existing-agent","token_file":
"/customer/private/existing.token"}]`. The token must authenticate as that agent,
with no admin permission. Reusing an existing Bot additionally requires its
`config_file`; its workflow settings and environment must already be approved.
Existing token/configuration files and runtime versions are preserved. Configure
an incompatible existing runtime separately before preparing this setup.

If the team was activated directly in Studio, use **Team → Runtime** with existing
private worker files. CLI preparation creates new credentials before activation;
it does not replace credentials for an already activated team.

## Approve runtimes, run workers, then start work

Approve the exact runtime plan returned by preparation:

```sh
gantry crew-setup configure --setup-id SETUP_ID \
  --journal /customer/private/runtimes --approve EXACT_RUNTIME_PLAN_HASH
```

This registers the exact reviewed environment for each new Bot. It prints an
ordinary `gantry bot-worker --config FILE --journal DIRECTORY` command per Bot.
Run those commands with the customer's normal process supervisor or terminals;
setup does not add an orchestrator. A configured worker remains **offline** until
the existing worker actually starts and heartbeats. Readiness reports Core's
current observation, not an inference from generated configuration files.

Explicitly enable the project's existing execution policy in Studio, reviewing
its scope and execution settings. Then queue the first planning task:

```sh
gantry crew-setup start-work --setup-id SETUP_ID \
  --journal /customer/private/runtimes
```

Core requires owner authorization, the enabled execution policy, the saved
baseline and an online lead runtime. The lead reasons and delegates through the
existing Bot task system. Import, analysis, preparation and activation never queue
work automatically. Mentor remains a separate optional service.

## Recovery and evidence

Preserve the operation directories. Each journal binds the endpoint, actor,
setup, exact proposal or input basis, and supplied configuration. Repeating an
operation uses its saved request and idempotency key. A lost acknowledgement after
activation or configuration is retried without generating credentials or invoking
analysis again. Changed credentials or configuration are rejected. Do not edit
journals to force an old approval onto new data.

An uncertain provider process is not automatically repeated. Inspect the private
inference receipt and confirm the old process has stopped before deliberately
starting a new analysis attempt in a fresh directory. Preserve partial credential
creation for inspection; do not overwrite an existing credential to recover it.
Expired inactive membership requests need fresh preparation and review. Customer
journals can contain source evidence, model receipts and credentials; retain or
remove them under the customer's own private-data policy.

`tests/test_crew_setup_client.py` verifies real-ledger setup, dedicated credentials,
offline/online gating, first-task creation, export preview, lost-response recovery,
config/token tampering, uncertain customer commands and existing-runtime reuse.
Its model output is synthetic. Passing these tests does not demonstrate model
quality, native tool compatibility or engineering speed improvements. Subscription
model smoke evidence must be recorded separately.

See [acceptance results and remaining boundaries](CREW_SETUP_ACCEPTANCE.md).
