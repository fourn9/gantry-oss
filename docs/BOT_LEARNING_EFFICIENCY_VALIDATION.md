# Experience receipt batching: measured validation

Recorded 2026-11-04. Implementation: `6b97ec4`.

An earlier private eight-run study found first-edit acceptance in both groups:
experience availability avoided no observed retry. Three separate experience-use
bookkeeping model turns consumed 39.06 seconds. Planning/reflection also grew.
Both groups already used Gantry and its planning/reflection path; this was not
Gantry versus ordinary files. Current planning already included file previews.

The additive completion-report contract now saves explicit experience/action links
atomically, retains private receipt access, and preserves reflection. It does not
infer use from retrieval, remove verification, or change adoption authority.
See [the contract](BOT_CONTINUITY.md).

## Fresh controlled comparison

Two code-report validation tasks derived from a prior engineering failure; two
independent pairs per task, counterbalanced order. Both variants received the same
imported experience, fixed inputs and 102-check verifier. Separate ledgers,
workspaces and model contexts. Requested model `gpt-6-astra`, reasoning `low`,
official subscription backend, no API-key fallback. Each trial allowed 300 seconds
and 12 calls. This was code validation, not a CAD build or physical certification.

| Metric | Previous path | Batched completion |
|---|---:|---:|
| Accepted | 4/4 | 4/4 |
| Mean total seconds | 112.50 | 99.07 |
| Model calls | 24 | 20 |
| Input tokens | 445,095 | 359,654 |
| Output tokens | 10,938 | 9,424 |
| Setup seconds, summed separately | 0.134 | 0.132 |

| Paired observation | Previous seconds | Batched seconds |
|---|---:|---:|
| Task A, pair 1 | 111.92 | 92.61 |
| Task A, pair 2 (reverse order) | 109.00 | 95.66 |
| Task B, pair 1 | 117.38 | 102.93 |
| Task B, pair 2 (reverse order) | 111.72 | 105.10 |

Observed total time decreased 11.9% and input tokens 19.2%.
All four paired observations were faster with batching. Every trial preserved one
explicit receipt linked to its actual edit and verification, visible in reflection.
All eight ledgers verified; frozen inputs matched; there were no formal adoptions.
The saved development states remained unverified; acceptance here refers only to
the frozen Python checks, not a broader verified design state.
Planning, recording, verification, waiting and reflection are included in time.
There were no failures/timeouts in these eight final runs. Monetary cost was not
reported per invocation and is not estimated.

## Integrity and limits

A preliminary implementation exposed private receipt text in shared reports and
raw finish actions. Review caught it, a regression test reproduced it, and the
read boundary was fixed. Three already-started prototype trials were retained;
five unstarted slots were stopped. Those outcomes are not pooled with this fresh
comparison of the corrected implementation.

Seven new regression scenarios cover atomicity, invalid/foreign evidence, stale
fences, lost acknowledgements, private views, full 40-link reflection, and empty/
null compatibility. Full Python suite: 1,409 invocations, 1,401 passes and eight
existing environment-dependent skips. Independent code review approved the fix.

This demonstrates lower bookkeeping overhead in a small comparison. It does not
establish that experience makes design work faster than working without experience,
that Bots acquired the input lesson autonomously, or that robot development as a
whole accelerates. Provider latency/cache are not fully controlled, and the frozen
verifier does not cover all numeric edge cases. No private cases, source project
data, credentials or model journals are included in public source.
