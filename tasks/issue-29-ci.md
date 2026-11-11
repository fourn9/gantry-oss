# Issue 29: active quality gates

Reference: Addy Osmani agent-skills revision
2686b620fc1fed2e8f60c704839c766b8594c6b6.

Acceptance: run all Python, product JS and website JS suites on Linux/macOS
and Python 3.11/3.12; failures must fail the aggregate gate; main requires checks
and one independent review. Release only a CI-verified revision.

Implemented: active matrix workflow, complete JS coverage, aggregate
`ci-required`, unavailable-sandbox guard regression, YAML block scalar commands,
read-only permissions and isolated project dependencies. Hosted macOS 14 was
retired, so use macOS 15. Provision patched Python 3.11.17/3.12.15 with pinned
setup-uv revision and uv 0.13.5, rather than relying on outdated hosted binaries.
The security baseline also recognizes stable two-component releases (e.g. 26.3)
without accepting prerelease/vendor suffixes. Duplicate branch/PR runs are avoided.

Verification exposed a pre-existing same-millisecond Studio comment ordering
failure. A deterministic constant-clock regression now covers sequence ordering
and cursor pagination. No tests were disabled to obtain a passing run; the sandbox
skip applies only when that optional backend is genuinely unavailable.

Remote CI and release evidence is recorded in PR #31 and its checks. Branch
protection is an operator setting and must be verified separately after merge.
This task excludes the unrelated Studio navigation proposal in issue #22.

Follow-up (PR #30): three `test_crew_integration` tests ran a sandboxed tool with no
guard and failed on a host with no supported sandbox. They now skip there, like the
other sandbox tests. With `gantry.project_sandbox.backend` replaced by `'unavailable'`:
12 tests, 3 skipped, no failure. With the real macOS sandbox: 12 passed, none skipped.
`CONTRIBUTING.md` and `docs/README.md` describe the active workflow.
