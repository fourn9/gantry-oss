# Remaining PR and issue review — 2026-11-12

Workflow: Addy Osmani agent-skills at `2686b620fc1fed2e8f60c704839c766b8594c6b6`. Preserve private data, existing incomplete work, required CI and independent review.

## Acceptance
- Resolve #22 against real Studio API paths, preserving exact state/anchor identity, drafts and authorization; see `issue22-component-navigation.md`.
- Review #17–21 against actual wheel metadata and isolated dependency resolution, not version numbers alone. Verify compatible changes using the CAD runtime.
- Retain useful unique changes from #30 without replacing the activated, verified CI with the stale proposal.
- Publish reviewed changes and evidence; do not bypass protected-main review requirements.

## PR #30 delta
CI activation, stable-version parsing and unlimited-connection sandbox handling already landed in #31. Retained missing sandbox guards for three Crew integration tests, keeping non-tool tests active. Updated stale CI documentation.

Reproduction: force `test_crew_integration.backend()` to `unavailable`; `test_same_bot_exact_state_and_subsequent_edit` failed with missing `exit_code` before the fix. After the fix, 12 integration tests pass with the real macOS sandbox; with the unavailable backend, 9 pass and exactly 3 tool-dependent tests skip. The hosted CI still preflights a real sandbox; these guards cannot turn a broken hosted sandbox into a green run.

## Dependency review
Reviewed exact one-line PRs against all constraints with a fresh CPython 3.12.15/macOS arm64 wheel-only resolver:
- #18: OCP 8 conflicts with CadQuery 2.8's OCP <8 requirement; closed with evidence.
- #20: proxy 8 conflicts with OCP 7.9.3.1.1's exact proxy requirement; closed with evidence.
- #21: multimethod 2.1 conflicts with CadQuery's <2 requirement; closed with evidence.
- #19: pip 26.3 resolves and installs all 50 pinned dependencies. Its own dry-run and `pip check` pass. Real 2×3×4 box STEP roundtrip remains valid, volume 24 mm³. CAD adapter 5/5, review context 5/5, requirement handoff 76/76 pass without skips; approved.
- #17: VTK 9.7.2 conflicts with OCP's exact 9.6.2 requirement. Kept open because it also tracks genuine GLTF security fixes missing in upstream 9.6.2. Latest released CadQuery/OCP do not provide a compatible patched combination. See HARDWARE-VERIFICATION.md; no dependency overrides used.

Primary metadata: https://pypi.org/pypi/cadquery/2.8.0/json and https://pypi.org/pypi/cadquery-ocp/7.9.3.1.1/json. VTK security sources are linked in HARDWARE-VERIFICATION.md and PR #17.

## Combined validation
- Full Python suite: 1,914 tests, 1,913 passed / 1 skipped, 237.018 seconds.
- Product JavaScript: 86 passed. Website JavaScript: 32 passed.
- Independent code review found two state/navigation regressions; both were reproduced and fixed with regression tests, then independently re-reviewed with no remaining actionable finding.
- Isolated real HTTP Studio sample, actual browser at desktop and 320px: component opens work, no-work Gripper opens Files; CAD/Code/Checks switching; base/shared comparison; exact CAD and code-line conversations; draft close/reopen; self-mention through Inbox back to original line/state; Work→Files→Work preserves saved state; no-evaluation stays Not tested/unadopted; narrow panel stacks and Escape closes it; mobile navigation opens/selects/closes. At 320px document scrollWidth equals clientWidth.
- Geometry, people, comments and results in the runtime sample are explicitly anonymous fixtures. No live agents/vendor tools or private project state were used. Browser checks cover interaction, not physical correctness.

