# Studio Bot workflow verification

Verified 2026-11-04 against base revision
`321f77989600a61c66a18a3033730e2f2b9b8c19` plus the uncommitted Studio Bot workflow
and concurrent guided-onboarding changes. No public release is implied.

## Automated evidence

- Integrated Python suite: 1,310 tests, passed; 8 existing environment-dependent
  skips (145.023 seconds).
- Integrated Node UI suite: 39 tests, passed; no skips.
- After correcting the Ask working-memory command allowlist, Studio Bot and
  continuity regression suites: 120 tests, passed (12.000 seconds).
- Clean-source wheel built offline with `pip wheel --no-deps --no-build-isolation
  --no-index`. New Python modules and browser assets are included; package imports
  pass from an extracted wheel outside the source checkout.
- Existing local ledger backed up before restart; hash verification and replay
  succeed. Schema additions are additive and preserve existing data.

## Actual execution paths

| Scenario | Observed result |
| --- | --- |
| Exact-version Ask | Original state/selection arrives in worker context; answer returns to its conversation and Inbox |
| Direct API bypass during Ask | Delegation, design mutation and stopping other tasks rejected; own working memory and recovery remain available |
| Scoped assignment | Saved file edit produces a separate shared candidate; original work remains unchanged |
| Handoff | Old task fence invalidated; stop acknowledgment required; new executor accepts; saved edits, unfinished context and dependency successors retained |
| Restart | Persisted request and ledger reopen before a customer worker retrieves and completes the task |
| Parallel candidates | Two independent workers overlap; manager receives their reports and selects/integrates a candidate; Studio receives its actual baseline diff |
| No accidental dispatch | Ordinary comments, mentions, Team inspection and selection do not create Bot tasks |
| No accidental adoption | Shared/completed candidate remains unadopted and unverified unless separate evidence/decisions exist |
| Owner boundary | Unauthorized team edits, stale configuration, scope expansion and human-principal Bot requests rejected |

The external-command scenario uses an actual HTTP client, local BotWorker and
separate Python process to edit and check saved files. Inference responses and
candidate selection in these tests are deterministic fixtures. They establish
transport, persistence, ownership and result handling, not model reasoning quality.

## Browser evidence

An anonymous project was tested through the real UI and HTTP server:

1. Open Team; inspect hierarchy/scope/offline presence; rename a member without
   replacing its Bot ID.
2. Select a code line; queue Ask while offline; start its worker; receive the
   answer on the exact selection and navigate from Inbox back to it.
3. Assign a scoped edit; hand off to another eligible Bot; acknowledge the stopped
   source; accept through the target worker; execute the file change/check.
4. Open the returned candidate and compare the saved before/after contents.
5. At 390 × 844, conversation and artifact remain accessible without overlapping
   controls; closing the conversation returns to artifact viewing.

The upgraded main local preview was also signed into through the browser: existing
project structure loaded, Team opened with an honest unconfigured state, and no
console errors were reported. No Bot credentials or permissions were added to that
workspace for this smoke check.

Screenshots, fixture ledger, HTTP execution evidence and backup are retained in
the private verification workspace, not in public source. Private credentials,
project history and customer designs are excluded from the repository.

## Explicit limits

- Native licensed CAD operation and live Codex/Claude model reasoning were not
  exercised by this verification. Existing customer backends are reused.
- Customer runtimes require their existing login/bridge, authorized principal and
  registered manifest. Browsing Team does not install or start them.
- Ask is enforced on Gantry-managed writes. A customer bridge is a trusted local
  process, not an OS sandbox. Remote process termination requires an explicit
  acknowledgment; invalidating a ledger fence cannot stop external software.
- No paid inference, physical action or automatic public deployment occurred.
- No development-time speedup is inferred from these functional tests.

See [workflow and setup](STUDIO_BOT_WORKFLOW.md).
