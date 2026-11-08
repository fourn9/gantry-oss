# Retain bounded read observations between Bot actions

Workflow: Addy Osmani agent-skills revision `2686b620fc1fed2e8f60c704839c766b8594c6b6`; debugging, TDD, context engineering and security review. User authorizes repairs to the autonomous development path.

Problem: a new inference per action receives only the latest result. After reading several chunks, earlier bytes are present in the ledger but absent from working input. Pagination alone therefore cannot support reasoning across chunks.

Acceptance: retain at most eight unique recent read chunks from the same task, bound the complete observation packet to 32 KiB, scan at most 64 actions, and check at most four source files / 2 MiB per input. Each observation identifies source path/hash, offset, action and attempt. Match recorded bytes against the current authorized manifest and actual workspace. Exclude stale, foreign, secret, unsafe or inconsistent observations; expose bounded omission counts. Preserve task contracts and full ledger receipts. No model inference, edits or tool effects are replayed.

Implementation is a context helper and one input-construction call. Existing native files and scoped APIs remain authoritative; observations are evidence, never instructions.

Validation: the actual worker regression retained all four chunks of a 20 KB source across an unrelated read, then invalidated them after a source edit. Foreign task, symlink, credential, forged and changed-source cases were excluded. Bounded scans/packet/source IO and duplicates were tested. Related read/context/replace/runtime suite: 125 tests passed (10.953s). Parent reviewed the completed helper after the implementation agent reached its usage limit; corrected scan metadata to report actual visited actions and unvisited window entries. No engineering decisions or project files changed.
