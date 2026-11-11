# Issue 29: active quality gates

Use Addy Osmani agent-skills revision 2686b620fc1fed2e8f60c704839c766b8594c6b6.
Acceptance: run all Python, product JS and website JS suites on Linux/macOS and Python 3.11/3.12; fail on test failures; missing sandbox skips the specific sandbox test; read-only workflow permissions; main requires checks and one independent review. Release only a CI-verified revision. Studio issue 22 is a separate change.

Implemented locally: active matrix workflow, complete JS coverage, aggregate ci-required gate, missing-sandbox guard with failing-before/passing-after regression, and repaired YAML shell quoting inherited from the old template. Product JS: 71 passed; website JS: 32 passed. Workflow parsed with Psych.

Publication blocked: GitHub rejected workflow creation because the current OAuth credential lacks workflow scope. Do not bypass this with another credential. Main protection is still disabled; required checks, independent review and release remain pending successful publication and remote CI. Issue 29 must remain open.

Issue 22 inspection confirms Structure still exists in studio.js and studio_views.js. Its proposed removal changes the previously agreed UX, so confirmation was requested before applying that redesign.
