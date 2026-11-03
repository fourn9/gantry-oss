# Planned native updates

This is an unreleased local implementation on the external-integrations branch.
It adds **thirteen explicit update operations across twelve SaaS providers** to
`gantry-integrations`. Request contracts and synthetic round trips are tested;
**no live vendor account or CAD workspace has been tested**. Do not interpret the
catalog's `native_write` flag as full editing, synchronization or vendor certification.

A customer agent can invoke the same CLI in its local environment. Gantry does not
host the agent, purchase vendor licenses, or incur inference charges in this path.

## Supported scope

| Provider / operation | Native update | Concurrency protection |
|---|---|---|
| GitHub `file.update` | Replace one existing UTF-8 file on an explicit branch, creating a commit | File SHA |
| GitHub `issue.update` | Title and/or body of an existing issue (also PR issue fields) | Preflight only |
| GitLab `file.update` | Replace one existing UTF-8 repository file on an explicit branch | `last_commit_id` |
| Confluence `page.update` | Replace title and storage body of a published current page | Next page version |
| Jira `issue.update` | Summary and/or plain-text description converted to ADF | Preflight only |
| Linear `issue.update` | Title and/or description; fixed GraphQL mutation | Preflight only |
| Notion `paragraph.update` | Replace one existing paragraph with plain text; rich-text styling is replaced | Preflight only |
| Google Drive `metadata.update` | Name and/or description | Preflight only; **not document/file content editing** |
| Google Sheets `values.update` | Replace exactly one rectangular A1 range, RAW values | Preflight only |
| Excel `values.update` | Replace exactly one rectangular workbook range through Graph | Preflight only; delegated Microsoft auth required |
| SharePoint `metadata.update` | Rename one drive item | ETag / If-Match; **not document content editing** |
| Slack `message.update` | Update one existing plain-text message the token may edit | Preflight only; no new messages, blocks, attachments or threads |
| Onshape `parameters.update` | Update named expression parameters of one existing Part Studio feature | Workspace sourceMicroversion + rejectMicroversionSkew |

File operations do not create branches, new files, PRs, merges or deletes. Range
updates do not create sheets or modify formatting; supplying values replaces any
formula at those cells. Excel formula-like strings are rejected. Onshape retains the
native feature fields and unchanged parameters; it does not create arbitrary geometry,
edit assemblies, export a complete editable project or validate physical performance.
Feature rebuild status remains in the raw response, separate from parameter persistence.

Cursor/Python retain their existing customer-agent/scoped-Runner paths. Relyence and
other export-only catalog entries do not gain native writes. Commercial desktop CAD
SDKs, OAuth installation/refresh, webhook sync and full bidirectional sync remain outside
this slice. See [all integration routes](EXTERNAL-INTEGRATIONS.md).

## Prepare → apply → collect

Example target file `target.json` (credentials are deliberately absent):

```json
{"provider":"github","operation":"file.update","repository":"your-org/robot","branch":"design-candidate","path":"src/controller.py"}
```

Example `change.json`:

```json
{"content":"# Reviewed candidate controller\n","message":"Update candidate controller"}
```

Configure a project-scoped token privately under an environment reference such as
`GANTRY_CONNECTOR_GITHUB_WRITE`. Do not put tokens in JSON, command arguments, prompts
or public logs. The name is a reference, not a token. Read and write credentials may
be separate; the provider enforces the actual user's scopes and object permissions.

```sh
# Read only: saves original response, exact target/request, reason and pinned refs.
python -m gantry.integrations prepare-write \
  --config target.json --change change.json --reason 'Implement the reviewed candidate' \
  --requirements requirements.json --credential-ref GANTRY_CONNECTOR_GITHUB_WRITE \
  --output ./captures/controller-plan

# Use the exact plan_hash returned above, after reviewing the plan.
python -m gantry.integrations apply-write \
  --plan ./captures/controller-plan --expect-plan PLAN_HASH \
  --journal ./.gantry-native-writes --credential-ref GANTRY_CONNECTOR_GITHUB_WRITE

# No remote writes: recover an uncertain outcome by reading again.
python -m gantry.integrations reconcile-write \
  --plan ./captures/controller-plan --journal ./.gantry-native-writes \
  --credential-ref GANTRY_CONNECTOR_GITHUB_WRITE

# Preserve the complete local receipt and before/after objects in a new capture.
python -m gantry.integrations export-write \
  --plan ./captures/controller-plan --journal ./.gantry-native-writes \
  --output ./captures/controller-written
```

Then use the existing `publish --bundle ... --state-id ... --change-id ... --version ...`
command to checkpoint this evidence into Gantry. The change's write scope must include
`imports/SOURCE_ID/`; inspect the exported manifest for the stable source ID. Original
native bytes, request, requirement references, response, observed new revision and
receipt are preserved. The normal Core version/access checks still apply to publication.

Preparation is not remote-write approval. `apply-write` names the exact reviewed plan;
it is not a signed user approval or automatic Crew delegation. Run it only with authority
for that target, including authority to update messages/issues visible to other people.
This local path checks the native baseline; it does **not** query Core to reauthorize a
stale work contract or requirement before dispatch. Agents must use their existing
execution/delegation checks when invoking the CLI. Publication does not automatically
select the new state, trigger Mentor, prove requirements or formally adopt a design.

## Other target/change examples

Each `target` object below is a separate config JSON; `change` is a separate file.
The API does not accept arbitrary fields, URLs, headers, methods or inline credentials.

```json
[
  {"target":{"provider":"github","operation":"issue.update","repository":"your-org/robot","number":"42"},"change":{"body":"Updated analysis"}},
  {"target":{"provider":"gitlab","operation":"file.update","project":"your-org/robot","branch":"candidate","path":"src/control.py"},"change":{"content":"# Candidate\n","message":"Update candidate"}},
  {"target":{"provider":"confluence","operation":"page.update","site":"your-tenant","page":"123"},"change":{"title":"Design review","storage":"<p>Updated evidence</p>"}},
  {"target":{"provider":"jira","operation":"issue.update","site":"your-tenant","issue":"ENG-42"},"change":{"summary":"Updated design review","description":"Recorded observations"}},
  {"target":{"provider":"linear","operation":"issue.update","issue":"ENG-42"},"change":{"description":"Recorded observations"}},
  {"target":{"provider":"notion","operation":"paragraph.update","block":"block-id"},"change":{"text":"Updated design note"}},
  {"target":{"provider":"google-drive","operation":"metadata.update","file":"file-id"},"change":{"description":"Candidate revision"}},
  {"target":{"provider":"google-sheets","operation":"values.update","spreadsheet":"sheet-id","range":"Design!B2:C2"},"change":{"values":[[12.0,"mm"]]}},
  {"target":{"provider":"excel","operation":"values.update","item":"item-id","sheet":"Design","range":"B2:C2"},"change":{"values":[[12.0,"mm"]]}},
  {"target":{"provider":"sharepoint","operation":"metadata.update","drive":"drive-id","item":"item-id"},"change":{"name":"candidate.step"}},
  {"target":{"provider":"slack","operation":"message.update","channel":"C123456","ts":"1234567890.123456"},"change":{"text":"Reviewed result"}},
  {"target":{"provider":"onshape","operation":"parameters.update","document":"aaaaaaaaaaaaaaaaaaaaaaaa","workspace":"bbbbbbbbbbbbbbbbbbbbbbbb","element":"cccccccccccccccccccccccc","feature":"feature-id"},"change":{"expressions":{"depth":"12 mm"}}}
]
```

Use actual IDs and parameter IDs discovered in the native application. Onshape writes
use a workspace (not an immutable version); the workspace's current microversion is
pinned during preparation. OAuth Bearer credentials and the public cad.onshape.com
endpoint are supported. HMAC API-key signing and enterprise domains are not provided.

## Outcomes, races and interruption

- `verified`: native update returned success, and selected fields matched on readback.
  This does not certify CAD validity, simulator behavior or formal engineering adoption.
- `unchanged`: desired fields were already present; no native mutation was dispatched.
- `refused`: an explicit HTTP refusal (including conflict/permission) was received.
- `applied_unverified`: update response succeeded, but readback could not complete.
- `readback_mismatch`: the observed fields do not match the proposed values; investigate
  native normalization, rebuild behavior or another writer. No automatic rollback.
- `unknown` / `dispatching`: the update may have applied (including a crash); retrying
  `apply-write` returns the saved receipt and **does not send another mutation**.
- `observed_desired`: a later reconciliation found the desired fields. This proves the
  observed state only, not which caller caused it or that no intervening write occurred.

Every apply rereads the baseline. Providers marked *preflight only* lack an atomic
condition in this recipe: another writer can change the object between the read and
write. These operations are blocked unless `--allow-nonatomic` is explicitly given;
use exclusive editing or resolve this with the service owner. The flag does not provide
an atomic guarantee. Other operations send the provider's documented condition as well.
GitHub's condition covers the file blob, not unrelated commits on the branch; GitLab
covers that file's last commit. No cross-tool transaction is claimed.

The local journal records state transitions and is fsynced **before** dispatch, with a
process lock preventing duplicate concurrent application. Keep the same durable journal
across retries and process restarts. It is not global deduplication across computers,
different journal directories, intentionally regenerated plans or lost disks. Do not
remove an uncertain receipt to retry. After inspection, prepare a new plan instead.
Each explicit preparation creates a fresh intent ID; retry the saved plan, rather than
preparing again automatically, when continuing the same intent.
Existing POSIX local-runner support applies; Windows runtime acceptance is not claimed.

## Security and evidence boundaries

All requests target fixed public HTTPS endpoints; redirects, proxy inheritance and
arbitrary target hosts are disabled. Credentials are explicit environment references.
Read transport rejects mutations; write transport rebuilds a validated provider recipe.
Payload is limited to 1 MiB; write observations/responses to 2 MiB; cell ranges to 1,000
cells. Secret-pattern scanning and configured-token checks are defensive filters, not a
complete data-loss prevention system. Review target, payload and token permissions.

Plans/journals are owner-controlled local files, not a remotely exposed write API.
Remote content is untrusted data and cannot supply its own write authority. Evidence
contains selected native content and may be confidential: keep it out of public git,
protect the local volume/backups, and publish only into authorized Gantry states.
There is no additional at-rest encryption. Private user data is not sent to Gantry's
publisher or model provider by this module. API usage may count against vendor quotas.

## Primary write contracts

- [GitHub contents](https://docs.github.com/en/rest/repos/contents#create-or-update-file-contents), [GitHub issues](https://docs.github.com/en/rest/issues/issues#update-an-issue).
- [GitLab repository files](https://docs.gitlab.com/api/repository_files/).
- [Confluence page update](https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-page/#api-pages-id-put), [Jira issue edit](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/#api-rest-api-3-issue-issueidorkey-put).
- [Linear GraphQL](https://linear.app/developers/graphql), [Notion block update](https://developers.notion.com/reference/update-a-block).
- [Drive files update](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/update), [Sheets values update](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/update).
- [Graph drive item update](https://learn.microsoft.com/en-us/graph/api/driveitem-update?view=graph-rest-1.0), [Graph range update](https://learn.microsoft.com/en-us/graph/api/range-update?view=graph-rest-1.0).
- [Slack message update](https://docs.slack.dev/reference/methods/chat.update/).
- [Onshape feature update](https://onshape-public.github.io/docs/api-adv/featureaccess/), [conditional feature definition](https://github.com/onshape-public/go-client/blob/master/onshape/model_bt_feature_definition_call_1406.go).
