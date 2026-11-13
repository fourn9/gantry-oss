# Local engineering workflow

This path joins existing Core state, external captures, saved files, physical
evidence and Mentor review. It does not replace Crew or start an agent service.
Use `gantry-engineering` (or `python -m gantry.engineering_cli`). All Core operations
use the existing authenticated commands and permissions. No paid model is invoked.

## Supported scope

| Path | Evidence |
|---|---|
| Saved files → immutable checkpoint → recovery/restore | Real Core integration tests |
| Headless OCP STEP edit → actual static clearance calculation → result capture | Real OCCT geometry tests; see HARDWARE-VERIFICATION.md |
| MCAD → harness → control dependency applicability | Explicit, version-bound declarations; contract tests |
| Results and downstream gaps → Mentor → correction request | Authenticated Core tests with synthetic review output |
| External solver launch and collection | Real local Python processes; synthetic physics fixtures |
| SaaS / native desktop capture → current change | Existing capture-bundle publication |
| Commercial CAD SDK operation | See [native qualification](NATIVE-DESKTOP.md); no new live vendor verification |

There is no built-in FEA, tolerance, thermal, dynamics or electrical solver.
Connecting a customer solver does not validate its physical model. Mentor quality
and development-time savings require separate evaluations, not these functional tests.

## Start and continue

First connect an existing project using the existing
[development workflow](WORKFLOW.md). Initialize a development state with original
files and requirements. Keep tokens outside the captured project. Example below
assumes `STATE_ID` identifies that state and an authorized owner supplies the scope.

```sh
gantry-engineering doctor
gantry-engineering --url http://127.0.0.1:8770 --token-file /secure/gantry.token \
  checkout --state-id STATE_ID --destination /work/candidate \
  --title 'Improve clearance' --purpose 'Check mechanical and control interfaces' \
  --assignee ACTOR_ID --scope b.step --scope collision.json \
  --scope cad-operation.json --scope .gantry-evidence/ --key clearance-start
```

The destination contains `workspace/` and the original `context.json`. The workspace
has a private `.gantry/engineering/connection.json` identifying the current change,
state and server, without a token. Subsequent commands use this file instead of
asking the user to copy new state IDs after every checkpoint.

Edit files using customer tools. `edit --root ... --request edit.json --output NEW_DIR`
also exposes the existing fixed OCCT operations. It writes a new output directory;
the operator chooses which generated files to bring into their candidate. It never
silently replaces the source CAD. Native desktop writes still use the prepare/apply/
readback workflow in `gantry-native`, with their original permission boundaries.

For ordinary code, CAD or configuration changes without a physical report:

```sh
gantry-engineering --url URL --token-file TOKEN_FILE checkpoint \
  --root /work/candidate/workspace --summary 'Saved candidate' \
  --reason 'Pending verification' --key candidate-1
gantry-engineering --url URL --token-file TOKEN_FILE status --root /work/candidate/workspace
```

Use `capture --root WORKSPACE --bundle CAPTURE_DIR --key UNIQUE_KEY` to publish a
SaaS/native readback bundle into this change. Include `imports/SOURCE_ID/` in the
write scope. Original provider bytes and version metadata remain intact. Imported
files live in Core; restore the resulting state into a new directory before editing
those imported files locally. `status` explicitly reports missing local tracked files.

`status` opens saved context; it does not restart processes. To continue on another
machine, restore the saved state using the existing restore API/CLI, or `checkout`
that state into a new candidate. Credentials and installed tools are provisioned
separately. No local journal or credential is needed to restore published artifacts.

## Cross-tool mapping

Use the existing engineering components, not a second component database. Mapping
v1 is a captured JSON file with `components` and `dependencies`:

```json
{
  "version": 1,
  "components": [
    {"id":"bracket","role":"support","assembly":"head","paths":["bracket.step"],
     "native_refs":[{"provider":"cadquery","document":"head","object":"bracket",
       "revision":"r1","unit":"mm","frame":"head","source_path":"bracket.step"}]},
    {"id":"harness","role":"wiring","assembly":"head","paths":["harness.json"]}
  ],
  "dependencies":[{"prerequisite":"bracket","dependent":"harness","kind":"uses_geometry",
                   "status":"unverified","rationale":"Routing requires a clearance check"}]
}
```

Run `bind --root WORKSPACE --mapping engineering-map.json --reason REASON --key KEY`
with Core credentials. The mapping file must be in the change's write scope if it
changed. This is an explicit reassessment: the supplied map replaces the declared
component/dependency map and binds its inputs to the captured hashes. Existing check
definitions and evidence remain. Include every component referenced by those checks.

Native references are declarations, not automatic recognition of CAD topology or
electrical nets. Original files remain available. Units and frames are recorded;
no implicit coordinate transformation is performed. `confirmed` means the caller
asserts compatibility at these exact input versions; `unverified` requires review.

Changing prerequisite bytes makes dependent components and their checks inapplicable,
transitively. Refreshing the changed component's own hashes does not refresh the
dependency contract. Re-bind only after reassessing the interface, with a recorded
reason. Old evidence is retained; no check is automatically rerun or declared passed.
Undeclared dependencies remain unknown. Cycles terminate via a visited set.

## Physical evaluation

Save a [physical plan](HARDWARE-ADAPTER.md) in the input state before evaluating.
The plan pins inputs, conditions, evaluator/environment identity, criteria and
requirement references. `publish --plan physical-plan.json` stores changed candidate
files and treats missing/old reports as unknown; it never adopts a candidate.

1. Publish the candidate inputs. The CLI refuses evaluation when local input hashes,
   change head, or linked requirement versions disagree with the saved state.
2. Select a trusted local executable and recipe. `recipe-hash` prints its digest;
   independently inspect the recipe before passing that digest as authorization.
3. Run the evaluator in a separate copied directory. Include evaluator scripts,
   material/model/mesh/configuration files in the plan's inputs.
4. Collect the result, then publish the candidate and evidence through Core.

```json
{"argv":["/opt/project/bin/python","-I","evaluate.py"],"timeout_seconds":300}
```

```sh
gantry-engineering recipe-hash --recipe evaluator-recipe.json
gantry-engineering --url URL --token-file TOKEN_FILE evaluate \
  --root WORKSPACE --plan physical-plan.json --check-id clearance \
  --recipe evaluator-recipe.json --approved-hash REVIEWED_DIGEST --job NEW_JOB_DIR
gantry-engineering collect --root WORKSPACE --job NEW_JOB_DIR
gantry-engineering --url URL --token-file TOKEN_FILE publish \
  --root WORKSPACE --plan physical-plan.json --key evaluation-1
```

If replacing a previous report, `collect` requires `--replace-report-sha256` with
its current hash. Collection preserves the raw report, logs, execution receipt and
timing under `.gantry-evidence/INTENT_HASH/`. Raw successful-looking output from a
failed or uncertain process remains evidence but cannot become an applicable pass.
Original reports over 1 MiB and logs over 8 MiB are bounded with explicit truncation.
Inputs are bounded to 100 files, 100 MiB/file and 256 MiB total. No credentials are
forwarded from the Gantry client into the evaluator environment.

The recipe runs with the operator's OS permissions. A copied directory and digest
are not a sandbox. Use containers/accounts for untrusted tools. Native plugins and
SDK runtimes must be installed separately. The process lifecycle is tested on macOS;
Windows child-process handling is not qualified and cannot yield a trusted pass.
Subprocesses must not escape their process group. Install immutable evaluator
environments; this captures executable/script hashes, not every system dependency.

## Recovery and concurrency

- Reuse an operation key only to recover the **same** publication intent. Exact
  checkpoint arguments are saved before dispatch. If the response is lost, rerun
  the same command/key: Core authenticates again and returns the original state.
  Later local edits are not silently substituted into a frozen request; use a new
  key for them. Different intent with the same key fails.
- A concurrent branch update fails at Core's atomic version check. Inspect it and
  explicitly rebase/start another change; the wrapper never silently overwrites it.
- A job with a launch intent but no terminal receipt is `execution_uncertain`.
  Do not run it again. Inspect/stop it and any children, then use
  `reconcile --job JOB --process-stopped`. This preserves an **unknown** result.
  A new job directory is needed for an explicitly requested new attempt.
- Local collection updates files independently, not as an atomic directory commit.
  Do not edit the candidate during collection. A retry checks saved input hashes
  and acquired output hashes; identical already-copied evidence is accepted.
- `.gantry` journals are private local continuation data, excluded from snapshots.
  Back them up until pending effects are reconciled. Deleting a journal can discard
  recovery knowledge. Already published history remains in Core.

## Mentor handoff

Configure the existing review team/provider, then call:

```sh
gantry-engineering --url URL --token-file TOKEN_FILE review --root WORKSPACE \
  --question 'Check mechanical/control compatibility and propose corrections' \
  --stage integration --acceptance 'Declared clearance and routing checks' \
  --required-role mechanical --key review-1
```

`get_change_review` now includes `engineering_dossier`: pinned state/baseline,
changed files, source identities, dependency impact, check applicability, frozen
criteria/observations, requirement coverage, and evidence gaps. It reaches the same
existing Mentor input path. Missing required evidence/dependencies prevent technical
OK. Existing findings, work proposals, correction responses and reflection APIs
retain the proposal → correction → outcome chain. No inference is invented by the
dossier builder, and this CLI does not automatically start a paid provider.

## Timing and diagnostics

Automatic spans cover publication/capture, CLI CAD edit, local evaluation and review
submission. Evaluator timing is collected into the ledger with its evidence.
Use the same journal to instrument additional agent/tool phases:

```sh
gantry-engineering timing --journal JOURNAL start --phase inference --state-id STATE --operation candidate-A
gantry-engineering timing --journal JOURNAL pause --span-id SPAN
gantry-engineering timing --journal JOURNAL resume --span-id SPAN
gantry-engineering timing --journal JOURNAL finish --span-id NEW_SPAN --outcome completed
gantry-engineering timing --journal JOURNAL report --output timing.json
```

Export into an authorized capture path and checkpoint to share other timing data.
Parent spans use `--parent-id`; operation/state IDs identify attempts and candidates.
Reports separate summed span durations, union of measured intervals, total observed
elapsed window, phase p50/p95, unfinished spans and unknown durations. The difference
between elapsed and measured time is **unobserved**, not inferred thinking/waiting.
No cross-host time alignment or full critical-path attribution is claimed. Work
outside instrumented paths stays unmeasured; historical durations are not invented.

## Acceptance smoke test

```sh
python examples/engineering_roundtrip.py NEW_DIRECTORY
```

Creates anonymous intersecting STEP solids, captures a baseline and explicit
mechanical/harness/control map, evaluates a real failure, edits the CAD, records an
unverified candidate, evaluates a real pass, injects a lost acknowledgement, recovers
the exact state, and restores the final bytes. Dependent wiring/control remain due
for reassessment and adoption remains `unadopted`. See
[verification record](ENGINEERING-WORKFLOW-VERIFICATION.md) for executed checks.
