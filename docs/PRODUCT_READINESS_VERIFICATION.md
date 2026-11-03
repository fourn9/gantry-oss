# Shared product paths — verification, 2026-11-04

This combines the previously separate external-adapter implementation with current
Studio, then adds scoped membership, larger captures and operational recovery.
No customer data, licensed CAD application, public cloud account, paid inference,
manufacturing or physical robot was used.

## Verified behavior

- Actual loopback CloudServer HTTP, isolated workspaces and two independent human
  credentials: import editable CadQuery STEP and code; save an unfinished update;
  share it; approve a recipient-generated access request for an exact session;
  restore through Gantry; create independent work; edit and share again.
- The restored STEP was reopened with CadQuery 2.8; its 2,400 mm³ volume matched
  the original. This proves the saved geometry path, not mechanical strength,
  manufacturing acceptance or complete native feature-history compatibility.
- Cross-workspace token use and revoked credentials were rejected. Shared work
  remained unverified and unadopted. Event replay matched the stored state.
- SQLite online backup plus referenced immutable artifacts restored into a new
  workspace and served the same saved manifest over HTTP. Raw token files were
  excluded. The separately retained recipient credential still worked there.
- Larger capture tests used a 33 MiB file and more than 1,000 files, froze the
  upload, simulated a lost acknowledgement, changed live source bytes, resumed
  the original submission and restored it. A separate 1,001-file initial import
  exercised the streaming path. These are synthetic capacity fixtures, not an
  industrial CAD assembly benchmark or a development-speed comparison.
- Duplicate credential assignment, stale/forged/expired/wrong-workspace grants,
  agent self-grants, out-of-scope changes, linked/secret files and concurrent
  request saturation were tested. The API bounds request threads at 16.
- Review fixes cover staging cleanup only after durable acknowledgement, cleanup
  recovery without resubmitting confirmed work, rejection of unrelated deletion
  targets, and token/request files created atomically with mode 0600 even under a
  permissive umask. The private upload is retained while acknowledgement is lost.
  Capture-intent recovery also covers interruption before a pending request is
  saved. Journal and directory changes are fsynced; simulated interruption tests
  are not physical power-cut certification.

Reproduce the real HTTP/geometry path in an environment with the optional CAD
runtime (use a fresh private output directory):

```sh
PYTHONPATH=. python examples/team-workspace/acceptance.py --output /private/new-acceptance
```

The directory contains private test credentials and ledgers. Do not publish it.
The emitted `results.json` reports checks and limitations without credentials.
The observed 2.200-second functional scenario includes local setup after server
start; it is **not** an A/B result, customer latency objective or speedup claim.

## Compatibility and review

No mandatory runtime dependency, new paid provider or destructive migration.
Existing artifact, state, change, permission, review and adoption contracts are
reused. Optional `snapshot` input lets the existing Studio commands accept already
stored chunk manifests. Small atomic browser uploads remain compatible. The
native/physical merge preserves both baseline-pinned acceptance checks and durable
publication recovery. Final Python regression: **1,279 invocations**, 1,271 passed,
eight optional/environment-dependent skips, no failures (148.571 seconds).
JavaScript: **31 passed**, no failures. These are test invocations, not distinct
user scenarios. Wheel build and an isolated installation passed; all four new or
related CLI entry points load, and the installed cloud-operations tests pass.
The existing local Studio ledger was backed up, restarted with this version and
its previous work remained readable through HTTP. No user data was reset.

The convenience membership action records an actual principal proposal,
endorsement, human approval and commit within one transaction; other policy
conditions still apply. It never adopts a CAD/code work state. Request hashes bind
reviewed scope, credentials stay on the recipient's device, duplicate credential
hashes are rejected, and sessions use expected versions. Existing same-zone artifact
visibility is documented; session membership is not a per-file secrecy boundary.

The maintenance environment audit found no advisories across its 35 installed
packages. Core has no mandatory runtime packages. This is not an OS/native-library
security audit or a guarantee against unknown vulnerabilities.

Public-source scan covered 311 tracked/new files. No private project references,
home-directory paths or real credentials were found by the checked patterns;
the four private-key-header matches are rejection-test literals, not key material.
This is a bounded scan, not proof that arbitrary binary documents are secret-free.

## Still requiring external qualification

- Licensed SOLIDWORKS, CATIA, Creo, Altium, Cadence and other native applications:
  exact read/write/save/reopen acceptance is not supplied by contract tests.
  Zuken/Capital SDK implementation and Cadence save/reopen contracts remain
  unresolved. See [native coverage](NATIVE-DESKTOP.md).
- Authenticated SaaS customer accounts: automatic OAuth setup and all vendor
  write paths have not been qualified against real customer tenants.
- Automatic CAD/code semantic correspondence: explicit/versioned dependencies and
  reviewed Mentor proposals are available; geometry alone does not prove design
  intent or discover all physical coupling.
- Real customer projects and large assemblies: synthetic files and one anonymous
  solid do not establish scaling on realistic B-rep complexity or developer effort.
- Linux/systemd/public TLS/edge deployment: configuration is supplied, but no cloud
  account or licensed runtime was provided. Operate the initial invited-team host
  behind an access gateway and complete a staging drill before wider exposure.
- SSO/email invitations, storage garbage collection, provider-specific full editor
  automation, customer monitoring/SLO evidence and a new controlled speed study
  are not asserted by this release.

The static public demo remains a separate, invented browser-only experience; it
must not accept customer credentials, real uploads or imply live agents.
