# Headless CAD runtime migration

Gantry's built-in STEP editor, static clearance screening and STEP/STL inspection
use `cadquery-ocp-novtk==7.9.3.1.1` and its matching proxy. This is the same OCCT
kernel version previously used through CadQuery 2.8, without VTK or CadQuery's
visualization dependencies. It does not implement general CadQuery scripting.

## Why remove VTK instead of overriding its pin?

[Full OCP 7.9.3.1.1](https://pypi.org/pypi/cadquery-ocp/7.9.3.1.1/json) pins VTK
9.6.2. [CadQuery 2.8](https://pypi.org/pypi/cadquery/2.8.0/json) requires OCP <8.
[VTK 9.7.1](https://discourse.vtk.org/t/vtk-9-7-1-release/16542) fixes GLTF parser
vulnerabilities absent from the pinned upstream VTK. A clean advisory scan is not
proof those native fixes exist. Forcing 9.7.2 violates the supported binary package
contract. Conda OCP 7.9 builds inspected on 2026-11-13 likewise require VTK <9.7.

The [official no-VTK distribution](https://pypi.org/project/cadquery-ocp-novtk/7.9.3.1.1/)
requires only its matching proxy. Gantry does not need GLTF parsing or VTK rendering
for its bounded operations. Removing this dependency resolves that exposure in a
fresh built-in runtime without a custom native build or dependency override.

## Migrate safely

1. Preserve existing environments and project history for reproducibility.
2. Create a **new** virtual environment with a security-supported Python version.
3. Install Gantry `[cad]` using the hardware-adapter installation instructions.
4. Run `gantry-engineering doctor`, `python -m pip check`, and the CAD smoke example.
5. Point the customer Runner and `GANTRY_CAD_PYTHON` at this new interpreter.

The inspection interpreter must have Gantry installed: isolated subprocesses load
its trusted adapter, not project Python files. Do not co-install `cadquery-ocp`
and `cadquery-ocp-novtk`; both own the OCP namespace and the adapter rejects that mix.
An in-place `pip install --upgrade` does **not** uninstall obsolete VTK/CadQuery.
The maintenance checker now reports installed VTK older than 9.7.1, including remnants.

External CadQuery scripts may continue in a separately managed environment, but
this migration does not patch that environment or its third-party native libraries.
Do not parse untrusted GLTF there. No existing ledger results are rewritten: new
reports record `cad_backend: OCP no-VTK 7.9.3.1.1`; prior environment identities stay intact.
Re-run affected evaluations under the new environment; do not inherit old passes.

## Limits

Native STEP/STL parsers still need the customer-local Runner's resource limits and
sandbox. This dependency change is not protection against every malformed native
file, physical certification, vendor-CAD qualification, or a claim of faster design.
No GLTF support is added. Editable parametric CAD remains in the external tool.

## Verification

See `tasks/cad-headless-security.md` and the linked PR for exact local/CI results.
CI installs the CAD extra, checks for absence of VTK/full OCP/CadQuery and runs real
geometry tests so an optional-dependency skip cannot hide a broken CAD runtime.
