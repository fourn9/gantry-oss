# Gantry Studio implementation

Reference: user-approved interactive Studio mock and 2026-11-03 request.
Skill source: Addy Osmani agent-skills, reviewed revision
2686b620fc1fed2e8f60c704839c766b8594c6b6. Existing approvals authorize this work.
Starting point: 9595a1c; clean tree. Preserve prior design-assessment work and private ledgers.

## Design and scope

One English product workspace: project hierarchy → Structure / Work → CAD / Code / Checks.
206px neutral sidebar, 12–13px text, thin dividers, artifact-first detail. Conversation
appears only on selection; stacks below artifacts on narrow screens. No KPI/log cards.
Reuse immutable development states, changes, shares, checks and authenticated commands.
Changes are work; projects and existing execution sessions remain distinct concepts.
Existing operational pages remain reachable under a secondary workspace navigation.

## Capability map / order

| Module | Responsibility | Depends on |
|---|---|---|
| studio-state | Authorized project/work/hierarchy and version projections | existing Core |
| studio-sharing | Atomic file import/checkpoint and share with note | studio-state |
| studio-discussion | Version/file/part/line anchors, mentions, personal Inbox | studio-state |
| studio-ui | Artifact workspace, version comparison, responsive conversations | all above |

New commands reuse Core transactions and permissions. Conversations are additive
events, with exact work/state/file hash anchors; Inbox is a projection of mentions.
No external messaging. Unknown/changed anchors stay on their original version.
Browser import overlays explicitly selected saved files, preserves other files and
scope, reports uncaptured edits, and never changes adoption. Adapter checkpointing
and share_change remain supported. Native CAD editing stays external. Initial real
3D display supports saved STL/OBJ meshes; proprietary CAD requires an exported
preview. Unsupported/loading/error/disconnected states are explicit.
Anonymous fixtures only; the supplied mock's robot, people and results are not copied.

## Acceptance and tasks

- [x] Authorized APIs: work lookup, hierarchy, old/new states, scoped conversations and mentions.
- [x] Import saved files → checkpoint → review paths/hashes → share; stale versions rejected.
- [x] Studio navigation with structure selection, Work ownership/state, real artifacts.
- [x] CAD mesh selection/orientation/comparison; code before/after and correct line anchors.
- [x] Checks show exact-state applicability; work/share/check/adoption stay independent.
- [x] Inbox links exact work, version and conversation; drafts survive errors; old threads isolated.
- [x] Empty/disconnected/loading/failed/unsupported states, responsive 320/768/1024/1440px.
- [x] Runtime browser scenario on isolated anonymous ledger, regression tests, security review,
      packaging and docs with actual limitations.

## Verification

Python unittest (tests/test_studio.py and existing continuity/product/web suites),
Node tests (tests/test_studio_web.mjs), full regression suite after integration.
Local authenticated HTTP/browser scenario with anonymous saved artifacts; no paid
providers, external tool accounts or public push. Build using existing pip wheel.
Capture actual UI/screenshots; distinguish sample geometry from verified product data.

## Result

Implemented and checked on 2026-11-03. See `docs/STUDIO_UI.md` and
`docs/STUDIO_VERIFICATION.md`. Real browser import/share and exact-anchor Inbox
flow passed on an isolated anonymous ledger; native vendor integration remains
explicitly unsupported without a saved preview. No public push in this task.

## UX review follow-up (2026-11-03, approved by “更新して”)

Keep the existing Studio visual language and implement the six reviewed fixes.
Source revision and skills remain the same as above; no migration or external service.

1. CAD selection and continuity (studio-ui): one file/part selection drives preview,
   comparison and conversation. Opening/closing discussions preserves camera/zoom.
   Plain wheel scrolls the page; explicit zoom buttons or Alt+wheel zoom the mesh.
2. Discussion discovery and updates (studio-state → studio-ui): version-bound comment
   markers/index; read-only activity polling with a small refresh notice. No background
   replacement of selected artifacts or unsent drafts. Old comments stay on old versions.
3. Reading and navigation (studio-ui): one-line revision note and expandable changed
   file list; aligned work/owner/leaf-scope/status; 12px key metadata; narrow conversation
   scroll/focus and a return-to-artifact action.

- [ ] Slice 1: reproduce camera loss, fix selection/camera and scroll, focused Node tests.
- [ ] Slice 2: authorized discussion summaries and non-destructive updates; backend and
      delayed-response tests (navigation, sign-out, draft retention).
- [ ] Slice 3: notes, changed files, list hierarchy, narrow navigation; browser verification.
- [ ] Review permissions/escaping/state anchors, targeted regression, build, documentation.

Commands: `node --test tests/test_studio*.mjs`; `PYTHONPATH=. python3 -m unittest
 discover -s tests -p 'test_studio.py'`; build with `python3 -m pip wheel . --no-deps`.
Run the existing regression suite once after integration. Use isolated anonymous ledger
and browser inspection; preserve historical data and public/private source boundaries.
