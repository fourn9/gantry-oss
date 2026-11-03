# Connect saved development to Studio

This workflow joins existing project import, saved external edits, intermediate
sharing, and continuation by another authorized participant. It reuses projects,
development sessions, immutable states, change sets, snapshots and engineering
evidence. It does not create another copy of the ledger or require a model call.

## Start with an existing project

Run the authenticated server using [administrator setup](ADMIN-AGENTS.md).
An owner needs `work` and `record` permission to import; participant identities
must already exist. This flow does not provision a public account or invite by
email. Use HTTPS for a remote server and a private token file for the local CLI.

In Studio, choose **Import project** under Projects. Select a saved project
folder, enter its name and the purpose of the first work, and optionally provide
a mapping manifest. Import preserves selected source bytes; it does not execute
any file. Hidden/generated/private paths are excluded from browser selection;
the server additionally rejects unsafe paths and recognized credentials. Scan
limits and credential patterns are a guard, not proof that an arbitrary folder
contains no confidential data. Select a deliberate project scope.

Without a manifest, files belong to one component and entered requirements are
descriptive notes. Cross-tool relationships are explicitly undeclared. Include
STL/OBJ exports alongside native CAD if you want the current 3D preview; STEP or
proprietary source alone is retained but is not rendered by the browser.

For a scoped CLI preview, adapt
[`examples/connected-workspace/project.json`](../examples/connected-workspace/project.json):

```sh
gantry --url http://127.0.0.1:8765 --token-file /private/owner.token \
  workspace import --root ./project --manifest ./project.json
# Inspect file paths, hashes, write scope, component mapping and omissions.
gantry --url http://127.0.0.1:8765 --token-file /private/owner.token \
  workspace import --root ./project --manifest ./project.json --apply
```

The first command sends no project data and creates no local binding. Apply
atomically creates the project, initial saved state and first work, then binds
the folder to that work. Retrying the same import uses a durable request key.
`paths` selects readable files/directories; `write_scope` defines the first work's
editable paths. `dependencies` contains exact baseline file paths, not directories.
`actors` contains existing participants, not a new permission grant.

## Save external changes and share a milestone

After a browser import, use **Connect / continue** in the work footer to obtain
commands for the actual server, work and selected state. Attach from the matching
external project folder; attach does not copy or overwrite files. Inspect status
before syncing, particularly if some imported files are absent locally: an absent
tracked file is an explicit deletion when sync is requested.

```sh
gantry --url http://127.0.0.1:8765 --token-file /private/owner.token \
  workspace attach --root ./project --work-id CHANGE_ID
gantry --url http://127.0.0.1:8765 --token-file /private/owner.token \
  workspace status --root ./project
gantry --url http://127.0.0.1:8765 --token-file /private/owner.token \
  workspace sync --root ./project --summary "Moved the carriage" \
  --rationale "Increase static clearance" --unfinished "Align controller and test"
gantry --url http://127.0.0.1:8765 --token-file /private/owner.token \
  workspace share --root ./project --note "Unfinished geometry ready for controls"
```

Or opt into `workspace watch --root ./project`. It polls saved files every two
seconds by default and waits for two equal observations. Ctrl+C stops it. It
creates **unshared checkpoints**, never shares, adopts, executes or infers a pass.
Use Studio's **Share update** to inspect exact before/after versions and share a
milestone. A subsequent local save starts another unshared version. Previously
shared versions and their conversations remain available.

Only changed file bytes are uploaded. Additions and deletions are explicit.
Unchanged content and prior context remain referenced. Local `.gantry/` holds a
private binding and durable outbox; it is excluded from captures and has its own
Git ignore rule. It does not store the access token. A pending outbox does contain
the scoped source bytes needed for retry. Those bytes are removed after a
confirmed receipt. Protect this directory as you protect the source workspace.

## Continue as another participant

The owner first registers the participant through existing administration and
includes the identity in the session. Each participant uses their own credential.
They must have session access plus `work` and `record` permission; read access alone
does not permit modifying someone else's work. The new work belongs to the caller.

```sh
gantry --url http://127.0.0.1:8765 --token-file /private/teammate.token \
  workspace continue --work-id CHANGE_ID --state-id SHARED_STATE_ID \
  --destination ./continued-work --title "Align controller and verify" \
  --write-path control/ --write-path checks/ \
  --dependency cad/base.step --dependency cad/carriage.step
```

The new directory contains `workspace/` with exact restored bytes, `context.json`
with the saved state/context, and a private retry receipt. It creates a separate
change set from that exact state and connects `workspace/` for subsequent sync.
Omit the scope/dependency options to retain the source work's declarations.
Use a new destination; nothing is silently overwritten. Repeating an interrupted
continuation with the same arguments resumes its receipts. Repeating after edits
does not reset the new workspace to old bytes.

Restoration verifies content hashes and records a receipt. It does not install
CAD software, rebuild a virtual environment, restore executable file permissions,
obtain licenses, inject credentials or resume a simulator's in-memory timestep.
Capture required assets, environment definitions and startup instructions as
files/context; use the existing simulation checkpoint adapter for runtime state.

## Keep hardware/software meaning with the files

`hierarchy` assigns stable component IDs and source paths. `context` retains
requirements, constraints, decisions, open questions and environment. Existing
`environment.engineering` declarations link component IDs, input hashes, checks
and evidence hashes. Existing versioned requirement references and verification
links are retained; free text is not converted into a verified requirement.

The saved-file watcher cannot infer that a CAD placement and a controller offset
represent the same physical coordinate. Supply correspondence and check results
through the existing adapters or an explicit updated context:

```sh
gantry --url http://127.0.0.1:8765 --token-file /private/owner.token \
  workspace sync --root ./project --context ./updated-context.json \
  --summary "Static clearance measured" --rationale "Report saved with evaluated inputs"
```

`--context` replaces the versioned context in full; start from the saved context
and preserve unrelated declarations. This can create a context-only checkpoint.
It does not automatically update input hashes or carry a pass to new inputs.
Checks show changed inputs/evidence as unknown; original results remain in the
old version. Studio's collapsed **Requirements & handoff context** shows this
information in Checks and Saved version. Physical interpretation remains the
responsibility of the declared evaluator and qualified review.

## Failure and concurrency behavior

| Condition | Result |
| --- | --- |
| Lost HTTP response after successful save | Replay identical bytes/key; no duplicate checkpoint |
| Different remote head | `stale_basis`; stop and inspect or continue into a new folder |
| Sharing changed metadata but kept the same head | Next local capture can proceed |
| Edit outside this work's scope | Hold; use a correctly scoped independent work |
| Unreadable directory/file, symlink, unstable save or detected secret | No deletion/checkpoint inferred; correct the cause and retry |
| Pending failed sync | Retain original request; retry before capturing later local edits |
| Revoked credential or work access | Hold; no authority fallback |
| Stop/restart watcher | Persisted binding/outbox reused; watching must be started explicitly |

The watcher does not auto-merge remote updates. Authorized concurrent writes use
Core's version checks. The browser's atomic workflow supports **1–1000 files,
16 MiB per file and 32 MiB total**. The local CLI automatically uses the chunked
path described below for larger saved workspaces. Neither limit is a universal
CAD capability claim.
The watcher currently scans scoped file contents, so cadence should suit file size.

## Architecture and migration

Browser import / local saved-file adapter → authenticated API → existing Core
project/session/change/state operations → event log + indexed state + artifact
store. Studio and other participants read those same states. Mentor and Crew can
consume the existing state/change/context APIs; this change does not automatically
start an agent or enable inference.

New APIs: `studio_import_project` and `studio_sync_update`. Existing share,
begin-change, read, restore and requirement/engineering evaluation APIs are reused.
The developer MCP profile exposes scoped sync and restore receipt recording;
initial import requires human project setup. No destructive migration is needed.
Existing projects, events and snapshots remain readable.

This is a real saved-file connection for installed editors/CAD tools, including
Git working trees. It does not imply live proprietary CAD API support, complete
feature-history capture, automatic component correspondence, managed cloud
accounts or production multi-organization onboarding. The public static demo has
no authenticated storage; it remains separate from this runtime.

See [verification and remaining limits](CONNECTED_WORKSPACE_VERIFICATION.md).


## Larger saved workspaces and team access

The CLI now automatically uses a streaming path when the atomic limits (1,000
files, 16 MiB per file, 32 MiB total) are exceeded. The complete scoped workspace
is bounded to 10,000 files and 1 GiB. Source bytes are inspected, frozen into
owner-only `.gantry/uploads/` staging and checked again before publication. Existing
immutable files are referenced, changed files use bounded chunks, and only the
completed manifest becomes a new work state. Network retries preserve the staged
bytes and idempotency keys even if the live editor has since saved another version.
The capture is saved-file content; it does not capture unsaved operations or claim
a simultaneous filesystem-wide snapshot. Browser uploads retain their smaller limits.

Pending staging is necessary for recovery. After acknowledgement and a durable
local state update, the client removes the matching private staging directory.
Deletion checks its path, ownership and filesystem identity. If cleanup fails,
the confirmed upload stays confirmed, `cleanup_pending` is visible in status and
the next sync retries cleanup before capturing more data. Import retries also
finish cleanup without duplicating the project. Staging is ignored by Git and
excluded from subsequent captures. Do not remove pending bytes manually.
A separate capture-intent journal is saved before writing staged bytes. Failed
freezes are removed, and the next sync/import recovers abandoned captures from a
process interruption before the pending request was saved. Active pending uploads
are protected. Journal replacements and directory entries are fsynced; recovery
tests simulate interruption boundaries, not hardware power-cut behavior.
The server keeps immutable committed artifacts; failed uploads can leave unreferenced
parts. Storage garbage collection is not part of this release.

For a second person or agent, use the request/grant procedure in
[CLOUD-OPERATIONS.md](CLOUD-OPERATIONS.md); a recipient's token stays on their own
device. Grant the relevant session before they run `workspace continue`. A saved
state can include native CAD, editable code, requirements and environment notes,
but exact engineering correspondence still needs explicit stable mappings or a
reviewed Mentor declaration. Filename similarity is never treated as verified
hardware/software compatibility.
