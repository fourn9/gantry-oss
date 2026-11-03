# Examples

Use anonymous fixtures in a fresh private output directory. Outputs can contain credentials, ledgers and model journals; do not commit or upload them. These examples demonstrate specific paths, not a finished robot or measured development speedup.

## Start here — no model calls

| Example | Demonstrates | Prerequisites |
| --- | --- | --- |
| [Development loop](development_loop.py) | HTTP capture, sharing and restoration | Installed Gantry |
| [Connected project](connected_project.py) | Edit, fixture review, correction and restart | Installed Gantry and supported command sandbox |
| [Studio demo](studio-demo/run.py) | Interactive artifact workspace with sample data | Installed Gantry; local browser |
| [Bot development](bot_development_loop.py) | Independent Bot task/report path | Installed Gantry; synthetic customer bridge |
| [Team workspace](team-workspace/acceptance.py) | Two identities, shared-state continuation and backup | Installed Gantry; local HTTP |

## Optional CAD environment — no model calls

| Example | Demonstrates |
| --- | --- |
| [Hardware evidence](hardware_evidence.py) | STEP editing and static collision checks; strength remains unverified |
| [Connected workspace](connected-workspace/acceptance.py) | HTTP sharing and independent restoration of saved CAD |
| [Engineering roundtrip](engineering_roundtrip.py) | CAD checkpoint, physical evidence and review |

These require a compatible CadQuery environment. See the [hardware adapter guide](../docs/HARDWARE-ADAPTER.md).

## Explicit customer-model execution

- [Connected project](connected_project.py) uses fixtures by default; `--live` makes subscription calls.
- [Crew reasoning loop](crew_reasoning_loop.py) requires explicit `--live-codex` for the real subscription exercise. Read its options before running.
- [Design change loop](design-change-loop/run.py) uses a customer subscription model and CadQuery. Read the [verification report](../docs/DESIGN_CHANGE_LOOP_VERIFICATION.md) first.
- [Learning comparison fixture](learning-comparison/case.json) is an input to the [paired evaluation procedure](../docs/BOT_LEARNING_EVALUATION.md), not a standalone executable.

Model usage consumes the customer's quota. No public example authorizes hardware operation, purchasing or formal adoption. Read the script's usage and its linked guide before running it; not every script uses the same command-line format.
