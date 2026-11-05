# Public website and demo

Editable static source for [gantryrobotics.org](https://gantryrobotics.org/).
`public/` is the complete web root: homepage, demo, news, shared assets and
Cloudflare Pages headers/redirects. There is no compilation step or npm dependency.

## Preview

From the repository root, with Python 3 and a modern browser:

```sh
python3 -m http.server 8828 --bind 127.0.0.1 --directory website/public
```

Open <http://localhost:8828/> or
<http://localhost:8828/demo/workspace.html#studio-inbox>.
Use the `.html` workspace URL locally; Cloudflare serves the extensionless URL.
Python's preview server does not apply Cloudflare `_headers` or `_redirects`.

## Verify

With Node.js 22 or newer, from the repository root:

```sh
node --test website/tests/*.test.mjs
```

The demo regression suite covers isolated/resettable visitors, version-bound
conversations, request-specific evidence, explicit earlier comparisons, reply
anchors, escaped text, scope restrictions and separate team creation/start.
These deterministic tests are not evidence of live agent execution.

For browser review, open Inbox and select the timing request. Code opens with
`SETTLE_TIME = 0.15` → `0.25` and line 2 selected. Switch to CAD to inspect the
related sensor bracket, then back to Code. The original changed line remains
selected. Replies refer to that line and saved version. On a narrow screen,
the evidence appears before the conversation.

## Deploy

Deploy the **contents** of `website/public/` to the existing Cloudflare Pages
project. For a manual ZIP upload, create the archive from inside that directory
so `index.html`, `demo/`, `_headers` and `_redirects` sit at its root.
A GitHub merge does not itself deploy this website. Revert a source commit or
restore a known prior Pages deployment to roll back.

After changes, run the tests, inspect desktop/narrow layouts and verify the
published files. Keep the version query strings on module imports and entry
points consistent when updating the demo's module graph.

## Demo and runtime boundaries

`public/demo/demo-data.js` and `demo-crew-model.js` supply invented data held
only in browser memory. Reload or Reset clears edits. The demo does not upload
project files, call models, connect external tools, dispatch agents, or notify
real teammates. Sharing and replying never imply verification or formal adoption.

The authenticated product lives in `gantry/web/` and uses the Gantry service.
The demo has deliberate navigation, fixture and interaction differences. Review
changes selectively; do not overwrite either implementation with the other.
Do not copy private ledgers, local configuration, credentials, customer assets
or runtime journals into this directory.
