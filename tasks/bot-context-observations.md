# Preserve peer/context read observations

Workflow: Addy Osmani agent-skills revision2686b620fc1fed2e8f60c704839c766b8594c6b6. User-authorized autonomous development-path repair. Anonymous failing tests preceded implementation.

Observed: a stateless manager repeatedly fetched its own action history to recover the source pointer and earlier chunks of peer records. The existing inspect outer limit100 rejected a6000-character limit although default retrieval itself returned6000characters.

Implementation: publish the actual read/context/inspect schemas used by runtime validation. Keep response cursors aligned with bounded actual delivery. Preserve at most8small historical context/inspect/inspect_json receipts in48KiB, scanning at most32actions from the same task. Include exact request, action/attempt/input-state and responsehash. Skip foreign, credential-bearing and oversized receipts. Mark these as historical observations; they never establish current state or authorization. Existing Core checks and immutable full-context snapshots remain authoritative.

Validation: three tests reproduced missing functionality;128related tests passed(10.843s). Final48KiB bounds and actual worker/replay were retested. Source-invalidated file observations remain separate because peer context can change independently. Parent performed the source review after helper agents reached their usage limit; do not imply completed independent review.
