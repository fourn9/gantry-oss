# Connected workspace verification

Date: 2026-11-03. Scope: first connected saved-file workflow, not universal tool
integration or production cloud readiness. Addy Osmani workflow revision:
`2686b620fc1fed2e8f60c704839c766b8594c6b6`.

## Real filesystem and HTTP acceptance

[`acceptance.py`](../examples/connected-workspace/acceptance.py) uses an isolated
ledger, a real loopback HTTP server, two authenticated identities, native STEP
files, STL previews, control source and saved check output. No private project or
model output is used. CadQuery 2.8.0 was installed in the test runtime.

| Step | Observed result |
| --- | --- |
| Preview/import existing scoped files and hierarchy | Preview sends nothing; apply creates one actual project/state/work |
| Initial static interference | One violating pair between anonymous solids |
| External STEP edit through the existing adapter | Real import, 10 mm translation and export; changed STEP/STL captured |
| Share before control work is finished | Saved as shared, unverified and unadopted |
| Continue with separate `controls` identity | Same CAD bytes restored; context preserved; new independently assigned work |
| Edit controller and run static CAD check | Report records zero violating pairs; explicit hashes/context saved |
| Change one declared input after that check | Effective check becomes unknown; old version retains its result |
| Formal adoption / history | No design adoption; event replay matches |

The correspondence and interpretation of the result are explicitly declared in
the fixture. The static geometric check does not test controller behavior, motion,
strength, tolerances or real hardware. Editing a numeric controller offset is not
evidence that its dynamic behavior is correct.

Reproduce in an environment with the optional CAD dependencies already installed:

```sh
PYTHONPATH=. python examples/connected-workspace/acceptance.py \
  --output /private/path/to/new-acceptance-directory
```

The output path must not exist. Add `--port 8795 --serve` to retain the isolated
server for browser inspection. It writes `results.json`, source/continued files,
raw check output, a ledger and a local access token. Do not publish that output
directory or token. No inference API call or physical operation occurs.

## Automated and browser checks

- Main Python suite: **1,156 tests**, no failures, eight optional tests skipped in
  the base environment (132.249 seconds). This is an execution count, not a count
  of distinct product scenarios.
- Optional CadQuery/hardware suites: **45 tests**, no failures with CadQuery 2.8.0
  (3.621 seconds). This overlaps coverage in the main suite; do not add the counts.
- All JavaScript test files: **31 tests**, no failures.
- The new workspace/API regression tests cover lost-response replay after a
  process restart, readonly dependencies, stale heads, explicit deletion, secrets,
  symlinks, unreadable directories, identity isolation, context-only updates,
  import preview, continuation and browser sharing followed by local capture.
- Browser: folder import produced an actual project and visible saved mesh;
  generated attach/continue commands contained the selected work/state; Checks
  showed the stale result and retained requirements/constraints/unfinished work.
- Connection dialog checked at 390 × 844 CSS pixels: dialog remained within the
  viewport, document width stayed 390 pixels, commands wrapped, close remained
  operable. This is a targeted responsive check, not an exhaustive mobile audit.
- No browser warning/error logs were observed during these checks.
- Wheel build succeeded; a separate target installation exposed the new CLI,
  contracts and packaged UI. No new dependency was introduced.
- Existing local Studio server was restarted against its original data directory;
  its earlier project remained readable and Import project was enabled.

## Review findings resolved

1. A share performed in the browser increments the work version without changing
   input bytes. The adapter now accepts that metadata-only advance while rejecting
   a different immutable head.
2. `os.walk` can silently skip an unreadable directory. The inventory now reports
   that failure; synchronization holds instead of recording false deletions.
3. Context-only checkpoints accept an actual context change and suppress no-op
   duplicates. Import scope is validated as an explicit path list. Malformed sync
   input is rejected before it can block the durable outbox.

Existing authentication, zone/session access, work author/assignee checks, atomic
version checks, path restrictions, credential scanning and content-addressed
storage are reused. UI strings are escaped. This review does not certify that
every possible credential format or vendor document payload is detectable.

## Remaining work

- Licensed SOLIDWORKS/CATIA/Creo/ECAD environments and their live APIs still need
  installed-product verification. Saved native bytes are supported; browser preview
  and editing capabilities depend on exported formats and external tools.
- Hardware/software meaning, coordinate frames, units and required evidence must
  be supplied by a mapping/adapter/reviewer. No automatic semantic matching claim.
- Larger assemblies need the chunked adapter flow and further performance work;
  this atomic connection is bounded at 1,000 files / 16 MiB each / 32 MiB total.
- Organization invites, hosted identity/provisioning and production cloud operation
  are separate from this local authenticated workflow.
- No measured engineering-time reduction, autonomous design success, or new
  paid-model integration was established by this acceptance.
- The public static website demo was not converted into an authenticated upload
  service. Real data uses the configured Gantry server and local adapter.
