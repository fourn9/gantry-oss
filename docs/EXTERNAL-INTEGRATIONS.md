# External engineering integrations

This local CLI captures selected external records into Gantry development states.
It preserves original bytes and publishes an explicit requirement-linked checkpoint;
importing a result does not prove a requirement, run a solver, or adopt a design.

The implementation provides selected acquisition and planned updates, **not feature parity with all
advertised Flow integrations**. Cloud endpoints have request/response contract tests,
not authenticated vendor-account acceptance. No vendor credentials were supplied.
Selected native writes now have a separate prepare/apply/readback path; see
[write operations, concurrency and limitations](EXTERNAL-WRITES.md). There is no
always-on sync, webhook listener or provider OAuth onboarding application.

## What can be used

| Provider | Implemented acquisition | Limits |
|---|---|---|
| GitHub | One Issue or PR JSON; existing connector also reads PR diffs/checks | No comments or repository clone in this new reader |
| GitLab | One immutable commit on gitlab.com | No diff/pipeline acquisition or self-hosted endpoint yet |
| Confluence Cloud | Page body in storage format and version | No attachments or child-page traversal |
| Jira Cloud | Issue fields/status | No full history or complete comments |
| Linear | Issue, team, workflow status and cycle via fixed GraphQL query | No creation; selected updates use the separate write path |
| Notion | Direct child blocks; optional bounded descendant/pagination capture and resume | No attached binaries or page-wide atomic revision |
| Google Drive | Google document export; blob file download with before/after version checks | Export is not the native editable cloud document; no dependent-file discovery |
| Google Sheets | Explicit A1 range values | No formulas/formats or atomic revision |
| Excel | Graph workbook range or local XLSX selected cells | No recalculation; cached formula values are marked unverified |
| SharePoint | Graph item metadata; selected file download from explicitly allowed tenant host | Global SharePoint Online only; no dependent-file discovery or document editing beyond named write operations |
| Onshape | Part Studio mass properties at an immutable microversion | No full document/assembly editing or material validation; named parameter updates use the write path |
| Slack | Explicit history window or thread; optional pagination and thread capture/resume | No live bot mentions, slash commands, new message posting or attachment download |
| Cursor | Existing `gantry connect --client cursor` / project MCP | Depends on customer's agent and client trust setup; no hosted Cursor launch |
| Python | Saved scripts/results plus existing scoped Runner recipes | Capture does not execute imported code |
| Relyence | Selected exports, retained in their original format | Native API schema/test tenant still required; no FMEA write-back |

All providers, including those below, can use **saved export capture**. This merely
stores selected bytes and provenance. It must not be advertised as a native connector,
lossless re-import into the vendor application, or vendor-specific extraction.
The same limitation applies to any proprietary file whose format cannot be decoded.

## Reference inventory

Source reviewed 2026-11-02: [Flow integration page](https://www.flowengineering.com/integrations).
It lists the fifteen providers above without a coming-soon badge. Its coming-soon
entries are Altium 365, Ansys, Duro, Epsilon 3, Exotrail, First Resonance ION,
Fusion 360, Fusion by Stoke, Manufacturo, Matlab, Microsoft Teams, SimScale,
Siemens NX and SolidWorks. These have export capture only in this module.
The separate `gantry-native` CLI adds bounded desktop API operations for selected
products, including SOLIDWORKS (not a full assembly editor). Its capability list
and runtime limitations are in [Native desktop connectors](NATIVE-DESKTOP.md).

The [home page](https://www.flowengineering.com/) additionally shows Dassault,
Outlook, Abaqus, LabVIEW, TestStand and dSPACE. A Dassault logo does not identify
which product/API is intended. These are catalogued separately as home-only logos;
no native support is implied. The separate experimental vendor-connector branch is
not merged here; the new desktop API module is independently implemented.

Run `gantry-integrations catalog` (or `python -m gantry.integrations catalog`) for
machine-readable routes and explicit `native_write` / `live_account_verified` flags.

## Configure and capture

Install Gantry from this checkout. Existing Gantry CLI, Core and MCP use the same
state/requirement records. No new database or mandatory dependency is introduced.

Example `jira.json`, with a tenant slug and an explicit issue:

```json
{"provider":"jira","site":"your-tenant","issue":"ENG-42","credential_ref":"GANTRY_CONNECTOR_JIRA"}
```

Set the environment reference privately in the local process. For Jira/Confluence
its value is `email:api-token` (Basic auth); GitLab, GitHub, Google, Microsoft,
Notion, Slack and Onshape use an access token (Bearer). Linear accepts a personal
API key, or an environment value beginning `Bearer ` for OAuth. Tokens are never
read from another application's credential store or put in config JSON.
Use read-only scopes restricted to the selected project/document wherever supported.
Token provisioning/renewal is operator-managed; OAuth consent is not automated here.

Optional `requirements.json`:

```json
[{"requirement_id":"req_payload","revision_id":"rev_approved_payload"}]
```

These must be adopted revisions present in the input state's and change's scope
when published. Omit the file for explicitly unlinked exploratory evidence.

```sh
python -m gantry.integrations pull --config jira.json --source-id controller-issue \
  --requirements requirements.json --output ./captures/issue-001
python -m gantry.integrations inspect --bundle ./captures/issue-001
```

`pull` only writes a new local bundle. It does not publish, start inference, or
follow instructions in remote text. Its output names capture limitations. For
Notion/Slack, `source.continuation` in the inspected manifest can be supplied as
`cursor` in a subsequent explicit request. Each page is a separate observation;
no complete-tree or cross-page atomic-version claim is made.

### Related records and resumable pagination

`pull-related` follows Notion `has_children` plus cursors, or Slack history cursors
and the reported threads. A Slack history config must specify `oldest` and `latest`;
alternatively select one `thread_ts`. Threads use `conversations.replies`, which
requires the customer's appropriate Slack token/scopes. It never follows links
embedded in messages, downloads attachments or invokes a model.

```sh
gantry-integrations pull-related --config notion.json --source-id design-notes --max-requests 20 --max-depth 6 --output ./captures/notes-001
gantry-integrations pull-related --config notion.json --source-id design-notes --resume ./captures/notes-001 --output ./captures/notes-002
```

Each response remains in `pages/NNNN.json`; `collection.json` associates it with
the source request/depth and records the pending work. Rate limiting, malformed
responses, cursor cycles and limits produce an explicit **partial** bundle. Resume
uses the same source/requirement scope, rechecks the recorded traversal and avoids
fetching completed pages. Credentials are supplied afresh and never serialized.
Use the same `--requirements` file when resuming a linked capture.

`complete_within_scope` means the selected traversal finished, not that a workspace,
all attachments or a consistent point-in-time snapshot was acquired. The provider
may change between requests. Limits: 90 responses/28 MiB per accumulated bundle,
1–90 requests per invocation, depth 0–12, 1,000 pending tasks and 300 seconds plus
the outstanding bounded request. Request/depth limits can be increased on resume;
an exhausted aggregate bundle requires narrower new capture scopes. Originals stay
unchanged. The normal `publish` command stores the bundle in a scoped checkpoint.

Sources: [Notion children](https://developers.notion.com/reference/get-block-children),
[Slack replies](https://docs.slack.dev/reference/methods/conversations.replies/).

### Cloud file content

`pull-file` adds file content to the existing metadata/export routes. These config
objects are alternatives, each in its own file:

```json
{"provider":"google-drive","file":"your-blob-file-id","credential_ref":"GANTRY_CONNECTOR_DRIVE"}
{"provider":"sharepoint","drive":"your-drive-id","item":"your-item-id","download_host":"your-tenant.sharepoint.com","credential_ref":"GANTRY_CONNECTOR_GRAPH"}
```

```sh
gantry-integrations pull-file --config file.json --source-id bracket-source --requirements requirements.json --output ./captures/file-001
```

The original bytes are in `content.bin`; the provider's original filename/type is
in selected metadata. Gantry preserves bytes, not the ability to edit an unknown
proprietary format. Google Drive blob files use `files.get?alt=media`; native Docs/
Sheets still use the export path. Download permission, declared size, before/after
version and available MD5 are checked. SharePoint uses a Graph-selected file and
compares eTag/metadata before and after. A changed source rejects the capture.
This brackets a read; it is not a multi-request atomic transaction.

SharePoint's short-lived content URL is used only in memory. The operator must
configure the exact `tenant.sharepoint.com` download host. The content request has
no Graph bearer token, cookies or Referer; redirects are refused. All resolved
addresses must be public, the selected address is pinned for the connection, and
TLS verifies the configured hostname. Signed URLs are excluded from saved metadata
and errors. Other CDNs, personal OneDrive, government clouds and arbitrary hosts
are intentionally unsupported. DNS resolution uses the operating system timeout;
the 30-second read deadline is checked after resolution and between bounded reads.

Maximum content is 8 MiB in this route. Larger files use local export capture or
the existing chunked artifact path. Downloaded files are not opened/executed. Check
for embedded sensitive data before sharing; pattern detection is not full DLP.
The normal publication path supports successive source captures and preserves
earlier source files, including snapshots assembled from stored chunks.

Sources: [Drive downloads](https://developers.google.com/workspace/drive/api/guides/manage-downloads),
[Graph content download](https://learn.microsoft.com/en-us/graph/api/driveitem-get-content?view=graph-rest-1.0).

### Provider configuration examples

All accept an optional `credential_ref` named `GANTRY_CONNECTOR_*`. Except public
GitHub reads, credentials are required by the transport. Only these fields are
accepted; callers cannot replace the endpoint with an arbitrary URL.

```json
{"provider":"github","repository":"owner/repo","number":"42","kind":"pull_request"}
{"provider":"gitlab","project":"group/repo","commit":"0123456789012345678901234567890123456789"}
{"provider":"confluence","site":"your-tenant","page":"12345"}
{"provider":"linear","issue":"ENG-42"}
{"provider":"notion","block":"your-page-or-block-id"}
{"provider":"google-drive","file":"your-doc-id","format":"text/plain"}
{"provider":"google-sheets","spreadsheet":"your-sheet-id","range":"Requirements!A1:F20"}
{"provider":"excel","item":"your-drive-item-id","sheet":"Requirements","range":"A1:F20"}
{"provider":"sharepoint","drive":"your-drive-id","item":"your-item-id"}
{"provider":"onshape","document":"aaaaaaaaaaaaaaaaaaaaaaaa","microversion":"bbbbbbbbbbbbbbbbbbbbbbbb","element":"cccccccccccccccccccccccc"}
{"provider":"slack","channel":"C0123456789","oldest":"1700000000.0","latest":"1700003600.0"}
```

The JSON objects above are separate config examples, not a single JSON file.
Onshape's `microversion` is deliberate: a mutable workspace name is not a fixed
measurement input. The default document configuration is used; non-default
configurations need a dedicated recipe before using their mass properties.

## Local exports, workbooks and views

```sh
python -m gantry.integrations capture --provider ansys --source-id bracket-stress \
  --root ./saved-analysis --path model.step --path report.json \
  --requirements requirements.json --output ./captures/stress-001
```

Include the actual native model, evaluator, input files and environment definitions
needed to continue work, not just a screenshot. Missing dependencies remain the
operator's responsibility to declare in the development context; the importer
cannot discover arbitrary vendor-specific references. It refuses symlinks and
known credential files, and scans for common secret patterns; manually inspect
selected files because pattern scanning cannot detect every secret or opaque binary.

For Excel, `cells.json` can be `{"Design":["A1","B1"]}`:

```sh
python -m gantry.integrations capture --provider excel --source-id design-sheet \
  --root ./documents --path design.xlsx --cells cells.json --output ./captures/sheet-001
```

The workbook bytes and derived `selected-cells.json` are both preserved. UTF-8 OOXML
only; encrypted/macro workbooks are unsupported. Formulas are retained as formulas,
not executed. Cached results are explicitly unverified. Cell units are not inferred.

For JSON payloads, `--select selectors.json` takes e.g.
`{"response.json":["/fields/summary","/fields/status/name"]}`. Each derived value
carries the raw source hash and JSON pointer. Source fields outside the selected
view are retained in the original payload. Missing values remain `not_captured`.
Projections are bounded to 1 MiB and do not imply successful verification.

## Publish into a development change

Use an existing change whose declared write scope contains `imports/SOURCE_ID/`.
The source prefix is stable. A subsequent observation replaces only that prefix;
old bytes remain in the prior immutable state. Other project files survive.

```sh
python -m gantry.integrations publish --bundle ./captures/issue-001 \
  --url http://127.0.0.1:8765 --token-file /private/gantry-token \
  --state-id STATE_ID --change-id CHANGE_ID --version 1 --key import-issue-001
```

The result is a paused, unadopted checkpoint. Core validates access and expected
change version atomically. Requirement bindings must be within the change's subset.
A local owner-only publication journal preserves the exact final request for retry
with the same key after a lost response; preserve the bundle when resuming.
Use a new key for a new observation. Stale requirements may be captured as historical
information but remain `needs_review`; existing Runner/Mentor/Crew execution guards
remain effective. Importing a requirement document does not silently modify adopted
requirements in the ledger.

The new state contains `context.environment.external_sources` with manifest path,
capture hash, source marker, pinned requirement references and omissions. Select or
submit that state through the normal workflow to make it the relevant Mentor/Crew
input. Publication alone does not automatically select a branch, start a Bot or
request a review. Raw responses and projections remain available through artifact
retrieval APIs, respecting the existing access scope.

For actual physical pass/fail, use the existing fixed acceptance plan and
[hardware evidence publication](HARDWARE-ADAPTER.md). A metric imported from a
spreadsheet or Onshape is evidence, not automatically a passing physical check.

## Security and operational limits

- HTTPS to fixed public SaaS hosts (plus explicitly allowed SharePoint content host); no arbitrary URL, redirects, inherited proxy,
  automatic command execution, or implicit writes. Native updates require the explicit
  planned-write path. Existing GitHub/cloud features
  outside this CLI are unchanged.
- One bounded request per pull; 8 MiB response, 15-second socket timeout and a checked
  30-second acquisition deadline (a blocked read may take up to one socket timeout
  beyond it). Rate-limit/auth failures return classifications without remote bodies.
- Raw capture: 100 files, 16 MiB per file, 32 MiB total. Larger CAD assets must use the
  existing chunked artifact route. These bounds are acquisition protections, not an
  engineering iteration cap.
- Credentials stay in process environment/headers. Configured-token echoes are refused.
  Bundles use owner-only filesystem permissions. There is no extra at-rest encryption;
  protect the customer's filesystem and backups appropriately.
- Captured content and claimed source revisions are external evidence. Content hashes
  detect local mutation; they are not signatures proving vendor origin or correctness.
- No customer data was sent to a publisher account or used for model training. This
  module does not use an LLM and does not add inference charges.

## Native connector backlog

Native Relyence needs a versioned API contract and a licensed test tenant. The
coming-soon/home-only products need exact product/modules, supported versions,
authorization and SDK/API access; generic exports do not resolve these gaps.
Next steps are authenticated read/write acceptance, complete pagination/nested-content
capture, broader native editing, and source-specific webhook/synchronization paths.
Planned updates cover only the operations explicitly listed in the catalog.

## Primary API references

- [GitHub Issues](https://docs.github.com/en/rest/issues/issues#get-an-issue), [GitLab commits](https://docs.gitlab.com/api/commits/).
- [Confluence pages](https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-page), [Jira issues](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/).
- [Linear GraphQL](https://linear.app/developers/graphql), [Notion block children](https://developers.notion.com/reference/get-block-children).
- [Drive exports](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/export), [Sheets values](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/get).
- [Graph drive items](https://learn.microsoft.com/en-us/graph/api/driveitem-get?view=graph-rest-1.0), [Excel ranges](https://learn.microsoft.com/en-us/graph/api/range-get?view=graph-rest-1.0).
- [Onshape OAuth](https://onshape-public.github.io/docs/auth/oauth/), [Part Studio API](https://github.com/onshape-public/go-client/blob/master/onshape/api_part_studio.go).
- [Slack history](https://docs.slack.dev/reference/methods/conversations.history/).
