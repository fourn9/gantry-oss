# Studio: shared state, files, requirements and conversations

User-approved design (2026-11-07). Apply Addy Osmani agent-skills at
2686b620fc1fed2e8f60c704839c766b8594c6b6. Preserve other tasks and private data.

## Capability map / implementation order
1. `state-library`: permission-checked, paged Files/Requirements and related records over immutable states.
2. `anchored-discussions`: project/component/file/requirement discussions reusing Studio threads and inbox.
3. `studio-navigation`: Structure / Files / Work / Requirements; Related / Discussion panel, names and roles.
4. `agent-context`: same state and requirement graph, mandatory constraints plus bounded drill-down.

No second ledger, inferred requirement satisfaction, paid model, native CAD editing,
identity grants, or automatic deployment. Current user's approval covers the design and normal implementation.

## Contracts
- Explicit project + immutable state for library reads. Default is the saved project baseline;
  never combine latest files from unrelated changes. State picker identifies session and shared/local status.
- Files retain native bytes, snapshot/path/hash. Paged file lists and verified per-file reads.
- Requirements reuse pinned requirement_refs and coverage. File links come from declared check
  input/evidence mappings, labelled as such; absence stays unlinked. No invented fulfills edges.
- Related work and state history use recorded changes, parents, requirements and exact versions.
- Expand existing studio_comment anchors additively. Work is optional only when an authorized
  project/state target is provided. Replies and inbox retain original project/state/anchor.
- Names enrich existing principal and persistent Bot IDs. Recipient access is rechecked. Mentions
  notify only; read-only Ask uses the existing fenced Bot queue; editing remains explicit scoped work.
- Agent context returns all pinned requirement statuses/constraints/unknowns, bounded related records,
  provenance and explicit paging/limitations. No semantic summarization or new inference calls.

## Design contract
English; existing neutral styles, compact tabs, artifact-first. Related and Discussion share a
right panel, stacked on narrow screens. All controls keyboard accessible. Empty/error/not-acquired,
external-only and unsupported states explicit. Demo records remain separate from real project data.

## Verification / tasks
- [x] Read API and scoped agent context: pagination, cross-project denial, old states, missing links,
      changed requirement/file invalidation, no bytes in summaries.
- [x] Conversations: file/requirement/component anchors, wrong hashes, old versions, recipient revocation,
      idempotency, named Bot and human recipients, read-only request/result round trip.
- [x] UI: four tabs, version selection, file preview/diff/download/history, requirement relations,
      exact-context conversations and Inbox routes, navigation race protection.
- [x] Regression + browser: real synthetic local Core, not production data; desktop and narrow widths.
- [x] Independent review and docs; inspect private Studio compatibility without publishing private content.
- [ ] Deployment follow-up (outside this source implementation): adapt private allowlist/CAD hooks
      and public demo responders before replacing their browser modules.

Results: [verification](../docs/STUDIO_LIBRARY_VERIFICATION.md). Full Python: 1,731
tests, 8 skipped; JS: 70 passed. Local wheel built. No data migration or deployment.

Python: python -m unittest discover -s tests -p 'test_studio*.py' -q
JS: node --test tests/test_studio*.mjs
Full regression: python -m unittest discover -s tests -p 'test_*.py' -q
Build: python -m build (if installed), otherwise standard local wheel build without isolation.
Style: small Python mixins and dependency-free ES modules; existing command schemas and Fault errors.
Threats: forged project/state/path, cross-member disclosure, thread retargeting, XSS, unauthorized Bot
writes and unbounded retrieval. Keep server-side authorization and escaped text; reuse verified storage.
