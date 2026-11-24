# Using a prior observation to complete a checked change

In the final matched experiment the flat bridge completed **0 of 24** tasks and the guided bridge completed **14 of 24**. All 24 guided tasks saved the correct bytes and passed the checker on their final state. Ten reached the eight-decision limit after rechecking; their missing submission or peer evidence still counted as failure. There was no matched successful baseline duration.

## Results

| Cohort and bridge | Accepted | Correct final file | Passed check on final state (tasks) | Same-state register rereads | Identical saves | Model calls |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| First, flat | 0/24 | 0 | 0 | 122 | 5 | 203 |
| First, guided | 14/24 | 14 | 14 | 0 | 26 | 222 |
| Follow-up, flat | 0/24 | 0 | 0 | 123 | 5 | 203 |
| Follow-up, guided | 14/24 | 24 | 24 | 0 | 0 | 226 |

In the follow-up, Qwen completed 10/12 and Llama 4/12 with guidance. Raw history alone yielded 8/12 successes and raw history plus the recalled lesson yielded 6/12. This shows an improvement in the **execution workflow** on these fixtures. Learning or generating more useful memories was not established. The guided provider started 16 consultations in 16 cases with an unambiguous register (flat: 7/16). Four of eight conflicting-register cases completed the entire required peer chain and final submission (flat: 0/8). On one failed guided run the model read blue, asked for confirmation, read blue again in the peer report, initially saved amber, observed a failed check, changed to blue and passed the check on its eighth decision. Correcting this took the place of submitting. A peer's wrong recommendation can also leave the conflicting-source requirement unmet even after the file passes its check.

All 24 flat trials hit the decision limit in each cohort. Guided successes in the follow-up took a median 1.79 s from assignment to independent scoring (1.48–3.88 s). Since the matched flat trials never passed, this is not a time-saving estimate. The next target is deciding when a consultation adds evidence and using that evidence on the first edit, without bypassing required peer review when sources conflict.

[Anonymous metrics for all 96 matched runs](evidence/worker-evidence-guide.csv). Consultation counts in this report refer to designer tasks that actually ran a peer. The two development pilots for each model were excluded. For the earlier baseline and its separate diagnostics, see [the original report](WORKER_PROGRESS_VALIDATION.md).

## Product behavior

An optional role-level Worker guide connects a source inspection, an editable candidate, a peer answer and the latest check for the current saved state. Each Bot receives its own authorized view. The source scalar is shown after its inspection matches the current file bytes and JSON pointer. The guide retains an inspected peer report with its limitations and state. A name match alone cannot carry a successful check to a new version or a changed tool declaration. The tool result is advisory evidence; the assigned work, verification and adoption contracts retain their existing meanings.

The Worker suggests action kinds for the next decision. A customer choice-based provider may offer these first, alongside a way back to the full menu. It can supply the proposed whole-file digests for literal edits to the guided candidate. After a failed check this moves an identical write out of the short menu. Rereading, retrying and alternative actions remain available. There is no automatic color selection, assertion that text in a report is true, or automatic submission. The ordinary free-form provider receives suggestions in its context and continues to choose actions. See [role setup](CREW_SETUP.md) for configuration.

## Comparative method

We used two local, 4-bit models in the same authenticated Core, ordinary Worker, sandboxed checker and independent acceptance scorer as the [earlier progress study](WORKER_PROGRESS_VALIDATION.md). Each cohort ran three anonymous tasks on entirely new clones for each arm. Two action orderings, both lesson conditions, and both model families gave 24 flat and 24 guided starts per cohort. Raw incident history was present in both memory conditions. Historical inputs, tool results and guides stayed in separate designer and manufacturing contexts. The checker and peer release were not supplied to the designer as an answer key.

The baseline bridge used the full flat action menu. The guided bridge projected the Worker guide into a brief and offered relevant action kinds first. The model could reopen the full menu. Both arms could make eight discretionary designer decisions and four peer decisions. Each escape cost an additional measured model call. State-level checking, the file hash, an actual completion report, and exact evidenced peer consultation when sources conflicted were all required for acceptance. Runs that stopped without these conditions count as failures. Timings include dispatch, worker execution, checks and independent scoring. Initial model loading and copying the common fixture fall outside each timed interval.

- First comparison, frozen at f898c2d: source-to-candidate and peer-report guide, three cases × two lesson conditions × two orderings (12 trials per arm per model).
- Follow-up: after observing identical saves of a rejected candidate, we registered a new comparison including the opposite conflict outcome. The full guide demotes literal no-change edits after a failed check and pins the check tool declaration. The baseline is measured again on the same new cases. Different fixtures prevent attributing a difference between cohorts solely to demotion of repeated writes.
- Developer pilots and the previously scripted smoke case are excluded. The experimenter defined the role workflow, model bridge, choices, fixed acceptance and checking tool. No parent supplied a part value, intervened, recovered a run, or overrode a model decision after dispatch. These are constrained decisions in a text fixture, with no physical robot, native CAD or paid inference API. Rotating a deterministic menu tests order sensitivity, not generalization to independent customer projects.

## Reproduction

Use the same MLX environment and model pins as the earlier study. The following paths must be private and outside the checkout. To reproduce the first cohort exactly use f898c2d for its two runs. Use the follow-up revision listed in the per-run CSV for the retry cohort and export.

```sh
export HF_HUB_OFFLINE=1
python examples/worker_progress_trial.py --compare-guide --model "$QWEN" --output "$STUDY/qwen"
python examples/worker_progress_trial.py --compare-guide --model "$LLAMA" --output "$STUDY/llama"
python examples/worker_progress_trial.py --compare-retry --model "$QWEN" --output "$STUDY/qwen-retry"
python examples/worker_progress_trial.py --compare-retry --model "$LLAMA" --output "$STUDY/llama-retry"
python examples/summarize_worker_progress.py --guides "$STUDY" > "$STUDY/metrics.csv"
```
