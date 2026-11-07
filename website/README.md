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

## Structure navigation

In the sample workspace's Structure tab, pinch the trackpad to zoom, drag the
map or scroll with two fingers to pan, and click a component to inspect its work.
Fit all restores the complete hierarchy. Zoom buttons and arrow / + / - / 0 keys
remain available; touch users can drag the map and use zoom buttons.
Sidebar and desktop detail dividers can be dragged or adjusted with arrow keys.

## Files, requirements and shared context

The static demo includes project and component Files / Requirements tabs from the
approved Studio library UI. Select an exact saved state, preview/download a file,
compare its parent, or open Related to follow declared check and requirement links.
Shared context displays the same mandatory requirements, constraints, open
questions and capture omissions returned by the in-memory `studio_context` read.
It includes no file bodies and makes no model request.

Use the second Inbox sample to open `settling-time` at `timing-r1`. Project,
component, file, mesh, code-line and requirement discussions keep their original
state and anchor. Choose Alex Morgan in the mention picker to create a local Inbox
entry. Alex Morgan and Sam Rivera are invented humans; Ari and Kai are invented
Crew agents. Their stable IDs remain `designer`, `mechanical-reviewer`,
`design-agent` and `controls-agent`. Ask/Assign are unavailable in this demo;
mentions never start agent work. The existing Team setup has its own explicitly
labelled simulation and still separates creation from starting.

`demo-library.js` supplies the three library reads without a backend. It validates
project/state/anchor identity, uses bounded file/work/message pages, and preserves
all mandatory requirements even when related records are limited. The public
fixture is deliberately small; this is not a benchmark or an authorization test
of the authenticated product. The Restore panel shows an example command; invented
demo state IDs cannot be restored by a real Gantry server.

The demo module graph, workspace/showcase entry points and homepage imports of
Studio assets use `library-20261107`. The original timing Inbox request, prepared
edit/import/share flow, team setup and structure-camera controls are preserved.

### Verification for this update

- `node --test website/tests/*.test.mjs`: 25 passing tests. New checks cover exact
  states and scopes, requirement/file relations, mandatory context with pagination,
  all discussion anchors, rejected retargeting, invalid/reset states, escaping,
  message history merging and import/cache consistency.
- In-app browser runtime: saved mesh and code preview, exact line comment and
  named mention, Inbox return, requirement revision discussion, Shared context,
  file-to-requirement Related link, parent comparison, saved-state selection and
  the original timing review (`0.15` → `0.25`, selected line 2) worked.
- Library layouts were inspected at 320, 390, 768, 1024 and 1440 CSS pixels;
  horizontal document width matched each tested viewport after fixing compact
  toolbar overflow. Related/discussion stacks below the artifact on narrow views.
- The feature overview rendered the new Files and Requirements excerpts; browser
  console inspection reported no warning/error entries during these flows.

These are local demo observations, separate from live model, connector, worker,
physical-verification or deployment evidence. No paid model, external tool or real
collaboration service was invoked.
