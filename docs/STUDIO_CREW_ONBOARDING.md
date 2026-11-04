# Studio team onboarding

Open the saved project's **Team → Initial team setup**. The selected project and
state supply the development context. An organization is separate from a project;
existing Bot identities and memories can be reused across authorized project setups.

## Three steps

1. **Sources** — name the organization, describe its responsibilities, optionally
   select saved Notion documents, Linear/Jira exports or CSV/XLSX role tables, and
   save the reviewed selection. This does not start inference or work.
2. **Team review** — choose the connected customer runtime and press **Suggest
   team**. Inspect the reporting hierarchy; expand a role to edit its mission,
   responsibilities and editable scope. Reasoning references and unknowns are
   available on demand. Editing requires **Prepare runtime** again. **Create team**
   approves the exact proposal and runtime preparation and creates/configures the
   identities. It does not start workers or enable execution.
3. **Start** — inspect the proposed first task and actual runtime status. Enable
   execution explicitly with **Start team**. The host starts customer workers and
   records the first planning task. **Stop workers** preserves queued work;
   **Resume workers** reconnects execution using the saved identities and journals.

JSON correction and individual CLI instructions remain in optional details. Normal
onboarding does not require JSON editing or copying one command per Bot. There is
no fabricated progress percentage. Runtime presence and queued/running/held job
states come from Core. Formal adoption remains a separate decision.

## Connect a customer runtime once

Studio cannot install CAD software or an agent on a customer's computer. The
customer runs the setup host using an existing owner credential and approved
local tool configuration. Keep its private directory and credentials outside Git.

A minimal private runtime template is:

```json
{"name":"Customer Crew runtime","tools":[],"local_tools":{}}
```

Configure actual tools using the existing worker runtime schema; this template
alone provides no CAD/editor capabilities. Make the template and owner token file
owner-readable only. Then run:

```sh
gantry --url https://your-gantry.example --token-file /private/owner.token \
  crew-setup-host connect --journal /private/setup-host \
  --backend codex-subscription --runtime-template /private/runtime.json
```

`connect` saves the private connection and runs the host in the foreground. Keep
it running while using Studio. After a normal restart:

```sh
gantry crew-setup-host run --journal /private/setup-host
```

The subscription route uses the customer's existing official CLI account and
refuses API-key fallback. `customer-command` is also supported with a private
`--inference-config` and worker template containing the approved executable and
its hash. This is trusted customer software, not an OS sandbox. It may have its
own billing; Gantry does not automatically choose or purchase a provider.

The host privately retains new credential/config mappings after activation. Later
setups can reuse these same Bots without recreating their credentials or runtime.
For Bots configured elsewhere, supply reviewed private `--bindings` when connecting;
see [the CLI setup guide](CREW_SETUP.md). It does not infer missing secrets.

## Ownership and recovery

- Only the session's human owner can request these setup actions. Bot/Mentor
  profiles do not receive setup-host commands.
- Browser requests contain bounded action names, versions and hashes, not local
  command lines, token paths or executable arguments. Local approved configuration
  remains authoritative for installed tools.
- Creation pins the proposal and runtime-plan hashes. Start also pins the current
  execution-session version, including owner-approved execution settings.
- A single host instance owns a job. Exact unknown HTTP responses reuse the saved
  request and private journal. Inference is not repeated automatically after an
  uncertain provider outcome.
- **Cancel request** is available before the host claims it. Held operations expose
  **Retry saved operation**; inspect the private journal and resolve the cause
  first. Version changes require renewed review, not silently refreshed approval.
- A held Start whose execution settings changed offers **Stop and reconcile**.
  This only stops/fences its workers; it never starts work or calls the model. The
  same journal and first task are preserved. Once all relevant runtimes are offline,
  the old request can be cancelled and a new Start reviewed against current settings.
  Missing journals or uncertain results remain held for recovery.
- Stop fences the owned Bot runtimes shown in this setup. If a Bot also serves
  another project, that same shared runtime stops there too; its queued work stays.
  Failed-start rollback only detaches newly added references and preserves an
  already-running shared worker.
- Stop does not discard work or imply that an in-flight provider call was cancelled.
  Its worker is fenced from later submission; local ownership is retained until
  the call exits. A different runtime cannot replace it while it still owns work.

Do not discard the private host directory to fix an uncertain operation. It contains
the receipts needed to avoid duplicated model requests and credential replacement.
The implementation adds no background OS service or cloud VM provisioning.

## Minimal UX options

| Option | Suitable use | Tradeoff |
| --- | --- | --- |
| Three steps (implemented) | First-time project and organization setup | Clear save/create/start boundaries; a few transitions |
| One progressively expanded screen | Frequent repeat setups | Less navigation, but a longer page |
| Conversation-first | Ambiguous responsibilities or missing organizational documents | Flexible clarification, but authority and hierarchy still need a structured review |

The initial release uses three steps, a collapsed role hierarchy and optional
details. Sources are saved exports, not live Notion/Linear/Jira synchronization.
See [functional acceptance](STUDIO_CREW_ACCEPTANCE.md) for what was actually tested.
