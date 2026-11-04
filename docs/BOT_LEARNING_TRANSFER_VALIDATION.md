# Generated-lesson transfer validation — 2026-11-04

Implemented: [selective effort, exact duplicate presentation, independent lesson
checks and failure-first transfer experiments](BOT_LEARNING_TRANSFER.md).

## Runtime evidence

Used the existing Codex ChatGPT subscription with requested `gpt-6-astra`, reasoning
`low`. No API-key fallback. Each run had a 360-second / 14-call experimental limit.
The task family concerns Python gates that classify saved CAD measurement receipts,
not execution of a CAD kernel or manufacture of a robot.

Inputs and acceptance were frozen before training. One training run began with no
imported lesson, observed a failing verifier, edited the gate, reran it successfully
and generated one conditional lesson. Training took **80.33 seconds / 5 calls**.
The lesson retained evidence, applicability and explicit exceptions: union formulas
must not be transferred unchanged to subtraction; software acceptance is not proof
of geometric or physical correctness.

Two different evaluation tasks began in independent fresh ledgers/workspaces/model
contexts, with and without that generated lesson. No training code/solution, raw
report or target-arm history was shared. One changed the operation to subtraction;
the other changed tolerances, numeric scales and boundary cases.

| Task | No lesson | Generated lesson | Frozen acceptance |
| --- | ---: | ---: | --- |
| Subtraction gate | 72.35 s / 5 calls | 113.02 s / 6 calls | Both passed |
| Changed-scale union gate | 67.92 s / 5 calls | 104.95 s / 6 calls | Both passed |
| Mean | **70.14 s** | **108.98 s** | 2/2 per condition |

Both conditions performed baseline check → one edit → check → completion, followed
by reflection. There were no redundant identical tool checks or post-edit failures
removed by the lesson. Both lesson runs recorded an explicit recheck decision and
an experience-use link to actual actions. The subtraction run explicitly replaced
the union-specific rule. This establishes conditional transfer and provenance,
**not improved task choice, accuracy or development speed**.

Across the two task pairs, no-lesson input/output tokens totaled 186,661 / 3,394;
lesson tokens totaled 244,573 / 5,629. The additional selection calls took 43.54
seconds in aggregate. Action and reflection calls also cost more. Training must be
added to the learned route's cost; there is no observed saving to amortize here.

## Separate empty-recall overhead check

A separately declared follow-up used the same no-lesson task in two fresh contexts,
with the same settings and implementation. This was an overhead check on a reused
task, not a new held-out learning claim.

| Mode | Time | Calls | Acceptance |
| --- | ---: | ---: | --- |
| Selective | 74.65 s | 5 | Pass |
| Always plan | 91.83 s | 6 | Pass |

Selective mode omitted only the empty experience-selection invocation. Normal
reasoning, actual failed/passing checks and reflection remained. The observed
18.7% reduction is one descriptive pair, not a reliable population estimate.

## Correctness checks

- Full Python regression: **1,626 executed, 1,618 passed, 8 environmental skips**.
- Additional focused regression after the final stale-discard fix: **269 passed**. Wheel packaging succeeded without downloading deps.
- New contracts tested with real Core/worker and explicitly deterministic inference:
  no-lesson routing, acknowledgement-loss recovery before/after commit, changed
  premises, exact grouping and correction exclusion, different-author consultation,
  evidence references, requester return, read-only scope, peer privacy, revoked
  participants, existing/new corrections, failed-report preservation and replay.
- Independent review found and fixed disclosure through decision records and a
  stale-result blocker. Explicit acknowledgement/discard can now clear a question
  without making the stale opinion usable. Review closed with no blocking findings.
- The five transfer ledgers replay identically and remain formally unadopted.
  Learned-use references point to real saved actions. The Python acceptance result
  did not promote a development state to physically verified/adopted.

## Limits

- Only one pair per held-out case and one overhead pair; no statistical effect claim.
  Provider load/cache and local concurrent regression load were not controlled.
- Both arms used Crew, so this is not Gantry versus ordinary development.
- The model already solved both tasks in one edit without a lesson. This task family
  cannot establish reduced engineering rework from learning.
- Independent peer-check plumbing was exercised using fixture reasoning and actual
  workers, not a live-model comparative study of reviewer quality. Distinct Bot
  identities can still share a model's mistakes.
- Exact grouping is conservative; it does not solve semantic recall or choose an
  optimal amount of learning. Reflection still has a cost. Native CAD, electrical
  and production physical qualification are separate integration work.
- No trial-time human intervention was needed. Experiment preparation time was not
  measured. Subscription usage was reported, per-call monetary price was not.
- Private frozen source, manifests, ledgers and model journals are retained outside
  this public repository. The measured source predates final peer-check privacy
  hardening; that unused path was verified separately against the final source.

Next useful evidence is a preregistered multi-stage task where prior experience can
change an actual dependency/test order, with an independent correctness criterion.
Another easy single-edit task would mainly measure added prompt and reflection cost.
