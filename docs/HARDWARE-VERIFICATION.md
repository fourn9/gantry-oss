# Hardware adapter verification

## Current dependency caveat — 2026-11-12

The optional CAD constraints still require VTK 9.6.2 through CadQuery/OCP.
[VTK 9.7.1](https://discourse.vtk.org/t/vtk-9-7-1-release/16542) fixes GLTF
parser vulnerabilities, including bounds checks missing from upstream 9.6.2.
A clean advisory scan below is historical evidence, not proof those fixes are present.
The current Gantry adapter reads STEP, not GLTF; no GLTF reader path was identified
in Gantry. Customer scripts using VTK directly are outside that guarantee.

Do not parse untrusted GLTF with this optional environment or override OCP's exact
VTK constraint to force an unsupported update. A supported patched dependency
combination is tracked in [PR #17](https://github.com/fourn9/gantry-oss/pull/17).
Current released CadQuery 2.8.0 and OCP pins do not support VTK 9.7.2. Upgrade
acceptance requires dependency resolution, real STEP roundtrips and screening tests.

## Earlier verification

Verified 2026-11-02, CPython 3.12.15 / macOS arm64 / CadQuery 2.8.0.

- Full Python regression run: 582 cases, no failures, one skip, 172.615 seconds.
  An additional focused test then confirmed a captured failed solver result reaches
  the authenticated Mentor review and prevents an OK response; changes_requested succeeds.
- JavaScript regression tests: 7 passed.
- Real CadQuery tests: STEP import/cut/translation/export, original preservation,
  stale-source refusal, path/operation rejection, actual collision and separated pairs.
- Core integration tests: immutable captured reports, unchanged acceptance plan,
  missing/malformed/failed evidence, successful retry, retained previous states,
  no automatic adoption and event replay.
- Measurement tests: numerical limits; stale CAD, conditions, evaluator/environment,
  unit mismatch, missing/nonfinite measurements never produce a pass.
- `examples/hardware_evidence.py` executed using the patched runtime. Initial actual
  geometry: clearance fail, strength unknown. After STEP translation: clearance pass,
  strength unknown; adoption unadopted. Both candidate states remain in the ledger.
- Built wheel successfully. Installed-wheel module/CLI smoke check succeeded.
- pip-audit reported no known vulnerabilities for the resolved optional CAD/tooling
  environment. Exact public package versions are in hardware-runtime-constraints.txt.
  This is a point-in-time advisory match, not native-code security certification.

No mock geometry was used in the CAD tests/demo. Strength observation unit tests
use synthetic numeric fixtures; no FEA, physical prototype test or live vendor CAD
account was executed. The standalone demo invokes the real Service in-process;
the additional live verification below exercises HTTP and actual model inference.
Mentor responses in the automated regression tests remain explicit fixtures.

Security review: no model-generated Python/shell execution, unchanged Core permissions,
plan/source hash checks, preserved raw reports, new CAD output paths, bounded JSON,
no new server-side native parser or network fetch. CAD native operations require a
customer-side resource-limited Runner/container for hostile files. The CLI is not
itself an OS sandbox. Existing external measurement authenticity and completeness
remain declared; measured criteria do not certify physical fitness.

The changes are additive and require no ledger migration. Existing engineering
context/checkpoint APIs remain authoritative; restoring previous states preserves
old results. Revert the adapter modules/optional dependency/UI-neutral state-view
field to roll back code; never delete stored project evidence as part of rollback.

## Additional live HTTP and subscription review verification

Verified against commit ba199d120a0d11ff31f5426f21f37c56fc700421 on 2026-11-02,
using an isolated synthetic assembly and a real loopback HTTP server:

1. Imported, translated and exported STEP geometry with CadQuery. Static clearance
   changed from fail to pass; the missing required strength result stayed unknown.
2. Captured artifacts, published checkpoints and submitted a change review through
   the authenticated HTTP Client. Worker artifact retrieval also used HTTP.
3. The existing Mentor worker invoked official Codex with ChatGPT subscription
   login for both the mechanical specialist and integration coordinator. Both jobs
   completed and their outputs were returned to Core. No fixture inference or
   API-key fallback was used in this live run.
4. The coordinator returned conditional, requested defined structural assumptions
   and a strength report, preserved the acceptance thresholds, and identified that
   the proposed plan changes were outside the delegated write scope.
5. Formal adoption remained unadopted. Event replay matched.

The worker restored STEP files but omitted native geometry from the LLM text
input. The reviewers inspected actual machine-produced evidence, not geometry
independently. The CAD edit recipe and experiment sequencing were supplied by the
operator. A subsequent autonomous developer correction job was not exercised.
This does not establish cloud deployment, live vendor connectivity, FEA execution,
tolerance analysis or physical prototype validation.

Two preliminary harness attempts stopped before inference: one used a stale
session version after team configuration; the other retained record-only mode,
which correctly prevented review scheduling. Correcting initialization order and
explicitly selecting suggest mode allowed the final run to complete. No product
code changes were required.

Only this sanitized summary is published. Model journals, local ledgers and
credentials are not included in the source repository. These feature-branch
results do not change the already published v3.1.1 release.

The later [design change loop verification](DESIGN_CHANGE_LOOP_VERIFICATION.md)
exercises actual model-chosen CAD/control corrections, revalidation and a fresh task
after a dependency change. The earlier review-only limitation above describes that
earlier run, not the later demonstration.
