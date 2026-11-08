# Crew action recovery guidance

Reviewed workflow: Addy Osmani agent-skills revision `2686b620fc1fed2e8f60c704839c766b8594c6b6` (specification, planning, incremental implementation, TDD, debugging, review and security). User authorized correcting gaps encountered during real Bot collaboration. Existing plans remain unchanged.

## Problem and scope

Real Bot collaboration repeatedly rejects file paths in evidence-ID arrays and JSON pointers aimed at the wrong response level. Rejection is correct, but generic messages make recovery require extra inference. Improve feedback without broadening accepted references, leaking other projects' identifiers or changing engineering decisions.

## Acceptance / tasks

- [x] Reproduce: anonymous tests show missing actionable evidence guidance and authorized-root pointer guidance.
- [x] Add bounded, generic evidence-reference guidance. A file remains evidence only through a saved state/action; raw paths/hashes do not become authoritative record IDs.
- [x] Invalid JSON pointers offer bounded root-key navigation only from the already-authorized response. Never include values or unrelated project metadata.
- [x] Test invalid and cross-project references, escaped keys, oversized keys/roots and absence of sensitive values; run focused Crew regressions and package build.
- [x] Record private runtime outcome separately. The live run started before this patch; do not attribute its earlier corrections to the patch.

Reuse `Fault.details`, existing contracts, stdlib and unittest. No dependency, permission, schema migration, provider or UI change. Run `PYTHONPATH=tests python -m unittest test_crew_action_guidance test_crew_runtime test_crew_coordination -v`; build with `python -m pip wheel --no-deps --no-build-isolation .`.

Validation: initial four regression tests reproduced three failures before the patch; five guidance tests now pass including escaped/Unicode keys. Focused Crew suite passed (158 tests before the fifth guidance case). Build succeeded with isolated build dependencies; the execution environment lacked setuptools for --no-build-isolation. Independent review caught an overbroad evidence instruction; it now distinguishes record-reference arrays from typed requirement-mapping path/hash objects. Live runtime evidence remains in the private experiment, not this source tree.

## Execution receipt follow-up

An actual tool process completed before oversized output capture failed; the action receipt discarded exit/time/stdout references. Four anonymous sandbox regressions reproduced this (oversize success/failure, unauthorized output, symlink). Preserve sanitized tool-execution.json and return explicit tool_capture with the process receipt while keeping workspace_changes_applied=false. Validate all outputs before writes, recheck task authority, and do not publish successful evidence on capture failure. Tests also cover authority loss after execution. No file-size or scope restriction is relaxed. This is recovery visibility, not acceptance of uncaptured output.
