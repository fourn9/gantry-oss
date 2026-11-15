# Crew live recovery and evidence retrieval

Follow reviewed Addy Osmani agent-skills revision
2686b620fc1fed2e8f60c704839c766b8594c6b6: planning, TDD, incremental implementation,
security review and independent review. Preserve unrelated plans and private data.

## Acceptance

- [ ] Reproduce peer memory arriving during real Core planning; accepted plan is
      rebuilt from fresh context automatically and old input/output remains saved.
- [ ] Only Core-classified recall/working-note staleness is eligible. Revoked
      authority, changed requirements, invalid outputs and unknown model effects
      stay blocked; no editing/tool side effects are repeated.
- [ ] Replan generations and inference receipts survive restart/recovery. A bounded
      three-refresh policy prevents endless model churn per task attempt; this is
      a safety bound on in-flight replanning, not a lifetime or test-count limit.
- [ ] Peer results have discoverable, bounded report/candidate/evidence paths,
      respecting existing authorization, redaction and project boundaries.
- [ ] Run regression tests, independent review and real monthly Codex exercise.
      Start with a new isolated fixture; no parent repair, answer edits or journal
      surgery after initial setup. Record failures honestly and retain prior runs.
- [ ] Push changes and sanitized validation to GitHub; merge only after required CI.

## Design

Core attaches a machine-readable reason to the existing stale_basis error only
when execution authority and unchanged task inputs have passed their checks.
Worker preserves each unaccepted plan in its original directory and starts a new
numbered learning generation, with durable generation pointer and stale reason.
Existing replay/idempotency and stopped-inference recovery use the active generation.
No model/provider changes. Mentor is not involved. Bots choose work and delegation.

Independent retrieval slice: tasks/crew-peer-evidence.md. No private journals or
customer project information will enter public source. Live acceptance repeats the
anonymous 3-Bot experiment; it is not CAD validation or a causal speedup study.
