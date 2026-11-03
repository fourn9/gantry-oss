# Guided project onboarding

Studio's **Import project** opens `#studio-start`. Bring existing saved work,
correct the few associations that matter, and open a real first work. This uses
the existing artifact, continuity, checkpoint and sharing models.

## Browser path

1. Give the project a name and optionally describe the work in progress.
2. Choose a local folder. Selection only previews file names and sizes locally.
   Review the file list and remove anything outside the intended scope.
3. Confirm saving the selected files and setup history, then choose **Inspect
   selected work**. Known private/generated paths are excluded; credential
   patterns are checked again by the server. This is not a guarantee that all
   confidential content can be recognized automatically.
4. Inspect the saved inventory and inferred folder grouping. Correct component
   names, parent associations or saved paths, with a short reason. Answer useful
   questions, or leave them unknown and continue. Answers survive reopening;
   changing the evidence marks their applicability stale without deleting them.
5. Optionally let an existing customer agent submit an interpretation (below).
6. Choose the first work title/purpose and **Open first work**. The saved artifacts
   and initial checkpoint are available in Studio. Use **Share update** separately.
7. Use **Connect / continue** to bind the original directory or let another
   authorized identity restore the shared version into a new workspace.

The connected-service alternative selects an already captured project state.
It does not initiate OAuth, fetch arbitrary URLs or start a new sync daemon.
Configure/import through the existing connector first. Local file upload is a
saved snapshot; later file changes require the existing workspace sync/adapter.

## Customer agent

Use the existing authenticated developer MCP profile. The owner may add existing
collaborator identities to this draft; this neither provisions identities nor
expands their principal/zone permissions. The owner can remove collaborators.
Underlying source access still follows the existing artifact zone policy.

The agent reads `get_onboarding`, inspects selected sources using
`read_artifact_chunk`, and submits `propose_onboarding`. The tool schema requires
the exact onboarding version and source snapshot, bounded component suggestions,
questions and findings with exact path/hash evidence, a suggested first work and
limitations. Responses are attributed and saved in the ledger.

Agent interpretation is unapproved context. It cannot grant access, execute the
project, certify a result or approve requirements. Human corrections take
precedence. A stale proposal is rejected. Source text is untrusted input, not
instructions to the inference runtime.

An explicitly started local analyzer is also available:

```sh
gantry --url http://127.0.0.1:8770 --token-file /private/path/agent.token \
  onboard analyze --onboarding-id ONBOARDING_ID \
  --backend codex-subscription --journal ./.gantry/onboarding-analysis
```

This reuses the existing subscription inference backend and its durable journal;
it has no API-key fallback. The customer must configure/authenticate that backend.
`--backend customer-command --inference-config /private/path/approved.json`
uses the existing approved executable/hash contract instead. Gantry does not
start either backend from the page or choose a paid provider automatically.
Inference journals contain selected source text: keep them private and outside
tracked source. Selected native binaries remain metadata-only in this analyzer;
use the customer's native tool through a separately authorized adapter when
semantic interpretation is necessary. The bounded text context is at most
160,000 bytes, with at most 24,000 bytes per file; omissions are explicit.

If a submission response is lost, rerun with the same journal. It retries the
exact idempotent submission, not another inference. If source/answers changed
before submission, preserve the old journal and use a fresh journal for analysis
of the updated state. Journals are bound to the server, actor and onboarding ID.

## CLI capture and resume

```sh
# Preview only: no server request or local journal is written.
gantry onboard start --root ./project --path cad/ --path control/ \
  --path README.md --name "Bench carriage" --goal "Share unfinished routing"

# Save the same explicitly selected scope with the owner's existing credential.
gantry --url http://127.0.0.1:8770 --token-file /private/path/owner.token \
  onboard start --root ./project --path cad/ --path control/ --path README.md \
  --name "Bench carriage" --goal "Share unfinished routing" --apply
```

The result contains the draft ID and Studio link. `onboard resume
--onboarding-id ID` reads it. `onboard refresh --root ./project --path cad/
--path control/ --path README.md --onboarding-id ID --apply` saves a new exact
source selection while retaining prior answers and corrections. A refresh replaces
the selected snapshot: specify the full intended scope, not just changed files.
Use `onboard finish --onboarding-id ID --title ... --purpose ...` to create the
first work; ordinary `workspace attach/sync/share/continue` follows.

## Data and migration

`onboardings` is an additive event-backed projection containing owner, existing
collaborators, zone, snapshot, observed manifest, provisional hierarchy, attributed
proposal, question/answer evidence, manual corrections, version and completion
result. Existing ledger replay supplies the new empty table; no destructive data
migration or new infrastructure is required. Restart the application to load the
new command contracts and static assets. Existing project APIs remain available.

Completion atomically uses `studio_import_project` and `checkpoint_change`.
It carries unknowns, selected-source provenance, answers, corrections and attributed
findings into the development context. Formal requirements remain empty until
explicitly registered. Sharing, verification and adoption remain separate axes.

## Current limits

- Guided setup accepts 1–1,000 ordinary saved files, at most 16 MiB each and
  32 MiB total. Chunked/large snapshots need the existing workspace import path;
  this page explicitly rejects them rather than claiming a complete import.
- At most 99 folders are initially grouped. Every selected file still belongs
  to the root and manifest. This is a provisional structure, not a dependency map.
- Native CAD topology, electrical connectivity, environment readiness, unsaved
  editor buffers, earlier operations and physical correctness are not inferred
  by the inventory inspector.
- This does not add a freeform collaborative flow editor, live cursors, generic
  provider sign-in, automatic agent provisioning or unattended agent startup.
- Setup/history is persisted under the existing ledger retention policy. Upload
  is not described as reversible deletion from append-only history.
