# Evaluate whether prior experience helps

`gantry-crew evaluate-learning` runs the same selected task in two fresh Core
ledgers and Bot contexts: prior experience withheld, and prior experience supplied.
Both use the normal Bot planning, iterative editing/tools and reflection path.
This isolates access to experience; it is **not** Gantry versus no Gantry.
See [the initial real-model smoke results](BOT_LEARNING_EVALUATION_VALIDATION.md).

Use an operator-authored case like
[`examples/learning-comparison/case.json`](../examples/learning-comparison/case.json).
It explicitly selects native files, writable files, a goal, acceptance criteria,
a read-only Python verifier, and prior notes with sources and limitations.
Cases are trusted executable configuration. Do not execute a case received in an
Issue/PR without reviewing its verifier and selected files. Credential-like files
and content are refused. This filter is not a guarantee that source contains no
confidential information; select only inputs you intend to send to your model.

```sh
gantry-crew evaluate-learning \
  --case examples/learning-comparison/case.json \
  --output /new/private/comparison \
  --model YOUR_SUPPORTED_CODEX_MODEL --reasoning-effort low \
  --max-calls 12 --seconds 600 --repetitions 2 --seed 42 --live-codex
gantry-crew learning-evaluation-report /new/private/comparison
```

`--live-codex` sends the selected project and experience to official Codex using
your ChatGPT login. It does not use an API key, start a paid fallback, or purchase
capacity. Provider subscription limits still apply. Experimental call and time
limits are explicit per-arm limits, not new global product caps. Calls include
planning and reflection. A rate limit or uncertain invocation is held without
automatic retries. Use a new output directory for a new experiment.

The verifier runs in the existing supported OS sandbox (macOS seatbelt or Linux
bubblewrap), without network or host-execution fallback. Only a Python verifier
is currently supported. This does not install CAD/CAE tools or prove physical
correctness. The supplied two-configuration example is a **synthetic smoke test**,
not a benchmark of robot development or automatically acquired learning.

## What is held fixed

Source bytes, write scope, acceptance, verifier, requested model/effort, Python
runtime, package-version inventory, CLI version, implementation hash and per-arm
limits are frozen before execution. Each arm starts with independent identities,
ledger, files and journals; no answers or newly created experience cross arms.
Run order starts from a seeded choice and alternates across pairs. Provider
infrastructure, caching and model stochasticity cannot be completely controlled.
Keep other workloads quiet and use several held-out cases before drawing conclusions.

Imported experience is a declared hypothesis with its source and limitations,
not fabricated proof of a previous successful execution. Incomplete applicability
stays subject to recheck. No experience is promoted to permissions or requirements.
Each arm may learn during its own task, but that new experience is discarded from
other arms. The existing project and its ledger are never updated.

## Results and limits

`report.json` and `report.md` keep every planned trial, including failed, held,
timeout, pending and interrupted cases. Successful completion requires a completed
Bot task, completed reflection, and an independent frozen verifier pass within the
time limit. The Bot's completion claim alone is insufficient. Each captured
candidate and the final state are submitted for checking in separate scratch
workspaces while time remains. Interruption or timeout can leave checks incomplete;
those trials do not count as accepted. A
pre-satisfied baseline is reported separately and does not generate a time ratio.

Primary elapsed time includes baseline checking, planning, editing/tools, Core
recording, independent verification, final report processing and reflection. Setup
cost is reported separately. Time ratios use only matched accepted/accepted pairs;
failures remain in overall success rates. An unstarted or hard-killed running row
remains incomplete when regenerating the report. This command does not blindly
resume an uncertain model/tool invocation.

Auxiliary data includes inference durations, known token usage, action order,
failed tool checks, repeated identical tool checks, and verification receipts.
Repeated identical checks are not automatically labelled waste. Unknown usage,
per-call money and human intervention time remain unknown. A small comparison
cannot establish statistical significance or general speedup. Task/verifier quality
and the representativeness of selected experience remain the operator's responsibility.

The output is a private directory containing credentials, native files, model
inputs/outputs and separate ledgers. Do not publish it or upload it as telemetry.
Source execution, file capture and checkpoint evidence are retained for audit.
There is no result-directory or telemetry upload, weight training, lesson promotion,
or design adoption. Selected model inputs are sent only through the opted-in Codex path.
