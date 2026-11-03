# Shared workspace deployment and membership

Gantry's API/Studio and stored shared state run on a customer-operated Linux host.
CAD, editors, evaluators, agent applications and their model credentials run on
customer PCs. The host does not run uploaded scripts or start paid inference.
This is a single-host deployment recipe, not a hosted SaaS subscription or an
assertion that a cloud account has been provisioned.

## Install and provision

Use a supported, security-patched Python >=3.11, a dedicated `gantry` system user,
and a private local disk (not a network-mounted SQLite database). Install a
reviewed wheel into a version-specific virtual environment under `/opt/gantry`,
then point `/opt/gantry/current` to it. Keep the preceding environment for rollback.
Install Caddy through its official package channel and validate the configuration
before starting it. No installation script is executed by Gantry.

```sh
sudo install -d -o gantry -g gantry -m 700 /var/lib/gantry/workspaces
sudo -u gantry /opt/gantry/current/bin/gantry-cloud provision \
  --root /var/lib/gantry/workspaces --workspace team --owner owner
```

The result contains the workspace ID and owner token **file path**, not the token.
Transfer that file privately to the owner; do not copy it into source, images,
public demo assets or a URL. Store its recovery copy separately from backups.
Provisioning refuses an existing workspace. The server never accepts anonymous
workspace creation. Optional feedback remains off.

Install `deploy/cloud/gantry.service` under systemd and copy its Caddyfile into
Caddy's configuration. Set `GANTRY_DOMAIN` in Caddy's service environment to a
dedicated hostname with correct DNS. Validate with `caddy validate --config ...`
and `systemd-analyze verify ...`. Then start Gantry and Caddy. Open only HTTPS/HTTP
(for certificate issuance) at the firewall; port 8770 stays loopback-only.
The workspace URL is `https://APP_HOST/w/team/`. Never expose Python's API port
on the public interface or reuse `gantryrobotics.org/demo/` as a data service.

The API already bounds request bodies, authenticates before large uploads, rejects
cross-origin writes and records no request bodies/Authorization headers. Caddy
adds TLS and Host routing. Put public deployments behind an edge with per-client
request/connection limits; the built-in authentication limiter is single-process
and sees the proxy address. The deployment is intended initially for invited teams
behind a VPN/access gateway. It is **not** an unqualified internet-wide multi-tenant
security certification. Operating-system patches, disk encryption, capacity limits,
DNS, certificates and edge monitoring remain operator responsibilities.

Caddy behavior follows its [request body](https://caddyserver.com/docs/caddyfile/directives/request_body)
and [reverse proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
contracts. Runtime acceptance on the target Linux/TLS environment is required;
local macOS tests do not verify systemd or public certificates.

## Invite a member without exchanging their private token

The owner runs `gantry-cloud --url URL --token-file OWNER_TOKEN members` and sends
only the workspace URL and returned `ledger_id` to the intended recipient.
The recipient creates their credential on their own device:

```sh
gantry-cloud request --member alex --ledger-id LEDGER_ID \
  --role contributor --zone root \
  --output-token ./private/alex.token --output-request ./access-request.json
```

Only `access-request.json` and its fingerprint go to the owner through an existing
trusted channel. No email address is required or automatically sent. The request
expires after 24 hours. The private token is never included in it. This is a
request-and-grant onboarding flow, not email verification or SSO.

The owner inspects the requested identity, role, zones and fingerprint. Use
`members` to select session IDs and exact versions, then preview:

```sh
gantry-cloud --url URL --token-file OWNER_TOKEN grant \
  --request access-request.json --fingerprint REVIEWED_FINGERPRINT \
  --session SESSION_ID:VERSION --reason 'Reviewed team membership'
```

Repeat that exact command with `--apply` to grant. This is an explicit human
permission decision. It atomically uses existing principal proposal, owner
endorsement, human approval and commit rules, then adds only selected sessions.
Other owners' policy conditions, conflicts or required validations are not bypassed;
if they block the convenience command, use the full proposal review path described
in [ADMIN-AGENTS.md](ADMIN-AGENTS.md). Existing scopes, recipes and running workers
are preserved. No administrator role is available in this convenience path.

Roles: `reader`, `contributor`, `agent-developer`, `agent-reviewer`, `agent-bot`.
Agent roles keep an explicit command allowlist and cannot approve membership or
formally adopt designs. Reviewer/Bot organization roles still require their normal
review-team/organization setup; granting a token does not manufacture those roles.
Optional `--expires-at EPOCH_MILLISECONDS` expires the activated credential.

A member logs into Studio with their local token, or passes `--token-file` to CLI.
For agent applications, use `gantry agent-config` with the matching profile. Their
token is not an owner token. Select a shared state and use `workspace continue` to
create independent work. Sharing, successful checks and adoption remain separate.

A zone is an artifact trust boundary. Session membership limits development
operations, but does not give per-file secrecy inside the same zone. Use separate
workspaces for mutually untrusted teams.

Revoke using the exact current member revision returned by `members`:

```sh
gantry-cloud --url URL --token-file OWNER_TOKEN revoke \
  --member alex --revision REVISION_ID --reason 'Collaboration ended'
```

Revocation is audited and rejects subsequent API calls; it cannot erase bytes
already downloaded or immediately terminate an offline CAD process. Use existing
reviewed principal changes for token rotation and owner/admin changes.

## Back up, restore and roll back

```sh
gantry-cloud backup --data /var/lib/gantry/workspaces/team \
  --destination /private-backups/team-SNAPSHOT
gantry-cloud restore --source /private-backups/team-SNAPSHOT \
  --root /private-restore-check --workspace team
```

Backup uses SQLite's consistent online backup and then copies only immutable blobs
referenced by that database. It checks blob hashes, event hashes and event-replayed
state against the saved projection. Restore repeats those checks before publishing
a new directory. Existing destinations are never overwritten. Raw owner tokens,
provider credentials, feedback logs and unrelated local files are excluded. Backups
contain sensitive project bytes and credential hashes: encrypt storage, restrict
access, set retention and keep a trusted checkpoint copy separately. Hashes do not
authenticate a backup against an attacker who replaces both backup and manifest.

Test a restored workspace under a separate root and port with retained credentials.
Confirm an exact artifact download and `replay`, not just a successful process start.
For a bad release: stop the service, preserve the current directory, switch the
`current` environment symlink to the known-good package, and restart only if that
package supports the saved schema. Otherwise restore the pre-upgrade backup to a
new root and explicitly account for post-backup events. Do not delete the newer
ledger or silently discard work. Record RPO/RTO from your measured recovery drill.

Monitor loopback `/health`, authentication/error rates, free disk, process memory,
request duration and backup age. Alert before the disk fills. `/health` proves the
API process responds; `backup`/restore drills verify data recoverability. No blanket
availability or engineering-speed improvement is claimed by this package.
