# Studio Crew onboarding

Reference: Addy Osmani agent-skills revision 2686b620fc1fed2e8f60c704839c766b8594c6b6. Apply planning, incremental implementation, TDD, interface design, frontend UI, security and independent review. Existing user authorization covers implementation; preserve other plans.

## Outcome and UX
Studio completes Sources → Team review → Start. Upload saved organization exports/notes against a saved project, request a customer-agent proposal, inspect/edit roles and scope, approve creation/configuration, and start/stop customer workers. No credentials, terminal copy/paste, or JSON required on the normal path. JSON/evidence are optional details. Alternatives discussed: progressive single screen, conversation-first; default three steps.

Customer host installation/connection is a one-time local prerequisite. An offline/absent host is explicit; the browser cannot install software. Inference uses the already configured customer subscription/command, never cloud paid fallback. Source labels remain saved exports, not live Notion/Linear/Jira connections.

## Shared API contract (additive)
All commands use existing authenticated command API and idempotency. Owner-only; host runs with that owner's credential locally. Host identity and journal are endpoint/actor/config bound. No arbitrary browser commands or paths.
- register_crew_setup_host {host_id, instance_id, name, config_hash, backend, tools: string[]} -> host. backend codex-subscription | customer-command. Single live instance; instance lease heartbeat.
- heartbeat_crew_setup_host {host_id, instance_id} -> host; may mark offline through disconnect_crew_setup_host.
- get_crew_setup_control {setup_id} -> {hosts:[{id,name,online,backend,tools,config_hash}], jobs:[job], prepared: null | {job_id,host_id,config_hash,proposal_hash,runtime_plan_hash,roles:[{role_id,principal_id,reused,name,tools}]} }. Owner scoped, bounded latest jobs.
- request_crew_setup_job {setup_id,version,host_id,config_hash,action, proposal_hash?,runtime_plan_hash?,session_version?} -> job. Actions analyze (proposal + inactive preparation), prepare (after edits), activate (create+configure, no execution), start (start workers + first task, requires delegation already enabled and exact session_version), stop. Approval pins both exact hashes; Core checks current setup and proposal. No two nonterminal jobs per setup/host. Old/unknown jobs are not silently duplicated.
- claim_crew_setup_job {host_id,instance_id} -> {job:job|null}. Atomic; one owner, setup, host/config/instance. Started jobs stay running/held across lost heartbeat; no automatic failover/reinference.
- finish_crew_setup_job {host_id,instance_id,job_id,status,summary,prepared?} -> job. status succeeded | held | cancelled (stop-only recovery); summary bounded, no raw exceptions/credentials. prepared schema as above without job_id/host_id/config_hash (server fills).
- resume_crew_setup_job {job_id} -> job (held -> queued, same ID/journal; no automatic new provider call).
Job: id, setup_id, host_id, config_hash, action, status (queued/running/succeeded/held/cancelled), proposal_hash?, runtime_plan_hash?, version (setup version pinned), summary, prepared?, instance_id when claimed.
Do not register these in customer Bot/Mentor profiles. Human owner and setup host only.

## Tasks and acceptance
- [x] Core queue: owner/project isolation, pinned basis/approval, one active operation, lease/instance fencing, idempotent retries, replay, no model/shell inside transactions. Tests first.
- [x] Customer setup host: trusted local config, private persistent journal, reuse analyze/prepare/activate/configure/start_work, genuine BotWorker lifecycle; sanitized public receipts; recovery never replaces uncertain provider receipt; CLI one-time connection. Tests with real Core and explicit fake inference.
- [x] Studio: three steps, connected host selector, actual action buttons, compact role editing, errors/offline/queued status, exact approval, preserved form values, responsive and accessible. JS tests + browser check.
- [x] End-to-end: sources → propose → approve → configure → start → first task, no implicit grants/execution, stop; report synthetic vs actual model evidence separately.
- [x] Independent security/correctness review, regression/build, docs and UX options.

## Threat boundaries
Owner browser requests a bounded action, never a command/path. Customer process owns inference auth and worker secrets. Source/model text is untrusted; existing schema/evidence/scope checks remain. Only public allowlisted summaries enter Core/UI. No cross-origin loopback bridge, CORS changes, secret display, or cloud execution. Preserve all old setups and Bot identities. Restore/retry from private journal; if host loses state or provider outcome is unknown, hold visibly rather than regenerate tokens/LLM requests.

## Implementation and verification notes

- Added `crew_setup_hosts` and `crew_setup_jobs` additive event projections. Existing ledgers need no destructive migration. Existing project/team/role/task models are reused.
- A claimed Start with changed execution settings can enter explicit stop-only `recovery_only` reconciliation. It preserves the immutable request and original private receipt, requires all activated runtimes fenced before cancellation, and permits a separately reviewed new Start. Missing journals remain held.
- Cancellation before claim and explicit journal retry are exposed in Studio. Repeated successful Start/Stop intents retire UI keys; uncertain responses keep them. Host instance changes and offline worker recovery no longer deduplicate to obsolete success.
- UI uses `session_details.link.project_id` (verified against actual HTTP responses); no artificial project field on the session.
- Fixed absent credential-expiry handling to avoid a two-clock race during team activation; an advancing-clock regression verifies it.
- Host CLI imports execution modules lazily, preserving ordinary CLI behavior and avoiding startup overhead for unrelated commands.
- Independent review: final scoped approval; no remaining required findings.
- Final shared-worker review: explicit Stop fences owned runtimes even when reused by other projects; partial-start rollback detaches only the new reference. Failed stop acknowledgements retain references for retry. All 17 host tests passed; Studio and the guide explain the cross-project stopping effect.
- Browser: real HTTP/Core/host/BotWorker, synthetic inference. Sources → Suggest → role edit → Prepare → Create → Start → Stop → Resume; exactly one first task, two Bots, matching replay. No real-model or engineering-speed claim.
- Responsive: 320/768/1024/1440 CSS-pixel checks, role editing on narrow layout; temporary viewport restored.
- User UX proposals documented in docs/STUDIO_CREW_ONBOARDING.md; three steps implemented by default.
- Final regression: 1,721 Python tests OK (8 skipped); 57 JS tests pass; wheel built and modules/assets matched working source; diff check clean. Earlier CLI eager imports fixed. Two intermittent existing learning-transfer failures passed isolated and final full rerun; cause remains unknown, recorded in acceptance.
- Changed-source privacy scan found no project-specific names, user home paths, private keys, or selected provider-token patterns. This bounded scan is not a claim of comprehensive security certification.
