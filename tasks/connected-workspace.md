# Connected workspace: import → capture → share → continue

Approved priorities: existing project import, actual saved-tool connection, daily
capture/upload, and hardware/software correspondence. Extend Studio/continuity;
do not replace the execution engine or publish fixture data as a real project.

Workflow reference: Addy Osmani agent-skills revision
2686b620fc1fed2e8f60c704839c766b8594c6b6 (using, specification/planning,
incremental implementation, TDD, API, frontend, security and code review).

## Contract and acceptance criteria

- A human imports an existing scoped workspace once, with hierarchy, requirements,
  constraints, environment and initial work. Reuse product/session/state/change.
- Native CAD, previews, code, configuration and evaluators retain original bytes;
  component paths and existing engineering input/hash/check declarations provide
  correspondence. No native semantics or physical compatibility is inferred.
- A local CLI connects an existing Studio work to a folder. Preview before upload;
  saved-file sync checkpoints additions/edits/explicit deletions, scoped to work.
  It never silently pulls over local edits, adopts a design or shares on save.
- Changes have a durable local outbox and fixed expected state/version. Interrupted
  uploads can retry with identical bytes/key. Concurrent updates hold, never rebase.
  Unreadable/unstable/secret files must not be mistaken for deletions.
- Watch is explicit opt-in polling with two equal observations before capture;
  it captures saved file states, not unsaved UI edits/tool calls. Status reports
  local differences, remote divergence and pending/error state.
- Share is a separate exact-version action, available in Studio/CLI. Another
  authorized participant can restore bytes/context to a new folder and begin a
  separate work from that exact state. No token copied into the handoff.
- Studio exposes import/connect/continue and context within the existing compact
  layout. Checks and requirement coverage stay bound to actual versions.
- Limits for the first atomic connected workflow: 1000 files, 16 MiB per file,
  32 MiB total. Larger captures keep existing chunked APIs; do not silently truncate.
- Existing data needs no destructive migration. All new APIs are additive.

## Slices

- [x] Atomic project import and scoped incremental checkpoint APIs, negative tests.
- [x] Local binding, preview/status, durable sync/watch/share and safe continuation.
- [x] Compact Studio onboarding, connection/continuation instructions and context.
- [x] Anonymous real HTTP/filesystem acceptance, regression/security review, docs.

## Evidence

See `docs/CONNECTED_WORKSPACE_VERIFICATION.md`: actual CadQuery/HTTP/two-identity
continuation, browser folder import, narrow connection dialog, 1,156 base tests
(eight optional skips), 45 optional CAD tests, 31 JavaScript tests and isolated
wheel install. Existing Studio data remains preserved. No public deployment or
engineering-speedup claim. Review fixes include stale metadata-only sharing,
unreadable-directory deletion protection and context-only checkpoints.

## Boundaries

This is saved-file integration for installed external CAD/editor tools and Git
working copies. Licensed vendor API/feature-history verification remains untested.
Existing auth, participant setup, physical validation and agents are reused. No
new paid model, automatic command execution, deployment or manufacturing action.
