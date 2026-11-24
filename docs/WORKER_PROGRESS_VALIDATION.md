# What the Bot does after reading, saving, and asking for help

On 2026-11-25 we observed **zero accepted tasks across 48 ordinary starts**. A separate set of **48 prepared-state diagnostic runs also yielded zero accepted tasks**. A source-linked past lesson and an explicit receipt for unchanged edits were both available for testing. Neither increased completed work on this fixture. There are no matched successful durations from which to estimate a speedup.

## What ran

- Two separate local model families, Qwen2.5-1.5B-Instruct and Llama-3.2-1B-Instruct (4-bit), selected from permitted actions. Both used greedy single-letter choice with two predetermined option orderings. The models used fresh prompts and separate designer and manufacturing histories. The bridge projected role-relevant observations and dispatched typed actions to the ordinary Gantry Worker. This tests constrained decisions on small models. It does not measure a general coding agent.
- Three anonymous text fixtures tested whether the historic amber choice still applied, a new register required blue, or contradictory signatures required a peer report. Both conditions received the original historical incident. One condition also received the same fixed lesson originally produced from it. The original lesson ends mid-sentence. No lesson was rewritten during the comparison. This measures exposure to this lesson, including its defects.
- Each model saw all three cases under both memory conditions and both edit-feedback conditions, with two option orderings. Each arm got a new ledger clone, fresh Worker journals and independent prompts. Arm order was shuffled with seed 9091. The two rotations test sensitivity to option order. Their deterministic outputs are not independent samples of real customer projects.
- Old-feedback prompts showed the saved content digest. New-feedback prompts also showed whether content changed and the recorded verification status from the matching state. Both arms used the same patched Worker. The comparison isolates information shown to the model. It does not measure filesystem I/O savings or the cost of running reflection. A check receipt and a formally registered state evaluation have separate meanings.
- Completion required a completed report, matching final file bytes and a successful sandboxed check on that exact final state. A conflicting register also required a peer to inspect the effective source, report it, and the requester to inspect and resolve that exact report with evidence. The checker compared actual file contents. Its scope was this fixture alone.
- One separately scripted smoke run exercised consultation, inspection, resolution, editing, checking and submission. The scorer rejected a different state, a wrong digest, and a removed peer inspection. The scripted success is excluded from all results.

## Frozen comparison

The Worker, bridge, rubric and allocation were frozen at 0f99eca. Each ordinary cell below contains six tasks (three cases, two orderings). Timings measure dispatch through independent scoring, including the Worker pair, consultation when used, check execution and state recording. They are elapsed times **to termination**, including failures.

| Model | Historical input | Explicit edit feedback | Accepted | Duplicate saves | Check calls | Median seconds to termination |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| Qwen | Raw | Off | 0/6 | 0 | 0 | 1.49 |
| Qwen | Raw | On | 0/6 | 0 | 0 | 1.47 |
| Qwen | Raw + lesson | Off | 0/6 | 5 | 0 | 1.85 |
| Qwen | Raw + lesson | On | 0/6 | 5 | 0 | 1.86 |
| Llama | Raw | Off | 0/6 | 0 | 12 | 1.50 |
| Llama | Raw | On | 0/6 | 0 | 12 | 1.50 |
| Llama | Raw + lesson | Off | 0/6 | 0 | 0 | 1.57 |
| Llama | Raw + lesson | On | 0/6 | 0 | 0 | 1.58 |

The designer chose the register lookup 276 times in 374 decisions. Of those, 230 retrieved the same pointer again on the same state in the same task. Qwen saved the wrong amber guide 12 times across two superseded-register runs; ten saves repeated existing content. It made five duplicate saves in each feedback condition. Llama made zero edits. Its two early completed reports had no matching file and check. The other 46 ordinary tasks exhausted the eight-choice cap. Twenty tasks involved a peer. None of the sixteen conflicting-register runs completed the required evidence chain. These are observable choices. The experiment does not identify a single cause inside either model.

## Prepared-state diagnostic

After observing repeated reads in the first cohort, we registered this separate diagnostic at 770144d. On two new cases a scripted prefix looked up the source, saved amber, and saved amber again. One register required amber and one required blue. On a third new case the prefix looked up conflicting signatures and asked manufacturing. All subsequent decisions (including all peer answers) came from the model. Arm allocation, acceptance and the eight remaining discretionary designer choices matched the first experiment. Setup prefixes are labeled in the journals.

| Initial position | Trials | Correct final file | Passed check on final state (tasks) | Accepted |
| --- | ---: | ---: | ---: | ---: |
| Saved amber; current register calls for amber | 16 | 16 | 3 | 0 |
| Saved amber; current register calls for blue | 16 | 0 | 0 | 0 |
| Conflicting signatures; question already opened | 16 | 0 | 0 | 0 |

All 48 diagnostic tasks exhausted their decision cap. Twelve passing tool receipts came from just three tasks with an already correct file. Those tasks did not submit successfully. None of the 16 stale-guide tasks edited the saved file. On the 16 pre-opened consultations, eight peers inspected the correct release, four requesters inspected a report naming the correct release, and four consultations were resolved with a citation. No single run joined all three steps with a completed peer report and subsequent successful development. A source inspection can occur even when the peer ultimately fails.

Across models, ordinary runs took 78.65 seconds in total and prepared runs took 90.32 seconds. Model loads took 1.02–1.38 seconds per cohort and common fixture preparation took 0.12–0.14 seconds. These setup times and per-arm fixture cloning are outside dispatch-to-score time. Routine Worker overhead is inside it. The CSV includes elapsed and model decision time per run. The remainder includes I/O, processes, scoring and runtime housekeeping; it is not a measure of idle time.

## Intervention and next test

The experimenter supplied the anonymous project, the archived lesson, role permissions, action menus, rubric, trial allocation and software revision. In the prepared cohort the experimenter also specified the prefix. No human intervention, model-answer replacement, forced requester submission, or crash recovery occurred after dispatch. Both models ran locally without a paid inference API. No robot or native CAD application was used.

The highest-priority follow-up is the transition from evidence to action. Supply each role with the evidence it already obtained on the exact input state and the work still outstanding under the assigned completion conditions. Keep a legitimate re-read available after a state change. For an unchanged state, test whether the model can use the current signed value, change the file, validate it, and submit once. For consultations, test whether the receiving Bot applies the peer's exact evidence to the pending decision. Compare the same decision projection with a stronger tool-using model; count working submissions and unsuccessful stops separately. No comparison in this study tests the benefit of training model weights or weeks of personalized use.

## Reproduction

The per-run anonymous metrics are in [worker-progress-study.csv](evidence/worker-progress-study.csv). Full Worker journals and inference transcripts stay local. Model revisions and the original acceptance protocol are in [the study plan](../tasks/worker-progress-study.md).

Use a source checkout on an Apple Silicon Mac with MLX-LM 0.32.2, MLX 0.32.4, Transformers 5.24.0 and Python 3.12.15. Install both pinned model snapshots in local directories. Set QWEN and LLAMA to their paths and STUDY to a new private directory outside the checkout. The shell below selects the new output path once in each invocation.

```sh
export HF_HUB_OFFLINE=1
python examples/worker_progress_trial.py --smoke --output "$STUDY/smoke"
python examples/worker_progress_trial.py --model "$QWEN" --output "$STUDY/qwen"
python examples/worker_progress_trial.py --model "$LLAMA" --output "$STUDY/llama"
python examples/worker_progress_trial.py --prepared-start --model "$QWEN" --output "$STUDY/qwen-prepared"
python examples/worker_progress_trial.py --prepared-start --model "$LLAMA" --output "$STUDY/llama-prepared"
python examples/summarize_worker_progress.py "$STUDY" > "$STUDY/metrics.csv"
```

The full integration includes the exact peer-report handle from PR #43 on top of the personal guidance branch in PR #46. Neither branch needs to be merged to reproduce the study from this checkout.
