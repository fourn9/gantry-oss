# Native host completion — 2026-11-03

User asks to complete actual native read/write integration. Existing code and
synthetic tests do not demonstrate licensed-product execution. Work remains in
the external-integration branch, independent of Bot work and private projects.
Addy Osmani agent-skills revision: 2686b620fc1fed2e8f60c704839c766b8594c6b6.
Apply source-driven design, explicit acceptance, incremental TDD and security review.

## Acceptance and sequence

- [x] Altium CLI dispatch: validate the exact generated v2 save/reload package,
  target baseline and pinned local X2 executable; launch the documented process
  without a shell. Persist a target hold before dispatch. Do not infer success
  from process launch/exit, kill the CAD host, or automatically retry.
- [x] Recover after client interruption: read the saved receipt and captured
  native bytes, retain evidence before releasing the hold, require explicit
  confirmation that the native writer stopped. Support repeat status reads and
  reject concurrent operations on the same target.
- [ ] Run synthetic process-boundary, integrity and recovery tests plus existing
  suites; package the executable CLI and document real-environment acceptance.
- [ ] Cadence persisted write/reopen: requires authoritative version-specific
  signatures and error semantics. Forum examples alone are not a qualified API
  contract. Do not invent calls or represent in-memory editing as persistence.
- [ ] Zuken / Capital native read-write: obtain exact SDK module/version,
  identity, parameter, persistence and error contracts, then implement and test.
- [ ] Licensed Windows end-to-end: prepare -> native execution -> persisted
  readback -> Gantry publication -> restoration. Pending customer environment.

## Source contract

Altium official command-line process execution:
https://resources.altium.com/p/continuous-integration-implementation-using-altium-designer

Altium RunScriptFile process and parameters:
https://www.altium.com/documentation/altium-designer/scripting/running-scripts

The adapter combines the documented command-line process mechanism with the
documented RunScriptFile process for a generated DelphiScript unit. Exact command
parsing, installed product version and save format still require a host test.
The native board must already be open and clean; no arbitrary script execution,
implicit document opening, application installation, or cloud access is added.

## Completion boundary

The goal is not complete until real native acceptance succeeds and missing SDK
routes exist. No accounts or licensed hosts were available at task start; the
request for current availability is pending. Test fixtures are synthetic and are
never described as licensed-product execution.

## Local implementation evidence

The native suite has 36 passing tests, including 11 process-boundary cases added
here. They exercise interruption before launch returns, launch errors, duplicate
requests, competing plans for the same document, wrong binary/script/baseline,
process-parameter injection, mismatched captures, fast completion racing launch
return, frozen evidence and CLI exit status. The process boundary is mocked; no
licensed Altium run occurred. In particular, an executable hash or mocked PID is
not runtime qualification.

The initial full suite passed 790 tests with the actual optional CadQuery
interpreter configured (90.769 seconds). A final CLI nonzero-error fix and its
test followed; final full-suite/package results will be recorded below.
