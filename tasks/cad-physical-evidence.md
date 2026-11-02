# CAD and physical evidence integration

Addy Osmani agent-skills revision: 2686b620fc1fed2e8f60c704839c766b8594c6b6.
Public base: 677237c; unrelated local development remains separate.

Scope: customer-local CadQuery STEP read/edit/write via bounded declarative JSON;
existing cad_screen interference checks; physical result ingestion against frozen
criteria with original reports, input hashes, evaluator/environment and limitations.
Reuse immutable snapshots, engineering declarations, change checkpoints, Mentor
review gating and existing authenticated API. No new model service or CAD credentials.

Build order: CAD adapter -> evidence evaluator -> checkpoint publisher -> end-to-end.
- [ ] CAD reads STEP, applies explicit translate/cut/fuse or box/cylinder operations,
  writes STEP into a new directory; rejects stale input, invalid shape, path escape.
  Never execute uploaded Python. Do not claim preservation of original CAD feature tree.
- [ ] Evaluate numeric interference/strength/tolerance/prototype observations using
  explicit units and fixed criteria. Missing/failed/stale results cannot pass.
  Bind material/load/boundary conditions, evaluator version and original report.
- [ ] Save candidate files, operation/result reports and engineering declarations in
  a new immutable checkpoint. Previous state and checks preserved; no auto-adoption.
  Mentor sees checks and blocks OK for required failed/unknown/unverified checks.
- [ ] Test real CadQuery geometry and real Core round trip, invalidation, replay,
  scope, rerun conflicts. Document precise support and non-certification limitations.

Trust boundaries: untrusted JSON, CAD native parser, external solver reports, paths,
API credentials. Native CAD computation runs only on customer runner, not HTTP server.
Use bounded input, no eval/shell, new output directories and existing permission checks.
No cloud API credentials, paid use, fabrication or physical actuation in this task.
