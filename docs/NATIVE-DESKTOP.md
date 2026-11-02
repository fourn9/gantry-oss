# Native desktop engineering connectors

`gantry-native` runs beside the customer's licensed application. It can attach to
the application API, read a selected field, prepare a change, apply it and capture
the observed result. A native API update is different from capturing a STEP/export
file. These connectors do not create an entire design or implement all vendor APIs.

**Qualification: experimental. No Windows/vendor application was available for
this implementation. Tests use synthetic API objects. No live vendor run, physical
validation, production qualification or performance improvement is claimed.**
Install and qualify against a disposable project before enabling an agent to write.

## Exact scope

| Product ID | Implemented path | Write/save scope | Still unavailable |
|---|---|---|---|
| `solidworks` | Attach to COM; read existing dimension | Set SI value in active configuration, rebuild, Save3, read back | Assemblies, feature creation, equations and dependency restoration |
| `catia-v5` | Attach to V5 Automation; read numeric part parameter | Set writable, non-relation-driven Value, Part.Update, document.Save, read back | CATProduct, 3DEXPERIENCE APIs, automatic unit conversion |
| `creo` | VB API asynchronous connection; read typed model parameter | Set scalar union value, regenerate, save local .prt, capture latest numbered file | Windchill, assemblies, dimensions, automatic application version detection |
| `solidworks-electrical` | Electrical COM API; identify environment/project; read user data | Set existing project user-data field, update database, read back | Wiring/routing edits, entire project archive, unrelated editor dirty-state capture |
| `altium` | Generate DelphiScript for the native PCB host | Existing PCB component comment; optional save/reload/readback and saved-byte capture | Automated host invocation, live runtime qualification, schematic editing, Altium 365 API |
| `cadence` | Generate SKILL for Allegro PCB Editor | Existing string property on current design; transaction and in-memory readback | Automated host invocation, verified native save, OrCAD/Virtuoso/general Cadence support |
| `zuken-e3` | **Blocked; no executable native driver** | None | E3.series module/version, licensed SDK member signatures and save/identity semantics |
| `capital` | **Blocked; no executable native driver** | None | Exact Capital module/version, licensed Java/SOA SDK, identity/transaction/save contracts |

Zuken CR-8000 is not E3.series. Capital is a product family, not one interchangeable
endpoint. The two blocked entries reject operations rather than returning mock
success. They are not native connections. The absence of a test machine alone is
not their only blocker: the precise SDK contracts are also missing.

The direct drivers modify **existing** selected fields. SOLIDWORKS Electrical
project metadata support does not mean its harness engineering workflow is automated.
All eight are listed by `gantry-native catalog` with `native_runtime_verified: false`.

## Execution path and authority

```text
Customer operator/agent, with local tool permission
  -> gantry-native inspect / prepare
  -> review immutable plan and exact target
  -> apply with plan digest and exclusive-editor acknowledgement
  -> local vendor API -> readback -> local journal and evidence bundle
  -> explicit publish -> existing Gantry scoped checkpoint API
  -> Core / Mentor / Crew can retrieve the requirement-linked state
```

This is an operator CLI, not a new unrestricted MCP tool. It uses the OS user's
vendor permissions. A Gantry server token does not grant permission to modify CAD.
Use the customer's existing agent/shell approval system for the native CLI and a
scoped Gantry token for publication. No new agent, model call, paid API, telemetry,
vendor account, OAuth app or background synchronization is started.

The native CLI is separate from the POSIX-specific scoped project Runner. Import
tests check that it does not load `fcntl` or that Runner. This is not evidence that
the full Gantry `connect` sandbox or server is Windows-qualified.

## Windows prerequisites

- Python 3.11+ with current security fixes, matching vendor SDK architecture.
- Installed, licensed application and registered automation/type libraries.
- Customer-controlled private local folder containing a disposable, saved part.
- One operator; pause other agents and GUI editing for the complete operation.
- Install this checkout in a virtual environment: `python -m pip install ".[native-windows]"`.
  This optional extra pins pywin32 312 and comtypes 1.4.17 on Windows only. These
  package versions have not been qualified against licensed CAD in this project.
- For Creo, follow the installed VB API registration/environment instructions and
  open one compatible session. The adapter attaches with Connect, never starts or
  ends Creo; it Disconnects on normal completion. The model origin and working
  directory must match. Native Save behavior remains subject to the Creo configuration.
- For SOLIDWORKS Electrical, supply the vendor API license code using a process
  environment reference `GANTRY_CONNECTOR_ELECTRICAL`, not in JSON, a plan or logs.
  The vendor application itself may require separate API licensing.

## Direct read/write example

Example `target.json` for a saved disposable SOLIDWORKS part:

```json
{"product":"solidworks","document":"bracket.SLDPRT","selector":"D1@Sketch1","unit":"SI","version":"operator-unknown"}
```

`document` is relative to the explicit operator root. Active document path must
match it. `inspect` returns the actual application version without enforcing the
declared version; copy `application_version` into the config before `prepare`.
For SOLIDWORKS it is the API revision string, not the marketing year.

```sh
gantry-native inspect --root C:/work/disposable --config target.json
gantry-native prepare --root C:/work/disposable --config target.json --value 0.03 --reason "Increase bracket reach" --requirements requirements.json --output C:/captures/change-001
# Review C:/captures/change-001/payload/plan.json and the reported plan_hash.
gantry-native apply --root C:/work/disposable --plan C:/captures/change-001 --expect-plan EXACT_PLAN_HASH --exclusive
gantry-native evidence --root C:/work/disposable --plan C:/captures/change-001 --output C:/captures/result-001
```

`--value` is a JSON scalar. Optional `requirements.json` contains immutable links:

```json
[{"requirement_id":"req_reach","revision_id":"rev_adopted_reach"}]
```

Other target shapes (values/version strings are examples, not qualified releases):

```json
{"product":"catia-v5","document":"bracket.CATPart","selector":"Length.1","unit":"native","version":"5.34.0"}
```

```json
{"product":"creo","document":"bracket.prt","selector":"LENGTH","value_type":"double","unit":"native","version":"operator-declared-installed-release"}
```

Creo accepts `double`, `integer`, `boolean`, `string`; the COM union rejects an
incompatible actual parameter. A logical `.prt` matches the highest local numbered
file, e.g. `.prt.7`. Runtime application version is **not captured** by this async
driver; the declared version and model version stamp are stored separately.

```json
{"product":"solidworks-electrical","project_id":"7","environment":{"hostname":"cad-db","working_folder":"C:\\ElectricalData\\"},"field":1,"unit":"text","version":"2026.0.0"}
```

Electrical environment fields must exactly match the API's hostname and working
folder. No password or connection string is fetched. Only the selected user-data
field and project metadata are captured; the native database is not backed up.
Pass `--credential-ref GANTRY_CONNECTOR_ELECTRICAL` on native commands.

## Altium and Allegro native script path

Prepare on the same machine/path where the licensed editor will execute the script.
Only printable ASCII paths/values are supported initially. Target examples:

```json
{"product":"altium","document":"board.PcbDoc","selector":"R1","version":"operator-declared-installed-release"}
```

```json
{"product":"cadence","document":"board.brd","selector":"DESIGN_NOTE","version":"operator-declared-installed-release"}
```

```sh
gantry-native script-prepare --root C:/work/disposable --config pcb.json --expected '"old"' --value '"new"' --reason "Clarify component value" --output C:/captures/pcb-001
```

The quoting above is shell syntax for passing JSON strings; use the corresponding
quoting for your shell. Open and review `operation.pas` or `operation.il`. In Altium,
add the `.pas` to a script project and run `GantryApply`. In Allegro, load `.il` in
the native SKILL host and call `gantryApply()`. These steps require a human/operator
and have not been run here. Nothing executes on `script-prepare`.

The script checks native document identity, existence and old field value before
editing. It writes `started` before attempting the operation and `result.json`
only after the selected value matches. An existing marker prevents sequential
retry; it is not a distributed lock. Keep exclusive editor access. Allegro uses
`axlGetDrawingName()` for the full path; a path spelling mismatch fails closed.

```sh
gantry-native script-collect --root C:/work/disposable --package C:/captures/pcb-001 --output C:/captures/pcb-result-001
```

With the default v1 plan, collection verifies the plan/script/digest, captures the
on-disk file, and reports `applied_in_memory` or `unknown`. It does not report a
saved update. Native save is an operator step and on-disk bytes may still be the
original file. Altium can opt into the separate v2 persistence path below; Allegro
retains the v1 `saved: false` contract.
The native-host receipt is an explicit report, not cryptographic proof against
tampering by the OS user. Absolute local paths appear in the generated script;
review before sharing the bundle. There is no arbitrary caller-provided script execution.

### Altium optional persistence

Add `--save-format 'PCB Binary'` to `script-prepare` for a new v2 plan. Run the
generated `GantryApply` in the licensed host under exclusive editor access. This
path checks the dirty flag and compares native bytes against the prepared baseline,
changes the selected comment, calls `IServerDocument.DoFileSave`, reloads with
`DoFileLoad`, reacquires the component and reads the value again. It captures the
saved file to `native-saved.PcbDoc` before producing a `saved_and_reloaded` receipt.
Collect rejects missing/stale captures or unchanged bytes for a reported change.

This outcome means **host-reported persistence**, not a qualified Altium runtime
or physical/electrical correctness. The script is contract-tested but has not been
compiled/run in Altium here. Confirm the installed save format in a disposable PCB;
other formats are intentionally rejected. The initial host command remains an
operator step. A failure after dispatch stays unknown; no automatic rewrite or
rollback. Original v1 scripts/receipts retain their in-memory-only semantics.
Allegro continues to require a separately qualified save/reopen implementation.

Primary save/reload contract:
[IServerDocument](https://www.altium.com/documentation/altium-dxp-developer/iserverdocument-interface),
[IClient document lookup](https://www.altium.com/documentation/altium-dxp-developer/iclient-interface).

## Recovery, integrity and limits

- Prepare captures original bytes and selected metadata, fixes desired value,
  reason, requirement links, declared version and operator-root identity.
- Apply requires a matching plan hash, saved/unchanged baseline and the same root.
  Dirty part, changed file/configuration/value/version, symlink/hardlink or outside
  path is rejected. Observation is repeated around capture to catch changing state.
- A synchronous SQLite journal commits `dispatching` plus a document-level hold
  **before** native mutation. The same plan returns its receipt, never dispatches
  again. Keep `.gantry-native` and its journal; deleting it defeats deduplication.
- This is preflight checking, not atomic vendor CAS. Native GUI/external processes
  do not obey Gantry's lock. Separate operator roots/machines do not share locks.
- After interruption, timeout, native API error or readback failure, the outcome
  can be unknown. The editor may have continued after the client stopped. Do not
  retry or create another plan until the original writer is stopped and inspected.
  Read-only `reconcile --writer-stopped` compares the current selected value:

```sh
gantry-native reconcile --root C:/work/disposable --plan C:/captures/change-001 --writer-stopped
```

  `observed_desired` permits releasing that local hold; it does not prove who caused
  the change. A mismatch keeps the hold. Existing terminal receipts/evidence are
  not overwritten by later reconciliation. No automatic rollback or forced release.
- `verified` means selected native value read back after save/update. It is not
  interference, strength, electrical, manufacturing or requirement verification.
- Direct captures are capped at 16 MiB/file, 32 MiB/bundle. An oversized input
  refuses before mutation; an oversized output keeps an unknown outcome/hold.
  Large assemblies and dependency-complete restoration remain unsupported.
- Credential filenames and recognizable secrets are rejected. This is not a full
  DLP scanner for binary proprietary files. Use a private folder; POSIX modes do
  not replace a Windows directory ACL. No automatic upload occurs.

## Publish to Gantry

Create/select an existing development state and change whose approved write scope
includes `imports/<source_id>/`. Its requirement scope must contain the bundle's
links. `source_id` is in the evidence manifest. Keep the token file outside captures.

```sh
gantry-native publish --bundle C:/captures/result-001 --url https://your-gantry.example --token-file C:/private/gantry.token --state STATE_ID --change CHANGE_ID --version 1 --key unique-publication-key
```

Publication uses the existing capture/checkpoint APIs, preserves other project
files, and rechecks expected change version. The resulting development state is
unverified and unadopted. Stale requirements remain historical/need review; this
adapter cannot approve them or start a task just by publishing.

## API sources and qualification checklist

Reviewed 2026-11-03. Vendor SDK redistribution is not included.

- SOLIDWORKS: [dimension values](https://help.solidworks.com/2016/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IDimension~GetSystemValue3.html), [save](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDoc2~Save3.html), [configuration constants](https://help.solidworks.com/2022/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swInConfigurationOpts_e.html).
- CATIA: Automation API members used are `ActiveDocument.Part.Parameters.Item`,
  `ReadOnly`, `OptionalRelation`, numeric `Value`, `Part.Update`, `Save` and
  `SystemConfiguration`. Cross-checked against the maintained [pycatia parameter bindings](https://pycatia.readthedocs.io/en/0.4.3/api/pycatia/knowledge_interfaces/parameter.html) and [system configuration bindings](https://pycatia.readthedocs.io/en/0.6.2/api/pycatia/in_interfaces/system_configuration.html).
  Installed Dassault CAA/type-library verification is still required; these bindings
  are not a certification of every CATIA V5 release.
- Creo: PTC [async connection](https://support.ptc.com/help/creo_toolkit/vbapi_plus/usascii/creo_toolkit/api/dita/t-pfcAsyncConnection-AsyncConnection.html), [model](https://support.ptc.com/help/creo_toolkit/vbapi_plus/usascii/creo_toolkit/api/dita/t-pfcModel-Model.html), [parameter value union](https://support.ptc.com/help/creo_toolkit/vbapi_plus/usascii/creo_toolkit/api/dita/t-pfcModelItem-ParamValue.html).
- Electrical: [vendor Python binding example](https://help.solidworks.com/2026/english/api/sldworkselecapihelp/index.html?id=3.0.3), [project](https://help.solidworks.com/2024/English/api/sldworkselecapihelp/interface_i_ew_project_x.html), [environment identity](https://help.solidworks.com/2026/english/api/sldworkselecapihelp/interface_i_ew_environment_x.html).
- Altium: [PCB object interfaces](https://www.altium.com/documentation/altium-dxp-developer/pcb-api-design-objects-interfaces-reference), [PCB server transaction/notification interfaces](https://www.altium.com/documentation/altium-dxp-developer/pcb-api-system-interfaces-reference).
- Allegro: [Cadence native transaction guidance](https://community.cadence.com/cadence_blogs_8/b/pcb/posts/functions-for-good-skill-programming), [property update](https://community.cadence.com/cadence_technology_forums/pcb-design/f/allegro-x-pcb-editor/34882/accessing-symbol-user-defined-properties-in-a-board-file), [full native drawing path](https://community.cadence.com/cadence_technology_forums/pcb-design/f/allegro-x-pcb-editor/20182/getting-fqn-of-the-current-board-file/1293751). Installed SKILL reference and runtime qualification are required.
- Zuken: [official E3 scripting introduction](https://www.zuken.com/us/blog/a-beginners-guide-to-scripting-for-e3-series/) describes COM and signal reading, but does not provide the write/save/identity contract needed here.
- Capital: [Siemens API/integration overview](https://www.siemens.com/en-us/products/capital/ee-systems-data-integrations/data-management/) describes extensibility, not the module-specific method signatures.

Before marking any driver qualified: record exact product/build/SDK/COM binding,
use a disposable native file, read/change/save/close/reopen, prove unchanged unrelated
fields, exercise wrong document/version/dirty state, interrupt a dispatched update,
reconcile without rewriting, and publish/restore evidence through Core. For scripts,
also compile/run in the native host and implement/qualify native save/readback.
No item in that live qualification checklist has been completed here.
