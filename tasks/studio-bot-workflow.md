# Studio Bot workflow — accepted implementation plan

Reference: Addy Osmani agent-skills revision 2686b620fc1fed2e8f60c704839c766b8594c6b6;
using-agent-skills, specification, planning, incremental implementation, TDD,
interface design, frontend, security and code review. User approved the ordering.
Existing incomplete plans and the separate guided-onboarding work are preserved.

## Objective and contracts

Project Team exposes persistent customer-owned identities, hierarchy, delegated
scope and runtime presence. A contextual Ask creates a read-only Bot task;
Assign work creates a version-pinned scoped development task. Ordinary comments
remain comments. Clicking a conversation or changing the selected Bot does not
start, transfer or stop execution. Task status and runtime presence are separate.
Results return to the original work/version/selection with links to separate
candidate changes. Sharing and completion do not imply verification or adoption.
Mentor is optional and is not invoked by this path.

Reuse organizations, persistent_bots, bot_bindings, bot_tasks, customer BotWorker,
state/checkpoint/share, scoped conversations and existing Core transactions.
Add request and handoff records; no new queue or duplicate Bot memory model.
Team setup uses existing owner-approved principals and existing delegation; it
cannot create credentials or expand session tool permissions. Customer processes
are not launched by browsing Studio. Offline requests remain queued.

## Ordered slices and acceptance

- [x] 1. Team and contextual requests: expose project team; owner setup; Ask has no
  write/delegation/integration capability; Assign has exact baseline and scope;
  deny unauthorized/stale requests; retry is idempotent. unittest API scenarios.
- [x] 2. Return path: actual customer worker reads version/anchor/question, records
  intermediate checkpoints and final report, exposes candidate diff and notifies
  requester only when action is relevant. No Mentor and no implicit adoption.
- [x] 3. Handoff: source execution fenced, explicit stopped/checkpoint acknowledgement,
  target acceptance, immutable history and preserved unfinished context; prohibit
  parallel ownership. Runtime replacement keeps identity/memory and cannot silently
  reset an online lease. Offline queue/restart and stale finish regression tests.
- [x] 4. Compact UI: Team at project level; Ask/Assign in selection panel; queued vs
  online states; results and handoff controls; runtime setup instructions. Existing
  CAD/Code/Checks and conversation navigation preserved. Node and browser tests.
- [x] 5. End-to-end: manager/specialist and independent candidates use this route;
  real subprocess edits/checks, restart and result retrieval. Explicitly synthetic
  reasoning where used. Native customer tools/licenses remain unverified.
- [x] 6. Review and integrate without overwriting concurrent onboarding edits;
  focused and full tests, package checks and documented runtime evidence.

## Security and verification

Trust boundaries: user input, model reports, tool output, saved source text and
customer process. Apply current principal/session/scope/version checks atomically.
No credentials or runtime fences in public team views; output encoding in UI;
request content and memories never grant authority. Saved results are evidence,
not instructions. Local external bridges remain owner-trusted processes, not an
OS sandbox. No paid provider, automatic deployment or physical action.

Commands: PYTHONPATH=tests ../gantry-security-env-20261024/bin/python -m unittest
 test_studio_bots -v; node --test tests/test_studio*.mjs; python -m unittest discover
 -s tests; build from clean source into an external wheel directory.

## Completion evidence

Implemented and integrated on 2026-11-04. Full integrated regression: 1,310 Python
tests (8 environment skips), 39 Node tests; final Ask working-memory correction
verified by 120 focused/continuity tests. Clean-source wheel and import smoke pass.
Browser exercised real HTTP workers, line-scoped Ask, assignment, acknowledged
handoff, returned diff, Inbox navigation and a narrow viewport.

Required review findings corrected: direct API Ask bypass, saved candidate loss
on handoff, cancelled predecessor dependency blocking, HTTP-browser intent IDs,
Ask reconnect/handoff blocking, and human-principal Bot ambiguity.

Concurrent guided onboarding preserved. Existing ledger backed up and replayed
before local preview upgrade. No source publication, paid model call, native CAD
claim or speedup claim. See docs/STUDIO_BOT_WORKFLOW_VERIFICATION.md for evidence
and explicit fixture/model boundaries.
