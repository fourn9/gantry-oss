# Bounded read-only structured evidence inspection

Workflow: Addy Osmani agent-skills revision
`2686b620fc1fed2e8f60c704839c766b8594c6b6`; reproduce, TDD, incremental fix and
security review. User authorized repairing runtime gaps encountered by actual Bots.

Problem: a read-only specialist can read bytes but cannot navigate an authorized
compressed JSON report without executing a tool. Add a generic `inspect_json`
action; no candidate-specific extraction, engineering answer or evaluator change.

Acceptance:

- Read ordinary JSON or explicit `zlib-base64-json-v1` envelopes from this task's
  restored workspace. Existing descriptor-relative file, private-path, link and
  16 MiB input restrictions remain. No commands, writes or external paths.
- Verify envelope base64/zlib format, exact decoded length and SHA-256. Bound
  decompression to 64 MiB; reject bombs, truncated/concatenated/trailing streams,
  malformed JSON and credential-like decoded content without echoing contents.
- Reuse JSON pointer navigation and pagination. Optional `nonempty_at` filters an
  array by a relative JSON pointer chosen by the model; return original indices.
- Bound returned values using existing preview behavior; retain source-file and
  decoded hashes, encoding, size, pointer and page metadata in the action receipt.
- Expose action schema/guide and allow read-only consultation/Studio Ask, under
  existing current-task authorization. No automatic validation/adoption inference.
- Tests cover malformed envelopes/bounds, path/link rejection, filtering/pages,
  receipt metadata and actual action-loop read-only use. Anonymous public fixtures.

Implementation: helper module for JSON decoding/navigation; small Crew runtime
dispatch/schema integration. No new dependencies, public data or live runtime edits.

Interface example (generic saved observations):

```json
{"path":"evidence/results.json","pointer":"/cases","nonempty_at":"/failures","offset":0,"limit":10}
```

`nonempty_at` is a literal pointer relative to each array element, never code or
a query expression. Missing, null, false, zero and empty values are excluded;
`filter_counts` separates missing from empty/false. `source_indices` preserve the
original unfiltered positions. Follow `/cases/<source_index>/failures` to inspect a
particular field if a returned item is preview-truncated. `total` and `next_offset`
paginate the filtered array. Source/decoded hashes identify the exact inspected
bytes; decoding or inspection does not establish a successful evaluation.

Verification: initial RED had 2 failures / 4 errors across 8 tests because the action
did not exist. After implementation, 8 passed. Added strict finite-number/depth and
filter-count guards; related Crew suite passed 131 tests in 15.478 s. Final security
review reproduced escaped-credential output leakage in plain/compressed JSON;
normalized returned-value screening fixes it. Final JSON + existing pointer-guidance
suite passed 16 tests in 0.545 s. No reported skips; `git diff --check` clean.

The new module preserves 16 MiB file reads and caps decoded bytes at 64 MiB;
JSON nesting is capped at 64 levels. NaN, Infinity and overflowing float literals
are rejected. The byte bound is not a claim of constant peak Python heap usage.
Fixture inference verifies the read-only action loop and saved metadata, not model
diagnostic reasoning. Runtime loading is a separate controlled operation.
