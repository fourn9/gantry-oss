# Gantry 2.0.2 — capture and authorization hardening

- Check committed Git snapshots and historical diffs for common credential patterns and sensitive filenames before upload. Bound snapshot sizes and require a commit-valued diff base.
- Enforce credential expiry and command restrictions before direct Python API GitHub sync, including cached responses.
- Validate feedback receipts against the actual encrypted envelope sent.

Validation: 271 Python cases (268 passed, 3 optional-dependency skips), 7 JavaScript tests passed. Regression tests include denied capture before upload, expired/restricted sync identities and mismatched upload receipts. The tested feedback dependencies have no known vulnerabilities in the release-time lookup.

No data migration is required and existing feedback consent is unchanged. This remains an early local-use preview, without an independent security audit, OS execution sandbox or native encryption at rest. GitHub Actions is not active; release checks ran locally. See [the publication review](https://github.com/fourn9/gantry-oss/blob/main/docs/SECURITY-REVIEW.md) for evidence and limitations.
