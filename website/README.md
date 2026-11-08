# Public website and demo

Editable static source for [gantryrobotics.org](https://gantryrobotics.org/).
`public/` is the complete web root: homepage, demo, news, shared assets and
Cloudflare Pages headers/redirects. There is no build or npm dependency.

## Preview and verify

From the repository root:

```sh
python3 -m http.server 8840 --bind 127.0.0.1 --directory website/public
node --test website/tests/*.test.mjs
```

Use Node.js 22 or newer. Open <http://localhost:8840/demo/workspace.html>.
Python does not apply Cloudflare headers or extensionless redirects.

## Studio navigation

Choose a component in the left hierarchy. Work shows **Changes / Verification**;
Files opens the full manifest at an exact saved state; Requirements shows recorded
requirements and coverage. Work and Files use the same saved bytes and hashes.
Viewers follow file formats, rather than categorizing all robot work as CAD/code.
The sample includes STL, Python, URDF, calibration YAML and measurement CSV.

The assembly below the hierarchy highlights explicitly mapped parts while a file
is open. Code may map to multiple parts; unknown mappings remain unhighlighted.
Select a mesh or use the part selector to navigate. Open 3D expands the assembly
in the centre; Back to file restores the existing file, comparison and draft.
Mesh parsing and total assembly geometry are bounded; unsupported native sources
must be downloaded or restored to external tools.

References and Discussion occupy a persistent right panel on desktop. Narrow
screens use a right drawer with focus containment, Escape and focus restoration.
Panel selection persists across files and views. Discussion targets remain pinned
to their original state/path/hash/line; changing a preview does not retarget a
reply. Drafts are scoped to their original target. Sidebar and desktop detail
separators support dragging and arrow keys.

Open Inbox's timing request: it restores `SETTLE_TIME = 0.15` → `0.25`, line 2,
the original shared state and conversation. Select the bracket or calibration in
the file picker to inspect the other changes. Verification links the exact sample
CSV, while full-motion clearance remains missing. Sharing never means verified.

## Data and agent boundaries

The anonymous demo uses invented, per-tab memory data in `demo-data.js` and
`demo-crew-model.js`. Reset or reload clears changes. It has no uploads, backend,
model calls, tool execution, live agents, or notifications to real teammates.
Alex Morgan and Sam Rivera are invented humans; Ari and Kai are sample agents.
Mentions record comments; they never execute agent work. Team setup separately
simulates Create and Start.

`studio_library`, `studio_related` and `studio_context` are bounded fixture reads.
Agent context keeps mandatory requirements, constraints and open questions, while
file bodies are fetched separately by snapshot/path/hash. Human views do not
require agents to ingest the entire UI or all file bodies. Shared context and
Restore / continue remain under the Files menu; sample state IDs cannot be
restored using a real server.

The authenticated product lives in `gantry/web/`. The public reference and the
OSS runtime have separate adapters. Issues #22 and #23 track runtime integration;
this website update is not evidence that live integrations are implemented.
Never copy private ledgers, credentials, local configuration or customer files
into this public tree.

## Deploy

Upload the **contents** of `website/public/` to the existing Cloudflare Pages
project. ZIP root must contain `index.html`, `demo/`, `_headers`, and `_redirects`.
Merging GitHub does not deploy this site. Roll back using the prior Pages deployment
or the archived prior web root. No data migration is involved.

Keep module and entry-point cache revisions consistent. The spatial UI uses
`spatial-20261108`. Before deployment, check the public baseline has not advanced;
after deployment compare published bytes and exercise a critical flow.

## Verification record

See `tasks/studio-spatial-work.md` for acceptance and evidence. Unit/fixture tests
cover immutable anchors, scoped changes, explicit spatial mappings, evidence links,
visitor isolation, escaping, version sharing, and camera bounds. Browser checks
cover real DOM interaction and responsive layouts. Neither establishes real
engineering correctness, physical verification, agent autonomy or live collaboration.
