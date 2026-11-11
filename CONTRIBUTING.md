# Contributing

Start with an issue describing the workflow, expected behavior and a minimal synthetic reproduction. Small pull requests with focused tests are welcome, especially for adapters, interoperability, performance and security. Use the private security-report channel for vulnerabilities.

Run the Python and JavaScript tests documented in README. Do not commit ledgers, credentials, generated token files, private project assets, real customer reports or runtime journals. New capture adapters must state what they capture, what they miss and how version binding and restoration are verified.

Maintain these invariants: immutable published states; atomic permission/version checks; no silent dependency resolution; explicit missing/unverified evidence; no automatic formal adoption by an agent; no telemetry without explicit local opt-in. Keep Core deterministic and model-independent. Preserve raw artifacts when adding derived views.

Contributions are submitted under the project's MIT license. Provide only work you have the right to contribute. There is no contributor license assignment requirement.

## Repository map

- `gantry/`: runtime, adapters and Studio UI.
- `tests/`: automated regression tests.
- [website/](website/README.md): public static website, browser-only demo and its tests.
- [docs/](docs/README.md): usage guides, contracts and verification records.
- [examples/](examples/README.md): anonymous demonstrations with explicit prerequisites.
- [tasks/](tasks/README.md): implementation history and unresolved task-specific items.
- `deploy/`: operator-managed service/proxy templates.

Keep a single guide authoritative for each workflow; link to it rather than duplicating its instructions. Keep dated test evidence separate from current setup instructions.

## CI

`.github/workflows/ci.yml` runs on pull requests, on pushes to `main` and on manual dispatch. It runs the Python tests with Python 3.11.17 and 3.12.15 on Ubuntu 22.04 and macOS 15, the dependency audit, and the JavaScript tests in `tests/` and `website/tests/`. The Linux jobs install bubblewrap, and each job checks the OS command sandbox before the suite, so sandbox tests run in CI. They skip only on a host with no supported sandbox. The `ci-required` job succeeds only when every matrix job succeeds. `docs/ci-workflow.yml` is kept as an identical copy. Requiring `ci-required` and a review before merge is a repository setting (branch protection); the workflow file does not enable it.

## Refresh the API reference

Generate from the same source revision after all service contracts are imported:

```sh
python3 - <<'PYTHON'
import json
from pathlib import Path
from gantry.service import Service  # registers service contracts
from gantry.contracts import CONTRACTS
Path("docs/api-contracts.json").write_text(
    json.dumps(CONTRACTS, indent=2, sort_keys=True) + "\n"
)
PYTHON
```

This is documentation generation, not a ledger migration or a service start.
