# Bounded source-observation retention

Reference: Addy Osmani agent-skills revision `2686b620fc1fed2e8f60c704839c766b8594c6b6`; using-agent-skills, performance-optimization, context-engineering, test-driven-development.

Observed private execution journals include repeated requests for unchanged acceptance/contract chunks explicitly omitted from retained observations. The existing four-source/eight-chunk count caps evict short documents before the 32 KiB context budget is full. This is a context-availability issue; no engineering review is removed.

Acceptance:
- Retain twelve small verified chunks across six authorized documents when below existing byte budgets.
- Preserve same-task authorization, manifest/content hash equality, symlink/secret rejection, source and packet byte caps, scan cap, provenance and omission reporting.
- Invalidated bytes must not survive edits or consultation resumption.
- Keep evidence-changing replans: all ten observed refreshes changed recalled items, not merely source inventory.
- Compare frozen real executions later; trace replay establishes availability only, not elapsed-time improvement.

Implementation: raise source/chunk count ceilings to 16/32 while retaining 32 KiB packet, 2 MiB source I/O, 64-action scan and essential-context protections. No persistent cache, model change, engineering solution change or acceptance change.

Validation: failing six-document regression observed (8 chunks instead of 12); run targeted context and runtime suites after fix. Private trace analysis remains outside public source.
