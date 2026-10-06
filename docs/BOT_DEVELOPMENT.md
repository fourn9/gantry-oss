# Gantry Crew: independent Bot development

Install this source revision to use the two entry points. No hosted Gantry service
or customer agent is started merely by installing the package.

`gantry-ledger` is the customer-led review entry point. It retains local `connect`,
project checkpoints, submissions and Mentor review. No organization is required.

`gantry-crew` is the delegated development entry point. It uses permanent Bot
identities and customer runtimes, but its assignments, reports and decisions use
`bot_tasks`, not `mentor_jobs`. No review team, submission, Mentor worker or Mentor
model is needed. Both entry points reuse Core, storage and authenticated APIs.
The original `gantry` commands remain available for compatibility/administration.

## Try the complete loop without a model bill

```sh
python -m pip install .
python examples/bot_development_loop.py --output /new/private/bot-demo
```

The example starts actual customer bridge subprocesses, edits two files, collects
departmental reports, wakes the integration Bot, integrates the shared candidates,
restores the result and verifies replay. Reasoning is explicitly synthetic, not an
LLM or engineering evaluation. `report.json` reports zero Mentor jobs. The example
directory also contains credentials and private journals; keep it private.

## Owner onboarding

The following are API operations, callable through `gantry-crew --url URL
--token-file OWNER_TOKEN call OPERATION --input request.json --key REQUEST_ID`.
Schemas are in [api-contracts.json](api-contracts.json); the example supplies every
field and demonstrates the full authenticated owner approval chain.

1. Initialize/serve a local or customer-hosted ledger with `gantry-crew init` and
   `gantry-crew serve`. The default address is loopback. Keep the owner token out of
   model input and customer worker credentials.
2. Create dedicated agent principals using `agent-request --profile bot`, review
   and activate their proposals as owner. Existing agent tokens do not silently
   acquire new commands. The Bot profile exposes no Mentor commands, owner setup
   or human adoption. Core also rechecks permissions on every API call.
3. Capture saved native files with `capture-workspace`; use `connect_development`
   and `initialize_continuity` to fix the state, hierarchy, requirements, constraints
   and unknowns. Explicitly choose the session's actors, write scope and concurrency.
   `max_executions: null` has no Gantry execution-count cap; finite existing limits
   remain enforced. Provider quotas and per-call timeouts still apply.
4. Reuse/create the organization and permanent Bots with `configure_organization`
   and `configure_bot`. Parent IDs define the reporting hierarchy; they grant no
   extra tool access or automatic management authority.
5. `configure_bot_project` fixes the session, organization, goal, acceptance,
   lead Bot and enabled status. It requires an initialized owner-matched state.
6. `bind_development_bot` assigns each Bot its principal, write scope and explicit
   `can_assign` / `can_integrate` capabilities. Managers may assign within their
   subtree. Workers can answer peers without gaining their authority.
7. Configure each customer runtime as below. Then assign the first `plan` task to
   the lead Bot using `assign_bot_task`. A saved proposal/profile alone starts no
   process. The customer explicitly starts workers or installs an opt-in service.

No Fusion, GitHub write, electrical CAD or firmware tool installation is performed
by these steps. Register the customer's existing tool bridge separately. Acquiring
a file is not proof that its original tool can reopen or edit it.

## Customer execution and MCP

For the opt-in iterative model/tool path, directed consultation, attributed decisions
and atomic team onboarding, see [Crew organization](CREW_ORGANIZATION.md). The
single-response customer bridge below remains supported for existing installations.

Use the runtime setup in [Persistent Bots](PERSISTENT_BOTS.md), adding
`"workflow": "bot_development"` to its configuration. Generate and approve the
environment manifest with the same configuration and executable used at runtime:

```sh
gantry-crew bot-worker --config /private/bot.json --journal /private/bot-journals --manifest
# Owner approves configure_bot_runtime with that exact manifest.
gantry-crew bot-worker --config /private/bot.json --journal /private/bot-journals
```

The external customer bridge receives JSON `{context, schema}`. Context includes
the task, exact state, private workspace path, team scopes, child reports, available
candidate changes, bounded source previews and persistent experience. The bridge
returns the required structured answer. It may return UTF-8 file edits or use its
installed tools to change the provided workspace. Native files are retained by
normal artifact capture. A configured subscription backend can return edits and
plans; it is not an automatic native-CAD operator.

The installed customer bridge is trusted local code, not an OS sandbox. Core
checks the saved diff against the task scope before accepting it. That check does
not undo external host operations: customer tool/OS permissions must bound them.
Unknown external side effects remain unknown. Runtime configuration is versioned
and its executable hash checked. No provider is selected implicitly or paid by the
publisher. A changed environment requires a new owner-approved manifest.

For a customer agent handling its own tools/lifecycle, use
`gantry-crew ... mcp --profile bot --require-agent`. It can claim an assignment,
call `checkpoint_bot_task` during work and return a report. Claims require an active
runtime fence. The checkpoint API retains incomplete/failed milestones. The bundled
worker captures saved files at return; it explicitly marks intermediate tool calls
as missing unless the bridge submits them. Source previews prioritize task
dependencies and write scope, and report omitted counts plus a bounded filename
sample. STEP/PDF/binary assets are restored but are not treated as text prompts.
Full authorized context, including manifests and restore receipts, is saved next
to the private workspace and referenced by path and canonical-content hash. An
agent can retrieve it without injecting every file hash into every model request.
Remembered tasks also retain their complete path/hash inventories there. The
inference input previews at most 20 entries per memory, prioritizing task
dependencies and scope, and provides counts, truncation flags and a JSON pointer
with the original record hash. Observations and limitations are preserved; a
preview is not evidence that omitted inputs match the current state.

The review service defaults to the separate `review` MCP profile. Product entry
points curate onboarding; scoped principal capabilities and Core are the actual
authorization boundary, not the executable name.
Both `mcp` and generated `agent-config` default to the service's own profile.
Unknown runtime workflows are rejected. `gantry-crew` rejects an explicitly
legacy-review runtime instead of changing its meaning. When generating an opt-in
background service, the saved config must explicitly contain
`"workflow": "bot_development"`, including when it uses the generic `gantry`
executable. The original `gantry bot-worker` without a workflow filter remains the
compatibility path for existing installations.

## Planning, reports and decisions

An `assign_bot_task` request fixes `state_id`, assignee, kind, title, completion
conditions, write scope, file dependencies and prerequisite task IDs. A manager
returns `status: waiting` with child `assignments`. Each child runs independently
from its fixed input. When all children report completed/failed/blocked/cancelled,
the parent is pending again with the actual reports and candidates. The next model
call can continue, request more work, report a blocker, or integrate shared changes.
Each attempt's rationale and applicable experience remain in Core.

`send_bot_message` stores peer questions, answers, objections, dependency waits,
handoffs and reports against a task. A reply does not silently resolve a blocker;
its author or the owner resolves it with evidence. Changed discussion invalidates
an in-flight answer. Reassign from the saved checkpoint under the new context
instead of accepting stale inference. A handoff message documents intent; it does
not transfer execution authority or cancel an already running process.

`finish_bot_task` records the outcome and creates provisional Bot experience.
Owner-enabled organization reflection sharing remains opt-in. Next-task onboarding
retrieves authorized experience; it does not train model weights or grant authority.
Integration reuses existing conflict/dependency checks. Unknown compatibility and
untested inputs remain unverified. Completed work, an integrated state and human
formal adoption are distinct. A worker's claimed success is not a physical pass.

Integration uses a separate task without its own file edits or previous integrated
output. Share the edited candidates first, then assign an integration task with
scope covering their actual changes. Continue from the resulting state in a new
task. This keeps fixed input/dependency checks intact and prevents an integration
report from overwriting a task's own saved edits.

## Interruptions and migration

- Stop the old process before recovery. Keep its per-Bot journal, tool environment
  and credentials. A runtime fence prevents two active instances owning one Bot.
- Pending tasks survive offline periods. Running/held tasks are not blindly replayed.
  Use `gantry-crew bot-worker --config ... --journal ... --recover-job TASK_ID
  --confirm-stopped "Previous worker and child processes stopped"`.
- Recovery enforces the same workflow filter as normal dispatch. A Bot-only worker
  cannot recover a legacy Mentor job, and an explicitly legacy-only worker cannot
  recover a Bot assignment. Use the original worker and journal for that workflow.
  Legacy retry/verification overrides are rejected for independent Bot recovery.
- Recovery reconciles lost claim/checkpoint/finish acknowledgements and reuses
  saved answers. An uncertain model/tool result without a saved receipt is held;
  the new path has no automatic retry-inference override. Investigate and explicitly
  create a new task if another execution is needed. Known active provider processes
  block recovery. Changed scope, baseline, hierarchy or discussion needs a new task.
- Disable a Bot project with `configure_bot_project`, or stop a task using
  `cancel_bot_task`. Old output cannot commit. Already-started customer processes
  need the customer's stop/reconciliation procedure. Cancellation is not recursive;
  inspect and stop child assignments explicitly.

Existing Mentor tasks, review bindings, Bot IDs and memories retain their meaning.
They remain on the legacy worker route. No existing connection is repermissioned.
New tables/indexes are additive and replayable; old events and artifact hashes are
unchanged. Back up before upgrade. Older binaries cannot read the new event tables,
so do not downgrade an updated ledger in place.

For existing review work, retain its saved state and complete/reconcile its jobs.
The simplest handoff is a new Bot development session initialized with those exact
artifact bytes and context, with the source state recorded in event `basis`. Give
the new session explicit delegation and a new assignment. This is a new work item,
not an automatic transfer of an in-flight review job. A session cannot enable both
automatic review dispatch and Bot development. Independent sessions can share a
ledger and run concurrently without converting each other's queue entries.

## Verified boundary and remaining limits

`tests/test_bot_development.py` verifies hierarchy, parallel edits, integration,
real customer subprocess execution, scope checks, stale input rejection, discussion,
saved experience, interruption/acknowledgement recovery, restore and replay without
Mentor. Existing review/Bot compatibility tests continue to run separately.

The runtime mechanics and saved records are real. These regression tests use synthetic model answers.
A separate [subscription fixture](CREW_ORGANIZATION_ACCEPTANCE.md) verifies real
Bot reasoning and exact-state tool checks. General planning quality, development speed, native CAD automation and firmware
toolchains need their own integration validation. No automatic optimal-organization
learning, arbitrary process-memory restoration or cross-service live-job transfer
is claimed.
