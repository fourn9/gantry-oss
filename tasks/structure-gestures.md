# Direct manipulation of product structure

Follow Addy Osmani frontend/incremental/test/review workflow at reviewed revision
2686b620fc1fed2e8f60c704839c766b8594c6b6. Publication explicitly requested.

## Acceptance
- Show recorded product hierarchy, with all roots and descendants, without turning it into change history.
- Trackpad pinch zooms around the cursor (ctrl-wheel; Safari gesture events).
- Mouse drag and two-finger scroll pan without scroll bounds. Primary touch can pan; buttons provide touch zoom.
- A card click opens its scoped work; a drag does not accidentally select it.
- Fit all, 100%, keyboard zoom/pan remain available. Camera stays centered when inspector width changes.
- Sidebar and detail panes can be resized within bounds; narrow layouts stack details.
- Teardown removes camera handlers and observers. No data, authentication, execution or adoption semantics change.
- Product and public demo share camera/layout modules; demo remains anonymous and browser-only.

## Verification
Pending final browser and publication checks. Synthetic wheel/Safari gesture tests
are separate from physical trackpad testing. No claim of native hardware gesture
verification or live CAD/model execution.

## Checked before publication
- 50 product JavaScript tests and 18 public demo tests passed.
- Four HTTP/web tests passed, including static delivery under existing CSP.
- Independent review identified and verified fixes for stale mouse drags,
  conversation-handle remounts and touch navigation after zoom.
- Actual browser: mouse drag, wheel pan without page scroll, card drag without
  selection, card click/details, Fit all and inspector recentering passed.
- Showcase still renders the hierarchy; existing demo version/comment/setup tests pass.
- Physical trackpad pinch and mobile touch hardware were not exercised. Their
  input paths have synthetic event tests; no hardware-wide compatibility claim.
- Changed public files scanned for private project names, local paths and common
  secret patterns. No private project data or credentials are part of this patch.
