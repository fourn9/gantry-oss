# Learning transfer and selective effort

Approved direction: implement the remaining learning paths discussed with the user.
Use Addy Osmani agent-skills at 2686b620fc1fed2e8f60c704839c766b8594c6b6.
Preserve the older incomplete plans. This file is this change's spec and task list.

## Objective and capability order

| Module | Responsibility | Dependency |
|---|---|---|
| transfer-evaluation | Generate lessons from actual training work, freeze them, evaluate separate unseen work with/without them | Existing evaluation, Core and customer worker |
| selective-learning | Avoid a separate experience-selection call when complete recall has no relevant experience; retain outcome reflection | Existing learning plans |
| compact-recall | Group exact redundant experience without losing references, changed conditions or contradiction warnings | Existing recall |
| independent-check | Bot requests a scoped peer check of a selected lesson; result returns with evidence and current applicability | Existing consultation and persistent memory |

This is local customer-owned inference through the monthly backend; no new paid
provider, cloud account, native CAD claim or autonomous adoption. External vendor
qualification and SSO are separate product work, not silently implemented here.

## Contracts and acceptance

- Evaluation: run real work with no imported lesson, preserve initial failure and
  outcome, export only generated reflection lessons with immutable provenance.
  Freeze evaluation inputs before training. Keep evaluation arms isolated, same
  model/settings/limits/verifier; include training, setup, failures and all calls.
  No answer or post-training trial experience crosses arms. A missing learned
  lesson is an inconclusive experiment, never a fabricated seed.
- Selective mode is opt-in and manifest-bound. When recall is complete and empty,
  record an explicit no-experience routing decision without claiming Bot reasoning.
  Ordinary Bot task reasoning and verification still run; outcome reflection is
  retained, especially for first failures. Nonempty or incomplete recall uses the
  existing model plan. Old configuration and journal recovery stay compatible.
- Compact recall: opt-in, exact-content/condition groups only; retain source IDs,
  counts and full packet lookup. Never collapse differing constraints, evidence
  conditions, contradictions or correction chains. Enforce fresh sources/access
  before acceptance and preserve per-memory use provenance.
- Independent checks: a Bot explicitly selects a peer and a readable shared lesson
  under an active task. Reuse read-only consultations, pin lesson/state/requirements,
  reject same-Bot/same-principal self-review, stale or revoked sources. Return the
  actual review report and evidence to the requester. No inferred verification,
  grants, new dispatch policy, Mentor coupling or formal adoption.

## Implementation and testing

Python standard library, existing Service transactions and indexed records. New
fields optional; no history rewrite. Reuse `require(..., 'stale_basis', ...)`,
existing receipt/idempotency and journal conventions. Tests use unittest with real
Core; deterministic inference is labelled as such. Private live outputs stay outside
the repo. No changes to UI density or unrelated integration code.

Commands (from this checkout):
`PYTHONPATH=tests ../gantry-security-env-20261024/bin/python -m unittest TEST_MODULE -v`
`../gantry-security-env-20261024/bin/python -m unittest discover -s tests`
`../gantry-security-env-20261024/bin/python -m pip wheel --no-deps --no-build-isolation --no-index . --wheel-dir /tmp/gantry-learning-wheel`

## Tasks

- [ ] Add failure-first transfer evaluation and isolated learned/no-lesson arms.
- [ ] Add opt-in empty-recall routing and recovery tests.
- [ ] Add conservative duplicate grouping with provenance/security tests.
- [ ] Add scoped independent lesson consultation and actual peer result path.
- [ ] Run frozen live monthly-model transfer and overhead checks; report null/negative results.
- [ ] Independent review, regression/package checks, docs and additive API catalog.

Risks: lessons can be wrong, absence of lexical matches is not absence of relevant
knowledge, independent peers can share model biases, provider latency/cache varies.
Do not describe these mechanisms as guaranteed learning or speedup. Correctness and
evidence boundaries take precedence over elapsed-time improvements.
