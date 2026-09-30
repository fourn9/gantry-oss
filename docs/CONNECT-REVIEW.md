# Scoped project connection review — 2.0.3

Date: 2026-09-30. This is a maintainer implementation review and local acceptance run, not an independent security certification or development-speed benchmark.

## Problem and resulting behavior

Previously, normal use required separately creating a principal, approvals, session, baseline, change and MCP configuration. A client could have recording access without the permissions or guidance to continue development. Existing Core/Mentor primitives did not by themselves provide one local entry point. These are code-path findings; the original user project's detailed execution logs were not available, so this is not a proven explanation of each earlier stop.

`gantry connect .` now discovers saved files without executing repository code and displays one explicit delegation. On owner confirmation it performs the existing proposal, submission, endorsement, human approval and commit steps internally. Activation, session membership and initial state are transactional. Developer and reviewer identities are separate, scoped, expiring and revocable. The default mode is work-capable; record-only is an explicit choice.

The regular route is status → edit/test → checkpoint → meaningful submission → grounded Mentor findings → current-state/scope checks → correction/test → checkpoint/respond → resume. A connected, active user agent performs this continuation. Gantry does not launch arbitrary agent apps, override their approval policies or certify the quality of their decisions.

## Reuse and extension

| Area | Treatment |
|---|---|
| Core approvals, principals, event store and artifact capture | Reused; approval activation composed inside one transaction |
| States, changes, sharing, continuity and adoption | Reused; a connection fixes a baseline, write scope and bounded alternatives |
| PR-style review, leases, evidence checks and response history | Reused; matching test observations and provisional assumptions added to context |
| Official subscription inference adapter | Reused; Gantry credentials stripped from the child environment |
| Local discovery, owner preview and client setup | New project connection layer |
| File edit/read, command sandbox and operation journal | New bounded local bridge |
| Data model | Two additive event-backed collections: connections and operations |

No historical events or artifacts are rewritten. Existing feedback consent is unchanged. New connection events require a reader that recognizes their table names; downgrading a ledger after using this feature is unsupported. Legacy Runner remains a separate route.

## Acceptance evidence

- Python suite: 291 cases; 288 passed, 3 optional-dependency skips. This includes 20 connection tests covering approval rollback, replay, exact permission plans, revocation, expiration including cached requests, secret/path exclusions, read-only acceptance files, cross-connection review access, evidence tied to the tested state, interrupted operation handling, branches, review/correction/response and private-file exclusion when Git is initialized after connection.
- JavaScript UI suite: 7 passed.
- Installed package: generated Claude, Codex, Cursor and generic stdio MCP entries were actually started. Initialization, tool listing and state retrieval succeeded; launching after revocation failed. A repository-local `gantry.py` plus hostile `PYTHONPATH` did not shadow the installed module because generated commands use isolated Python imports. This does not exercise those clients' GUI permission dialogs.
- macOS command sandbox: an actual test process was denied reading and writing an external canary and opening a network socket. Missing sandbox support failed closed. Linux bubblewrap was not executed on this host.
- Synthetic packaged example: failing clamp test → saved checkpoint → fixture Mentor findings → scoped correction → unchanged test passes → saved state → new client resumes. Audit verification and replay matched. Fixture model output is explicitly labeled.
- Upgrade smoke test: a synthetic ledger created with the published 2.0.2 wheel opened under 2.0.3, retained its original trusted event checkpoint, activated a new connection and replayed successfully. No production ledger was changed for this test.
- Static analysis: 27 low and 2 medium findings, no high findings. The pre-existing SQL finding uses allowlisted columns and bound values; the new temporary-directory finding is the `/tmp` tmpfs mount inside a bubblewrap namespace. Low findings include deliberate subprocess calls and boolean fields incorrectly flagged as passwords. This triage is not proof that unreported vulnerabilities are absent.
- Secret scanning: five candidates, all existing synthetic negative-test fixtures; no operational credential was identified. The built wheel contains source, static UI assets and package/license metadata. Known-vulnerability lookup for the tested optional dependencies (PyNaCl 1.6.2, cffi 2.1.1, pycparser 3.0) returned no known vulnerabilities; external tools and OS packages were outside that lookup.

### Live subscription experiment

A separate synthetic example used the official Codex CLI under a ChatGPT login. Mentor inspected saved source and the failed test, produced a concrete lower-bound correction, and a second model call produced the corrected file. The bridge applied it, the same test passed, the state was saved and resumed, and the audit/replay checks passed. No model output was mocked in this run. Owner approval and the act of invoking the developer continuation were supplied by the test harness.

There were two preceding failed attempts. The first returned evidence IDs with explanation text appended; Core rejected the invalid references. The second exposed shared-schema aliasing that incorrectly constrained file paths; Core rejected the nonexistent path. Exact evidence-ID enums and alias-free schema copies corrected these defects, with regression coverage. The successful run preceded the final review-path guard and file-count alignment; those final changes were covered by regression tests and the installed deterministic example, without another model call.

Successful-run provider-reported usage: Mentor 12,319 input / 413 output tokens; developer 9,186 input / 65 output tokens. The two failed attempts also consumed subscription quota. These counts are not a cost estimate or time-saving claim; the CLI used its default model. No API-key fallback, purchase, hardware operation or formal adoption occurred. Final state remained unadopted and physically unverified.

## Security and product limits

- Core enforces connection, project zone, session, expiry, command permissions and limits. The bridge additionally checks readable/writable paths, expected file hashes and exact command identity. Tests refuse changed read-only acceptance files. A review-linked edit must match the current reviewed state and proposed paths.
- Commands operate on a scratch snapshot, without host environment credentials, network access or hardware/project writes. The configured runtime is a trusted read-only input. This is not a resource-isolated VM; strong isolation from hostile processes using the same OS account is not provided.
- The bridge does not sandbox a user's independent shell, agent or CAD app. Owner credentials are not passed through MCP, but a fully privileged same-user process can access local files. Separate OS accounts/VMs remain appropriate for stronger separation.
- The owner approval is authenticated by the local owner credential and explicit confirmation/hash, not biometric proof of a human. Do not allow an untrusted host agent unrestricted access to the owner's CLI or credential storage and expect an MCP capability to constrain that separate route.
- File paths reject traversal, links and common sensitive/generated locations. Credential detection is best-effort. Explicit artifact APIs and other adapters have their own capture boundaries.
- The simple connection path is limited to 1,000 files, 32 MiB total and 16 MiB per file, matching the existing atomic capture contract. Larger CAD assemblies require the existing chunked adapters. No universal CAD integration is claimed.
- Client-driven Mentor output may come from the same reasoning context as the developer. Separate credentials are an authority boundary, not proof of an independent reviewer. Missing CAD/physics evidence stays unverified.
- Receipts are authenticated adapter reports, not remote attestation that a trusted process produced a measurement. The local host and adapter are trusted. A test pass is not formal engineering approval.
- Goals, constraints and hold conditions guide the user agent; generic natural-language compliance is not mechanically proven. Limits and scope are enforced; physical validity still requires appropriate evidence and review.
- Automatic inference is opt-in and sends the saved review context to the user's configured subscription provider. Recording and installation make no model calls. Feedback sharing is separately controlled and never enabled by connecting.
- Uncertain tool or inference outcomes are journaled and are not blindly retried. Host prompts, subscription quota, expiry and stopped clients can interrupt continuation. Saved files are recoverable, but arbitrary live application memory is not captured.

Before broader deployment: qualify Linux and real client UI setup, exercise customer CAD runtimes, perform an independent security review and measure end-to-end time on comparable development tasks. The earlier publication review's hosting, at-rest encryption and release-provenance limitations still apply.
