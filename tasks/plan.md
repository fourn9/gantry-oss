# Organization and personal Bot foundations

## Current follow-up: independent services

Reuse the following historical foundations, but remove Mentor as a dependency of
Bot development. Add separate service CLI/MCP profiles, owner-approved development
bindings and a dedicated task/report queue. Managers delegate through fenced task
reports, receive child results and select the next work. Workers restore exact
states, capture changes, save experience and reconcile interruptions. Reuse Core
authorization, immutable states, integration checks and adoption boundaries.

Storage changes are additive. Legacy Mentor jobs retain their handlers; no old
permissions or task histories are reinterpreted. Verify independent operation with
real file edits and customer-bridge subprocesses using labeled synthetic inference,
then run the existing regressions. Live model quality and development speed are not
established by these tests. See `docs/BOT_DEVELOPMENT.md` and `tasks/validation.md`.

## Historical v3.0.0 implementation plan

Extend the existing authenticated review team and durable job queue. A Bot is a
versioned role with project context and evidence-backed experience; the customer's
agent supplies inference. This change does not train model weights, grant new
permissions through memory, or run a paid service.

1. Preserve unlimited local review submissions, including legacy connections.
2. Add optional role profiles to the existing team. Store inferred team proposals
   separately; only the human owner can activate them. Existing teams remain valid.
3. Assemble role onboarding from the exact development state, hierarchy, progress,
   bounded memory and communications. Put it on the actual job/review input path.
4. Add durable questions, answers, objections and handoffs. Unresolved blocking
   messages prevent a technical OK and dependent execution; messages do not grant
   authority. Keep existing leases, recovery and identity checks.
5. Preserve evidence-backed personal/team lessons, including contradictions, and
   automatically reuse applicable experience on the next review. New experience is
   provisional and cannot edit policy, requirements or adoption.
6. Expose the path through CLI and MCP for customer agents; verify hierarchy,
   handoff, next-task memory, stale inputs, permissions and deterministic replay.

Storage is additive: profiles live on versioned review teams, and new projections
hold proposals, communications and memories. Existing events/artifacts are retained.
No public examples or fixtures use private project data. Full autonomous project
planning, automatic organization activation and measured speed gains are out of scope.

## Persistent organizations, Bots and customer runtimes

Keep the existing review queue and checkpointed worker. Add an owner-controlled
organization and permanent Bot identity, bind that identity to session roles,
reuse evidence-backed experience across authorized sessions, and explicitly share
organization lessons. A binding is not an access grant. Source access is checked
again at retrieval; memories never become executable instructions or permissions.

Give each Bot a versioned customer-owned environment declaration and durable local
workspace/journal. A customer-started background worker discovers assigned jobs
without a chat prompt. Fence the runtime, recheck delegation before applying edits,
retain queued work while offline, and hold uncertain interrupted executions for
recovery. Reuse submission -> specialist -> coordinator -> developer -> reflection
triggers rather than run inference on every log. Support a replaceable inference
bridge plus the existing opt-in subscription runner. No provider is enabled by default.

Verify a real multi-role edit/review/reflection loop with labeled fixture inference,
cross-session continuation from a fresh process, concurrent runtimes, offline queues,
revocation, stale profiles/environments, scoped memory, and deterministic replay.
This adds projections; it does not rewrite existing ledgers or connect separate
customer stores automatically. No model-weight training or arbitrary desktop-app
startup is implied.

Validation: focused synthetic end-to-end tests with real Core/storage/worker paths,
then existing regression suite and security/public-source checks. Fixture inference
is labeled explicitly; no model calls are needed for tests.
