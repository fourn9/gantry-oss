# Carrying an observed value through a Bot handoff

## What changed

A reporting Bot can publish the value from its own read by reference. Core verifies the read against the immutable artifact before storing the report. The designer still consults, reads and cites the peer when required. A matching or reviewed value supplies the exact bytes for the owner-declared candidate file. The Worker rejects a conflicting manual edit or replacement of that file.

The designer may attach a conditional submission to the installed check. The report and its limitations are chosen before the run. A successful check triggers a separate, journaled finish. The Worker rechecks the current candidate, check and review state. Core rechecks the task, attempt, discussion version, input revision, receipt and authorized report in the transaction that completes the task. A failed or stale check invalidates the conditional submission. The submitted change remains subject to existing review and adoption rules.

## Measurement

The first implementation was frozen at `81301b3`. On the six regression fixtures it improved acceptance from 30 to 47 of 48 with zero incorrect reports or writes in the new arm. The remaining requester repeatedly ran a release check on the initial pending file. Before examining the held-out outcomes we separated the readiness condition for release checking from deliberate baseline diagnostics. We froze the resulting implementation at `2357f40` and reran both arms and both cohorts. A diagnostic cannot authorize submission; its purpose and result are retained. That revision still produced 47/48 on the regression cohort: the remaining requester obtained a passing check but kept choosing standalone checks. At `ae97731` we added an explicit edit → check → submit instruction and reran both arms on the regression fixtures and a new transfer set. Each step is still a separate ledger operation. Selecting an edit alone or a diagnostic remains possible. The comparison arm is the previous conditional consultation guide, including its existing check and resolution gates. Both arms use the same model weights, checker, evidence, authority, lesson condition, action-order variant and starting snapshot. Each trial uses an isolated ledger and fresh model prompts. Qwen2.5-1.5B and Llama-3.2-1B ran offline through MLX. Bots use constrained choices and can expand a focused recommendation to the alternatives provided for that stage. The study's bridge supplies a small action menu; a general code-writing agent may make different choices. In the bound arm, a model chooses whether to use a reference operation. Gantry supplies its literal arguments from verified evidence. A conditional finish runs deterministically on the Bot's recorded instruction.

Six regression fixtures reproduce the previous two-value task. Six initial held-out fixtures used teal, white and violet. The final transfer fixtures use left, center and right, including a conflicted release matching neither cited value and two incomplete pairs. Each inference prompt receives only the role's evidence. The grading label is used by the scorer and checker. Each cohort comprises two models × six fixtures × two lesson settings × two menu orders × two arms. A separate diagnostic fixture was used to test and revise the choice interface. Its runs are excluded.

The acceptance criterion is unchanged: a correct candidate, a passed check on its final state, and a submitted report. Disagreement or missing evidence additionally requires a real peer read, inspection of the correct linked report and a cited resolution. The requester has eight operations including waiting and conditional submission; the peer has four separate operations. The trial exporter reconciles counts against ledger receipts. Only the administrative budget-exhaustion marker is excluded. Timing covers assignment through terminal return; loading the local models and cloning the test ledgers are setup. The parent prepared the fixtures, implementation and scorer. It supplied no answers and made no recovery interventions in measured trials.

## Final results at `ae97731`

| Fixtures | Previous valid submissions | Updated valid submissions | Previously failed pairs recovered | Previously successful pairs lost |
| --- | ---: | ---: | ---: | ---: |
| Original six | 30/48 | 46/48 | 16 | 0 |
| New six | 29/48 | 48/48 | 19 | 0 |
| Both cohorts | 59/96 | 94/96 | 35 | 0 |

All 32 updated trials with agreeing records proceeded without a question. In all 64 trials with conflicting or incomplete evidence, the peer read the authoritative field and the requester inspected and cited the correct report. Sixty-two of those 64 reached submission. Across the two cohorts the previous arm logged 20 incorrect reports and 49 wrong write operations. The updated arm logged zero of each. These are counts of actions, and a trial can include multiple writes. We additionally read the saved check receipts for all 153 accepted submissions across both arms. Each included a successful, non-diagnostic `release_check` with an output artifact and check definition on the submitted state.

The two updated failures were Qwen on the same regression fixture with the lesson enabled and opposite menu orders. Both resolved the conflict correctly, saved the right value, and passed the check. One used its remaining operations to rerun the passed check twice. The other reread the register twice before its edit and reached its eighth operation at the passing check. Both had chosen standalone actions. Neither had given the Worker a conditional submission instruction. Both counted as failures. The procedure was frozen before collecting the final transfer data.

In the updated arm 92 checks and 94 submissions used a Bot's conditional instruction. All 62 accepted consultations used seven requester operations and two peer operations; if the budget were eight combined, only the 32 agreement submissions would fit. No parent intervention occurred in any of the 192 final trials. The parent implemented the feature, set up the scorer and fixed defects between measurement rounds.

Among the 59 pairs accepted by both arms, median elapsed task time by arm was 2.01 s before and 1.33 s after. These times cover local bounded category decisions, file writes, checks and submission. The experiment measures this handoff on twelve fixture definitions. It does not measure open-ended CAD design, engineering judgment, or general development speed.

[Per-trial metrics for all three development rounds](evidence/worker-literal-validation.csv). Select the `ae97731` commit prefix for the 192 final trials. `routed` denotes the previous policy and `bound` the new policy.

## Reproduction

From a source checkout, use an environment with the OS sandbox and the two pinned local MLX model directories documented in [the previous comparison](WORKER_CONSULTATION_VALIDATION.md). Use fresh private output directories outside the checkout. Run the cohorts and models sequentially.

```sh
export HF_HUB_OFFLINE=1
for cohort in regression transfer; do
  python examples/worker_consultation_trial.py --handoff "$cohort" --model "$QWEN_MODEL" --output "$RESULTS/$cohort-qwen"
  python examples/worker_consultation_trial.py --handoff "$cohort" --model "$LLAMA_MODEL" --output "$RESULTS/$cohort-llama"
  python examples/summarize_worker_consultation.py "$RESULTS/$cohort-qwen" "$RESULTS/$cohort-llama"
done
```
