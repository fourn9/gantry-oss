# Crew runtime efficiency and recovery

User-authorized follow-up to a recorded long-running development exercise.
Workflow: Addy Osmani agent-skills revision
`2686b620fc1fed2e8f60c704839c766b8594c6b6`; specification, TDD,
incremental implementation, performance, context, security and independent review.

## Evidence and scope

The measured elapsed interval mixed host suspension, model/provider waits,
manual infrastructure repair and engineering work. Most completed model calls
requested another read. This does not establish pure model thinking time or an
engineering speedup. Preserve private source records outside the public repo.

## Acceptance

- Preserve and publish existing continuation repairs after review and fixes.
- Reject decoded credential-like JSON before error diagnostics can reveal it.
- Bound the complete model input after schemas, configuration and previous result
  are added; keep authority intact and references to omitted evidence.
- Fetch multiple independent observations in one model turn, with read-only
  allowlist, bounded output, individual provenance and unchanged write fencing.
- Deliver a bounded handoff index for state changes, child evidence and unknowns;
  source data remains retrievable and historical evidence is labelled.
- Add owner-approved, default-off limited recovery. Unknown side effects and
  changed authority remain held; saved responses are reconciled, not recomputed.
- Record phase intervals without payloads/secrets, distinguishing elapsed wait
  from CPU/inference work. Do not infer sleep from a gap alone.
- Test real Core/worker paths with anonymous deterministic inference and compare
  call counts for identical retrieval tasks. Such tests are functional evidence,
  not a claim of faster robot development or live-model reasoning.
- Run focused tests, full suite, build, privacy scan and independent review;
  publish code/docs/tests only. No paid API or private engineering experiment.

## Progress

- [x] Inspect previous timing evidence and implementation; independent review.
- [x] Fix review blockers and checkpoint existing repairs.
- [x] Batched observations and handoff context.
- [x] Bounded opt-in recovery and phase timing.
- [x] Verification, limitations and GitHub publication (PR #25).

## Increment evidence

- Confirmed RED: escaped credential keys leaked through missing-pointer errors;
  complete action inputs outgrew provider budget. Both fixed, including a real
  Core/worker large-receipt regression.
- Confirmed RED then GREEN: batch delivery, handoff indexing and phase receipts.
  Four identical reads plus completion require five fixture model turns before,
  two after, with identical content/hash results and matching ledger replay.
- Independent review found Unicode accounting and mixed-batch recency failures;
  added failing regressions and fixed both. Final scoped review found no blockers.
- Recovery has 17 new lifecycle cases; its separate final review found no blockers.
  See [recovery evidence](bot-auto-recovery.md) for guarantees and exclusions.
- No live model, paid API, private project trial, supervisor deployment or host
  suspend/resume experiment was performed. No end-to-end engineering speedup claim.

## Integrated validation

- Python 3.12 full suite: **1,900 tests in 214.751 s**, 1,886 passed and
  14 environment-dependent skips; zero failures. No tests disabled for this work.
- Website tests after integrating current main: **32 passed**, zero failures.
- Built with the existing packaging environment using
  `python -m pip wheel . --no-deps --no-build-isolation --no-index`.
  The runtime-only environment lacks packaging dependencies; no dependency was
  installed to work around that. Wheel import/default-policy smoke passed.
- Wheel: `gantry_ledger-3.4.0-py3-none-any.whl`, SHA-256
  `9ff7c0b81703c52aebfd83054a7595d29bf89fdaf9c050863f8559c24bb175e6`.
  All 179 packaged source/assets match the final implementation tree.
- Targeted changed-file and wheel scans found no private project names/paths or
  provider credential markers. This is not a formal security audit or proof that
  every possible sensitive string is detectable.
- Independent code/security reviews completed for observation/context/timing and
  recovery slices. Review findings were fixed with failing-then-passing regressions.
- Runtime policy is default-off, package version unchanged, no customer worker
  configuration or host power setting changed, and no release tag created.
