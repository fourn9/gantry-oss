# Studio: shared development workspace

Studio is the default authenticated web view (`#studio`) of the existing Gantry
server. It reads real projects, immutable development states and change sets.
It does not start agents, adopt designs or certify physics by displaying a file.
The existing execution, integration, review and adoption screens remain under
**Workspace tools**. There is no new UI framework or browser dependency.

## Daily workflow

For first use, **Import project** accepts a saved folder and optional component/
context manifest. The [connected workspace guide](CONNECTED_WORKSPACE.md) covers
scoped import, opt-in saved-file watching and continuation by another participant.

1. Open a project in the sidebar. **Structure** shows its saved component hierarchy,
   labelled with the source state; selecting a component shows associated work.
   **Work** lists change sets, owners (human or agent), component scope and recorded status.
   **Files** browses actual saved bytes, parent diffs and state history. **Requirements**
   shows the pinned requirements, applicable checks and missing evidence. The **Related**
   panel connects these views using recorded check inputs and requirement references.
2. Open work. Select **CAD**, **Code** or **Checks**. Choose a saved version and,
   for CAD/code, optionally compare another version. **Version details** exposes
   the capture omissions and restore command. The shared update note (or checkpoint
   note) stays visible beside an expandable changed-file summary.
3. Edit in the external CAD/editor and save. **Import changes** accepts selected
   saved files, lets you map destination paths, and creates an unshared checkpoint.
   Unselected files are retained. The scope and expected work version are checked.
   **Connect / continue** provides commands for local saved-file sync/watch and
   restoration to a new independently assigned work. The existing
   `checkpoint-workspace` adapter remains available for larger captures.
4. **Share update** lists paths and before/after content hashes against the previous
   shared version. Add a short note and share the work in progress. Sharing does
   not complete work, pass a test or formally adopt a design. Historical views are
   read-only for import/share; open the latest state to continue that work.
5. Select a mesh part or code line, or open the work conversation. Mention a session
   member/agent with the picker. Their **Inbox** opens that exact work, state,
   artifact and selection. Old comments stay on their original version. Closing
   the panel returns to artifact viewing. Replying uses the same immutable anchor.
   **Browse conversations** lists targets and versions, including older conversations.
   File/mesh markers and code-line counts only include comments on the displayed version.
6. **Recent** / **Recent work** show work opened in the current browser tab. This
   initial implementation does not persist browsing history across sign-out/reload.

Files and Requirements also support conversations without creating work. Mention
named members or Crew agents; mentions only notify. **Ask Crew agent** uses the
existing read-only request queue; an explicit assignment requires existing delegated
scope. See [Files, requirements and shared context](STUDIO_LIBRARY.md).

Unshared describes publication status, not an additional privacy boundary: existing
session authorization still determines who can inspect checkpoints. The browser
cannot see unsaved local edits. It labels imported files as saved checkpoints and
reports what was not captured. Draft comments and tokens stay in tab memory.

## Data and API contracts

All commands use the existing authenticated API, transaction, event log, permission
checks and write idempotency. They are also exposed through CLI/MCP profiles.
Existing credentials with explicit command allowlists keep their approved scope;
adding tools to a profile does not silently widen an issued credential.

| Command | Contract |
| --- | --- |
| `studio_overview` | Authorized projects/hierarchy and paged change-set work list; no estimated progress |
| `studio_work` | Work ID plus optional state ID; exact manifest, versions, check applicability, participants, versioned discussion index and activity token. `activity_only: true` returns only the token after the same authorization checks |
| `studio_import_update` | Work ID, expected version, path/base64 files, summary; upload screening + immutable overlay + existing checkpoint |
| `studio_import_project` | Saved files, hierarchy/context and initial work scope; human-authenticated atomic project/session/state/change creation |
| `studio_sync_update` | Expected work version and state, changed file bytes, explicit deletions, reason and optional updated context; scoped immutable checkpoint |
| `studio_share_update` | Work ID, expected version, exact current state, note; existing share operation, no adoption |
| `studio_library` | Project and optional exact state; paged files, requirements or saved states |
| `studio_related` | Project, state and anchor; linked requirements/checks/files/work and paged conversations |
| `studio_context` | Same pinned state, mandatory constraints/requirements/unknowns, bounded related records and optional state delta |
| `studio_comment` | Work ID or project ID, state ID, exact anchor, optional thread ID, body, recipient IDs |
| `studio_inbox` | Only the current recipient's accessible mentions, with exact target and cursor |
| `studio_acknowledge` | Only the recipient can mark the request read |

Anchors include `{kind: "work"}`, `{kind: "project"}`, `{kind: "component", component_id}`,
`{kind: "requirement", requirement_id, revision_id}`, `{kind: "file", path, hash}`,
`{kind: "cad", path, hash, part}`, and `{kind: "code", path, hash, line}`.
`part` is currently the immutable mesh file path,
not a guessed native CAD face/feature. `line` is 1-based in the saved UTF-8 bytes.
Deleted comparison lines bind to the old state. Replies cannot change an anchor.
Recipients must have current access to the session and referenced state.
Mentions are internal requests; they do not send external messages, grant access,
start inference or authorize execution.

The additive `studio_threads`, `studio_messages`, `studio_notifications` projections
are event-sourced. Existing ledgers open without rewriting history. New writes
replay into the added tables. Existing artifact/state/change/share IDs are reused;
no duplicate project or version model is introduced.

## Supported artifacts and real connection boundaries

| Capability | Implemented | Remaining connection work |
| --- | --- | --- |
| CAD | Actual saved STL/OBJ assembly preview, orbit/zoom, top/front/isometric, file-part selection, old-file overlay; opt-in local saved-file synchronization | Native CAD tessellation, stable subpart/face IDs, live vendor API/runtime validation |
| Native CAD source | Source download with exact version; explicit unsupported preview | Export a preview next to editable source, preserving units/coordinate frames; no native editing in browser |
| Code | Saved UTF-8 content, exact line anchors, inline old/new diff; recorded repository/source commit when available | Git provider/adapter must supply accurate repository/revision metadata and checkpoint files; browser does not pull a repo automatically |
| Checks | Existing engineering checks and evaluations; stale inputs/evidence and non-applicable prior results stay visible; input-bound running execution is labelled separately | Tool must return exact state/input hashes, evaluator/environment/scope and evidence; no simulated pass is generated |
| Import | Browser project/file upload, scoped delta sync/watch, explicit deletion in local adapter, independent continuation | Live unsaved-change detection, browser deletion/rename UX, native vendor operation capture |
| Conversation | Version-bound selection, human/agent mentions, personal Inbox, replies | Native-feature remapping, notification delivery/agent reaction policy; no guessed carry-forward of old comments |

Known limits: preview files up to 16 MiB, 40,000 triangles/file, current assemblies
up to 12 files/80,000 triangles (larger assemblies show a selected file); previous
selected file may add up to 40,000 triangles. Meshes share their exported coordinate
system; no assembly transforms or unit conversion are inferred. Preview is not a
collision checker. Code preview/anchoring is limited to 256 KiB; large diffs use
separate panes and truncated previews with a restore path. Existing **Import changes**
accepts 1–200 files, at most 32 MiB each/48 MiB total. **Import project** and the new
atomic saved-file connection use 1–1000 files, 16 MiB each/32 MiB total.
Full chunked adapters can handle larger artifact workflows. Work/Inbox and project
library lists paginate. Project conversations load the latest 50 messages first,
with older pages available. Legacy work-detail history/conversation reads still
need pagination for very long-lived projects.

Missing artifacts show **not captured/not connected** guidance; fetching shows a
loading state; rejected imports retain the dialog and error; unsupported formats
show a source download and connection guidance. Existing **Connections** continues
to show connector setup/synchronization/error status.

Visible Studio pages check for activity every 15 seconds while authenticated. Work
polls return a fingerprint without rebuilding artifact manifests/diffs; they track
work, shares, discussions and related execution context. Other pages use their
existing overview/Inbox reads. This is a read-only poll, not a push service or a
new external-tool synchronization path. A small notice offers **Load updates**;
the selected work version, camera and unsent comment stay in place. **Open latest**
explicitly switches to the newer version. An unavailable poll offers a retry;
navigation and sign-out invalidate pending notices. Files/Requirements use bounded
related reads for activity. Legacy work history/conversation scans still need
indexing/pagination before claiming large-project scaling.

The artifact-file selector and mesh selection identify the same file-part for
comparison and discussion. Opening/closing a conversation preserves the view and
zoom for that work/version (within this tab). Use the zoom buttons or Alt+wheel;
ordinary wheel input scrolls the page. On narrow screens, opening a discussion
moves focus to its panel; **Back to artifact** returns to the preview. Conversation
headers stay visible below the workspace header. Work lists align name, assignee,
leaf component and status; ancestor components remain in the saved hierarchy.

## Isolated demo and verification

```sh
PYTHONPATH=. python examples/studio-demo/run.py --output /tmp/gantry-studio-example --port 8793
```

Use a new directory. Open the printed localhost URL and load its `access.token`
using the login file picker. The script creates an **explicit sample project**
through actual Core APIs, with invented geometry, code and identities. It never
runs a model or tool service. Generated tokens/ledgers are local and must not be
committed. Normal startup never seeds this demo. Original mock data is not shipped.

See [Studio verification](STUDIO_VERIFICATION.md) for the checked scenarios and limits.
