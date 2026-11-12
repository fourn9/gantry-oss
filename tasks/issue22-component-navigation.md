# Issue 22: component-first Studio

Source workflow: Addy Osmani agent-skills revision `2686b620fc1fed2e8f60c704839c766b8594c6b6`; using-agent-skills, specification, planning, incremental implementation, TDD, frontend UI, security and code review. User authorization covers the issue's component-first design and Structure removal.

## Acceptance and boundaries
- Component selection opens related work; no work opens Files; multiple work items expose a compact picker.
- Work / Files / Requirements share component and explicit saved-state context; legacy Structure routes resolve to this flow.
- Tree selection has green styling, a non-colour indicator and aria-current; file/CAD selections update component.
- Files and Requirements use a single item picker; existing exact anchor hashes/revisions, Inbox pins, drafts, history, comparison, imports and authorization remain intact.
- Work CAD / Code / Checks remain available, with Related and Discuss contextual panels and advanced details secondary.
- Navigation and panel focus/closing work at 320px; mesh orbit/zoom bounded.
- No private fixtures, website demo mutations, dependency changes, or API permission changes.

## Slices
1. Test pure component/state routing; implement navigation helpers and component work routes.
2. Compact view/item/content pickers and selection; contextual Related and accessible panel handling.
3. Bounded camera, responsive styling, regression tests and review.

## Verification
Run `node --test tests/test_*mjs`. Record actual runtime/browser evidence separately from synthetic checks. Existing tests protecting discussions, artifact integrity and permissions must continue to pass.

## Implementation evidence
- Added component/file mapping and related-work routing, including legacy Structure routes and no-work Files fallback. Explicit state transitions consult recorded related work; they never substitute another head silently.
- Work, view and library-item pickers retain saved-state IDs. Removed standalone Structure rendering/controller actions. Tree selection is green, marked with a chevron and `aria-current`; automatic CAD/Code file selection updates the breadcrumb/tree and work picker.
- Related uses recorded API links; Discussion retains exact saved anchors and drafts. Added a regression for Inbox thread identity across Related/Discuss changes. Existing permission and integrity code remains authoritative.
- Library CAD previews include bounded available assembly meshes; Work retains its existing saved assembly preview. Orbit/zoom and restored camera values are bounded, with keyboard orbit/zoom/reset.
- Added responsive 320px layout rules, panel focus/scroll/escape handling, navigation Escape return, and existing Gantry logo with Gantry Studio label.
- Anonymous fixture now depicts Desktop robot arm with stable existing IDs, plus a new Gripper component/file without work. No website demo files were changed. The fixture remains sample-only with no live execution.
- Automated evidence: `node --test tests/test_*mjs` passes 83 tests; `git diff --check` passes. New tests cover component mapping, legacy/no-work/multi-work routes, saved-state mismatch, escaped compact pickers, pinned Inbox drafts, camera bounds, and concise agent requests. Prior controller async-race, permissions presentation and exact-anchor tests continue passing.
- Security review: all new names/paths/request text HTML-escaped; no API authorization changes, remote assets, new dependencies or private fixture content. Artifact hash verification/size limits retained. Generated sample tokens stay in the caller-selected isolated output directory, never source.
- Runtime/browser evidence is being collected independently by the parent agent against the isolated real sample server; automated DOM-boundary tests are not a substitute for that evidence.

## Review follow-up: list pagination scope
Independent review caught selection-derived component scoping on subsequent library pages. Reproduced with two failing controller regressions: a project-wide 50-file first page losing another component on Load more, and a parent-component query narrowing to its selected child. The controller now retains the original list query component separately from the highlighted selection component. Both regressions and the complete 85-test Node suite pass; `git diff --check` passes.

## Review follow-up: historical component routing
Independent review also caught component resolution against the latest project hierarchy before reading an explicit historical state. A failing controller regression uses a removed component ID and a work whose latest component mapping differs. Studio now resolves the requested saved hierarchy first, retains it for Files/Requirements routing, and trusts the exact-state related-work query rather than re-filtering its results against latest work summaries. The regression and complete 86-test Node suite pass; `git diff --check` passes.

## Parent runtime and regression confirmation
Isolated sample HTTP server and real browser checked at 1280px and 320px: component→work/no-work→Files; CAD/Code/Checks; comparison; exact part/line conversations; draft retention; mention→Inbox→same line/state; Work/Files roundtrip retains state; narrow panel/navigation and Escape. No horizontal overflow at 320px. Full Python suite 1,914 tests (1 skip) and website JS 32 pass. Final product JS 86 pass. Independent re-review confirmed pagination and historical routing fixes. Sample-only, no live inference or physical validation.

## Browser follow-up: imported checkpoint selection
Reproduced a code-only imported checkpoint resetting an unset CAD file to Base despite Sensor bracket being the work component. Artifact fallback now first chooses among paths mapped to the current component (retaining changed-file and mesh preferences there), then uses the existing global fallback only when that component has no files in the content view. The new controller regression failed before the fix and passes afterward. Full Node suite: 87 tests passed; diff check passed.
