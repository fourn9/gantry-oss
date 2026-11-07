# Studio library verification — 2026-11-07

Scope: application source for Files / Requirements / exact-state conversations and
agent retrieval. All data below is synthetic and local. No private project data,
real model calls, paid services, public deployment or external messages were used.

## Automated checks

| Check | Result |
| --- | --- |
| Full Python regression, `python -m unittest discover -s tests -p 'test_*.py' -q` | 1,731 tests in 200.181 s; passed, 8 skipped |
| Studio Python subset | 33 tests passed |
| JavaScript, `node --test tests/*.mjs` | 70 tests passed, including final history-dialog fix |
| Local wheel, `python -m pip wheel --no-deps --no-build-isolation --wheel-dir /tmp/gantry-library-wheel .` | Built successfully; no new dependencies |
| `git diff --check` | Passed |

An earlier full run failed the existing time-bounded learning evaluation assertion
`test_real_core_isolates_arms_and_does_not_trust_completion_claim` (one plan instead
of two). Its isolated seven-test module and the subsequent full run passed without
changing that test or learning implementation. Treat this as observed variability,
not proof that the timing issue is fixed. The skipped tests are not claimed as passes.

Added coverage includes cross-project and forged-target denial; immutable requirement
and input applicability; missing links; state-specific related work; independent
work/delta/message cursors; newest-message retrieval for long conversations; replay;
named recipient identity; project/component Bot request/result without synthetic work;
and stale navigation/draft protection. The Bot round trip uses actual Core/queue/local
worker code with a deterministic fixture response, not production LLM reasoning.

An independent code review identified exact-state relation errors, anchor filtering,
cursor reuse and latest-message pagination problems. Each was corrected and covered
by regression tests. Browser testing additionally caught the history dialog remaining
open after navigation; state selection now closes it first.

## Browser checks

A disposable localhost Core/server hosted an anonymous bench project containing text,
a saved triangle STL, three immutable states, formal requirement references and checks.
The real authenticated API and saved artifact store were used, not a static demo API.

- Four project tabs; Files shows saved bytes and a real parent text diff.
- Saved STL opens the mesh viewer; text-line selection opens an exact-state discussion.
- A named human mention is saved, appears in Inbox and reopens the original code line,
  file hash and state.
- Related shows the recorded requirement/check input and checkpoint-containing work.
- Requirements shows an unknown check after changed input and a missing/unverified
  check, without implying formal adoption.
- Versions opens past states; Restore / continue identifies the selected state and
  shows capture omissions/unfinished work. This check verifies the instruction UI,
  not a new native CAD runtime restoration.
- At 1,440 × 950 and 430 × 900 viewports, content remains usable; on the narrow viewport
  conversation stacks below the artifact and accepts a draft without overlaying it.
- Temporary viewport overrides were reset. The disposable browser/server was stopped.

## Boundaries

Public demo and the customized private Studio installation were not deployed. Their
compatibility work remains: static demo responders must support these read contracts;
the private runtime's explicit allowlist and custom CAD/structure hooks must be preserved
when adopting the new target mixin and browser modules. Private data was not changed.

No new live native-CAD/Git connector, native subpart remapping, physical certification,
large-project throughput claim, model-quality result or development-time reduction
is established by these checks. Requirement links use recorded references only.
