# Coherent file-read pagination

Workflow: Addy Osmani agent-skills reviewed revision
`2686b620fc1fed2e8f60c704839c766b8594c6b6`; reproduce, TDD, focused repair/review.

Observed defect: a file read can return more than 8,000 text/base64 characters and
an end-of-file cursor, while the next model input truncates that value to 8,000.
The model cannot follow the supplied cursor to obtain the omitted tail.

Acceptance:

- Each read delivers its entire returned byte chunk to the next model turn.
  `next_offset` advances by exactly those delivered bytes, and becomes null only
  when no source bytes remain.
- Preserve exact source hash/size. Multibyte UTF-8 chunks may use base64 when a
  byte boundary splits a character; concatenating decoded bytes must be lossless.
- Keep existing path/scope checks and generic result-preview limits.
- Minimal implementation: cap raw read chunks at 6,000 bytes, so base64 is at most
  8,000 characters and the existing preview does not cut it. Larger requested
  `length` remains an upper bound; disclose the effective cap in the action guide.
- Anonymous real action-loop tests reconstruct ASCII and multibyte files larger
  than the preview limit, with no workspace changes. No live experiment changes.

Read pagination validation: 3 tests reproduced two truncation failures before the
change; the fix and related runtime/inspection/security tests passed (110 tests,
10.647 seconds).

Additional evidenced gap: stateless action turns retain only the latest result,
so chunk pagination does not make whole-file re-emission reliable. Add one
minimal `replace` action: exact, unique UTF-8 old/new text, pinned full-file hash,
existing write scope and credential checks. Reject empty, missing, overlapping or
ambiguous matches, stale files, binary sources, and read-only requests; preserve
all unrelated bytes. No regex, fuzzy matching, external files, or engineering
choices. Test the real action loop with a source omitted from inline previews,
recorded intermediate checkpoint, exact retained tail and replay.

Replace validation: five tests reproduced four failures and one unknown-action
error before implementation; read/replace tests then passed (8 tests, 0.502 s).

The same cursor mismatch affected context/peer inspection. Root array/map pages
now deliver at most 30 entries; string pages at most 6,000 characters, allowing
even escaped astral Unicode to fit the 96 KB inline cap. Cursors count the actual
string page; nested previews still explicitly require narrower pointers. Three
tests reproduced seven failing subcases before this fix.

Final focused validation: 118 tests passed in 10.291 seconds across
`test_crew_replace`, `test_crew_read_delivery`, `test_crew_runtime`,
`test_crew_json_inspection`, `test_crew_action_guidance`, and
`test_crew_tool_capture`. No live experiment state was edited or restarted.
