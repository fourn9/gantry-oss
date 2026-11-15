# Engineering evidence in Studio

Work → Checks keeps existing evaluations primary. Two collapsed sections add
context without changing CAD, Code, conversation anchors or adoption controls:

- **Change impact & evidence** compares the work's baseline with the selected
  saved state. Fields show before/after observations, classification, method,
  units, frame and time basis when acquired. Source links open the exact saved
  file state and hash in the existing Library. Declared and extracted values are
  explicitly not verification results.
- **Verification plans** shows recorded `plan_verification` Bot action receipts
  for this work's task: the question, input state, tool, check scopes, assumptions,
  missing inputs and pass/fail/unknown next steps. A plan is not execution. Plans
  for another input state are labelled **Previous / other version**.

`studio_work.design_assessment` uses the existing `get_design_assessment`
contract. Selecting an older work state recomputes the comparison for that
state; results and observations are not carried forward as passes. New evidence
or task action records change the Studio activity token, so an open work view can
offer its existing refresh action.

`studio_work.verification_plans` is a bounded projection of recorded actions,
not new storage: at most ten plans from the latest fifty actions, within a 64 KiB
response budget. `partial` and a `history_request` identify omitted history.
The same existing action visibility rules apply. Full task records remain
available via `get_bot_records` with `kind: actions`.

Missing observations, conflicts and partial evidence stay explicit. The view
does not predict intent, certify physical behavior, execute a plan, approve a
design or infer progress. Unconnected projects still show source identity rather
than generating broken Library links.

## Verification

Anonymous fixtures cover exact state/source links, escaped imported content,
partial/conflicting evidence, unconnected projects, plan-versus-execution
wording, selected-state assessment, activity refresh and work/task isolation.
These are product contract checks, not evidence of engineering correctness or
development speedup.

The actual view modules were also rendered with a private synthetic fixture in
a local browser: the disclosures started closed, expanded independently and
showed exact before/after source links. The expanded view was inspected at the
default desktop width and 360 CSS pixels; it had no page-width overflow at 360
pixels. This browser check used fixture data, not a production connector or a
physical experiment.

```sh
PYTHONPATH=tests python -m unittest test_studio_engineering test_studio
node --test tests/test_studio_engineering.mjs tests/test_studio_web.mjs
```
