# Studio spatial context and change-centered work

Approved design: the conversation's Gantry spatial-context mock, 2026-11-08.
Tracker: https://github.com/fourn9/gantry-oss/issues/23 (follow-up to #22).
Workflow reference: addyosmani/agent-skills at
`2686b620fc1fed2e8f60c704839c766b8594c6b6`.
Existing incomplete task plans are preserved; this file owns this website change.

## Scope and architecture

Update the public LP, demo feature overview and `/demo/workspace`. The authenticated
OSS implementation is tracked separately in #23. Preserve the deployed component
UX, news pages, existing imports/sharing, immutable anchors and sample-only boundary.
Baseline is main `0ab19dd` plus the verified public `component-20261107` deployment.
No database, authentication, dependency or live-agent changes.

Three desktop regions: hierarchy and persistent assembly location on the left;
actual files/differences and verification in the centre; References/Discussion on
the right. Mobile uses a right drawer, not below-artifact stacking. Reuse the
existing mesh renderer and content-addressed artifact reader. Work lists actual
changed files and verification links; Files browses the same manifest at the same
state. Add robot-model/configuration/measurement sample artifacts with explicit
component paths. Never infer a part link from unknown content.

## Acceptance and ordered tasks

1. Reconcile published source in its own commit; existing 29 tests pass.
2. Add shared artifact selection and realistic sample evidence; test exact state,
   artifact format handling, changed-file scope and missing verification.
3. Add Changes/Verification and right contextual tabs; test retained anchors,
   saved versions, comments, drafts and original Inbox request.
4. Add small assembly below hierarchy with bounded camera and linked selection;
   expansion returns to prior file/version/diff/draft. Test stale async loads and
   empty/unmapped/multiple-part states; verify interactively.
5. Update LP and demo overview excerpts/copy/entry links. English, restrained
   density, same artifact model; preserve sample-only disclosures.
6. Run full website tests and syntax/module checks; inspect 320/768/1024/1440px,
   keyboard/focus, right drawer, model selection, versions and comparison. Record
   real browser evidence separately from deterministic tests.
7. Check deployed baseline has not advanced, package the existing static root,
   deploy to existing Cloudflare project, verify published bytes and UI. Publish
   source to GitHub with the issue reference. Do not close the OSS-port issue just
   because the public reference is deployed.

## Commands and style

Buildless ES modules, existing `esc()` output encoding, `data-studio` actions,
small view/model helpers, no new dependency. Static source: `website/public/`.
Tests: `node --test website/tests/*.test.mjs`.
Preview: `python3 -m http.server 8840 --bind 127.0.0.1 --directory website/public`.
Syntax: `node --check` on changed JavaScript modules.
Package the contents of `website/public/` (not its parent directory).

## Boundaries and risks

Always preserve exact state/hash/line targets, escape text and keep mandatory
context intact. Human mentions do not run agents. Reject unsupported/binary
previews honestly. Never copy private data, credentials or local runtime journals.
Rollback is the unchanged previous Pages deployment / baseline archive.
The static site has no package lock or dependency installation/audit boundary.

## Evidence

- Read current #22 and review. Created #23 with agreed specification.
- 8 representative deployed HTML/module files match the retained published tree.
- Reconciled published source; all 29 existing website tests passed.

### Implementation and local verification (2026-11-08)

- Added shared artifact format/scope helpers, explicit spatial mappings, robot URDF,
  sensor calibration YAML, and illustrative measurement CSV. Work and Files use
  identical state/path/hash targets. Verification links exact evidence and leaves
  missing full-motion coverage unverified.
- Added assembly below hierarchy, multiple-part highlights, format-driven Changes,
  Verification, persistent References/Discussion, and a right drawer on narrow
  screens. Expanded model restores the existing viewer DOM and draft.
- Updated homepage and demo excerpts/copy; cache revision `spatial-20261108`.
- All 32 Node tests pass; new tests first failed on the absent artifact helper,
  then passed after implementation. All demo JS syntax checks and diff whitespace
  checks pass. No added dependencies or authentication/backend changes.
- Browser verified YAML diff and mapped part, expansion/return preserving file,
  compare and draft; right tab switching; exact line comment with a named human;
  Verification -> pinned CSV; model -> Gripper Files with right panel retained.
- Browser verified import -> share -> original Inbox request still opens original
  v1 / motion.py:2 / 0.15-to-0.25 comparison. Fixed retained previous-version
  conversation loading so the three original messages remain visible after import.
- Inspected 320, 768, 1024 and 1440 CSS-pixel layouts. 320/1024 document width
  matched viewport; narrow context panel is a right dialog with inert background,
  Tab containment, Escape and focus restoration. Desktop has all three regions.
- Homepage and demo overview rendered updated excerpts; console had no warning or
  error entries in inspected flows. All observations use invented browser-only data.
- Eight representative production files still matched the reconciled baseline
  immediately before release preparation; origin/main remained 0ab19dd.
