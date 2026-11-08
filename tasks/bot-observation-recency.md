# Preserve actual Core history ordering

Workflow: Addy Osmani agent-skills revision `2686b620fc1fed2e8f60c704839c766b8594c6b6`; debugging, failing regression, minimal fix, security and runtime review.

Observed: `_crew_records` returns descending `created_seq,id`. The new observation helpers reversed that list and stopped at eight items, favoring older source/peer reads. Optional action previews also treated the list as append-ordered. Existing short worker tests stayed below the retention limit, while synthetic fixtures incorrectly used ascending order.

Acceptance: preserve Core's newest-first input order during bounded selection, then render retained observations chronologically. Prefer newest action previews; appended task reports still retain their latest tail. Keep byte/IO/count bounds, exact source/hash validation, private-record handling and complete ledger records unchanged. Do not increase context limits or synthesize source summaries.

Three tests failed before the fix: a real worker with twelve unique source reads, peer history exceeding its scan window, and optional action/report selection. Correct the synthetic fixtures to match Core. Run focused and full regression suites, build, and retain private recovery evidence separately. This fixes which observations reach inference; it does not prove fewer reads or faster development.
