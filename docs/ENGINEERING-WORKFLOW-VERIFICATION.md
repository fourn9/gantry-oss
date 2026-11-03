# Engineering workflow verification — 2026-11-03

Scope: local workflow and Core integration, outside Bot organization/reasoning
development. Addy Osmani skills reference:
`2686b620fc1fed2e8f60c704839c766b8594c6b6`.

## Executed evidence

| Check | Result |
|---|---|
| Python full regression suite | 757 tests, 1 optional interpreter test skipped, no failures |
| Final malformed-input diagnostic guard, tested after the full suite | Physical execution: 9 passed; HTTP CLI: 2 passed |
| JavaScript review/requirements tests | 9 passed |
| Wheel built and installed in a fresh environment without optional CAD dependencies | Engineering CLI/help/doctor and existing native CLI work |
| Real CLI against an isolated authenticated HTTP server | Checkout, changed-file checkpoint, rejected invalid token, same-key recovery passed |
| Real CadQuery smoke test | Python 3.12.15, CadQuery 2.8.0; intersecting solids fail, translated solid passes |
| Old result after CAD edit | Unknown for the new input combination |
| Transitive mechanical → wiring → control dependency | Wiring/control remain due for reassessment after the mechanical edit |
| Deliberately lost response after a real Core checkpoint | Recovered the identical saved state, without redoing CAD/evaluation |
| Restore + replay | Restored bytes match; ledger replay matches |
| Formal adoption | Remains unadopted |
| Mentor dossier and feedback | Real authenticated Core context and feedback path; synthetic model response explicitly used in tests |
| Timing | Parallel interval union, pause/resume, unfinished spans, clock discontinuity and duplicate finish covered |

Run `python examples/engineering_roundtrip.py NEW_DIRECTORY` to reproduce the
geometry, publication and restoration checks. This saves the full isolated ledger,
source/candidate/restored files, evaluator logs, execution receipts and timing summary
under that directory. No private design or proprietary project data is used.

## Faults found and repaired

- Final checkpoint acknowledgement loss previously surfaced as a stale head.
  Exact arguments now survive in the local journal and are replayed through Core.
- Capturing an external source in Core followed by a local full-directory checkpoint
  could omit imported files absent from the local directory. It now requires restore.
- A refreshed CAD component could hide a dependent interface's old prerequisite
  version. Separate dependency bindings now invalidate downstream applicability.
- A successful-looking report from a failed process could be imported alone.
  The collector preserves it as raw evidence and marks the operative report as error.
- A process wrapper could exit while its solver children continued. Surviving
  process-group members now prevent a pass and are stopped.
- Post-execution log changes now fail acquired-output hash verification.

## Security review

Single-agent implementation/review; no independent security certification claimed.
New logic uses existing Core authentication, scope and atomic version validation.
Unauthorized retries reach Core instead of receiving cached authenticated results.
No credential is stored in connection metadata or forwarded into evaluator env.
Source capture keeps existing credential exclusions/scanning. Logs are sensitive
local evidence, not automatically sent telemetry; publication runs the same scanner.
Scanning is not a guarantee that arbitrary binary CAD files contain no secrets.

Local journals use private permissions, parameterized SQLite, unique request keys,
frozen payloads and explicit unknown execution states. Bounded file reads reject
path traversal and symlinks; output hashes are rechecked before collection. Existing
external imports cannot silently disappear during whole-workspace capture.

No dependency or lockfile changed. The optional CadQuery dependency is unchanged.
No new HTTP endpoint or unrestricted MCP execution tool was added. A recipe hash
is explicit operator authorization, not a sandbox; operating untrusted executables
still requires an OS/container boundary. Workspaces must not be concurrently edited
by hostile OS principals. Windows child-process lifecycle is unqualified.

## Remaining qualification

- No Windows commercial CAD/ECAD/harness license or live customer account available.
  The existing [native matrix](NATIVE-DESKTOP.md) is unchanged: Zuken/Capital SDK
  implementations remain blocked, and other native paths require live qualification.
- No real FEA, dynamic simulation, tolerance solver, electrical solver or prototype
  test was executed in this implementation. Included real physics coverage is
  single-pose static geometry, not whole-system acceptance.
- Native object correspondence and dependency completeness are submitted
  declarations. No automatic topology/net matching or semantic geometry inference.
- Mentor's additional context is verified; better recommendations or fewer design
  iterations are not proven by a synthetic review response.
- Timing covers instrumented paths. No retroactive full-project duration, cross-host
  critical path, cost savings or speedup claim is made.
- This is an isolated implementation branch. No main Bot workspace, hosted
  deployment, public GitHub branch, version tag or release was changed.
