# Files, requirements and shared context

Studio presents one saved development state through **Structure / Files / Work /
Requirements**. It does not create a second ledger for humans or a lossy copy for
agents. Read models reference the same immutable states, manifests and events.

## Human workflow

- Open Files from the project or a component. Select a saved file to inspect its
  text or STL/OBJ preview, download native bytes, or compare the first recorded
  parent. A merged state can have multiple parents; this control compares only
  the first. Versions selects another saved state. Restore / continue provides
  the existing CLI restore command and capture/unfinished context.
- Open Related to see pinned requirements, declared check inputs/evidence, and
  work starting from or containing this exact state. Unrelated newer work is not
  presented as evidence for an older state.
- Open Requirements to inspect required checks, missing evidence, changed inputs
  and requirement revisions needing review. A file's existence, a successful
  check, completed work, sharing and formal adoption remain different facts.
- Open Discuss on a project, component, file, mesh part, code line or requirement.
  A work record is optional. A code line or file always retains its hash and state;
  a requirement retains its revision. Inbox returns to that original target.
- Mention a named member or Crew agent. Stable principal IDs identify recipients;
  names and roles come from existing participant and persistent Bot bindings.
  A mention only notifies. Ask Crew agent requests a read-only answer. Explicit
  assignment uses the existing authorized scope, queue, worker and result path.
  A disconnected worker leaves a queued request; the UI does not simulate a reply.

Related and Discussion share one side panel and stack below the artifact on narrow
screens. Drafts remain in tab memory per target. The latest 50 project messages load
first; Load earlier messages retrieves older records. Load updates merges newly
arrived replies without discarding already loaded messages or changing the state.

## Agent retrieval

These commands use the normal authenticated command API and CLI/MCP registry:

```json
{"command":"studio_context","args":{"project_id":"PROJECT_ID","state_id":"STATE_ID","anchor":{"kind":"component","component_id":"COMPONENT_ID"},"limit":20}}
```

The example describes a command and its arguments; use the transport's existing
envelope and credentials. `studio_context` returns all pinned requirements,
constraints, open questions, unfinished work and capture omissions, plus bounded
related metadata and source IDs/ledger sequence. It does not put native file bytes
into every context or ask an LLM to summarize them. Retrieve the selected artifact
through the existing verified artifact API when necessary.

`studio_library` supports `section: files | requirements | versions`, `after` and
`limit` (1–100), optional component scope, file query or exact path. The default
state is the project's saved baseline, never an implicit combination of branch heads.
`studio_related` requires an exact state and anchor. Related work uses `after`/`next`;
conversation messages use a separate `message_after`/`message_next` cursor, ordered
newest first for retrieval and chronologically for display. An empty filtered work
page can still have `next`. Follow it rather than treating that page as the end.
Related check/file lists are bounded and expose truncation. Full Files remains paged.
`studio_context` accepts `since_state` and independent `delta_after` for a paged delta.
Mandatory constraints are not silently removed to meet a related-record limit.

## Link meaning and authority

File-to-requirement links come from existing engineering check input/evidence paths
and pinned `requirement_refs`. They mean "used by this check", not "this file proves
the requirement". Legacy prose notes remain visibly unlinked. There is no inferred
requirement satisfaction, automatic backfill or semantic CAD compatibility judgment.
Prior results remain recorded; changed inputs/evidence or requirement revisions can
make them inapplicable to the displayed state.

All reads enforce project-zone and saved-session/state access. Anchor validation
rejects foreign states, missing components, mismatched hashes/revisions and invalid
code lines. Recipients must currently have access. Replies cannot retarget threads.
Project assignment requires the current session state, authorized owner and existing
write scope; Ask is read-only. Mentions do not grant permissions or start execution.

## Compatibility and delivery

The change is additive: existing work conversations and IDs remain valid, and past
events are not rewritten. New project conversations reuse the thread/message/inbox
projections and replay correctly. Issued credentials with command allowlists retain
their scope; deliberately update them if these additional reads are needed.

This implementation is in the application source. Static public demo responders and
private installations with customized read allowlists, CAD hooks or structure indexes
need an explicit compatibility update before deploying the new browser assets. Do
not overwrite those custom runtimes or publish private snapshots. This change does
not deploy either installation.

Native CAD preview generation, native face identity/remapping, live CAD/Git capture,
real model inference and worker availability remain connector responsibilities.
This UI does not add them. Large-project performance is not established by the
functional tests; legacy work-detail reads still have scaling work outstanding.

See [verification evidence](STUDIO_LIBRARY_VERIFICATION.md).
