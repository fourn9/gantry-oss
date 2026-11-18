# Reflection path contract correction

Addy agent-skills revision: 2686b620fc1fed2e8f60c704839c766b8594c6b6.
Workflow: using-agent-skills, debugging-and-error-recovery, test-driven-development.

Observed defect: a real reflection described an unexecuted verification accurately,
but attached its future report filename as if bytes existed in the saved state.
Core correctly rejected this. The reflection input did not explain path evidence
or provide the saved path manifest; the schema offered no typed unresolved path.

Acceptance (before implementation):
- Reflection input identifies the exact saved state and a bounded existing-path/hash manifest.
- `paths` remains strict: every path must exist in that saved state; no synthetic file or silent omission.
- An optional `unresolved_paths` field retains future or uncaptured references explicitly as non-evidence.
- Unresolved paths cannot overlap saved files, escape the workspace, or grant permissions/proof.
- Existing reflection payloads remain valid. Replay preserves typed unresolved references.
- A rejected reflection remains locally held while another Bot can complete normal work.
- Required reviews, actual verification evidence and original failed receipts remain intact.

This slice does not change the experiment's acceptance/scoring or automatically retry uncertain provider effects.

Implemented:
- Read packet lists up to 200 path/hash entries with total/truncation metadata.
- Optional, nullable `unresolved_paths` preserves planned/not-captured filenames and reasons;
  present/unsafe/duplicate references are rejected. These paths never enter input hashes.
- Recall adds `unresolved_path_references` and disallows direct apply until rechecked.
- Explicit retry of a rejected legacy reflection refreshes only evidence guidance;
  original input/response remains archived. No automatic provider retries added.

Verification:
- Before fix, new manifest/typed-reference tests failed (2 errors).
- Legacy retry regression failed before guidance refresh, then passed.
- Focused reflection-path suite: 54 tests pass (includes inherited Core regressions).
- Peer work continues despite one held reflection; polling held reflection does not repeat inference.
- Synthetic tests establish contract behavior only, not real-model completion or speedup.
