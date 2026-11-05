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

## CI setup

`docs/ci-workflow.yml` is a GitHub Actions template. A repository owner with workflow permissions can copy it to `.github/workflows/ci.yml` to run Python 3.11/3.12 and JavaScript tests on Ubuntu. It is not active merely by being in `docs`.

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
