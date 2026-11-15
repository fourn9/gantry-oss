# Peer result retrieval

Reference: Addy Osmani agent-skills reviewed revision `2686b620fc1fed2e8f60c704839c766b8594c6b6` (using-agent-skills, specification, planning, incremental implementation, TDD, interface design, security and review). Existing authorization covers this implementation.

Acceptance criteria:
- Bare inspect returns a compact result index with exact inspect requests for available reports, candidate, saved actions, development and related public result sections.
- Explicit pointer/offset/limit clients retain value/total/next_offset; oversized nested content yields exact follow-up pointers and strings have delivered-character cursors. Results survive observe and inline preview budgets.
- No invented verification/evidence, no extra authority or private learning/note access. get_bot_task remains the authorized source and cross-session inspect remains denied.
- Anonymous fixtures test large and escaped content, pagination, authorization/redaction and an actual Core/worker retrieval sequence (fixture inference, not autonomous-model evidence).

Plan: write failing regression tests; implement a small peer-result presentation helper; verify targeted Crew tests and review boundaries. Parent runs combined checks. No persistence format or dependencies change.

Implemented:
- Bare `inspect` returns allowlisted sections plus full-history `records` entrypoints. Explicit root and pointer pages remain available.
- Nested omissions contain exact escaped pointer requests; string and collection cursors describe only delivered content and stay inside batched-observation budgets.
- `records` accepts optional same-project `task_id`; own-task calls without new arguments preserve their existing shape. Peer reads use existing Core redaction and get_bot_records pagination, capped at 30 records. Nested reads retain source after/limit and a page hash; changed source pages fail with stale_basis instead of returning a different receipt.
- History is not an atomic task snapshot; recheck saved identities/versions before acting. No verification or adoption is inferred.

Verification:
- RED: new overview, nested omission and next_request assertions failed on prior behavior; older-history test failed before the history route existed.
- GREEN: `python3.12 -m unittest discover -s tests -p test_crew_peer_evidence.py` — 7 passed.
- `python3.12 -m unittest discover -s tests -p 'test_crew*.py' -q` — 364 passed (before final page-hash refinement).
- After page-hash refinement: focused 7, observe 9, action-guidance 5 tests passed; `git diff --check` passed. Combined final-suite verification belongs to the parent integration task.
- Real Core/storage/worker fixtures reconstructed a 26,000-character peer report, traversed 25 saved tool-action fixtures beyond the recent-20 window, rejected private learning links and foreign-session retrieval, and preserved private working-note redaction. Inference and tool evidence are anonymous deterministic fixtures, not live model or physical verification.

Security review: no Core auth changes, no additional persisted private fields, no private fixtures copied, no dependencies or schemas at rest changed. All optional peer routes call get_bot_task before presentation and get_bot_records retains its own authorization/redaction. Read requests cannot alter task identity for writes.
