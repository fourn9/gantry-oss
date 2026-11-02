# External integration verification — 2026-11-03

Implementation snapshot: `f8638821667e75ff8c05f015d3a138718e80809f`.
This report records local and contract evidence, not full vendor qualification.
No customer credentials, licensed Windows hosts, paid services or remote writes
were used. Existing ledger data and the separate Bot checkout were not changed.

Subsequent Altium CLI host dispatch/recovery work is tracked in
[native host completion](../tasks/native-host-completion.md) and documented in
[Native desktop operations](NATIVE-DESKTOP.md). It does not change the absence of
licensed-runtime acceptance recorded here.

## Completed changes

| Area | Change | Evidence |
|---|---|---|
| Altium | Opt-in generated PCB comment update, native save/reload and saved-file capture; original v1 path preserved | Six new script/receipt tests; no live host execution |
| Notion / Slack | Bounded descendant/thread pagination, raw page preservation, partial capture and validated resume | Eight collection tests, including scope tampering, cursor cycles and rate limits |
| Drive / SharePoint | Selected file body capture, before/after revision checks, bounded downloads | Seven file tests; cloud responses simulated |
| Core publication | Preserve previous imports when source files are already assembled from stored chunks | Actual local CLI, two-source publication, requirement links, binary restoration and replay |

The Core roundtrip exposed and fixed a pre-existing failure: importing a second
source attempted to use an assembled file as an ordinary file part. Publication
now reuses the existing leaf references. A failure to import is not silently
converted into a successful checkpoint.

## Checks performed

Runtime: Python 3.12.15 with the existing optional CadQuery 2.8.0 installation.
No new runtime dependencies. Package version remains 3.3.0; no release was made.

| Check | Result |
|---|---|
| `python -m unittest discover -s tests` | 780 discovered; 779 passed, one optional CAD-interpreter test skipped; 92.530 seconds |
| Skipped CAD test, rerun with `GANTRY_CAD_PYTHON` configured | Passed in 4.258 seconds; real STEP geometry and difference via CadQuery |
| External integration subset | 51 passed; included in the full suite |
| Native connector subset | 25 passed; included in the full suite |
| `node --test tests/test_review_web.mjs tests/test_requirements_web.mjs` | 9 passed |
| Wheel from committed source, fresh virtual environment | Installed with no dependencies; new CLI entry points and module imports passed |
| Installed capability catalogs | 35 external inventory entries and eight native product entries; blocked routes remain blocked |
| Public GitHub REST smoke | Actual unauthenticated read of `octocat/Hello-World` issue 1, CLI capture and bundle integrity check passed |
| `git diff --check eb5a488` | Passed |
| Targeted scan of 17 changed files | No private project name, personal home path, common API token or private-key patterns found |

Test counts overlap; they must not be added together as independent test coverage.
Catalog entry count is not a count of fully implemented or qualified integrations.
The public GitHub test proves only that read path; it does not validate account
scopes, authenticated writes, other cloud providers, or native desktop applications.

For the optional CAD test:

```sh
GANTRY_CAD_PYTHON=/path/to/cad-python PYTHONPATH=tests python -m unittest test_review_context.CADInspectionTests.test_actual_cadquery_geometry_and_difference
```

## Security review scope

- Remote records remain data; capture does not execute their content or follow
  embedded instructions/links. Resumption is bound to the original source and
  requirement scope and reconstructed from captured page relationships.
- SharePoint downloads use only an explicitly configured tenant hostname, public
  resolved addresses pinned for the connection, TLS hostname verification, no
  redirects and no forwarded Graph token/cookie. Temporary content URLs are not
  saved in evidence or reported in errors.
- File size, response count, traversal depth and deadlines are bounded. DNS uses
  the OS resolver timeout; request-boundary checks are not a hard process deadline.
- Native script receipts describe host-reported results. They are not proof
  against a malicious OS user, not an atomic vendor transaction and not evidence
  of physical/electrical correctness. Exclusive editor access remains necessary.
- Pattern scanning is not full secret detection or an independent security audit.
  Opaque native files may contain embedded sensitive data and need review before
  sharing. Captures are local until explicitly published.

## Not yet complete

| Gap | What is needed to finish and verify it |
|---|---|
| Zuken E3.series native read/write | Exact module/version, SDK identity/read/write/save contracts, licensed runtime and disposable test project |
| Siemens Capital native read/write | Exact product/module/version, licensed SDK/API and transaction/persistence contracts, test environment |
| Cadence Allegro save/reopen | Verified version-specific save/reopen API, error/dirty-state semantics and a native runtime; current generated script has only in-memory readback |
| Altium host execution | Compile and execute generated script in the supported version; verify installed `PCB Binary` save format and failure handling |
| Other implemented desktop drivers | Run selected read/write/save/recovery cases on licensed Windows applications; all currently unqualified |
| Authenticated SaaS acceptance | Customer-provided disposable accounts/projects with scoped credentials; exercise read, reviewed write, readback and uncertain-result recovery |
| Broader tool operations | Current contracts only cover named fields/objects. Complete assembly/PCB/harness editing, dependency discovery, OAuth onboarding and continuous sync require additional implementation |

There is no executable Zuken/Capital native driver hidden behind export capture.
Missing SDK contracts are not replaced by guessed calls or mock success. Real
environment acceptance remains necessary before claiming native integration is
complete for any of these licensed products.

Usage and primary API references:
[cloud captures](EXTERNAL-INTEGRATIONS.md),
[reviewed writes](EXTERNAL-WRITES.md),
[native desktop operations](NATIVE-DESKTOP.md),
[local engineering workflow](ENGINEERING-WORKFLOW.md).
