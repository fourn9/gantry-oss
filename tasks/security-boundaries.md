# Storage and workspace boundary hardening

Reference: Addy Osmani agent-skills 2686b620fc1fed2e8f60c704839c766b8594c6b6 (TDD, security, CI).

Acceptance before implementation:
- Arbitrary caller metadata round-trips unchanged; a read-only subscription cannot damage verification, export or replay, including after restart.
- Compression applies only at explicit artifact entry boundaries; legacy encoding remains readable without rewriting history. Lossy writes roll back before event insertion.
- Cloud workspaces have unambiguous credential namespaces. References are checked on configuration, display and use; old ambiguous references fail closed and require operator reconfiguration.
- Temporary anonymous fixtures exercise these boundaries without production credentials or external requests.
- Full regression suites and CI gate precede publication. No private project data or advisory text is copied into public documentation.

Reproduction: both boundary regressions failed on the preceding implementation:
reader metadata caused an event-chain mismatch; a nested workspace credential was
accepted. Both pass after the fix, including restart/replay and denial before
external acquisition. The storage codec now writes version 2 with explicit manifest
paths and verifies logical round-trip equality before insertion. Existing version 1
records remain readable. Already damaged historical data is not rewritten or claimed
repaired; restore such data only from a verified backup after incident assessment.

Independent review: no actionable findings across correctness, authorization,
storage compatibility and performance. Anonymous mixed v1/v2 history passed
capture, cached response retrieval, verify, replay and restore, preserving old
event bytes. Product JS 71/71 and website JS 32/32 passed. The dated local runtime
baseline passed; pip-audit found no known dependency vulnerabilities (the local
Gantry distribution itself is source-reviewed, not a PyPI advisory match).
Final cross-platform suite results are attached to PR #31; these tests do not
claim inspection or repair of any live customer ledger.
