# Design change loop verification

Local feature-branch verification, 2026-11-03. These results do not publish a new
release or claim general robot-design autonomy.

## Actual model and native CAD

Environment: Python 3.12.15, CadQuery 2.8.0, macOS arm64, `macos-seatbelt` sandbox.
The real HTTP Core and customer BotWorker used official Codex with ChatGPT login,
model `gpt-6-astra`, reasoning `low`. No mock inference, mock geometry or API-key
fallback was used in the successful live run.

| Step | Observed outcome |
| --- | --- |
| Import existing failed state | Two real 10 mm solids overlap at a 5 mm center offset; frozen requirement is unmet. |
| First Bot task | Model chose carrier position 15 mm and command target 15 mm, ran the unchanged verifier and published the report. |
| Native result | Intersection 0 mm³, clearance 5 mm, position 15 mm within [11,20], command error 0 mm. Linked requirement became `met`. |
| Saved-state continuation | Another worker/journal restored the candidate; operator changed the calibration offset from 0 to +1 mm. |
| Evidence invalidation | Previous requirement coverage changed from `met` to `unverified`; stale evidence remained in history. |
| Second fresh Bot task | Model chose target 14 mm for the unchanged 15 mm carrier, reran native verification and published the report. Coverage returned to `met`. |
| Record/replay | Actions, reports and candidate states persisted; event replay matched over 81 prior events. Both outputs remained unadopted. |

Nine actual model calls: five actions in the first task, four in the second.
Worker-observed task durations were 45.271 s and 33.575 s. These include model,
tool and ledger operations within each task, but exclude setup. They are functional
observations, not a paired speedup benchmark or a claim about whole-product design.

The final assessment stayed `needs_review`: independent physical certification,
unsaved edits and complete dependency maps were not acquired. Only the explicit
static/interface criteria passed. The model preserved these limits in its reports.

Manual actions were fixture/requirement/tool setup, task assignment and the calibration
perturbation. Corrections, local tool invocation and evidence publication were chosen
by the model. The harness performed transport, capture, scope/version checks and
threshold comparison. Mentor was not required for these Crew tasks.

## Problems found during verification

- A virtualenv CAD tool could not read its own `pyvenv.cfg` in the existing sandbox.
  Adding `sys.prefix` to the explicit approved read-only runtime fixed import; old
  manifests require reapproval. Network and host-credential access remain denied.
- A first example run completed the first CAD correction but used the restore bundle
  directory rather than its `workspace` for the next checkpoint. Core rejected the
  out-of-scope paths. The example was fixed and the full two-task run was repeated;
  the preliminary ledger and calls were retained privately.
- Broader regression tests exposed imported sessions whose parent is in another
  session. Mentor now compares from the new session's imported baseline rather than
  implicitly crossing that boundary.
- Independent review found old dependency results could be reused, stale native
  sources could describe a new map, map changes did not invalidate Mentor inputs,
  and nested previews could grow without a limit. These received targeted fixes
  and regression cases. Partial assessment previews cannot pass the Mentor OK gate.

## Automated evidence

Targeted tests cover cumulative multi-checkpoint diffs, requirement revisions,
removed checks, cross-session refusal, changed dependency inputs, stale map sources,
Mentor fingerprint invalidation, report/replay preservation, partial previews and
reasoned not-applicable checks. A real action-loop regression edits a plan, checkpoints
it, then tries to publish; the task is held with `stale_basis`. A separate test starts
new work from the reassessed plan and can publish successfully.

Final automated results:

- Full Python regression: 1,136 executed tests, no failures, 8 optional skips;
  127.312 seconds. Counts include inherited fixture tests.
- Focused assessment/review/baseline suite: 66 passed after final review fixes.
- Native CadQuery suite in the separate CAD runtime: 5 passed.
- JavaScript regressions: 9 passed.
- Wheel built with `pip wheel --no-deps --no-build-isolation`; source contains no
  new mandatory third-party dependency. The `python -m build` frontend was not
  installed in the test venv, so the existing pip/setuptools build path was used.
- Wheel-only import, Core bootstrap/verify and new API contract smoke checks passed.
- Independent read-only review and `git diff --check` completed.

The first broad regression run found imported-session comparison failures and a
legacy test fixture that prepared its acceptance plan inside the change under
review. The session baseline logic was corrected; the fixture now starts work
from the saved plan. The successful full regression above includes these fixes.

No private project assets, credentials or raw model journals are included here.
