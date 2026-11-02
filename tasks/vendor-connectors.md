# Vendor connector implementation

Reference: Addy Osmani agent-skills 2686b620fc1fed2e8f60c704839c766b8594c6b6.
User confirmed no vendor installations/test environment are available.

## Scope / architecture
- vendor-contract: local request/result bundles, exact input hashes, explicit tool
  product/version and capability, preserved native files, normalized observations.
- vendor-capture: validate bundles and feed existing artifact/checkpoint APIs.
- vendor-drivers: vendor APIs run on customer machines; no native parser in Core.
Build contract → capture → available native drivers. No migration.

Products: SOLIDWORKS, Creo Parametric, CATIA V5, Altium Designer, Cadence
Allegro/OrCAD (edition unresolved), Zuken E3.series (assumption for harness),
Siemens Capital (module unresolved), SOLIDWORKS Electrical.

Success criteria: offline handoff tied to exact input and request; reject changed
inputs, changed output, missing coverage, path escapes, fabricated verification
status; save raw and normalized data together; preserve unrelated state. Tests
must distinguish protocol fixtures from real product execution. No real product
connection may be claimed without live licensed validation.

This slice does not silently execute vendor macros, fetch credentials, modify an
open customer project, certify physics, or automatically adopt changes. SDK/API
availability and supported edition are explicit prerequisites, not capabilities
inferred from a vendor name. Native write operations remain disabled until a
vendor-specific implementation is validated.

- [x] Bundle contract and regression tests
- [x] Explicit native API capability/status registry
- [x] Saved-file capture via existing artifact APIs; checkpoint attachment documented
- [x] Experimental read-only saved-document drivers for SOLIDWORKS/CATIA; COM doubles only
- [x] Product setup instructions and limitations
- [x] Full regression and package build verification
- [ ] Live licensed vendor tests (blocked: no environment)

## Verification / outstanding
- Full regression: 642 cases, no failures, one skip. JS: 7 passed.
- Vendor contract checks use synthetic bundles and COM doubles, not vendor engines.
- Real local Core captured native bytes and normalized evidence together.
- Six native SDK drivers, all write/edit operations and live Windows/vendor testing
  remain incomplete. User has no environment; no claim of eight working integrations.
- Isolated feature branch, no published release change.
