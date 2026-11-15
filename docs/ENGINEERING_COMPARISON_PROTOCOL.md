# Held-out engineering-loop comparison

`examples/engineering-crew/compare.py` is an opt-in experiment harness, not a
published speedup result. It uses real native STEP geometry, the same executable
software filter and the official monthly Codex login adapter. It does not mock
model responses, fabricate tool receipts or accept model-generated shell commands.

## Conditions

- **A — files and logs:** an independent action loop with read, edit, installed
  tool and finish actions. It keeps ordinary workspace files and JSON action
  logs. No Gantry service/ledger is created or consulted in the measured loop.
  The bridge reuses Gantry's safe file helpers and sandbox for equal tool access.
- **B — Gantry:** one fresh BotWorker and isolated Core ledger. The Bot can use
  the existing Core context, engineering evidence, planning and action paths.
  No Mentor, additional Bots, prior memory, personal continuity or learning
  reflection is enabled. This isolates a small ledger/action-harness treatment;
  it does not measure team coordination or experience-learning benefits.

Both use `infer_monthly(model=None, reasoning_effort='low')`, the same installed
Python, CAD kernel, approved `build`/`verify` recipes, sandbox and accessible
starting files. Native Codex tools stay disabled. Each inference is ephemeral
and receives only its arm's context and history. Do not copy the other arm's
answers, files or journals into its output directory or prompt.

The held-out input parameters differ from the earlier demonstration. The initial
carrier position is -4 mm, command is 0 mm and calibration offset is -3 mm.
Actual build and verify tools create the initial STEP/report files before the
clock starts. The baseline is expected to fail; no passing solution is supplied.
These parameters must not be used for tuning before the actual comparison.
`--prepare-only` checks setup and produces no model answer or development result.

## Frozen acceptance

The same read-only plan requires nominal clearance >= 1 mm, overlap <= 0.001 mm³,
carrier x in [11,20] mm, CAD/source error <= 0.01 mm and final software-filter
position error <= 0.01 mm. The evaluator, controller implementation, calibration,
plan and scripts are hashed before inference. The acceptance hash includes these
immutable sources and must match between arms. Environment/package/code hashes
and the CLI version are retained with each run. Generate one `--prepare-only`
fixture and give both arms its `--fixture` directory. This reuses the exact initial
STEP/report bytes, avoiding serializer timestamp differences. The loader checks
file hashes, unchanged scripts, held-out parameters, plan, acceptance and runtime.
It reads no source-run journals or model answers. Compare `fixture_manifest_hash`
as well as `acceptance_hash` before interpreting results.

The final audit **only runs verify** on a copy of the submitted saved files. It
does not rebuild CAD, choose design values, rewrite sources or repair missing
outputs. It checks immutable hashes, submitted report input hashes, the actual
tool provenance and fresh independent measurements. B also requires the linked
check to be effectively passing on its selected output state. Sharing, completion
and a model's success statement do not count as acceptance. Neither arm can claim
physical safety, dynamic performance or formal adoption from this experiment.

## Running

Run from the source root with an environment that has Gantry and its native CAD
kernel installed. Outputs must be **new private directories outside the source
repository**. B's output includes local ledger credentials; never publish these
directories. Use an existing monthly ChatGPT login; there is no API-key fallback.

```sh
PYTHONPATH=. python examples/engineering-crew/compare.py --condition A --output /private/path/fixture --prepare-only
PYTHONPATH=. python examples/engineering-crew/compare.py --condition A --fixture /private/path/fixture --output /private/path/run-A
PYTHONPATH=. python examples/engineering-crew/compare.py --condition B --fixture /private/path/fixture --output /private/path/run-B
```

Use `--prepare-only` for a no-model setup check in separate disposable output
directories. A prepared directory may supply frozen bytes through `--fixture`,
but is never reused as a measured output directory. Record the
run order; run serially on the same machine without competing experiments. If
either arm needs a harness correction, preserve the failed result, freeze the
correction and restart both arms independently before making a comparison.

## Time, usage and failures

Setup is reported separately: shared baseline generation is recorded once and
each arm's fixture-copy/Core initialization cost is recorded per arm. The measured window starts immediately before the
action loop and includes context preparation, inference, editing, tools,
recording, final state retrieval and independent verification. Both receive the
same 1,800-second observation ceiling. Checks before inference/Core actions and
during sandbox execution enforce it; an in-flight model call is bounded by the
remaining window. This is not an OS-wide hard process supervisor.

`timeline.jsonl`, `model-calls.json`, `actions.json`, private provider journals and
`result.json` preserve timestamps, attempts, errors and outcomes. Metrics include
total wall/monotonic time, model-call time, tool time, remaining harness/recording/
restore/wait time, token usage when actually reported, tool/action counts and
child-process CPU observations. The remaining category is a residual, not a
measurement of waiting alone. There is no deliberate polling sleep in this
single-task experiment. Host suspension and provider wait are unknown; model
duration is not model thinking time. Subscription cost is not reported per call
and is left unknown. Token totals distinguish observed from complete counts.

Parent intervention during each run is zero by construction of the harness:
it provides the frozen task and tools and never supplies intermediate answers.
Any operator modification invalidates that claim and must be recorded separately.
Harness setup/development labor is not measured automatically. Failures, held
tasks, provider errors and timeouts stay in the report; they are not discarded or
silently restarted. A timeout is not a successful sample with a slower time.

## Interpretation limits

One parameter case per arm is a preliminary functional observation. B's larger
action menu and Core-generated context differ from A's file/log prompt. The
accessible engineering data are matched, not the literal prompts. `model=None`
uses the CLI default, so resolved-model identity cannot be guaranteed from that
setting alone. The remote provider may also vary across calls. These differences,
run order, stochastic inference and n=1 preclude a causal speedup estimate.

Report each arm's acceptance, elapsed time and failures first. Only if both meet
the fixed criteria is a descriptive wall-time ratio meaningful; it still cannot
be generalized to robot development, cross-team coordination or learning.

## Harness validation status

Both `--prepare-only` paths were exercised with actual sandboxed native CAD
build/verify tools. A second B preparation reused the shared fixture and matched
all initial file hashes and acceptance hashes. A native audit check changed only
the CAD source position and confirmed that final verification rejected the stale
STEP without rebuilding it; changing the frozen evaluator was also rejected.
No model was invoked during harness implementation. The experiment result remains
unmeasured until the opt-in runs are completed.
