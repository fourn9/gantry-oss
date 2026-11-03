# External engineering integrations

Reference workflow: Addy Osmani agent-skills, reviewed revision
2686b620fc1fed2e8f60c704839c766b8594c6b6. User authorized development; preserve
the concurrently edited checkout and private projects. This branch starts at e252da3.

## Objective and boundaries

Connect services listed by Flow Engineering to Gantry's existing saved-state,
requirement and evidence model. The official integration page lists 15 current
integrations and 14 coming-soon products; the home page also has product logos
without per-product contracts. Record these distinctions and do not claim parity
from a logo, an export-file import, or a mocked HTTP response.

## Capability map and implementation order

1. catalog: source-backed inventory, capabilities and verification status.
2. acquisition: bounded, read-only product-specific API requests; local exports.
3. capture: preserve original bytes, derive selected views, record provenance,
   revision limitations, incomplete capture and explicit requirement bindings.
4. publication: immutable merge/checkpoint using existing Core APIs and scopes;
   no automatic requirement adoption or pass from imported data.
5. CLI and tests: operator-owned credentials; agents can invoke the same CLI;
   documentation specifies native read, export-only and unsupported writes separately.

Cloud reads initially target public SaaS endpoints with explicit object identifiers.
No workspace-wide crawling, inbound webhook server, OAuth consent application,
silent credential discovery, arbitrary script execution or remote writes. Existing
GitHub/agent/Runner/physical-evidence paths remain reusable. Relyence and licensed
desktop tools require a documented API/SDK and a test environment before claiming
native support. Export captures work without those licenses, but are not live sync.

## Acceptance

- Catalog covers every integration-page name and separately labels home-only logos.
- Fixed endpoint recipes reject alternate hosts, redirects, credential parameters,
  malformed identifiers and unbounded data. Tokens come only from named environment
  references and are never serialized in bundles or errors.
- Raw payload bytes are retained with SHA-256. A view never replaces a native format.
- Object versions are captured when available; otherwise a captured content hash
  identifies the observation, not a claimed atomic remote revision.
- Pagination, nested content, omitted binaries and unavailable native edit support
  are explicit. Imported content is untrusted evidence, not agent instructions.
- A saved bundle can be published idempotently as an immutable development checkpoint,
  retaining existing files and scoped requirement references. Changed baseline and
  out-of-scope imports fail. Mentor sees the source mapping; no pass/adoption inferred.
- Local workbook cells, Python results and generic native exports are testable without
  customer credentials; cloud clients use fixture transport and are labeled unverified
  on live accounts until credentials and test projects are available.

## Validation commands

`python -m unittest discover -s tests -p 'test_external_integrations*.py' -v`
`python -m unittest discover -s tests -p 'test_*.py' -q`
`python -m gantry.integrations catalog`

New code lives in gantry/integrations; tests use synthetic data only. No changes to
the parent branch, version tags, remote services or public release in this side task.

## Implemented slice and acceptance (2026-11-03)

The user confirmed no live test accounts; implement and contract-test without
requesting credentials. Twelve current providers have fixed scoped SaaS read recipes.
Cursor/Python reuse the existing agent/Runner paths. Relyence and the 20 coming-soon
or home-only entries have saved-export capture only, explicitly not native connectors.
Native write-back, full recursive/page synchronization and OAuth app provisioning are
not implemented; see the exact provider matrix in docs/EXTERNAL-INTEGRATIONS.md.

Implemented original-byte bundles, bounded JSON-pointer views and local XLSX cell
views, explicit requirement references, credential-free provenance, capture omissions,
integrity inspection and immutable publication through existing Core checkpoints.
Same-source replacement preserves other files; local publication journals support
idempotent retries after a lost response. Old requirement baselines remain historical,
not newly satisfied. Native solver results still require the existing acceptance plan.

Evidence:
- Sixteen new tests passed: request/response cases for all twelve SaaS readers,
  GraphQL errors, pagination, credential/host/redirect/size boundaries, corrupted
  bundles, real XLSX ZIP/XML parsing, real Core publication/retry/requirement gaps,
  scoped-write rejection, changed requirements, Mentor context and replay.
- Full Python suite: 699 cases, one skipped, no failures (92.167 seconds).
- Wheel built/installed outside checkout; real CLI saved-file capture and manifest
  integrity inspection passed. No new dependency, Core schema change or ledger migration.
- Cloud responses are fixtures. No live vendor account, remote write, native commercial
  CAD, webhook, continuous synchronization or engineering speedup was verified.

Next integration acceptance requires actual read-only tenant credentials and test
objects. Relyence additionally needs its versioned API contract; commercial desktop
tools need the specified product/module and licensed runtime. Do not call exports
native integration or describe this slice as full Flow feature parity.
