# External integration completion — 2026-11-03

## Scope and authority

Finish gaps in the existing customer-local connectors; reuse immutable captures,
scoped publication and reviewed write plans. User authorized implementation and
contract tests without vendor accounts or licensed desktop environments. Work stays
in this side worktree; no main Bot changes, remote publication, paid services or
private project fixtures. Addy Osmani agent-skills reviewed revision:
`2686b620fc1fed2e8f60c704839c766b8594c6b6` (specification, planning, incremental
implementation, TDD, source-driven API design and security/review).

Python 3.11+ stdlib package, tested on the existing Python 3.12 runtime. No new
runtime dependencies. Existing captures and native v1 plans remain readable.

## Slices / acceptance

- [x] Altium opt-in native save/reload: inspect a clean selected PCB, change only
  the selected comment, save in explicitly selected native format, reload and
  reread that component. Save/reload failure has no success receipt. Collector
  preserves original/result bytes and explicit host-reported persistence, never
  physical correctness or runtime qualification. Old in-memory plans unchanged.
- [x] Bounded paginated capture: Notion nested blocks and Slack selected windows
  or threads retain each raw response and source relationship. Cursor loops,
  malformed payloads and acquisition bounds cannot masquerade as completeness.
  Partial acquisition persists completed pages and a resumable pending queue.
- [ ] Cloud file bodies: Google Drive blob download and SharePoint selected file
  download with before/after revision checks, size checks and original bytes.
  Downloads never forward API credentials to a content host. Short-lived signed
  URLs never enter captures/errors; unexpected hosts/redirects fail closed.
- [ ] Existing publish/restore and reviewed writes continue working. CLI and
  capability catalog describe exact scopes. Regression, packaging and security
  checks recorded separately from unavailable authenticated/vendor tests.

## Boundaries / unresolved prerequisites

Zuken E3 and Capital lack exact SDK member/identity/transaction contracts; their
native write routes stay blocked, not replaced by mock success. Cadence Allegro
save/reopen signatures are not confirmed from available primary API documentation.
No claim of whole-product editing, CAD dependency discovery, continuous sync,
OAuth onboarding, physical correctness or qualification of any licensed runtime.

## Evidence sources

- https://www.altium.com/documentation/altium-dxp-developer/iserverdocument-interface
- https://www.altium.com/documentation/altium-dxp-developer/iclient-interface
- https://developers.notion.com/reference/get-block-children
- https://docs.slack.dev/reference/methods/conversations.replies/
- https://developers.google.com/workspace/drive/api/guides/manage-downloads
- https://learn.microsoft.com/en-us/graph/api/driveitem-get-content?view=graph-rest-1.0
- https://www.zuken.com/us/blog/a-beginners-guide-to-scripting-for-e3-series/
- https://www.siemens.com/en-gb/products/capital/ee-systems-data-integrations/data-management/

## Verification

Use `python -m unittest discover -s tests -p 'test_external_*.py'`, focused native
tests and complete `python -m unittest discover -s tests`. Use synthetic vendor
responses at the transport boundary and real local bundle/Core publication,
restoration and CLI execution. No secret credentials or vendor binary fixtures.

Slice 1: native suite 25 tests passed, including 6 persistence cases (RED first:
missing save_format path). These are generated-script/receipt contracts, not live
Altium execution. No installed vendor host is available.

Slice 2: external integration suite 43 tests passed. Eight collection tests cover
resume, raw page preservation, nested blocks, thread pagination, rate limits,
cursor cycles, depth/request bounds and tampered resume scope. No account calls.
