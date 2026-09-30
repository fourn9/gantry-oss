# Encrypted, consent-based feedback

Feedback is optional and does not affect features. `gantry init` asks a terminal user to choose:

- **No feedback** (default).
- **Statistics**: API operation counts, coarse latency and failure categories.
- **Statistics + selected diagnostics**: the above and only diagnostic text files explicitly selected for a particular report.

Noninteractive initialization defaults to off; an operator can explicitly use `init --feedback diagnostics`. Existing installations can run `gantry feedback configure --mode diagnostics --data .gantry`. `feedback configure --mode off` withdraws future sharing and deletes local aggregate counts. The application never grants consent through MCP or a remote API. An agent with unrestricted local shell access can act as the OS user; this CLI cannot distinguish it from a human at the keyboard.

There is no automatic background collection of logs and no background upload. The receiver accepts uploads automatically **after the user confirms a report**. No public receiver is preconfigured in the package.

## User workflow

Install the maintained libsodium binding used for sealed-box encryption:

```sh
python -m pip install '.[feedback]'
```

Run this inside the verified Gantry checkout. For a downloaded release wheel, specify its local path followed by `[feedback]`. No PyPI package publication is implied.

Obtain `recipient.json` and an invitation token file from your intended recipient over a trusted channel. Independently check the recipient's HTTPS URL and public-key SHA-256 fingerprint. The recipient can decrypt the report; encryption is not anonymity or a promise that the recipient cannot read it.

```sh
gantry feedback prepare --data .gantry --recipient recipient.json \
  --log selected-error.log --output feedback-preview.json
```

`--log` is optional, repeatable up to five files, and requires diagnostics consent. Files must be UTF-8 `.log`/`.txt`, at most 128 KiB each, regular and not symlinks. The preview uses neutral labels instead of original filenames. Common tokens, authorization fields, URLs, emails and home-directory paths are redacted. **Redaction is incomplete**: arbitrary code, CAD details, prompts, encoded secrets or project names may remain in logs. Inspect and remove them manually. The preview is plaintext with owner-only permissions; protect or delete it after use.

After inspecting the entire preview, confirm its exact SHA-256 (recompute it if you edited the file):

```sh
gantry feedback send --data .gantry --preview feedback-preview.json \
  --confirm-sha256 REVIEWED_FILE_SHA256 --output report.sealed.json \
  --upload-token-file invite.token
```

The command encrypts to the preview's pinned recipient public key, then uploads over HTTPS (HTTP is accepted only for loopback testing). HTTP redirects are rejected. Recheck the recipient URL and key after any preview edit. `feedback seal` with the same preview/hash/output options creates an encrypted file without uploading. An uncertain network outcome is not automatically retried: retain the encrypted file and contact the recipient. Each upload has a receipt derived from its encrypted bytes; identical envelope reuploads are deduplicated.

Neither statistics nor the envelope contain an installation ID, email or account name. Selected diagnostic text and network metadata may identify someone; do not call the whole submission anonymous. Gantry does not authenticate the report author's identity. The sealed-box format proves ciphertext integrity to the recipient, not the sender's identity.

## Recipient/maintainer setup

On an **offline or separately secured operator machine**, generate a key pair:

```sh
gantry feedback keygen --private-key recipient-private.key --recipient recipient.json \
  --url https://feedback.example.org/v1/feedback
```

Replace the example domain with your actual domain. Store and back up the private key in a restricted secret store; never commit it or place it on the online receiver. The generated private key file is owner-only but not encrypted at rest by Gantry. Publish the public recipient configuration and its fingerprint through a trusted release channel.

On the receiver host, generate a strong invitation token, keep it mode 600, and provide it only to pilot users through a private channel. Rotate it by changing the file and restarting the receiver. It is an anti-abuse gate, not individual identity tracking.

```sh
gantry feedback receive --directory /var/lib/gantry-feedback \
  --upload-token-file /etc/gantry-feedback/invite.token \
  --key-id PUBLIC_KEY_SHA256 --port 8780
```

It binds to loopback and requires a TLS proxy for remote access. Example Caddy and systemd templates are in `deploy/feedback/`. Provision an unprivileged account, writable private inbox, a read-only Gantry installation, domain/TLS, `receiver.env` containing `GANTRY_FEEDBACK_KEY_ID`, edge connection/rate limits, monitoring and disk limits. Do not store the private decryption key there.

The receiver accepts at most 2 MiB per request and 30 requests/minute globally, with a 100 MiB inbox cap. It does not expose downloads, render logs, decrypt data or run models. Files expire after 30 days; cleanup runs every minute while running and on restart. Backups and offline copies require a separate deletion policy. An operator can delete the file corresponding to a user's receipt on request. Proxies/cloud providers can see connection metadata: disable unnecessary access logging and document any retained metadata.

Offline, decrypt a received envelope with:

```sh
gantry feedback decrypt --private-key recipient-private.key \
  --input received.sealed.json --output reviewed-report.json
```

Treat decrypted text as untrusted input. Do not execute it, render active HTML or automatically feed it into a privileged agent. Delete raw reports after triage (within 30 days) and retain only necessary non-identifying aggregate findings. Received deletion requests must cover operator copies as well as the inbox.

The provided receiver is a bounded pilot component, not a deployed cloud service or an externally audited Internet endpoint. Do not open it publicly without provisioning the surrounding controls.
