# Design change → evidence → next change

Approved scope: finish the existing development path, not a new dispatcher or solver.
Workflow reference: Addy Osmani agent-skills at
`2686b620fc1fed2e8f60c704839c766b8594c6b6` (specification, planning, incremental
implementation, TDD, API design, security and independent review).

## Objective and assumptions

Customer Bots should receive a current, version-bound answer to what changed,
what may be affected, which checks/requirements still lack applicable evidence,
and how that differs from their assignment baseline. They choose the next action.
Mentor remains an optional reviewer. Core must not choose engineering solutions.
Use existing immutable states, engineering checks, requirements, validation maps,
Bot actions/reports, scoped tools and durable recovery. Preserve all old data.
Unknown physical relationships and test adequacy stay explicit; passing recorded
checks is not whole-product certification or human adoption.

## Slices / acceptance

- [x] Add a read-only design assessment over baseline/current state. Include cumulative
  file changes, declared component/check impact, optional existing validation-map
  traversal, requirement transitions, missing/stale evidence and unresolved scope.
  Deleted baseline checks or unknown mappings cannot silently become covered.
  Enforce both states' project/access boundaries; no new mutable assessment store.
- [x] Put this assessment on normal Bot and Mentor inputs and saved Bot reports.
  Preserve task requirement subsets (including explicit exploration); make focused
  current source previews available to experience planning. No extra model call.
- [x] Pin physical acceptance plans to the work/change baseline, not an intermediate
  checkpoint. A checkpointed relaxation must not become authorized acceptance.
  Reassessed new work can intentionally use a newly approved input state.
- [x] Demonstrate real CAD change → failed measured evidence → model-chosen correction
  → rerun → requirement coverage. Continue from saved output in a fresh task and
  show a dependency change invalidates earlier evidence. Keep native CAD and actual
  model calls distinct from deterministic regression fixtures. No paid API fallback.
- [x] Independent review, full regressions, wheel build and user documentation.

## Interface / implementation

Add `get_design_assessment` with `baseline_state_id`, `state_id`; the response is
derived from exact state IDs and current requirement revisions. Internal contexts
reuse its canonical builder. Bounded views explicitly mark omitted information.
No changes to existing task-completion or human-adoption semantics. Saved reports
retain the assessment used at return time, so future reads do not rewrite history.
Use repository Python style, `require(..., code, message)`, existing contracts and
parameterized indexed reads. New pure logic lives in `gantry/design_assessment.py`.

## Threat model and boundaries

Untrusted source files, model conclusions and adapter declarations are evidence,
not authority. Check both states before any read. Avoid automatic network/tool
execution from assessments. Never allow changed evidence/criteria to inherit pass.
Native tools remain in the customer sandbox. Do not publish local credentials,
model journals or private engineering data. New examples use anonymous assemblies.
No DB migration, new cloud service, physical operation or automatic adoption.

## Verification commands

From repository root, use the existing environment:

```sh
../gantry-security-env-20261024/bin/python -m unittest discover -s tests -p test_design_assessment.py -q
../gantry-security-env-20261024/bin/python -m unittest discover -s tests -p test_requirement_handoff.py -q
../gantry-security-env-20261024/bin/python -m unittest discover -s tests -q
node --test tests/*.mjs
../gantry-security-env-20261024/bin/python -m pip wheel --no-deps --no-build-isolation . -w /tmp/gantry-design-wheel
```

Native CAD checks and the subscription-backed example use the existing separately
installed CAD runtime; record its exact versions and all outcomes in verification
documentation. Tests do not prove development speedup.

## Completion evidence

- `docs/DESIGN_CHANGE_LOOP.md`: API, normal paths, acceptance pinning, upgrade and limits.
- `docs/DESIGN_CHANGE_LOOP_VERIFICATION.md`: native two-task subscription run and failures retained.
- Full Python run: 1,136 tests, zero failures, 8 optional skips; 127.312 seconds.
- Focused design assessment suite: 66 tests passed. Native CadQuery suite: 5 passed.
- JavaScript suite: 9 passed. Wheel built via pip/setuptools without build isolation.
- Independent read-only review found and drove fixes for causal evidence binding,
  stale map sources, Mentor input freshness, nested response bounds, hierarchical
  subject selection, partial-preview approval, and reasoned not-applicable checks.
- No DB migration, old-data rewriting, model charge outside the subscription,
  private project publication, formal design adoption or physical operation.

Remaining limits: manually declared dependency completeness, engineering acceptance
adequacy, vendor-specific live environments and physics beyond the demonstrated
static/interface checks. Functional success is not measured development speedup.
