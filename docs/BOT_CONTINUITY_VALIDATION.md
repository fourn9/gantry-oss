# Personal Bot continuity: validation

Recorded 2026-11-03. This extends the existing learning implementation with
persistent working context, experience/action links and selective continuation.
It does not establish model-weight learning, consistently better decisions,
engineering speedup or equivalence to another personal-agent product.

## Verified paths

| Path | Evidence | Limits |
| --- | --- | --- |
| Fresh task reads prior commitments and canonical state | Core/worker regression; real subscription model received the prior note | Working notes are Bot hypotheses, not new design requirements |
| Private notes and memory remain private in peer receipt views | Direct and nested `records`/`inspect` regression | A Bot can intentionally disclose information in a shared report |
| Recalled experience links to actual action receipts | Deterministic iterative worker test, same-attempt checks, forged-reference rejection | Reported influence is not proof that memory caused success |
| Conditional ordered procedures and corrections | Iterative worker regression; real reflection saved a procedure | Corrections preserve historical lessons; quality still requires evaluation |
| Relevant change or due time wakes the responsible Bot | Watched-path/task and due regressions; real due-time wake | Only configured watch conditions; worker must be running |
| No new signal produces no model call | Restart regression and real idle poll | Does not measure large-scale polling cost |
| Revocation reaches descendants | Queued/running task and consultation regressions | It prevents subsequent authorized actions, not reversal of an external effect |
| Reflection failure does not silently retry or block unrelated work | Failure/recovery regression; real invalid-response hold and recovery | Detailed provider receipts remain in the private local journal |
| Existing interfaces and storage remain compatible | Full regression, replay, schema and wheel checks | Live commercial CAD and cloud deployment are outside this exercise |

## Regression and review

The integrated suite ran **865 tests in 102.430 seconds: no failures, 8 skips**.
The count includes inherited unittest cases; it is not a count of distinct new
scenarios. A subsequent focused run passed **182 tests in 19.169 seconds**,
including nested receipt privacy and rejection of unrelated output artifacts
after the final review. See `tests/test_bot_continuity.py`
and `tests/test_bot_learning.py` for reproducible cases.

```sh
PYTHONPATH=tests python -m unittest test_bot_continuity test_bot_learning -q
python -m unittest discover -s tests -q
python -m pip wheel . --no-deps --no-build-isolation --wheel-dir /tmp/gantry-wheels
```

The exported 202-command API schema matched the command registry. The `bot`
capability profile includes the new working-state/experience operations; it does
not grant owner-only standing-delegation configuration. The package includes the
new modules and no runtime journals, credentials or private projects.

An independent read-only code review found two defects before completion:
standing-authority revocation did not reach descendant work, and nested action
receipt views could expose private context. Both were fixed and regression-tested.
The workflow followed the repository's reviewed Addy Osmani skills revision.

## Real subscription-model exercise

This used the existing customer ChatGPT login through `codex_subscription` with
no API-key fallback. A new anonymous local fixture supplied two saved text inputs
and an installed Python interface-agreement check. Initial history and delegation
were synthetic setup; subsequent model responses and tool execution were real.
No commercial CAD, physical simulation or private project was used. The CLI's
configured model was not explicitly pinned, so this is a functional smoke test,
not a reproducible model-quality benchmark.

The successful main path was:

1. Owner standing delegation and an elapsed Bot-authored due time created a task.
2. The model read prior working context and conditional experience, and planned.
3. It chose and executed the installed tool. The real process returned exit 0 and
   `interface_values 1 1 equal True`.
4. It updated its commitments, remaining unknowns and watched dependencies.
5. It reported completion without edits or formal adoption. Physical behavior
   remained explicitly unverified.
6. Reflection produced a conditional ordered procedure and recorded limits.
7. An idle restart made no additional inference calls; ledger replay matched.

Two integration defects were exposed during this exercise. An earlier run cited
its saved learning plan, and the main run cited its saved tool-output artifact;
Core initially rejected those legitimate evidence references. Validation now
accepts the exact plan and output artifacts linked by same-attempt tool receipts
before the report. Unrelated artifacts are rejected. Evidence semantics still
separate planning intent, saved bytes, reported actions and physical validation.

After that correction, the main reflection was completed by reconciling its
**already saved model response**, with zero additional inference. This included
manual diagnosis and code repair; it was not an uninterrupted autonomous success.
The main run made five model calls over 89.708 seconds before the hold, reporting
84,938 input tokens and 1,869 output tokens. Receipt reconciliation took 0.014
seconds. Those timings exclude setup and the manual repair interval and must not
be presented as total development time or as a speedup.

The model did not claim that the remembered lesson caused the successful check:
the task already required that check. Consequently this live run has no
`experience_use` claim; that link path is separately covered by deterministic
tests. This distinction prevents a completed task from being counted as evidence
of learning efficacy.

## Initial follow-up hold

A fresh task was then started to reuse the newly saved procedure. Its frozen
planning input contained the current working note and recalled experience, but
the provider returned **HTTP 429 Too Many Requests** on the first call. The worker
returned `held` after 2.693 seconds, preserved its state/journal, and did not switch
to a paid provider. Replay still matched. There was no completed planning response
or subsequent tool execution for this follow-up.

At that point the next-task reuse path had deterministic Core/worker coverage,
but the second real-model cycle had not completed. The explicit follow-up below
advanced that same saved task rather than creating replacement history.

## Explicit real-model follow-up, 2026-11-03

Source revision: `cf40e035e81023ecd000c0645bc6e4390e4e0c27`.
CLI: `codex-cli 0.154.0`, existing ChatGPT subscription, CLI-default model.
No product code or model answers were changed for this follow-up.

An operator inspected the prior terminal 429, confirmed the process was stopped
and no completed response existed, archived the failed provider files, and used
the original fenced task recovery API. This was manual recovery preparation,
not an automatic retry policy. The saved task, planning input, ledger and previous
successful work were retained. Each model response used a fresh ephemeral CLI
context populated by Gantry.

Three real model responses then succeeded:

| Stage | Observed result |
| --- | --- |
| Plan from saved experience | The model selected `apply` for the previous real reflection's procedure because dependency hashes and acceptance matched. It rejected synthetic seed evidence and marked incompletely captured memories `recheck`. It explicitly said the old pass did not satisfy the new task's execution requirement. |
| Execute | The model chose `check_interface`; the sandboxed Python tool actually ran once, returned exit 0 and `interface_values 1 1 equal True`. |
| Persist ongoing work | The model updated the working note from version 4 to 5 with the new action/output references, remaining commitments, dependency watches and physical unknowns. |

The next action response failed with terminal HTTP 429. Two bounded, explicit
retries, including a 45-second pause before the last, also received 429. Prior
responses/effects were retained and the completed tool was **not executed again**.
There were six model invocation attempts in this follow-up: three successful
responses and three failures. Successful receipts reported 63,582 input tokens
and 1,000 output tokens; usage for failed requests was not available. No API-key
fallback or credit purchase was used. The desktop usage snapshot reported
ordinary usage allowed, so these errors do not establish that the entire
subscription allowance was exhausted.

The three harness runs took 56.714, 2.560 and 3.075 seconds, excluding manual
inspection and waiting. These are not full development elapsed time or a speed
comparison. Inspection of the final ledger confirmed:

- Task remains `held`; there is no final completion report for this task.
- Exactly one tool action and one working-state action were saved.
- The plan contains the chosen real procedure, but **no `experience_use` receipt**
  was committed before the hold. A plan-to-action causal benefit is not established.
- No new outcome reflection was created because reporting did not complete.
- Event replay matched. No source edits, integration or formal adoption occurred.

This demonstrates real-model retrieval, conditional procedure selection, actual
tool execution and cross-task working-context updates. It does **not** complete
the second report/reflection cycle. The prepared changed-input negative scenario
was not executed because the preceding cycle remained held. Its deterministic
test coverage remains separate from real-model evidence.

Remaining operational gap: known failed action/planning inference still required
manual provider-journal archival before the existing task recovery command could
make an explicit new request. Unknown effects remain protected against blind
retry, but a unified explicit recovery operation would make this less error-prone.
No unattended worker was left running. Resume from the preserved task and journals
when the subscription inference endpoint accepts requests; do not repeat completed
tool effects or replace failures with manufactured model responses.

Next assess held-out tasks with and without experience, changed-condition
rejection, repeated mistakes, independent correctness and full time/token cost.
The current evidence demonstrates persistence and execution plumbing, not that
the Bot gets smarter on every iteration.

Raw model journals, ledger exports and credentials are retained outside the
public source repository. This report intentionally contains only anonymous
observations and aggregate measurements. See [operation and recovery](BOT_CONTINUITY.md).
