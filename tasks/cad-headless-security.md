# Remove unnecessary VTK from the built-in CAD runtime

Date: 2026-11-13. Addy Osmani agent-skills revision 2686b620fc1fed2e8f60c704839c766b8594c6b6.

Scope: PR #17 cannot resolve as a one-line pip pin. CadQuery 2.8 requires OCP <8;
OCP's VTK wheel pins 9.6.2. Use the official same-version OCP no-VTK build for
Gantry's bounded STEP operations. Do not override package metadata, rebuild native
libraries, or alter users' existing CAD environments. External CadQuery scripts
remain external and need their own environment. Core data and auth unchanged.

Acceptance / ordered tasks:
- [ ] Fresh wheel-only environment resolves with no VTK, CadQuery or dependency overrides.
- [ ] Built-in box/cylinder/translation/boolean/STEP edit and collision/clearance use the same OCCT kernel; real analytic geometry regression tests pass.
- [ ] Isolated review subprocess measures STEP/STL without VTK and retains timeout/hash checks; hardware evidence declares the actual backend.
- [ ] Distribution/doctor/docs/CI verify the new optional runtime. Existing environments need recreation (in-place pip upgrades do not remove old packages).
- [ ] Full regression, dependency audit, independent review and published PR evidence.

Trust boundary: native files are untrusted inputs, still parsed locally under the
existing runner/resource limits. Removing VTK avoids its GLTF parsers; this does
not certify OCCT against all malformed STEP/STL or establish physical fitness.
No support for GLTF, native parametric CAD editing, or automatic adoption is added.

Primary sources:
- https://pypi.org/pypi/cadquery/2.8.0/json
- https://pypi.org/pypi/cadquery-ocp/7.9.3.1.1/json
- https://pypi.org/project/cadquery-ocp-novtk/7.9.3.1.1/
- https://github.com/CadQuery/ocp-build-system/blob/main/README.md
- https://dev.opencascade.org/doc/refman/html/class_s_t_e_p_control___reader.html
- https://dev.opencascade.org/doc/refman/html/class_b_rep_algo_a_p_i___boolean_operation.html

## Evidence

- Fresh CPython 3.12.15/macOS arm64 wheel-only OCP installation succeeded. Package
  metadata contains no VTK/full OCP/CadQuery; `pip check` and current `pip-audit`
  pass (local editable Gantry skipped by advisory lookup, not native dependencies).
- Analytic real geometry tests: 9 passed, including STEP multi-solid roundtrip,
  cut/fuse, preserved source solids, touching/disjoint intersection, clearance,
  STL inspection and isolated installed-adapter subprocess.
- New old-VTK baseline test failed before adding the floor, then all 5 baseline
  tests passed. Fresh-env geometry tests initially failed for missing adapter;
  STL test failed for absent export support before implementation.
- Actual hardware example: clearance fail → pass; strength stays unknown and
  adoption unadopted. Engineering roundtrip restores exact bytes and replays
  consistently; lost acknowledgement recovery is an explicitly injected failure.
- Connected-workspace example: real loopback HTTP, native STEP/STL, two identities,
  shared checkpoint and continuation. Anonymous fixtures only; no live model,
  licensed CAD service, dynamics/FEA or physical hardware was used.
- Independent review found a two-shape constructor performing a destructive build
  before the flag and a second build afterwards. Fixed to configure arguments and
  nondestructive mode before one build. Geometry regression and re-review passed.
