# Native engineering evidence: live validation

2026-11-15. Small anonymous vertical slice, using the engineering-evidence changes
on top of `a5dd2b5`. This is not a complete robot, commercial CAD integration or
physical certification. No private project was used in the public example.

## What ran

Three separate subscription-backed Bot contexts (lead, mechanical, control),
scoped principals, real Core/Worker action journals, saved artifact bytes and OS
sandboxed tools. Official Codex CLI 0.154.0 with existing ChatGPT authentication,
CLI default model and low reasoning; no paid API-key fallback or model mock.
The resolved default model was not pinned, limiting reproducibility.

The baseline contained actual STEP solids generated through OCP no-VTK
7.9.3.1.1 and a discrete software position filter. The fixed evaluator read the
STEP files, measured intersection/distance/placement, executed the filter, and
bound its report to source hashes and one explicit requirement revision.
This was **not** a dynamic actuator, electrical, structural or hardware test.

Frozen criteria: overlap <=0.001 mm3, clearance >=1 mm, carrier center in
[11,20] mm, CAD/source position error <=0.01 mm and control/geometry error
<=0.01 mm. Calibration, controller implementation, criteria and evaluator were
read-only. CAD construction and verification were separate commands; verification
did not repair CAD inputs.

## Observed sequence

1. Actual baseline evidence failed four of five criteria: overlap about 500 mm3,
   zero clearance, center 5 mm and control error about 2 mm.
2. Lead extracted saved design/control/calibration scalars with source identity,
   compared corrections, selected center 15 mm and target 13 mm for the existing
   +2 mm calibration, and delegated mechanical and control work. These values
   were chosen by the model, not supplied as the task answer.
3. Specialists edited independently. Mechanical rebuilt STEP and created an
   explicit verification plan before measuring its partial candidate. That
   candidate still failed the cross-domain control check; it was not called a
   combined success. Control returned the scoped command correction.
4. Lead retrieved both results. Joint integration was rejected because each
   candidate pinned the other domain's baseline input. **This failure is retained.**
5. Without parent intervention, lead recorded a recovery decision: integrate the
   mechanical candidate, read the current control hash, reapply the inspected
   control correction within its authority, rebuild and reverify. It did not
   bypass the conflict check or claim both original branches merged successfully.
6. Lead recorded a verification plan and ran the approved evaluator. All five
   final criteria passed: overlap 0 mm3, clearance 5 mm, center 15 mm, CAD/source
   error 0 mm and control error about 1.52e-9 mm. The report includes the actual
   execution action key, input state and saved output artifact.
7. All three tasks completed. Reflection retained the integration failure and
   revised the coordination lesson: separate write scopes alone do not resolve
   cross-domain dependency assumptions. Ledger verify passed over 2,461 events;
   replay matched.

Alternatives were compared in reasoning, but only the selected correction was
implemented. This run does not demonstrate parallel exploration of multiple
complete design alternatives or optimality.

## Parent involvement and timing

Parent preparation: fixture, fixed acceptance, role/authority configuration,
registered tools and objective. After activation: **zero parent repair values,
semantic corrections, task restarts, journal edits or manual integration**.
Read-only monitoring and evidence analysis are separate from Bot work.

| Observation | Result |
| --- | ---: |
| Automated fixture/authority preparation | 1.16 s |
| Setup through final reflection/integrity result | 690.36 s |
| Model calls | 47 (lead 30, mechanical 9, control 8) |
| Summed model call duration (parallel intervals overlap) | 900.85 s |
| Actual Bot tool executions | 4, all exited 0 |
| Summed tool subprocess duration | 1.81 s |
| Integration conflict, recovered by Bot | 1 |
| Reported input/output/cached-input tokens | 2,161,480 / 13,898 / 138,368 |

The timed preparation excludes parent implementation/test-writing time. Model
latency includes CLI/provider wait; host sleep and human active time were not
separately measured. Other local regression tests ran concurrently. These figures
show functional overhead, **not a causal time-saving result**. Large repeated
context and many separate extraction/inspection turns remain costs to measure.

## Code revision and remaining uncertainty

This first live process loaded the initial implementation before the final
source-watermark stabilization and decoded-credential hardening. Those later
fixes were made in the source checkout while it ran; its loaded process and
fixture were not restarted or edited. The initial source snapshot and complete
private journals are retained. Regression tests cover the final implementation;
the held-out comparison runs use the final frozen source tree. Do not describe
this first process as running the exact final commit.

The explicit `placement` requirement passed; the fixture also retained an
unlinked prose requirement and lacks a complete physical dependency map. The
assessment therefore still requires review. No formal design adoption occurred.
Source extraction preserves values, not automatic engineering semantics. A
verification plan is an advisory saved action, not an enforced execution gate.
Native CAD object semantics, strength/tolerance/dynamics and commercial solver
integration remain separate work.

## Reproduce

Install the repository with its CAD extra in an isolated supported Python
3.11/3.12 environment and configure official subscription CLI authentication.
Use a fresh private output directory outside the checkout:

```sh
PYTHONPATH=. python examples/engineering-crew/run.py --output /private/new-run
```

This explicitly invokes real model calls and local sandboxed tools. Output
contains credentials and model journals: do not publish it. Acceptance and roles
are in the example, not proprietary project data. For deterministic native
geometry/control checks without model calls, run
`python -m unittest discover -s tests -p test_engineering_native_fixture.py`.
