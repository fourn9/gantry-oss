# Persistent personal Bot development

Started 2026-11-16; implementation proceeds in an isolated checkout from 3e191ae.
This is an engineering design, not a claim of equivalence to Instinct or trained
model weights. Existing project requirements and human adoption remain canonical.

## Capability map

| Module | Responsibility | Dependency |
| --- | --- | --- |
| commitments | Bot-owned durable responsibilities linked to existing tasks; outcome-aware continuation | Existing identity, tasks, standing delegation |
| procedures | Conditional use/retirement of existing learned procedures with independent scoped evidence | Existing memories, peer checks, actual tool receipts |
| preferences | Human-attributed feedback, explicit task/phase/project scope, correction and withdrawal in future context | Existing project ownership, Bot identity and task context |
| continuous-work | Restart, reassess, delegate, execute, learn and continue using the same records | All above; existing Worker and sandbox |

Core validates identity, access, versions and evidence. Bots choose priorities,
solutions, consultation partners and assignments. Crew is the whole service;
there is no new central planner or Mentor dependency. Existing queue, tasks,
candidate states, tools, experience and journals are reused.

## Acceptance

1. A Bot records a responsibility, links actual owned/delegated tasks, restarts,
   sees changed outcomes and reassesses once under standing authority. A finished
   child is not a completed responsibility or formal adoption.
2. For an explicitly enrolled procedure, preferred status requires the stated
   scoped evidence; changed inputs or contrary evidence require reconsideration.
   Unenrolled memories retain the existing provisional apply/recheck/reject path.
   Self-ratings do not establish tested procedures. Retirement is persistent.
3. Human feedback distinguishes a one-task request from a continuing project
   preference. Corrections/withdrawals reach future Bot context. It cannot grant
   permissions or alter requirements. Peers cannot read private personal context.
4. Separate real model contexts can continue after restart using these records;
   no parent-written repair value or fabricated model output counts as autonomy.
   Deterministic execution tests and model observations are reported separately.

## Boundaries

Additive event-backed records, optimistic versions and existing idempotent APIs.
Preserve old working notes and all history; do not silently convert prose into
confirmed commitments or policy. No new dependency, paid API, external messages,
hardware operation, automatic permission expansion or deployment.
Customer workers must be running. Learning means contextual procedural adaptation,
not automatic model training or guaranteed improvement. Semantic memory synthesis,
held-out comparative procedure testing and organization optimization require their
own explicit contracts; a success receipt cannot substitute for those capabilities.

## Workflow

Follow Addy Osmani agent-skills revision
2686b620fc1fed2e8f60c704839c766b8594c6b6: specification, planning, incremental
implementation, TDD and review. Staff Engineer and AI Researcher are distinct AI
review roles, not consultations with real employees. The Principal role integrates
their contracts and rejects duplicate schedulers, duplicate memory databases and
unsupported claims of intelligence. All public examples are anonymous.

Tests: `PYTHONPATH=tests python -m unittest test_bot_commitments test_bot_procedures test_bot_procedure_flow test_bot_preferences -q`;
full regression: `python -m unittest discover -s tests -q`;
build: `uv build --wheel --out-dir /tmp/gantry-personal-wheel`.
Python modules live in gantry/, real Core/Worker tests in tests/, anonymous examples
in examples/. Use existing compact Python conventions and registered API contracts.

## Execution and ownership

The same persistent Bot identity survives projects/tasks; its current project
binding still defines what it may read/write. A human owner sets responsibilities,
constraints, standing authority and explicit preferences. The Bot chooses work,
consultation, delegation and procedure disposition. Core stores those choices and
checks their identities, versions and evidence. Existing Worker tasks execute them
and return checkpointed results; Crew is this whole collaboration, not an extra
manager. No Mentor call is introduced.

A normal cycle is:

1. A report, linked outcome, due responsibility or explicit project feedback wakes
   an already authorized Bot once. Held work suppresses replacement work.
2. Current state, scoped preferences, unresolved commitments and conditional
   experience enter its context. It can page responsibility history and peer work.
3. The Bot selects actions, delegates or asks another Bot. Existing sandbox and
   task authority apply; a memory or commitment cannot grant access.
4. Actual outputs/checkpoints return to the same task. The Bot reconciles the
   responsibility; finishing a child does not silently complete the responsibility.
5. Reflection creates conditional lessons. A Bot can explicitly select a procedure
   after an independent scoped check, or retire it. Changed conditions require a
   recheck. Future work receives that disposition, including with learning disabled.

## Data and APIs

- `bot_commitments`: current projection of a Bot-owned responsibility, acceptance,
  priority/reason, linked task IDs, due time, lifecycle and optimistic version.
  `bot_commitment_events` retains every explicit update and terminal-link retirement.
  It is distinct from engineering `bot_issues` and task execution status. Old prose
  commitments remain hypotheses; they are not silently migrated into this model.
- `bot_procedure_decisions`: append-only choices over **existing** procedure lesson
  IDs, with basis, author, prior decision, peer-check IDs and tool receipt IDs.
  States are candidate/preferred/retired. Preferred means scoped, attributed support,
  not physical validation, general effectiveness or formal adoption.
- `bot_preferences`: owner-authored, versioned task/project feedback. Disable or
  replace it explicitly; the event log retains history. It is project-local, not
  a global psychological profile. It must not contain credentials or unrelated
  personal information. Withdrawal prevents future use, not historical erasure.

Bot commands: `create_bot_commitment`, `update_bot_commitment`,
`get_bot_commitment`, `list_bot_commitments`, `record_bot_procedure_decision`.
Owner command: `set_bot_preference` (see generated API contract for exact fields).
The action loop exposes `commitment_create`, `commitment_update`, `commitment`,
`commitments`, `procedure_decision`; project/Bot identity is supplied by runtime.
Prepared learning is discarded if visible responsibilities, outcomes or feedback
change. The action loop checks feedback basis before executing a prepared answer.
Already executing/uncertain effects remain subject to the existing recovery protocol;
a preference edit is not an emergency stop or a permission revocation.

## Upgrade and use

No destructive migration or data rewrite is required. Indexed records and replay
use the additional collections. Preserve the ledger and journals as with existing
upgrades. Existing scoped credentials do **not** gain new commands: an owner must
explicitly grant the desired new commands through the normal principal/delegation
change process. New commands not granted to the executor are omitted from its
advertised action catalog. Existing limited Bots retain their old capabilities.

Use a customer-owned Worker with `workflow=bot_development`, `agent_loop=true`,
`experience_learning=true`, and `personal_continuity=true`; keep its authorized
runtime configuration and journals. Configure standing authority with existing
`configure_bot_continuation` and human feedback with `set_bot_preference`.
No new Studio settings screen or unattended machine startup is installed by this
change. Restarting a Worker reuses the existing identity, ledger and journals;
without an online authorized Worker, pending work stays pending.

## Specialist review decisions

- Staff Engineer: replace free-form duties with task-linked lifecycle and one-shot
  reassessment. Accepted; reuse the queue instead of creating a second scheduler.
- AI Researcher: separate reflected hypotheses, scoped evidence and explicit
  procedure choices. Accepted; self-rated helpfulness cannot establish effectiveness.
- Cross-review found missing pagination, ordinary-context procedure visibility,
  changed-input invalidation and read-only consultation guards. These were fixed
  before the final gate. Legacy plans cannot silently ignore newly added feedback.
- Principal: preserve scope and provenance, and keep owner preferences separate
  from requirements. Existing credentials are never widened by migration.

[Reflexion](https://arxiv.org/abs/2303.11366) motivates using feedback and episodic
text memory; [ACE](https://arxiv.org/abs/2510.04618) motivates incremental reflection
and contextual playbooks. These are design influences, not evidence for Gantry's
engineering efficacy or a claim about Instinct's private implementation.

## Remaining development toward long-lived personal Bots

| Area | Current implementation | Further work |
| --- | --- | --- |
| Ongoing responsibility | Durable task-linked duties and outcome-aware wakeups | Evaluate prioritization across many simultaneous project goals |
| Experience adaptation | Conditional lessons, scoped peer checks, explicit reuse/retirement | Automatic semantic consolidation and conflict resolution with traceable provenance |
| Personalization | Explicit owner feedback, scoped correction/withdrawal | Propose inferred organizational habits for review; do not silently convert observations to permanent rules |
| Learning effectiveness | Existing paired evaluator, new functional lifecycle tests | Held-out, role-specific longitudinal evaluation before claiming cumulative improvement |
| Efficiency | Indexed/paged responsibility retrieval; no new memory database | Reduce repeated context and idle bookkeeping; measure on the current performance branch separately |
| Product integration | Studio Team guidance, linked lessons, standing delegation, CLI/API and worker paths | Production integration and longitudinal customer evaluation |

Explicit limits: 20 active commitments in the initial context (more are paged),
40 applicable preferences, existing bounded lexical memory retrieval. None of these
is an all-project omniscient planner. The one-observation report is in
[PERSONAL_BOT_VALIDATION.md](PERSONAL_BOT_VALIDATION.md).

## Personal guidance in Studio

Open **Team**, choose the named Bot, then **Guidance** as the project owner.
Configure its standing responsibility, permitted paths, completion conditions and
optional routine. A customer Worker with personal continuity enabled must be
running for scheduled work. A routine becomes due at the next interval; an
offline Worker can pick it up on reconnect.

- **Owner guidance** records the author, reason, version and scope of an instruction.
  Each topic resolves in order of specificity: task, phase, project. A phase is the
  exact `context.environment.development_phase` on the task's pinned input state.
  Withdrawing an exception reveals the applicable wider instruction. Edits require
  the expected version. Existing unscoped legacy IDs keep their update path.
- **Recent lessons** shows a lesson's hypothesis, conditions, evidence IDs and source
  task. **Correct this lesson** attaches the owner's words to its immutable memory ID.
  The scoped correction reaches both the ordinary Worker and its learning planner.
  While it applies, the planner may recheck or reject the old procedure. Withdrawing
  guidance never establishes that the old lesson was correct.
- **Recent work** shows recorded actions, declared reasons and any explicit links
  from a lesson to an action. A delivered preference snapshot records availability.
  A Bot's report of using it is a separate observation.
- Explicit guidance belongs to the development session, named Bot and bound executor. A separate project session needs its own owner guidance. Studio shows up to 10 recent
  lessons plus accessible lessons used by the selected task, 20 recent tasks, up to 20 actions and use receipts per selected task,
  and paginates instructions 40 at a time.

**Skill.** A reusable procedure describes what to inspect, its applicability,
disconfirming conditions and source observations. The Bot may propose and revise
these procedures. Its own guesses about an owner's preferences stay provisional.

**Harness.** The Worker binds the input state and effective owner guidance to
prepared work. Core checks the guidance digest in the same transaction that saves
a pinned checkpoint or terminal report. The iterative Worker reconsiders stale
prepared actions; a single-response external bridge can be held for recovery when
its previous side effects are uncertain. Independent peer evidence, required
checks, tool permissions and formal adoption keep their existing contracts.

**Background reflection.** After a reported attempt, the asynchronous Worker
compares its plan, current owner guidance, action receipts and up to three earlier
task outcomes from the same bound project and executor. It can retain a conditional
lesson, link a contradiction, or extract nothing. The saved lesson identifies the
guidance snapshot and previous reports supplied for comparison. A reference shows
what was presented; the action-use receipt records what the Bot reports using.
Lessons influenced by private guidance or earlier outcomes stay private on the
automatic sharing path. Work continues with persistent memory across model calls;
this does not update model weights. The design draws on [Anthropic's discussion of
background memory consolidation](https://www.anthropic.com/research/components-of-agent-memory).
