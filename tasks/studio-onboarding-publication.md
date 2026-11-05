# Publish Studio team onboarding

User authorized public deployment and GitHub update. Follow Addy Osmani
agent-skills revision 2686b620fc1fed2e8f60c704839c766b8594c6b6:
git workflow, security/review, frontend and shipping. Product implementation
acceptance is in STUDIO_CREW_ACCEPTANCE.md. Existing in-progress native/CAD work
is excluded using a separate publication checkout and an explicit file list.

## Acceptance

- [x] Publish the reviewed source to GitHub main with current API contracts and
  a human-readable changelog; retain existing data and version semantics.
- [x] Add the three-step onboarding to the existing public browser-only demo,
  clearly identify sample responses, and retain its network-disabled boundary.
- [x] Verify published content and interactive flow; preserve rollback artifacts.

## Verification and release boundaries

The package has no mandatory third-party runtime dependencies. The supported
Python environment's 35 installed packages passed pip-audit on 2026-11-05.
This is a known-advisory check, not a security certification.
No mandatory/optional dependency declarations changed. New host modules and
web assets were byte-matched against the built wheel.

The isolated publication checkout passed 1,722 Python tests (8 skipped) and
57 JavaScript tests. Independent publication review found no required findings.

The website is a Cloudflare Pages static demo, not a hosted Gantry Core service.
Its initial source is retained separately for rollback; production deployment
can also be rolled back through the existing Pages deployment history.
No real files, live model connections, credentials, or private project state
are copied into the static demo. Source publication does not deploy a customer
runtime or enable inference. No new packaged version is declared by this change.

## Publication result — 2026-11-05

- Product source merged in PR #13: https://github.com/fourn9/gantry-oss/pull/13
  (merge commit `803543e5d3cb8090c0cde407e60ff868f37ff09f`).
- Public sample onboarding: https://gantryrobotics.org/demo/workspace#studio-crew
- Website source revision `caad40f` deployed through the existing Cloudflare
  Pages project. The deployment UI reported success. Nine public HTML/JS/CSS
  responses, including unchanged home/news, exactly matched local release bytes.
- Public browser verified Sources → Team review → Prepare → Create → Start →
  Stop → Resume. Creation kept work unstarted; execution is explicitly simulated.
- Static demo: 11 Node tests passed. Local browser also checked role editing,
  keyboard entry/reset and widths 320/768/1024/1440 without horizontal overflow.
- The source package uses the customer setup host for real execution. The public
  demo accepts no project uploads and makes no model or runtime calls.
