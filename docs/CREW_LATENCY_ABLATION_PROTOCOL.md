# Gantry latency ablation protocol

This opt-in experiment compares Gantry to itself. It does not infer causes from
one files/logs versus Gantry comparison. The protocol is frozen before real model
calls; no parameter case is tuned using model results.

Four new parameter cases use the same native STEP generation, immutable evaluator,
software filter and five acceptance predicates as the existing engineering
comparison. Each case's exact bytes are shared across four **independent** Core
ledgers, workspaces and model contexts. Case parameters change initial position,
command and calibration; this is one narrow task family, not four robot domains.

Conditions:

- `baseline`: current Gantry context and normal actions.
- `plan_tool`: an opt-in combined model response for verification intent and
  approved execution. The runtime retains ordinary durable plan, tool and evidence
  receipts, and stops when planning is unexecutable. It does not weaken acceptance.
- `compact_schema`: description-only compression of the action guide, retaining
  all exact action schemas and capabilities. Despite the short condition name,
  this does **not** test removing or dynamically loading tool schemas.
- `compact_context`: replaces repeated identical structured subtrees with explicit
  local reference pointers. Unique data remain available, and reconstruction must
  recover the original input. This does not summarize away failed checks.

Only one treatment is enabled per run. The 4x4 cyclic Latin-square schedule rotates
condition order across cases; every condition occupies every within-case position
once. It balances position, not all carryover/provider effects. All 16 runs execute
serially to avoid local resource contention. No answers or journals cross runs.
Each model call is ephemeral and uses the same explicitly selected model and low
reasoning. `CLI_DEFAULT`, if deliberately chosen, means an unpinned default and
must be reported as such, never silently substituted for an unsupported model.

Prepare with no inference:

```sh
PYTHONPATH=. python examples/engineering-crew/ablation.py --prepare-only --model SUPPORTED_MODEL --output /private/new-protocol
```

After tests/review and implementation freeze, execute the schedule:

```sh
PYTHONPATH=. python examples/engineering-crew/ablation.py --prepared /private/new-protocol --output /private/new-results
```

An optional `--index 0` executes only one predetermined row in a fresh directory.
Do not discard failures or repeatedly rerun a row until it passes. Any implementation
change invalidates the frozen protocol; archive the failed attempt and prepare a
new protocol before restarting the complete comparison. A provider/login failure
stops further attempts and is retained. These are private outputs containing local
credentials and model journals; do not commit or publish them.

The harness verifies fixture hashes, acceptance, executable/packages/sandbox/CLI,
Gantry implementation hash and experiment source hashes before each row. Core
setup is timed separately. The main clock includes context transforms, inference,
file edits, approved tools, ledger recording, restoration and final audit. The
independent final audit runs only the fixed verifier: it cannot rebuild or repair
CAD for the model. Acceptance requires successful linked real tool receipts and
fresh matching inputs/report, not a passing text statement. No formal adoption.

Saved observations include wall and model time, tool time, residual harness time,
request section sizes before/after transformation, token usage, read/retrieval
counts, actions/errors, immutable acceptance and evidence validity. Failures and
timeouts remain samples. The same 1,800-second observation ceiling applies to each
row. Host sleep and remote provider wait are not separately observable; no
intentional sleeps occur. Preparation/development human labor and subscription
per-call monetary cost are not measured.

Interpretation: compare each treatment with baseline **within each case**, then
report all paired differences, medians, acceptance/error counts and payload/turn
changes. Four observations per condition remain preliminary. A treatment unused
by the model is not evidence that its mechanism saves time. A reduced payload may
increase retrieval or failure; report that tradeoff. A faster failed run is not a
successful speedup. Do not generalize these tasks to memory learning, multi-Bot
coordination, native commercial CAD or physical robot correctness.
