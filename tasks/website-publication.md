# Public website source publication

Request: publish the implemented website/demo on GitHub as well as Cloudflare.
Source: reviewed static website revision d822261. Workflow reference:
addyosmani/agent-skills 2686b620fc1fed2e8f60c704839c766b8594c6b6,
using-agent-skills and git-workflow-and-versioning.

Acceptance criteria:
- Preserve the already published HTML, assets and request-specific evidence behavior.
- Track editable static source under website/public and its existing tests under website/tests.
- Document local preview, validation, deployment root, demo limitations and synchronization rules.
- Include only public site assets and anonymous fixtures; exclude local task logs, screenshots,
  deployment archives, credentials and private project data.
- Verify all published files are unchanged by the move, run demo regressions and check imports.
- Publish through a focused PR and merge without overwriting concurrent repository work.

This is source publication of the existing browser-only demo, not a Python package
release or a port of the simulated behavior into the authenticated Studio runtime.

## Validation — 2026-11-06

- All 61 static files are byte-identical to the reviewed website source d822261.
- Eight public responses (homepage, demo entrypoints and changed modules) match
  the copied files byte-for-byte. Existing desktop/mobile interaction verification
  applies to these unchanged files: Inbox → code diff → CAD → code → reply.
- All 16 demo regressions pass from the new directory; only their import prefix
  changed from ../dist/ to ../public/.
- Every JavaScript module passed node --check and local imports resolve.
- Publication scan found no local user paths, private-key blocks or common
  credential patterns. Only tracked public source/assets and tests were copied.
- No runtime Python files or authenticated Studio modules changed.
