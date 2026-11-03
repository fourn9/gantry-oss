# Studio Bot workflow

Studio connects a project team to customer-owned agent runtimes. A Bot is a
persistent role and memory identity; a task is one request. Opening Team, selecting
a Bot, browsing a conversation or mentioning someone does not start a process.
Mentor remains an optional submitted-change review service, separate from Crew.

## Where to use it

- **Project → Team**: inspect roles, reporting hierarchy, file scope, customer
  principal and online/offline status. The project owner can add/edit members,
  configure an exact runtime manifest and enable previously delegated execution.
- **Work / CAD part / code line → conversation → Ask a Bot**: queue a read-only
  question anchored to that work, state, file hash and selection. The answer
  returns to the same conversation and the requester’s Inbox.
- **Assign work**: specify purpose, editable paths and completion conditions.
  Only the work author/assignee or project owner can delegate this operation,
  from the latest work checkpoint and within its scope. The source work remains
  intact. The Bot returns a separately shared candidate with a baseline diff.
- **Hand off**: request transfer to another authorized Bot, or to the same Bot
  after replacing its stopped runtime. Source output is fenced immediately.
  Source executor or project owner must explicitly acknowledge the process has
  stopped and summarize saved/unfinished work. The target runtime then accepts.
  Closing a panel is never a handoff or a process stop.

Queued work can exist while its runtime is offline or execution is disabled.
An expired connection while a task is running is shown as connection loss,
not successful execution. Reconnection does not silently retry uncertain work.

## Customer setup

Use a dedicated **agent-bot** principal for each independently executing Bot.
Request/grant that identity through the existing `gantry-cloud request` and
`gantry-cloud grant` workflow described in [Cloud operations](CLOUD-OPERATIONS.md); grant only the
intended development session and zones. Team setup selects existing authorized
agent identities and never generates or displays their credentials.

1. Import/connect the project and create work using existing Studio/workspace
   operations. Confirm recorded requirements, file scope and missing information.
2. Grant the customer agent principal access to the development session. Bind it
   in Team. Define one project lead, then managers and specialists below it.
3. On the customer machine, save a private BotWorker configuration. Existing
   backends are `codex_subscription` and `external_agent` (an explicitly installed
   JSON bridge). This release adds no paid provider fallback.
4. Print the manifest and submit that exact result in Team → Runtime:

   ```sh
   gantry-crew bot-worker --config /private/bot.json --journal /private/journal --manifest
   ```

5. Enable assigned execution in Team → Execution settings. Existing actor,
   recipe, scope and requirement constraints still apply. A blank execution
   count limit means no fixed count limit; concurrency is explicit.
6. Start the customer worker:

   ```sh
   gantry-crew --url http://127.0.0.1:8765 --token-file /private/agent.token \
     bot-worker --config /private/bot.json --journal /private/journal
   ```

The worker polls the existing Bot task queue, claims a fenced task, restores its
saved state, runs the configured customer bridge, captures changed files and
returns a structured report. A customer agent using MCP may perform the same
contract through `mcp --profile bot --require-agent`.

Runtime replacement preserves Bot ID and memory. Stop the old worker first.
An online lease or active execution cannot be silently reset by Runtime settings.
For uncertain execution, use the existing explicit BotWorker recovery operation;
for changing the executor, use acknowledged handoff. Never put credentials in the
public environment manifest.

## Execution and ownership

`studio_request_bot` records the contextual thread and an existing `bot_task` in
one transaction. No new scheduler or Mentor job is created. Manager Bots may
return subordinate assignments, independent candidate IDs and comparisons using
existing Crew contracts. Child reports wake their waiting manager. Candidate
selection and engineering judgment belong to the Bot, not to the UI or Core.

Core verifies the current identity, state, scope, dependency and delegation. It
holds stale work; it does not decide whether a design is physically correct.
Completion, sharing, test success and formal adoption remain separate.

**Ask is restricted at both the worker and Core API.** Because a normal customer
MCP credential is reusable rather than task-scoped, an agent principal answering
Ask is reserved for that read-only task while running, held or awaiting handoff.
Other writes using that principal are denied. Use separate dedicated principals
for parallel execution. Finishing, stopping/reconnecting its runtime, recovering
its own task and acknowledged handoff remain available. Recorded experience is
still retained; the optional pre-task learning planner is skipped for Ask.

A customer-installed process is owner-trusted and is not an OS sandbox. Gantry
cannot stop arbitrary processes on a customer PC or prevent an independently
credentialed agent from acting outside Gantry. The source-stop acknowledgment is
an explicit assertion with an audit record, not proof of remote termination.

## Records and API additions

Existing organizations, persistent Bots, bindings, runtimes, tasks, changes,
states, memory, comments and notifications are reused. New append-only projected
records are `studio_bot_requests` and `bot_handoffs`.

| Command | Contract |
| --- | --- |
| `studio_team` | Authorized project team and public runtime presence |
| `studio_setup_team` | Owner-only atomic team proposal/activation with a configuration token |
| `studio_execution_policy` | Owner-only versioned execution enablement/concurrency/limit |
| `studio_request_bot` | Exact work version, state, selection, mode, Bot, purpose, scope and completion |
| `request_bot_handoff` | Versioned request fences source; does not stop its process |
| `acknowledge_bot_handoff` | Source/owner states it stopped; saves summary and unfinished work |
| `accept_bot_handoff` | Target accepts with its current runtime fence |
| `list_bot_handoffs` | Authorized paginated handoff list for a Bot |

Handoff keeps a source/successor chain, predecessor reports and child evidence.
Saved edits become a new candidate rooted at the original baseline, so completing
without another edit still returns the earlier work and diff. Dependencies follow
the successor chain; old required tasks do not remain permanently cancelled
blockers. A cancelled handoff leaves the acceptance queue.

Existing databases need no destructive migration: the two projection collections
are additive. Replay reconstructs them from new events. Back up before upgrading;
older binaries cannot be assumed to understand these new event effects.

## Boundaries

- No native CAD editor, cloud VM provisioning, provider login UI or automatic
  customer-process installation is added.
- Supported saved CAD sources and STL/OBJ previews keep existing behavior.
  Licensed CAD APIs and customer tool bridges still require their actual setup.
- File capture does not imply capture of all tool calls or unsaved edits.
- Reasoning quality, physical correctness and development speed need real project
  evaluation. Deterministic integration tests establish the execution contract,
  not engineering intelligence.
