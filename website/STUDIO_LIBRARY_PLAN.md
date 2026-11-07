# Static Studio library compatibility update

The approved product implementation is commit `794da61`. This demo uses Addy
Osmani agent-skills revision `2686b620fc1fed2e8f60c704839c766b8594c6b6`.

Acceptance criteria, recorded before implementation:

- Structure / Files / Work / Requirements remain reachable at project and
  component scope. Files preview/download their saved bytes, compare a parent,
  and switch saved versions. Related shows explicit check links and relevant work.
- Requirements show revision-bound coverage, missing evidence and changed inputs.
  Shared context returns all mandatory requirements, constraints and omissions
  from the same state, with bounded related metadata and no file bodies.
- Project, component, file, mesh, code-line and requirement discussions retain
  their exact state/hash/revision in replies and Inbox links. Named invented
  humans and Crew agents retain stable principal IDs.
- Preserve the timing Inbox evidence, previous-version comparison, component
  camera, team creation/start separation and browser-memory reset behavior.
- No backend, model, uploads, real notifications or private data are introduced.

Implementation slices: fixture contract and regression tests; selective product
library UI integration; guide/showcase and cache-key update; tests and browser
review. Only `website/` is in scope. Parent handles commit and deployment.

Verification command: `node --test website/tests/*.test.mjs`. Preview:
`python3 -m http.server 8828 --bind 127.0.0.1 --directory website/public`.
Synthetic tests establish demo behavior only; runtime/browser observations are
recorded separately in the delivery notes.

Completed slices:

- [x] Invented saved-state library/context fixtures and exact discussion targets.
- [x] Product library UI integrated selectively; demo timing evidence and Team
  simulation retained. Work-to-library navigation retains its selected state.
- [x] Named participants, exact Inbox links, Shared context, guide and showcase.
- [x] Cache graph aligned; 25 tests passing and local in-app browser checks done.

Runtime evidence and demo limits are recorded in `website/README.md`. The initial
Chrome connector failed before page load; the background in-app browser succeeded.
No files outside `website/` were edited for this slice; no commit or deployment was
performed by the demo implementation agent.
