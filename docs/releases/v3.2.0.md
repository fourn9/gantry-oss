# Gantry v3.2.0 — local CAD and physical evidence

Additive update to the public preview. No ledger migration is required.

## Added
- Optional CadQuery adapter: STEP import, bounded declarative editing and export.
- Static interference/clearance reports bound to the exact CAD inputs.
- Capture external strength, tolerance and prototype measurements against a fixed acceptance plan.
- Publish raw artifacts and physical check outcomes as immutable development checkpoints available to Mentor.
- Missing, stale or incompatible evidence stays unknown; sharing and review never imply formal adoption.

## Installation
Download the attached wheel and install it using an updated Python environment:

```sh
python -m pip install --upgrade ./gantry_ledger-3.2.0-py3-none-any.whl
# Optional local CAD support:
python -m pip install './gantry_ledger-3.2.0-py3-none-any.whl[cad]'
python -m gantry.hardware --help
```

CadQuery requires a compatible platform/Python and native dependencies. Tested on macOS arm64, Python 3.12.15, CadQuery 2.8.0. See docs/HARDWARE-ADAPTER.md.

## Verification and limits
582 Python regression cases (one skip, no failures), seven JavaScript tests, real STEP edit/collision/recheck and checkpoint publication. A separate authenticated loopback HTTP run used real Codex subscription inference for specialist and coordinator reviews; missing strength evidence produced a conditional verdict, not adoption. See docs/HARDWARE-VERIFICATION.md.

This is not an FEA solver, tolerance simulation engine, physical test-bench driver, continuous-motion verifier or live Onshape/Fusion connector. External measurements must come from those systems. The live verification used an operator-specified CAD edit, not autonomous CAD redesign. Native CAD parsing runs locally and requires an appropriately resource-limited environment for untrusted files.

## Upgrade and rollback
Back up the ledger and artifact store before upgrading. No stored history is rewritten. To roll back, stop workers and reinstall the v3.1.1 wheel; preserve the ledger and artifacts. New adapter commands are unavailable on the older version. Updating Gantry does not update Python or OS security patches.
