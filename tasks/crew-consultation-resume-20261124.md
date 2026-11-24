# Read a returned consultation directly

Follow the repository workflow using the reviewed Addy Osmani skills revision
2686b620fc1fed2e8f60c704839c766b8594c6b6.

A recorded resumed task traversed the peer's reports array, report envelope and
report body across three inference calls. Provide a request for the exact response
report in the resumed task context. Derive it from the saved same-project
consultation and answer. Reading a response must still use the existing authorized
inspection action. Resolution requires a separate Bot judgment. An unavailable or
cancelled response must not be presented as a completed report.

Test ask, wait, answer, direct retrieval and explicit resolution through the normal
worker loop. Keep this change separate from the frozen before/after comparison.

The link carries the saved answer ID, report sequence and state ID. A Bot
uses the existing inspect action and its pagination to read the report.
Cancellation now returns the cancellation reason even when a response task
previously reported that it was waiting. Existing saved messages keep their
original contents. No data migration is required.

Regression coverage exercises the two-worker API/Runner path, a still-open
consultation, cancellation after an intermediate report, and ledger replay.
