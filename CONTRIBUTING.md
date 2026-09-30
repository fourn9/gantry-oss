# Contributing

Start with an issue describing the workflow, expected behavior and a minimal synthetic reproduction. Small pull requests with focused tests are welcome, especially for adapters, interoperability, performance and security. Use the private security-report channel for vulnerabilities.

Run the Python and JavaScript tests documented in README. Do not commit ledgers, credentials, generated token files, private project assets, real customer reports or runtime journals. New capture adapters must state what they capture, what they miss and how version binding and restoration are verified.

Maintain these invariants: immutable published states; atomic permission/version checks; no silent dependency resolution; explicit missing/unverified evidence; no automatic formal adoption by an agent; no telemetry without explicit local opt-in. Keep Core deterministic and model-independent. Preserve raw artifacts when adding derived views.

Contributions are submitted under the project's MIT license. Provide only work you have the right to contribute. There is no contributor license assignment requirement.

## CI setup

`docs/ci-workflow.yml` is a GitHub Actions template. A repository owner with workflow permissions can copy it to `.github/workflows/ci.yml` to run Python 3.11/3.12 and JavaScript tests on Ubuntu. It is not active merely by being in `docs`.
