# Vendor CAD connections — experimental work in progress

This is NOT eight working native integrations. The common capture protocol is
implemented; two read-only Windows Automation drivers are written but have not
been exercised with licensed products. Six native SDK drivers remain to be built.
No vendor installation, license or product-specific test project was available.
The published v3.2.0 release does not include this work.

## Coverage

| Product | Gantry-side handoff | Native driver | Not implemented |
|---|---|---|---|
| SOLIDWORKS | implemented | experimental active saved document capture via COM | feature editing, assembly/dependency traversal, PDM |
| Creo Parametric | implemented | requires TOOLKIT implementation and release selection | native read/write/export |
| CATIA V5 | implemented | experimental active saved document capture via Automation | feature editing, assembly traversal, 3DEXPERIENCE |
| Altium Designer | implemented | requires PCB/Sch scripting implementation | circuit/board extraction, edit, ERC/DRC execution |
| Cadence | implemented | product unresolved (Allegro vs OrCAD) | native extraction/edit/check execution |
| Zuken E3.series | implemented | requires COM implementation/version selection | connector/wire topology, edit, checks; other Zuken products |
| Siemens Capital | implemented | module/API/SDK unresolved | model extraction/edit/check execution |
| SOLIDWORKS Electrical | implemented | requires separate Electrical API and applicable API license | project/device/wire extraction/edit |

A successful protocol fixture is not a successful vendor connection. Do not use
these names as a compatibility or vendor certification badge.

## Data contract

`python -m gantry.vendor_bridge catalog` reports the actual driver status.

The local `prepare` command copies explicitly selected native files into a new
bundle. `request.json` fixes product, application version, operation, request ID
and input hashes. Credentials are never part of the bundle. The digest is an
integrity binding, not a signature authenticating the vendor. Use a private local
workspace with trusted operator access; a malicious owner can rewrite a bundle.

The customer-side vendor plug-in produces `output/` and `result.json`:

- schema_version, request_id, request_hash, product, version and operation must
  match the request; only capture is currently supported.
- status must be completed for collection. A failed run must not create success.
- files maps each relative output path to SHA-256. No unlisted files are accepted.
- observations carries kind, source_id, source_path and attributes. Kinds include
  document, component, parameter, net, connection, wire and diagnostic. IDs are
  vendor-local and only stable as far as the originating API guarantees. Units,
  frames and pin identifiers must be explicit attributes where applicable.
- coverage must list captured, missing and inferred information. Raw native files
  remain intact alongside observations; this is not lossy universal CAD conversion.

The format does not infer circuit semantics or cross-tool component equivalence.
It does not accept a global verified flag. Physical evidence still uses the separate
frozen acceptance-plan path in HARDWARE-ADAPTER.md.

`collect` validates exact hashes and source references and writes a new collection.
`publish` uploads that collection through existing authenticated artifact APIs.
It does not attach a snapshot to a change, merge, adopt or execute CAD operations.
Use existing checkpoint APIs with a complete workspace to attach artifacts to a
change; preserve unrelated files. Do not substitute a partial collection for the
full project snapshot.

## Example: experimental saved-document capture

On the customer Windows machine, install Gantry and pywin32 in an isolated Python
environment. Run an existing licensed SOLIDWORKS application. All commands below
are local except the explicit publish step.

```sh
python -m gantry.vendor_bridge prepare --root C:/project \
  --file bracket.SLDPRT --product solidworks --version 34.0.0 \
  --output C:/gantry-jobs/capture-1
```

Version must be the exact `ISldWorks.RevisionNumber()` string from the local
installation (34.0.0 above is an example, not a tested release). Open the copied
`input/bracket.SLDPRT` in SOLIDWORKS manually, without modifying it. Then:

```sh
python -m gantry.vendor_desktop --bundle C:/gantry-jobs/capture-1
python -m gantry.vendor_bridge collect --bundle C:/gantry-jobs/capture-1 \
  --output C:/gantry-jobs/collected-1
python -m gantry.vendor_bridge publish --collection C:/gantry-jobs/collected-1 \
  --url https://your-gantry.example --token-file C:/private/gantry.token --key capture-1
```

The driver refuses dirty documents, a different active document, wrong version,
modified inputs, nonempty output or an existing receipt. It does not launch CAD,
open arbitrary files, save a project, traverse dependencies or execute macros.
Native file references may still point outside the copied directory: review them
before opening the copy in vendor software. Staging is not a native-app sandbox.

CATIA V5 uses `--product catia-v5`, native `.CATPart` etc., and the exact version
string `SystemConfiguration.Version.Release.ServicePack` (for example `5.30.1`).
Only saved active-document capture is implemented. Product API behavior and COM
binding still need live validation on the actual release.

## Limits and security

- Native binary files may contain embedded scripts or confidential data. Gantry
  does not execute them; the customer app may. Secret detection is heuristic,
  not a guarantee of native-content inspection. Review selected data before sharing.
- Current bundles cap each file at 64 MiB and aggregate input/output at 256 MiB;
  up to 1000 selected files. Large production assemblies need a streaming follow-up.
- No vendor SDK, license key, private customer project or model journal is bundled.
- No generic shell/COM evaluator or arbitrary macro execution is provided.
- Missing SDK drivers fail as unsupported rather than pretending file capture is
  native manipulation. Failed/partial output is not automatically retried.
- COM calls are synchronous and can block on application dialogs; use a supervised
  customer process. Automatic timeout/recovery of vendor applications is not provided.

## Sources and remaining prerequisites

- [SOLIDWORKS API](https://www.solidworks.com/sw/support/api-support.htm): COM;
  GetPathName/GetSaveFlag/RevisionNumber provide the read-only capture checks.
- [Creo TOOLKIT](https://www.ptc.com/en/support/help/Creo_Toolkit): select release,
  C++/Java/VB binding and available licensed SDK before implementing native calls.
- [Dassault developer guides](https://www.3ds.com/support/documentation/developer-guides):
  CATIA V5/CAA differs from 3DEXPERIENCE. Validate against installed Automation docs.
- [Altium scripting API](https://www.altium.com/documentation/altium-dxp-developer/pcb-api-system-interfaces-reference):
  PCB/Sch objects and edit notification/undo contracts require product scripting.
- [Cadence SKILL](https://video.pcb.cadence.com/watch/5H3V6EGDpKrMUtS9jvt3c1?chapter=1):
  Allegro and OrCAD must not be assumed to share one integration API.
- [Zuken E3 API](https://www.zuken.com/en/product/e3series/e3-series-2025-whats-new/):
  versioned COM interface; E3.series is the provisional harness target.
- [Capital integrations](https://www.siemens.com/en-gb/products/capital/ee-systems-data-integrations/data-management/):
  Java/JavaScript and SOA interfaces; exact module/SDK needed, no invented endpoint.
- [SOLIDWORKS Electrical API](https://help.solidworks.com/2023/english/api/sldworkselecapihelp/index.html?id=3.0):
  separate application/API licensing and factory; not SOLIDWORKS MCAD COM.

Before production enablement: provide the installed release/SDK, a synthetic
project, expected object IDs/units, read/export/edit acceptance tests and an isolated
customer environment. Native editing must preserve originals, record API errors,
and support uncertain-outcome reconciliation before it can be enabled.
