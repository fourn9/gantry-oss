# Security maintenance verification — 2026-10-24

Release: 3.1.1. Base: public main at 0fa407c. No ledger migration.

## Checks performed

- CPython 3.12.15 on macOS: 552 unittest cases, no failures, 4 skips (75.878 seconds).
- JavaScript UI: 7 tests passed.
- Six new offline-version/real-HTTP tests; encoding tests failed before the fix.
- Wheel built and installed; CLI help and offline security check succeeded outside the source directory.
- pip-audit 2.10.1 found no known vulnerabilities in resolved public dependencies.
  Runtime/build packages checked: cffi 2.1.1, packaging 26.3, pycparser 3.12,
  PyNaCl 1.6.2, setuptools 84.2.1, wheel 0.48.0.
  A separate tooling audit also covered pip 26.2.2, certifi 2026.10.23 and uv 0.13.5.
  Gantry's locally built wheel was skipped by the advisory catalog (URL requirement);
  its input-handling changes were inspected and regression-tested, not certified by pip-audit.
- Wheel contains package/static assets and distribution metadata; no project databases,
  credentials or development artifacts were included.
- GitHub vulnerability alerts and Dependabot security updates enabled; secret scanning
  and push protection remain enabled. Weekly pip dependency update configuration added.
- CI instructions updated in docs/ci-workflow.yml; this remains a template, not an
  activated GitHub Actions workflow.

## Failure encountered and resolution

The first full run had one sandbox fixture failure. Its Python virtual-environment
symlink caused Python to read pyvenv.cfg outside the approved runtime. The fixture
now selects the resolved runtime executable, consistent with the existing sandbox
integration test. No production sandbox permissions were broadened. Tools requiring
virtual-environment-specific dependencies still need an explicitly supported execution
configuration; this patch does not add that support.

## Limits

This is a source/distribution review and local test, not a penetration test of a
running customer deployment. Existing installations, OS trust stores, reverse proxies,
standalone Node/uv executables and system-linked native libraries are not automatically
patched. No production cloud endpoint was deployed in this maintenance task. Other
Python versions and operating systems were not regression-tested here.

See [update steps and upstream advisories](SECURITY-UPDATES.md). A clean advisory
scan is a point-in-time result, not proof of absence of vulnerabilities.
