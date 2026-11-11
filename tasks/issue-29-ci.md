# Issue 29: active quality gates

Use Addy Osmani agent-skills revision 2686b620fc1fed2e8f60c704839c766b8594c6b6.
Acceptance: run all Python, product JS and website JS suites on Linux/macOS and Python 3.11/3.12; fail on test failures; missing sandbox skips the specific sandbox test; read-only workflow permissions; main requires checks and one independent review. Release only a CI-verified revision. Studio issue 22 is a separate change.
