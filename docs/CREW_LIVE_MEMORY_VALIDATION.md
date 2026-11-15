# Live memory, delegation and reflection validation

2026-11-15. Tested source: `3a6b7a217c7e1ee78d6ac2c1f2fb863ac6a12d12`.

**Initial run: the live-model path completed after manual recovery. It was not an
uninterrupted autonomous success or evidence of engineering speedup.**

## Method

Three persistent Bots (lead, mechanical, control) used separate inference contexts,
scoped credentials, real Core/Worker execution and a sandboxed Python evaluator.
An anonymous two-file configuration represented a coupled actuator interface;
this did not exercise CAD, physical simulation or real hardware.

The parent supplied the initial inconsistent configuration, fixed acceptance,
immutable evaluator, organization and scoped tools. A real-model diagnostic task
first measured the baseline failure and saved a conditional lesson through the
normal reflection path. No lesson or model answer was seeded by the parent.

Fresh workers then started a due owner-approved standing routine using the same
ledger. The parent supplied no repair value or next-task assignment. Inference
used official Codex CLI 0.154.0, existing ChatGPT authentication, CLI default model
and low reasoning. No API-key fallback. The exact default model was not pinned;
this is functional validation, not a reproducible model-quality benchmark.

## Observed behavior

1. Lead recalled two earlier records and chose `recheck`, distinguishing the earlier
   diagnostic scope from present implementation authority.
2. Lead compared alternatives and selected a one-field repair that retained the
   existing control setting. It recorded rationale and delegated implementation
   to mechanical and compatibility assessment to control.
3. Specialists ran concurrently. Mechanical edited its scoped file and ran the
   unchanged evaluator; control reported compatibility without editing.
4. Lead planning was held with `stale_basis`: specialist reflections added shared
   experience while its model response was in flight.
5. After manual replan recovery, lead inspected actual reports, candidate diff and
   receipts, integrated the candidate and ran the evaluator on the combined state.
6. Final execution exited zero with all four numerical predicates true. Five
   reflections completed across diagnostic, waiting and completed reports.
7. Mechanical and lead recorded explicit memory-to-action links. Final feedback
   correctly kept causal usefulness `unknown`: following a remembered sequence
   and succeeding does not prove benefit over current task instructions alone.
8. Ledger verification succeeded and replay matched (1,188 verified events).
   Physical uncertainty, incomplete requirement linkage and no formal adoption
   remained visible; tool success was not promoted to product acceptance.

## Parent involvement

- Preparation: anonymous fixture, immutable checks, Bot responsibilities and
  authority, worker startup/monitoring and activation of the second-stage routine.
- Connection correction: an explicitly selected app-visible model identifier was
  rejected by the CLI backend before any answer; the preserved first run was
  followed by a fresh run using the existing CLI-default connection.
- Manual recovery: after all workers stopped, the parent preserved the unaccepted
  stale learning journal and used the existing task recovery path to obtain a new
  plan. No execution actions had started in that attempt. Recall grew from six to
  eight records. This journal operation is **not an automatic product recovery**.
- No parent-written repair, delegation answer, specialist edit or success result.
  Completed specialist effects were not repeated.

## Timing and limitations

The successful run including its hold/recovery interval took about 489 seconds:
53 seconds baseline, 159 seconds continuation until hold, 119 seconds from hold
until parent recovery began, and 157.5 seconds after recovery began. These exclude
initial preparation and the first rejected connection attempt. The hold interval
is elapsed diagnosis/scripting/communication time, not measured human labor.

Thirty completed model calls: lead 20, mechanical 6, control 4. Provider receipts
reported 873,030 input tokens, 11,619 output tokens and 55,296 cached input tokens.
Repeated context contributes to these counts; parent chat usage is excluded.
Cumulative inference time was about 493 seconds and overlaps across concurrent
Bots. No dollar-cost or speedup claim is made.

Two concrete gaps remain: automatic replanning after shared experience changes,
and clearer bounded discovery of peer reports/evidence. The lead encountered five
not-found pointer requests and truncated results before finding the right pages;
it recovered independently and recorded the retrieval failure as a lesson.

No product code was changed during this exercise. Private model journals,
credentials and experiment data are intentionally excluded from public source.
Further tests need independent no-memory comparisons and domain-specific work.


## Follow-up: automatic replan and discoverable evidence (2026-11-15)

Tested implementation: `c858dfd`. A fresh isolated run repeated the same anonymous
fixture with separate Bot principals and real subscription inference. The parent
again prepared acceptance/tools/roles and activated the standing responsibility
after diagnosis. There were **no parent repairs, restarts, journal edits, answer
rewrites or delegated solution values after activation**. No model mocks or paid
API fallback were used. This does not remove the need for initial owner setup.

Observed sequence:

1. The diagnostic Bot ran the unchanged evaluator and recorded failure evidence
   and a conditional lesson. The next task recalled and rechecked that lesson.
2. Lead compared alternatives, selected one configuration edit, and delegated
   mechanical implementation and an independent control-side source review.
3. Specialists returned their scoped change and evidence. Both recorded explicit
   memory-to-action usage, distinguishing diagnosis from implementation authority.
4. Lead's planning input became stale **twice** as specialist reflections arrived.
   The worker preserved generations 0 and 1, refreshed the memory packet and
   accepted generation 2. No parent recovery was needed.
5. Lead followed `inspect` overview sections to both reports, the candidate,
   assessment and saved action evidence. Three batched observations resolved the
   peer retrieval sequence; there were no failed pointer requests or action errors.
6. Lead integrated the specialist candidate and ran the unchanged evaluator on
   the combined state: exit zero, all four numeric predicates true. Five
   reflections completed. Ledger verification covered 1,285 events; replay matched.

The final assessment still says `needs_review`: formal requirement linkage and
physical dependency mapping are missing in this deliberately small fixture.
Physical geometry, electrical behavior and hardware performance remain unverified.
There was no formal adoption. This validates the development/recovery path, not
physical correctness, robot completion or general autonomous engineering ability.

### Observed timing, not a controlled speedup experiment

| Observation | Previous run | Follow-up |
| --- | ---: | ---: |
| Elapsed diagnosis through final reflection | 489.4 s | 382.8 s |
| Parent hold-to-recovery interval | 119.2 s | 0 s |
| Automatic memory refreshes | 0 | 2 |
| Completed model calls | 30 | 29 |
| Failed peer pointer requests | 5 | 0 |

Follow-up diagnosis took 56.1 seconds and continuation 326.3 seconds. Summed model
call time was 505.7 seconds (parallel calls overlap), with 782,612 input tokens,
11,926 output tokens and 62,464 cached input tokens reported by the provider.
Setup/parent chat usage is excluded. The default model was unpinned and local
tests ran concurrently, so the elapsed reduction is **not a causal speedup claim**.
The concrete result is removal of the observed manual recovery and retrieval
failures in this run. Replanning still consumes model calls; memory coalescing and
more compact evidence retrieval need further measurements.

### Regression and disclosure

Local Python suite: 1,937 tests passed, 3 skipped; the final dedicated refresh
suite has 9 passing tests, including working-note updates, durable-pointer crashes
and full active-generation task recovery. Peer retrieval has 7 dedicated passing
tests including long reports, old receipts, stale-page hashes and access denial.
Node tests: 119 passed. Development-loop smoke and security baseline passed.
GitHub CI runs the final combined tree on Linux/macOS and Python 3.11/3.12.

Raw model journals, credentials, ledger and per-action evidence remain private.
The implementation and this sanitized report are public. The prior manually
recovered run remains documented above; it has not been relabeled a success.
