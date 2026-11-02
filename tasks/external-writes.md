# Scoped native writes

Addy Osmani agent-skills reviewed revision: 2686b620fc1fed2e8f60c704839c766b8594c6b6.
Apply specification, planning, TDD, incremental implementation, interface design,
security and code review. User authorized local implementation and contract tests;
no live accounts exist. Keep this side branch isolated and do not publish it.

## Objective and acceptance

Extend the read/capture integration slice to explicit native updates of existing
objects. No delete, permissions changes, arbitrary HTTP, bulk edits or remote execution.
API credentials are supplied separately for each invocation, never included in plans.

1. `prepare-write` reads the selected object and saves an immutable plan, exact
   update, source identity, baseline, reason and requirement links. It never writes remotely.
2. `apply-write` requires the exact plan digest, rereads the baseline, uses provider
   concurrency controls where documented, writes once and reads the object back.
   APIs lacking atomic conditions require explicit `--allow-nonatomic` acknowledgement.
3. Durable local journal claims the plan before dispatch. A retry cannot dispatch
   again. Unknown outcomes may only be reconciled by reading; no exactly-once claim
   across devices/independent journals. Concurrent callers serialize per operation.
4. Before/after raw responses, request, observed revision and outcome become a normal
   capture bundle for existing immutable Core publication and requirement context.
   Matching requested fields is write verification, not engineering acceptance/adoption.
5. Failed, unconfirmed, conflict and readback-mismatch outcomes remain distinguishable.
   External content cannot authorize writes; path/host/body bounds and credential
   scanning apply before dispatch as well as to persisted evidence.
6. Native write coverage: GitHub issue and existing repository file; GitLab existing
   repository file; Confluence page; Jira/Linear issue; Notion paragraph; Sheets/Excel
   rectangular values; Drive/SharePoint metadata (not file-body replacement);
   Slack existing message; Onshape existing feature's named parameter expressions.
   The other catalog entries remain explicitly unsupported for native writing.

## Plan / task list

- [ ] GitHub file vertical slice: plan, conditional write, verification and durable retry.
- [ ] Remaining provider recipes with strict native targets and selected fields.
- [ ] CLI + evidence publication roundtrip; no silent pass/adoption.
- [ ] Security/negative cases, full tests, build, capability and usage documentation.

## Threat boundaries and limitations

Local operator controls CLI and credential scopes. A checksum detects changes but is
not a user signature or a substitute for provider authorization. No public write endpoint
is added. Provider ACLs remain authoritative; remote content is data, never instructions.
Journal should live on durable owner-controlled storage. Same-user malicious processes
and deliberate copying of plans/journals are outside the local process trust boundary.
No OAuth onboarding, continuous sync or licensed desktop SDK automation in this slice.
No live remote mutation, paid service, customer data or parent checkout change.

Commands: `python -m unittest discover -s tests -p 'test_external*.py' -v`;
`python -m unittest discover -s tests -p 'test_*.py' -q`; `python -m build --wheel`.
