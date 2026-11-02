# Studio verification — 2026-11-03

Implementation baseline: `9595a1c`, extending the existing development-state model.
Independent review followed the repository's reviewed Addy Osmani skills revision.
No private project ledger, vendor account or paid inference was used.

## Functional evidence

Authenticated browser testing used an isolated **Demo · Bench robot** ledger,
created through real Core operations. Sample geometry was actual generated STL,
not the reference mock's shapes. Sample identities/results are not real customer
activity. An agent-kind identity was operated manually to test access and Inbox;
no agent reasoning or external CAD edit was claimed.

| Scenario | Observed result |
| --- | --- |
| Hierarchy → component → related work | Saved product hierarchy and change-set links opened the correct work |
| Team Work view | Human and agent assignees, scopes and recorded state in one list |
| CAD/Code/Checks | Tab switch, saved mesh, actual code and version-specific evidence |
| CAD selection/comparison | File-part selection, orientation and prior-version amber overlay worked |
| Code comparison | Added/deleted lines retained correct before/after line numbers |
| Previous-line conversation | Deleted line comment bound to baseline; Inbox reopened baseline/code/file/line |
| Human/agent mention | Agent identity received only its request, opened exact older part/state and replied |
| Upload → share | Existing saved code uploaded at mapped path; v2 unshared checkpoint → explicit preview → shared WIP |
| Status separation | After sharing, Checks remained Not tested; work stayed In progress and Not formally adopted |
| Old conversation isolation | v1 comments were not moved onto v2; old target displayed Previous version |
| Narrow viewport | At 320, 768, 1024 px conversation stacked below artifact; document width matched viewport. At 1440 px panel occupied its own 280 px column |
| Import/identity boundaries | Scope escape, credential-like file paths, inaccessible work/recipient and wrong anchor rejected by API tests |
| Async navigation | Deferred response tests: send A/navigate B, late deleted-line lookup, old artifact failure and typing during send cannot overwrite the new context/draft |

The browser also confirmed personal Inbox read acknowledgement, actual file hashes
and notes in the share dialog. No new browser console errors were observed during
the acceptance flow. Sample files and test reports remain outside public source.

## Automated and packaging checks

- Full Python regression: **1,141 tests, passed, 8 skipped**, 128.189 seconds.
  Skips are existing optional/environment-dependent checks; this is not vendor
  CAD-runtime certification.
- Final focused Studio backend checks: **5 passed**, including shared discussion
  reuse, idempotency, authorization, replay and retained files.
- Node suite: **20 passed** (11 Studio tests, including 4 actual-controller
  deferred-response tests and 2 evidence/escaping presentation tests).
- Wheel build: successful; Studio JS/CSS and Python modules are packaged.
- Independent review findings about stale asynchronous responses, old conversation
  state, Inbox deep links and deleted-source downloads were fixed and rechecked.

## What this does not demonstrate

No CATIA/SOLIDWORKS/ECAD application, GitHub account, live CAD synchronization,
physical solver or robot was exercised. Existing API/adapter paths supply saved
state; this UI adds authenticated file import/share and versioned discussion around
it. Stable native CAD subpart identifiers, automatic vendor preview conversion and
continuous external change capture still require integration work. No engineering
performance improvement or physical correctness follows from these UI tests.
