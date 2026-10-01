# Gantry 2.1.0 — recovery and tool views

Early public prerelease. This extends the existing project connection and review
workflow; it does not introduce a new agent organization or a paid model service.

## Added

- Recover a stopped Mentor worker using its original private journal and delegated
  identity. Core checks current inputs, permissions and execution conditions before
  rotating the lease. Saved model output, applied edits and completed verification
  can be reused without repeating the work.
- Resume an expired project review through `gantry project mentor-recover` or
  `project_mentor_recover` in MCP. The original review context and saved answer
  remain tied to the same evidence.
- Render selected evidence fields through explicit, versioned JSON output
  profiles, retaining source references and conversion provenance. Supported unit
  conversions do not overwrite native data; missing information stays explicit.
- Optional CAD screening for hash-pinned STEP files. Each part's bounding box is
  computed once per pose, with exact checks for unresolved pairs and measurements
  of calculation counts and time.

## Fixed

- Reconnecting to a review no longer changes its saved model input merely because
  the server clock or lease metadata changed.
- Recovery reconciles ambiguous acknowledgements using durable request IDs. Known
  live processes, changed premises and revoked permissions prevent unsafe reuse.
- Interrupted verification is collected as an unknown outcome, never inferred to
  pass or automatically rerun. A new inference attempt requires explicit selection
  and consumes the existing allowance; no paid API fallback is introduced.

## Validation and limits

The Python suite ran 327 cases: 320 passed and 7 optional-environment cases skipped.
The UI suite passed all 7 cases. Coverage includes HTTP/service restart, lease
expiry, stale inputs, lost acknowledgements, process checks, project MCP recovery,
output mappings and native STEP checks with the optional CAD runtime installed.
Model responses in these regression tests are fixtures, not live-model evaluation.

The built wheel was installed into a clean environment and exercised through the
synthetic project example: saved failure, review, correction, unchanged passing
test, new-client resume and matching audit/replay. Static scanning reported no
high-severity findings; the two existing medium findings remain the allowlisted
SQL query and the sandbox's temporary mount described in the connection review.
Secret-scanner candidates were the same five existing negative-test fixtures.
The checked optional feedback dependencies (PyNaCl 1.6.2, cffi 2.1.1 and pycparser
3.0) had no known advisories at publication review. These checks are not an
independent security certification.

Recovery requires the same identity and private journal; it does not launch an
arbitrary user agent or transfer credentials. Tool profiles are selected JSON
mappings, not universal CAD/electrical converters. CAD screening covers explicit
pairs at a declared pose, not continuous motion or physical certification.
Existing evaluators must explicitly adopt the helper and verify equivalent
results. No end-to-end development speedup is claimed by this release.

See [usage, contracts and remaining limits](runtime-recovery-and-tool-views.md).

## Upgrade

Back up the ledger, artifacts and private worker journals; stop active workers,
install the new version, then restart servers/workers. No destructive schema
migration is required, and previous events and artifacts are retained. New journal
fields are additive. Recovery neither extends expired credentials nor changes
feedback consent or formal adoption.

If rollback is needed, stop workers and restore the matching pre-upgrade backup
with its previous executable. Do not mix old workers with newer recovery journals
or assume an older reader supports events written by a newer version.

The preceding release's connection behavior and qualification limits remain
documented in [the 2.0.3 connection review](CONNECT-REVIEW.md).
