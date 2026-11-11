# Active CI workflow

Status: implemented; local checks passed; the first hosted run is the remaining evidence. Tracks issue #29.

Problem: no workflow ran on pushes or pull requests. `docs/ci-workflow.yml` was a template outside `.github/workflows/`, and its JavaScript step ran one of the 15 test files in `tests/` and none of the 8 in `website/tests/`. On a host without a supported OS command sandbox, four tests failed instead of skipping, so the Python step could not pass on a plain Linux runner.

Acceptance:
- A workflow under `.github/workflows/` runs on pull requests and on pushes to `main`, with read-only repository permission.
- It runs the Python suite, the dependency audit, the synthetic example, and every JavaScript test in `tests/` and `website/tests/`.
- One job runs on macOS so that the Seatbelt sandbox tests are executed, not only skipped.
- On a host with no supported sandbox, sandbox-dependent tests skip and the rest pass.

Changes:
- `docs/ci-workflow.yml` moved to `.github/workflows/ci.yml`. Ubuntu runs Python 3.11, 3.12 and 3.13; macOS runs 3.13. JavaScript steps use the documented globs.
- The template was not valid YAML: the step with `--only-binary=:all: ` held a colon and a space in a plain scalar, so GitHub rejected the file. The step is now a block scalar. The first push of this branch showed the rejection; a YAML parser confirms the template on `main` has the same error.
- `tests/test_unlimited_connection.py`: the guard `if not backend()` never skipped, because `backend()` returns the string `'unavailable'`. It now compares with that value.
- `tests/test_crew_integration.py`: the three tests that execute a sandboxed tool skip when no sandbox is available. `test_dirty_workspace_refused` still runs there.
- `CONTRIBUTING.md` and `docs/README.md` point to the active workflow.

Validation (macOS, Python 3.13.9, Node 24.22.1):
- `node --test tests/test_*.mjs`: 71 passed. `node --test website/tests/*.test.mjs`: 32 passed. `python examples/development_loop.py`: exit 0.
- Full Python suite with `gantry.project_sandbox.backend` replaced by `'unavailable'` before test import: 1,907 tests, 63 skipped, 3 errors, all in `test_crew_integration`. After the guard, `test_crew_integration` and `test_unlimited_connection` pass in that mode (3 and 1 skipped) and pass with the real sandbox (none skipped).
- Not verified locally: the hosted runners themselves, Python 3.11 and 3.12, Node 22, `python -m gantry.security_check` against the runner's interpreter patch level, and `pip-audit`.

Not in scope: branch protection (required checks and review) is a repository setting, and release tagging is a maintainer decision. Dated verification records that mention the former template path are left as written.
