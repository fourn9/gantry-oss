# Gantry v3.1 — Bot-owned hierarchical development

Package version: **3.1.0**. Designated by the project owner on **2026-10-07**.
This labels the implemented and verified organization loop. Local source and tag
are prepared; this update does not publish a GitHub release or deploy a service.
The prior [v3.0 record](releases/v3.0.0.md) is preserved.

## Added

- Persistent integration, department-manager and specialist Bots reason in their
  own customer-agent contexts, delegate work and collect reports without Mentor.
- Directed peer consultation creates a read-only response task, then resumes the
  requester with the saved answer and explicit resolution of blocking questions.
- Opt-in action loops connect context retrieval, scoped edits, actual tool results,
  intermediate checkpoints, decisions and reusable provisional experience.
- Independent candidate states and exact-state verification support Bot-authored
  comparison and selection. Selection is separate from human formal adoption.
- Versioned organization proposals support atomic owner activation without creating
  credentials or expanding existing principal privileges.

## Fixed and hardened

- Preserve exact provider inputs and reconcile lost Core acknowledgements on recovery.
- Reject stale completion and cancellation, scope violations and unanswered blockers.
- Bound action history in prompts while retaining paginated lossless records.
- Attribute tool evidence to its current checkpoint and project zone; avoid duplicate
  final checkpoints when intermediate work is already saved.

## Verification and limits

The preceding implementation passed 538 Python cases with 8 optional-environment
skips, plus 7 UI tests. Five real subscription Bots completed an anonymous two-candidate
comparison through actual execution and recorded selection. Failed earlier attempts,
source versions, usage and the limits of that evidence are documented in
[Crew acceptance](CREW_ORGANIZATION_ACCEPTANCE.md).

The v3.1 designation changes version metadata and release documentation only.
No new robot-development speed, CAD fidelity or model-quality claim is made.
Customer inference remains customer-funded; no publisher API account is introduced.

## Upgrade

Back up the ledger, artifacts and worker journals; stop workers before installing
3.1.0. Existing configurations retain their behavior. Explicitly enable action loops,
approve their environment manifests and delegate new commands to existing principals.
Storage additions preserve old events, Bot IDs and Mentor work. Older executables
cannot read new event types in-place; rollback uses the matching pre-upgrade backup.

See [Crew organization and operation](CREW_ORGANIZATION.md),
[separate service entry points](BOT_DEVELOPMENT.md) and
[validation history](../tasks/validation.md).
