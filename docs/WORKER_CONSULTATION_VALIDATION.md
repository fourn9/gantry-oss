# Revising a saved candidate with conditional peer consultation

This study compares the retry-aware evidence guide at `ab9e5d6` with conditional routing frozen at `0400e09`. The baseline uses the same study runner, signed records, consultation instructions, two-role workflow, feedback and no-op handling. The intervention adds a configured comparison of two saved fields to the provider input, focuses the action menu and checks the resulting evidence before accepting a completion. The study measures that combined intervention.

## Task and protocol

A designer selects one of two fixture guides, saves the file, runs a real local checker and submits. Manufacturing owns the effective release. Six anonymous fixtures cover agreement, disagreement and a missing signed entry; each condition contains one blue and one amber release. Both arms can look up the register, and the peer can look up the effective release. Neither decision prompt includes the fixture's grading label. For each fixture, local model and arm we run two menu orders with the same frozen lesson on and off. Each starts from an independent ledger clone and empty inference history. A deterministic seed shuffles arm order. Within a model every matched pair starts from the same saved state; the two model cohorts initialize independently with the same fixture contents.

The primary metric is the number of accepted submissions. Acceptance requires the correct candidate digest, completed task and a passing checker on the submitted state. Conflict and missing evidence additionally require a peer read of the actual release, an inspection of the correct linked report, and resolution citing the recorded answer. Both arms have eight requester operations **including the waiting handoff and submission**, and four separate peer choices. A terminal budget-exhaustion receipt records failure. The two roles use the same local model and separate prompts, role credentials, Worker invocations and ledger receipts. The bridge ranks action labels by first-token logits. A return to the full menu can therefore make two inference calls for one operation.

The parent prepared the fixture, installed the policy and scorer, and started each cohort. The runner cloned ledgers, woke the peer when needed and returned control. No human or parent picked actions, repaired files or restarted individual measured trials. The separate scripted diagnostic is excluded.

## Observed results

| Evidence | Prior accepted | Routed accepted | Tasks asking a peer, prior → routed | Correct peer evidence chain, prior → routed |
| --- | ---: | ---: | ---: | ---: |
| Two matching entries | 12/16 | 16/16 | 8 → 0 | Optional |
| Conflicting entries | 4/16 | 8/16 | 10 → 16 | 6 → 12 |
| Missing entry | 4/16 | 6/16 | 10 → 16 | 6 → 12 |
| **All** | **20/48** | **30/48** | **28 → 32** | **12/32 → 24/32 on required cases** |

Qwen improved from 8/24 to 16/24; Llama from 12/24 to 14/24. Twelve matched tasks gained acceptance, two lost it, eighteen passed in both arms, and sixteen failed in both. In the prior arm twelve submitted tasks lacked mandatory peer evidence and sixteen failed before submitting. All thirty routed submissions met the independent acceptance criteria. Eighteen routed tasks exhausted the operation limit. All forty-eight routed candidates had the correct file and a successful final-state check, including the eighteen failures.

On the 32 required cases the routed peer read the release and the requester inspected and cited the peer report. The report matched that release in 24 cases. Eight Llama peer reports said blue after reading amber. In another eight cases the peer answered correctly but the requester first saved the opposite value, then spent its remaining operations correcting and rechecking it. In the final two failures it had valid evidence and a passing check but chose redundant reads or writes instead of submission. These observations identify where the operation limit was spent. A cited completed report proves that a consultation occurred; it cannot certify that natural-language advice correctly reflects the underlying evidence.

Counting both roles against **one** eight-operation budget changes how the same receipts are interpreted. Eight prior submissions and sixteen routed submissions completed within eight combined actions, all on agreement cases. All fourteen accepted routed consultations used nine combined actions: the requester asked, waited, inspected, cited, edited, checked and submitted (seven), and the peer read and reported (two). This is a secondary count from the same logs, not a separate run permitting a different strategy.

The 48 task windows totaled 82.69 s before and 82.98 s after. Across the 18 doubly successful pairs, median completion times were 1.71 s and 1.48 s respectively. Model calls fell from 348 to 338. The primary improvement was more valid submissions under the operation cap. These are constrained local file decisions on six fixtures; model/order/lesson variants are repeated measurements. The data do not establish faster general engineering or CAD development.

[Anonymous metrics for all 96 trials](evidence/worker-consultation.csv)

## Reproduction

Use a source checkout with a supported OS sandbox, two downloaded MLX model directories and an environment containing `mlx==0.32.4` and `mlx-lm==0.32.2`. Run the models sequentially. The command requires fresh result directories outside the checkout.

```sh
export HF_HUB_OFFLINE=1
python examples/worker_consultation_trial.py --model "$QWEN_MODEL" --output "$RESULTS/qwen"
python examples/worker_consultation_trial.py --model "$LLAMA_MODEL" --output "$RESULTS/llama"
python examples/summarize_worker_consultation.py "$RESULTS/qwen" "$RESULTS/llama"
```

Model revisions: `mlx-community/Qwen2.5-1.5B-Instruct-4bit@8b403126fc14f14cfc99bb4cfa72ecbc129ea677` and `mlx-community/Llama-3.2-1B-Instruct-4bit@08231374eeacb049a0eade7922910865b8fce912`. Inference ran offline on an Apple M4 Pro. Private run folders contain the individual ledgers, prompts, model outputs, action receipts and elapsed times. The public CSV contains anonymous metrics.

Local regression checks covered 2,034 Python tests (19 skipped, zero failures) and 127 JavaScript tests (zero failures). A separate normal Worker regression attempted submission with a passing tool and missing peer evidence, observed the rejection and recorded a blocked outcome.
