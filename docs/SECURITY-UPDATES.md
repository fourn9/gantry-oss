# Runtime and installer security maintenance

Reviewed 2026-10-24. Gantry 3.1.1 is a security maintenance patch, not a security
certification. Updating the source does not update an existing Python interpreter,
virtual environment, browser, reverse proxy or OS certificate store.

## Scope and findings

| Component | Finding and action |
| --- | --- |
| PHP | No PHP source, Composer manifest or PHP deployment in this repository. PHP2Shell is not applicable to this distribution; separately operated PHP services remain outside this review. |
| Brotli | No Brotli dependency or decompression call in Gantry. Node is used for JS tests, not the server. Unsupported HTTP content encodings are now explicitly rejected; this is defense in depth, not a claim that Gantry contained the Brotli CVE. |
| Python | The package previously specified only 3.11+. Use patched CPython: 3.11.17+, 3.12.15+, 3.13.17+, 3.14.9+ or 3.15.1+ within those release lines. Locally verified with 3.12.15; other lines are advisory baselines, not a claim of full-suite verification. |
| TLS trust / installers | Python's eMudhra advisory requires pip 26.2.2+, certifi 2026.10.19+ where installed, uv 0.13.4+ where used, and updated OS trust stores. Installing a new Gantry wheel alone is insufficient. |
| Build backend | Raised setuptools floor from 61 to 78.1.1, excluding CVE-2025-47273 affected versions. Its legacy download path is not called by Gantry, but vulnerable build tools should not be selected. |
| Feedback crypto | PyNaCl already required 1.6.2+, which includes the libsodium fix for CVE-2025-69277. System-linked libsodium builds require separate vendor verification. |
| HTTP errors | Invalid input exceptions no longer echo their Python exception details to the client. |

Gantry does not extract tar/zip archives or configure server-side TLS/SNI callbacks.
That limits reachability of several recent standard-library advisories, but is not
a reason to retain an old interpreter. Customer runners may use those features.

## Update an installation

1. Back up the ledger and artifacts. Install a security-patched Python from a
   trusted distribution; update OS certificates and any TLS proxy separately.
   Distribution backports need vendor evidence, not just a version comparison.
2. Create a new virtual environment with that interpreter. Bootstrap pip using
   the wheel hash published by the Python security team:

   ```sh
   python3 -m venv .venv
   .venv/bin/python -m pip install 'pip @ https://files.pythonhosted.org/packages/3f/06/3e4420302363fbb71be3c7f35ce042f54bfca330e3e66b3a2e3c4cca579f/pip-26.2.2-py3-none-any.whl#sha256=fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70'
   .venv/bin/python -m pip install --upgrade --only-binary=:all: 'pip>=26.2.2' 'setuptools>=78.1.1'
   .venv/bin/python -m pip install .
   .venv/bin/python -m gantry.security_check
   ```

   For feedback, install PyNaCl from wheels before installing the extra:
   `.venv/bin/python -m pip install --only-binary=:all: 'PyNaCl>=1.6.2,<2'`.
   Update certifi/uv too if used in this environment. A standalone uv installation
   must be updated using its own trusted installation channel.
3. Restart the server and reload MCP clients against the new interpreter. Keep
   the original database/artifact location. Verify a read and checkpoint using
   synthetic data first. Do not automatically rerun interrupted engineering jobs.

The offline check prints only interpreter/package versions and findings. It reads
no project files or tokens and sends no telemetry. Exit 1 means an old or
unreviewed version; exit 0 means only that these dated version checks passed.
Missing optional packages are not installed automatically. It does not inspect
all environments, native libraries, standalone executables or the OS trust store.

## Dependency scanning and deployment

In a separate audit environment with patched pip, install `pip-audit` using
`--only-binary=:all:`. Audit the resolved public dependency versions, not private
project requirements. pip-audit sends package names/versions to an advisory
service; the offline baseline command does not. Record exact versions with each
release. The package has no mandatory third-party runtime dependencies.

Keep Node's supported release line patched for contributor tests. The CI template
requests the latest patch in each configured line. Public deployments still need
TLS, request/connection limits at the proxy, backups, and operational review.
Do not enable request decompression in front of the API/feedback receiver.

## Primary advisories

- [Python certificate incident and verified pip bootstrap](https://discuss.python.org/t/information-for-python-users-regarding-emudhra-emsign-ca-certificate-security-incident/109576/1)
- [Python 3.12.15 security fixes](https://www.python.org/downloads/release/python-31215/)
- [Python October release baselines](https://blog.python.org/2026/10/python-31022-31117/)
- [Python October 21 expedited releases](https://discuss.python.org/t/python-3-15-1-3-14-9-and-3-13-17-are-out/109595)
- [PHP October advisories](https://www.php.net/archive/2026.php)
- [Node October security release including Brotli](https://nodejs.org/en/blog/vulnerability/october-2026-security-releases)
- [Setuptools path traversal advisory](https://github.com/advisories/GHSA-5rjg-fvgr-3xxf)
- [PyNaCl release notes](https://pynacl.readthedocs.io/en/latest/)
