# Privacy and optional feedback

The default local service does not send development records or usage statistics to the maintainer. Your configured agents, inference providers, GitHub connector and external tools may communicate with their respective services. Decide what data they can access before connecting them.

`gantry usage enable` opts into local aggregation. It records known API operation names, coarse latency buckets, outcome categories and counts. Local aggregate rows expire after 30 days. Export includes the schema version, Gantry version and those counts. It excludes dates, user/project identifiers, paths, code, CAD content, prompts, tokens and error text. Enabling statistics does not enable transmission.

`gantry usage export --output usage-preview.json` creates a file for inspection. Share it manually only if you choose. Operation counts can still reveal aspects of a workflow; review the file first. `usage disable` stops collection and deletes local aggregates. It cannot delete copies you have exported or shared.

Maintainers can run `gantry usage summarize --input report1.json report2.json` on voluntary reports. These are aggregate invocation counts, not unique-user metrics or proof of development-time savings. Duplicate exports are not deduplicated. GitHub issues and their attachments are public: prefer synthetic reproductions.

## Encrypted diagnostics

First-run consent now distinguishes off, statistics, and statistics plus individually selected diagnostic logs. Every upload requires an exact preview hash confirmation. The recipient, its public-key fingerprint and its URL are visible in that preview. Logs are never discovered/uploaded automatically. Their contents are not guaranteed anonymous or fully redacted.

The optional receiver stores only encrypted envelopes, with 30-day retention while running and deletion on restart for expired files. It has no decryption key. Recipient operators are responsible for protecting their offline key, deleting decrypted copies within the stated period, honoring deletion requests by receipt, and disclosing proxy/network metadata handling. There is no default public receiver or usage identity tracking. See [the full consent and sharing flow](FEEDBACK.md).
