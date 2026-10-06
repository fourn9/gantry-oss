# v3.1 designation — 2026-10-07

The owner designated the existing Bot-owned organization implementation as v3.1.
Package/runtime metadata and the README now use 3.1.0. Version propagation to the
HTTP/MCP modules and a newly built 3.1.0 wheel were checked. The release record
preserves v3.0 history and links to the prior implementation verification below.
This metadata-only change did not rerun the engineering/model experiment or the
full behavioral suite, and did not push to GitHub or alter a saved ledger.
Agent-skills reference: 2686b620fc1fed2e8f60c704839c766b8594c6b6;
using-agent-skills, documentation-and-adrs, git-workflow-and-versioning.

# Bot-owned organization extension — 2026-10-06

See [acceptance evidence](../docs/CREW_ORGANIZATION_ACCEPTANCE.md) for the real
subscription run, earlier failed attempts, token usage, exact limits and final
546-case regression suite. This implementation is local and not published.
The persistent implementation workflow is recorded in [AGENTS.md](../AGENTS.md).

# Independent services: validation on 2026-10-04

Verified for this source revision after v3.0.0. No paid
model calls, customer-data uploads, physical operation or service installation
were performed. The wheel was installed only into a temporary verification venv.

## Current verification

- Reconfirmed on 2026-10-04 with Python 3.12.14 in the clean verification
  environment: 392 tests, 382 passed, 10 optional-environment skips, no errors;
  UI tests: 7 passed. The earlier run below used a different optional-dependency
  environment. macOS system Python 3.9 is unsupported (the package requires
  Python 3.11+) and was not used as the acceptance runtime.
- Re-ran the customer-bridge example in a fresh isolated ledger: both edited
  files restored correctly, Mentor jobs remained zero, replay matched and the
  hash chain verified. The result remained unadopted and physically unverified.
- Reconfirmed all 180 API contracts against the registered inputs and all 67
  Python source files against the previously built verification wheel. This
  confirmation did not publish a release or replace any live ledger/worker.

- Publication branch check on 2026-10-05: 392 Python tests passed with 8 optional
  skips; 7 UI tests passed. A clean Python 3.12 environment built and installed
  the wheel, and both `gantry-ledger --help` and `gantry-crew --help` exposed
  their separate commands. This check used synthetic inference and no robot.

## Earlier verification in the same source revision

- Full Python suite: 392 tests, 385 passed, 7 skipped; 65.326 seconds.
- Independent Bot scenarios rechecked: 30 passed; 2.847 seconds.
- Seven skips are optional feedback-extra tests (six) and the separately configured
  native CAD interpreter test (one); independent service tests have no skips.
- UI suite: 7 passed (`node --test tests/test_review_web.mjs`).
- API reference: 180 registered operations; schemas checked against the command set.
- Wheel build and clean-venv installation passed; both `gantry-ledger --help` and
  `gantry-crew --help` expose their separate commands. Package version remains 3.0.0
  until a release is explicitly prepared.
- `examples/bot_development_loop.py`: actual customer bridge subprocesses edited
  two files, returned reports, woke the integration Bot, integrated the candidate,
  restored both outputs, and verified replay. Mentor jobs: zero. Result remained
  unadopted, unverified and of unknown physical compatibility.
- Migration check using the actual previous commit `b744d47`: 27 historical events
  and two legacy Mentor jobs survived opening in the new implementation; verify
  and replay passed. The export was unchanged on opening; all historical events
  and artifact bytes remained equal after replay's own audit event was appended.

## New path evidence

`tests/test_bot_development.py` has 30 focused scenarios. They use non-admin scoped
principals and real Core/storage/worker operations, with explicitly synthetic
reasoning:

- Integration leader, department manager and workers delegate and return reports
  without creating a review team or invoking Mentor. Independent file changes can
  run concurrently and become a candidate with exact saved content.
- Actual installed bridge subprocesses consume structured context and return
  edits/results through the default worker. A separate test executes a local tool
  against the restored workspace; missing intermediate capture stays explicit.
- Peer blockers, failed child reports, manager resumption and next-task experience
  are saved. A fresh context restores an interrupted intermediate checkpoint.
- Claims are scoped, atomic and idempotent. Hierarchy, task scope, changed baseline,
  organization revocation and stale discussion are enforced. Narrower integration
  tasks cannot use their Bot's broader binding to accept other changes.
- A mixed edit/integration report cannot silently replace its saved edit; it must
  hand off to a separate integration task with fixed inputs.
- Recovery reuses saved answers and reconciles lost claim, checkpoint and finish
  acknowledgements without repeated effects. Uncertain provider outcomes stay held.
- Normal dispatch and explicit recovery respect the same workflow boundary in both
  directions. Independent Bot recovery cannot invoke the legacy Mentor handler.
  Legacy-only recovery cannot invoke the Bot handler. Unsupported legacy retry
  flags are rejected before attempting independent task recovery.
- Service-specific MCP configuration has the correct default profile. Explicit
  legacy runtime configuration is not silently reinterpreted by `gantry-crew`;
  invalid workflows fail closed. Generated background services require the saved
  Bot workflow explicitly, even when using the generic executable.
- Additive backup/import/replay preserves events, tasks and native content. Legacy
  review functionality is covered by the remaining regression suite.
- A 10,000-file restore inventory stays available in the private saved context,
  with bounded model previews, explicit omissions and a canonical-content hash.
  Large file inventories do not have to be repeated in every inference input.
- Thirty remembered tasks with 2,001 source files each retain their full records
  while the inference input stays below 160 KB. Dependency hashes are prioritized;
  counts, truncation markers and exact record references disclose the preview.
  Observations and limitations survive unchanged. This addresses growth in past
  task inventories in addition to the current restore inventory.

## Limits

These tests establish mechanics, not live-model planning quality, engineering
correctness or development speed. A trusted customer bridge is not an OS sandbox.
Native CAD/firmware integrations still need customer-specific validation. Sharing,
integration and work completion never imply formal adoption. Automatic ownership
transfer of an in-flight job between the services is not implemented: reconcile
the old task and explicitly initialize/assign the next one from saved state.

See [independent Bot setup](../docs/BOT_DEVELOPMENT.md) and
[service boundaries](../docs/SERVICE_SPLIT.md).

---

# Historical v3.0.0 Bot and connection validation

Status: implemented and publication-checked. No paid inference, automatic service
installation, physical robot operation or customer-data upload was performed.

## Final verification

- Full Python suite: 362 tests, 354 passed, 8 skipped; 59.663 seconds.
- UI suite: 7 passed (`node --test tests/test_review_web.mjs`).
- Published API contract file exactly matches the 165 registered operations.
- CLI worker help, service generation and diff whitespace checks passed.

## Persistent organization/Bot evidence

`tests/test_persistent_bots.py` contains 13 synthetic integration scenarios:

- An offline Bot's submitted work remains queued. Specialist, coordinator and
  developer workers complete an actual file-edit, resubmission and reflection loop.
- A fresh Service/client on a second development session receives the same Bot ID,
  profile, prior individual experience and owner-authorized organization reflection.
  Formal adoption stays unadopted; missing physical verification stays unverified.
- Source-session access removal prevents later memory retrieval. An agent cannot
  expand organization sharing, runtime configuration or its own identity authority.
- Two concurrent runtimes cannot own one Bot. Changed onboarding rejects old
  inference output. Queue/status reads do not disclose the runtime fence.
- A saved inference receipt survives interruption and a fresh worker without a
  second model attempt. A recovery commit whose response is lost also survives a
  further runtime restart, without consuming a second inference allowance.
- A cross-session contradiction retains both old and new evidence.
- Organization revocation during inference rejects edits before files are changed.
- Runtime lease expiry/replacement invalidates the old fence and holds uncertain
  work for explicit recovery instead of silently repeating it.
- Generated launchd/systemd service files are opt-in; no provider is selected by
  default. They are generated and parsed in tests, not installed on the host.
- A real synthetic customer bridge process reads JSON context/schema, returns a
  structured report and completes a queued job through the default worker path,
  saving durable Bot experience. Its executable hash and saved receipt are checked.
- A disabled binding cannot write new persistent experience.

Inference assertions are fixtures, not engineering truth or commercial model
quality measurements. Core transactions, indexes, runtime fences, queue ordering,
workspace restore/edit/capture, receipt persistence, experience and replay are real.

## Existing paths retained

- `test_bots.py`: local CLI/MCP onboarding, three-level reporting, owner approval,
  communication blockers, scope and evidence checks, reflection and replay.
- `test_unlimited_connection.py`: no default expiry, optional owner-selected expiry,
  13 actual sandboxed test runs, idempotency, owner renewal retaining identity,
  rejection of unauthorized renewal and revival of revoked credentials.
- `test_unlimited_reviews.py`: new/legacy repeated reviews and immutable original
  connection plans; local counts are audit-only.
- Existing review, continuity, job recovery, adapters, security and UI regressions.

## Security and publication checks

- Offline secret scan found no secrets in the new persistent Bot implementation,
  customer worker, acceptance tests or setup document.
- Private-project name/path/connector checks found no matches in the new material.
- Focused Bandit review: two low-severity subprocess notices remain for the explicit
  customer-installed inference bridge. No shell is used; argv/config comes from
  the owner, the executable hash is checked, and host credentials are not inherited.
  The bridge and verifier are trusted local processes, not a new OS sandbox.
- Dynamic SQL ordering was replaced with fixed parameterized queries. Job lookup
  uses a disposable index instead of loading all historical jobs/contexts.
- Runtime credentials/fences are excluded from onboarding and public status views.
  Private local journals remain sensitive; they are never a telemetry payload.
- Shared memory always rechecks source access. Revocation cannot erase data already
  legitimately delivered to a previous model invocation or local workspace.

## Product boundary

Organization/Bot identities, role bindings, per-Bot local environments and queued
PR-triggered execution now persist independently of conversations. Outcome sharing
can be automatic under a human-approved organization policy. This is retrieval and
reflection learning, not weight training or proven improvement in model competence.

The owner configures existing principals, session review hierarchy, bindings and the
customer inference bridge. Separate local ledgers are not automatically federated.
The worker does not provision a cloud VM, launch arbitrary desktop-agent windows,
restore arbitrary process RAM or automatically choose the best organization/design.
The actual local service has not been installed/enabled in this development task.
See `docs/PERSISTENT_BOTS.md` for setup and recovery.
