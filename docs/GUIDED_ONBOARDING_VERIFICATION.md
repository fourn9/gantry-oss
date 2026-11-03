# Guided onboarding verification — 2026-11-04

This is functional verification, not an engineering-validity or time-saving claim.
All fixtures are anonymous. Private tokens, journals and runtime source captures
remain outside the public repository.

## Automated evidence

- `test_onboarding.py`: 17 tests pass, including existing workspace tests inherited
  by the fixture. Covers persisted restart, source selection, stale evidence,
  preserved manual corrections, exact proposal hashes, unauthorized identities,
  collaborator removal, cyclic hierarchy rejection, credential/path rejection,
  atomic failed completion, bounded grouping, preview without network/writes,
  idempotent upload, response-lost inference recovery and two-identity continuation.
- `node --test tests/test_onboarding_web.mjs tests/test_studio*.mjs`: 25 tests pass.
  Includes selection limits/exclusions, output escaping and existing Studio behavior.
- Existing Studio Python tests: 10 pass.
- Existing interface tests: 6 pass. Security-pattern Python tests: 40 pass.
- The initial full suite ran 1,168 tests and exposed 15 CLI subprocess failures
  from an eager new import on the system Python. The onboarding parser now lazily
  imports workspace/inference code; the affected interface/security tests pass.
  The integrated full-suite run subsequently passed: 1,295 tests in 149.067
  seconds, with 8 environment-dependent skips. A final stable-question
  instruction correction and regression test then passed the 17-test focused suite.

## Actual local UI and HTTP

In an isolated ledger and server, the browser selected an anonymous project folder
with four saved files and one excluded `.env` fixture. No external source or real
robot was used. Through the UI, it saved a draft, answered a CAD association
question, renamed a component and recorded the reason. Server restart and browser
reopening retained those answers/corrections. At 390 px viewport width the page
had no horizontal overflow. No browser console errors were observed.

Codex in the current interactive chat read the bounded saved context and submitted
one attributed proposal over the actual HTTP API, using an existing fixture agent
identity. This was a **manual API bridge**, not a separately running autonomous
analyzer. The proposal preserved the user's renamed component, suggested a first
work, and treated a control value as an unapproved configuration rather than a
requirement or successful test.

The owner opened the first work and shared its initial unfinished checkpoint
through the UI. Studio displayed `Shared`, `unverified` and `Not formally adopted`
as separate facts. A second authenticated identity then used the real HTTP path
to restore that state and begin its own work. All four restored file hashes matched;
onboarding answers, corrections and limitations were present in the new context.

The two STEP fixtures intentionally contain synthetic text headers only. Studio
correctly reported native preview unsupported instead of displaying invented CAD.
No CAD executable, simulation, physical test or external model billing was used.

## What remains unverified here

The subscription/customer-command adapter itself is reused from the existing
inference implementation. This change's automatic analyzer was tested with a
synthetic inference function, including post-commit response loss. A fresh real
subscription CLI inference was not launched in this side conversation. Native CAD
interpretation, external provider authentication and engineering outcomes require
their respective tool/environment validation. The feature does not claim those.

## Reproduce

Run the named test files. For UI, start a separate anonymous Studio demo ledger
using `examples/studio-demo/run.py` on an unused port, sign in with its generated
owner token file, and use **Import project** with a small fixture directory.
Add an existing demo collaborator, submit a hash-bound proposal using its identity,
reopen the draft, open first work, share, then use another identity's
`workspace continue` into an empty directory. Compare saved hashes and inspect
verification/adoption independently. Do not use production ledgers or customer
files for this smoke test.

## Integration

The feature is integrated on top of main-checkout commit `321f779`, including
its current team membership, cloud and streaming-workspace changes. The isolated
preview was restarted from that combined source and its saved draft/work reopened
successfully. No other running server was restarted; other processes need their
normal restart to load new backend command contracts. No public deployment was
performed by this implementation task.
