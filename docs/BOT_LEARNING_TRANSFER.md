# Generated lessons, selective effort and peer checks

Gantry keeps the customer Bot's experience outside individual model conversations.
The Bot still decides what to do; Core checks identity, access, versions and evidence
references. These paths do not update LLM weights or guarantee better engineering.
Mentor remains separate. No new paid provider or hosted service is required.

## Selective learning

In a private worker configuration, use:

```json
{
  "workflow": "bot_development",
  "experience_learning": true,
  "learning_mode": "selective",
  "agent_loop": true
}
```

Merge these fields into the existing configuration; keep the customer backend,
local tools and scoped identity. Regenerate and approve that runtime's manifest
before starting the worker. Existing tokens need the current Bot profile if they
will call `complete_empty_bot_learning`; existing permissions are not enlarged.

The default remains `always` when `learning_mode` is omitted. Selective mode:

- Performs the same scoped recall. If it is complete and empty, records an explicit
  `selection_method=no_matching_experience` receipt without a separate selection
  model invocation. The normal action model still plans and performs the work.
- Retains the outcome reflection, including failures and first tasks with no prior
  experience. It does not discard the data needed to learn from new failures.
- Uses the model selection path for nonempty or incomplete recall. A missing lexical
  match is not proof that no relevant experience exists; this limitation is saved.
- Presents exact duplicate bodies once, retaining every memory ID and requiring
  an apply/recheck/reject decision for each ID. Differing author, evidence, source
  state, conditions, applicability or feedback prevent grouping. Incoming and
  outgoing contradiction/correction links are never grouped. Full records remain
  available through `get_bot_learning_plan`.

This conservatively removes avoidable work. It is not a semantic search engine or
an automatic predictor of the monetary value of learning. Small tasks may still
cost more with experience selection and reflection than without them.

The new empty-recall endpoint uses the same frozen premise, current source-access,
working-state and task-fence checks as a model plan. Saved journals reconcile lost
acknowledgements before retrying and never invent an inference receipt for this
mechanical route. An unknown provider result remains unknown.

## Independent lesson consultation

A Bot can explicitly select a peer using its existing `ask` action:

```json
{
  "to_bot_id": "reviewer-bot",
  "question": "Check whether this lesson applies to the current assembly",
  "evidence": ["STATE_ID"],
  "memory_id": "MEMORY_ID"
}
```

For direct API/MCP use, call `ask_bot` with the active task ID/fence and a stable
idempotency key. This creates a read-only report task for the selected peer. The
requester finishes `waiting`, as for an ordinary consultation. It does not grant
new access or automatically activate another machine. The peer's running customer
worker claims the pending task; offline workers can do so after reconnecting.

The lesson must be shared and readable by both participants, in the same project.
The reviewer must be a different Bot **and principal** from both the requester and
the lesson's author. Two identities may use the same model and share its biases.

The task pins the lesson hash, requesting task, development state, requirement
revisions and currently accessible corrections. Execution/read/resolution recheck
those inputs and source/participant bindings. Disabled or expired participant and
source-author credentials make the check unavailable, without deleting history.
New corrections require a fresh check. A bounded, incomplete correction scan is
held rather than assumed complete.

The reviewer gets `get_bot_task.experience_check` and records actual observations.
A completed `finish` report must include:

```json
{
  "experience_check": {
    "verdict": "inconclusive",
    "reason": "The saved measurements do not establish clearance under load",
    "action_ids": ["OBSERVATION_ACTION_ID"]
  }
}
```

This is an optional field of the ordinary full report, not a standalone report.
Other verdicts are `supported_for_scope` and `contradicted`. IDs must refer to
observations from this peer task's current attempt. Core checks the references,
not whether the natural-language conclusion logically follows. A review cannot
edit or integrate a candidate through its empty write scope/report.

The original question receives a response and wakes its waiting task. The requester
uses `inspect`/`get_bot_task` to read the actual private result and cited actions,
then resolves the question explicitly. A stale response may be explicitly discarded;
resolution records its unavailable status and never makes it usable. Failed/blocked reports retain their real
explanation with no supporting verdict. Public task reports/messages use a generic
summary; the lesson interpretation, actions and decisions are available only to
currently authorized participants and the owner. General project peers do not gain
access to these details from task listing. API consumers must inspect `available`
and `reason` rather than interpreting a missing result as a successful check.

`bot_experience_checks` is an additive indexed record collection. Recall includes
up to five recent readable checks of a memory. Inconclusive, contradicted or
changed-basis results require reassessment. Even support for the exact scope does
not clear other applicability warnings, validate physical behavior, formally adopt
an artifact or enlarge execution authority. Old checks are retained.

## Failure-to-lesson-to-held-out-work experiment

`gantry-crew evaluate-learning` can first run a training case, then run an isolated
with/without-generated-lesson pair on an evaluation case:

```sh
gantry-crew evaluate-learning \
  --training-case /private/training/case.json \
  --case /private/heldout/case.json \
  --output /private/new-transfer-run \
  --model YOUR_MODEL --reasoning-effort low \
  --learning-mode selective --max-calls 14 --seconds 360 \
  --repetitions 1 --seed 1 --live-codex
```

Use the existing explicit-file case format from [learning evaluation](BOT_LEARNING_EVALUATION.md).
Both cases must start with `experiences: []`. The Python API
`run_transfer_evaluation(training_case, cases, ...)` also accepts several distinct
evaluation cases. Model/effort and bounds are explicit experimental settings, not
new product-wide usage limits. This command requires a supported OS sandbox and
an existing Codex ChatGPT login; it never falls back to an API key.

All selected files, acceptance, verifier and environment are frozen **before**
training. Identical task contents/verifiers are rejected even if renamed. This is
not a semantic leakage detector: the experiment designer must select genuinely
held-out tasks with meaningful changed conditions.

Training must have a failing frozen baseline. Only actual lessons from its saved,
completed reflection are transferred, with original conditions, limitations and
source hashes. No training solutions, full reports, model journals or target-arm
results are imported. No generated lesson means an inconclusive study, not a
handwritten replacement. Training that fails to finish cannot establish successful
training, even if its failure yields a usable hypothesis; inspect its saved status.

Every evaluation arm starts in a separate ledger, workspace and model context.
Both use the same Crew implementation, tools, initial files and acceptance. All
model calls, action order, failed/repeated checks, experience-use receipts and
outcome verification are retained. Training cost and per-arm setup cost are separate
from task time and must be included in any amortized benefit claim. Timeouts,
failures and missing metrics are preserved. Money is unknown when the subscription
provider does not report a per-call charge.

The output directory contains credentials and private source/model journals. Keep
it private; publish only reviewed aggregate observations. This comparison measures
experience availability, not Gantry versus no Gantry, nor general CAD design speed.

## Compatibility and validation

No historical event or artifact is rewritten. Existing worker configurations,
ordinary `ask_bot`, reports without the new field and saved plan journals remain
valid. Use current API schemas; endpoints retain shared authentication and atomic
idempotency. See [validation](BOT_LEARNING_TRANSFER_VALIDATION.md) for observed
runtime results and the distinction between fixture reasoning and model inference.
