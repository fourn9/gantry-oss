# Local Bot and connection validation

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
