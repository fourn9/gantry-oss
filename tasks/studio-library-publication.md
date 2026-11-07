# Studio library rollout — 2026-11-07

User authorized GitHub publication, public demo and existing workspace updates.
Follow Addy Osmani agent-skills at 2686b620fc1fed2e8f60c704839c766b8594c6b6:
incremental implementation, security, independent review, git and shipping.

- Publish the application changes from 794da61 with the compatible static demo.
- Keep public sample identities, geometry, discussion and requirements browser-only.
- Preserve demo Inbox evidence, team setup and no-network CSP; use the same library
  UI with simulated contracts, not a pretend real backend.
- Update the existing private viewing workspace in place, preserving its owner-only
  loopback listener, native preview hooks, source-backed hierarchy and frozen state.
  No inference/execution or broader access is enabled. Do not change original data.
- Back up private runtime/source before replacement; no engineering-data migration.
- Verify exact-state content/requirement navigation, discussion/Inbox, old versions,
  auth/forged anchors and desktop/narrow layouts; test imports and artifact packaging.
- Publish only anonymous source through reviewed PR; verify CI and remote commit.
- Deploy website/public contents to the existing Pages project and verify live assets.

Rollback: restore saved private runtime and restart the same loopback listener;
restore the previous Pages deployment for website; revert the scoped GitHub PR.
No credentials or private backups belong in this repository.

## Verified before publication

- Public demo: 25 Node tests and browser flows at 320–1440 px; original Inbox
  evidence flow preserved, exact-state discussions and named mentions verified.
- Product browser/controller suite plus website: 95 passing Node tests.
- Independent review found descendant component relations incomplete; fixed both
  related records and file/requirement scope through one helper, with a regression.
- Typed adoption lookup avoids materializing unrelated artifact manifests; covers
  pending inserts/type changes and packed/legacy records.
- Existing private viewer updated separately with its preview and hierarchy
  extensions preserved. Its original source ledger is unchanged. Owner-only
  authentication, loopback bind, denied execution/sync/adoption and forged anchors
  verified. New read endpoints inherit existing access; no engineering migration.
- Public-source/site scan found none of the private project names, IDs or paths.

No remote model, agent execution or real user notifications occur in the public
fixture. Its invented states cannot be restored by a real server.

- Full Python discovery completed: 1,732 tests, 14 optional-environment skips.
  After the review fix, all 11 library/typed-index tests passed (including the
  newly added descendant-scope and transaction-cache regressions).
- No GitHub Actions workflow is configured in this repository; these are local
  verification results, not a claim of hosted CI.
