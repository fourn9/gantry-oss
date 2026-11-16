# Crew latency ablation

User approved four conditions independently: baseline; combined plan/tool turn;
compact operation descriptions; duplicate context removal. No default product
behavior change until causal evidence supports promotion. Addy skills revision
2686b620fc1fed2e8f60c704839c766b8594c6b6: planning, performance, TDD.

Acceptance: 4 fresh anonymous nominal CAD/software cases, four fresh isolated
contexts each, identical frozen inputs/tools/criteria within case, fixed low
reasoning and same explicit model where connection supports it. Rotated order,
serial execution. Retain failures/timeouts; verify actual execution provenance,
unchanged evaluator and fresh independent checks. Report 16 outcomes, elapsed,
usage, retries/retrieval, evidence omissions. No general speedup claim from n=4.

Tasks: runtime agent owns composite action+tests; harness agent owns experimental
runner/protocol; context agent owns compact input transformations+tests; parent owns model connection,
independent review, live runs and analysis. No private data or raw journals public.

Model preflight: explicit gpt-6-astra / low succeeded using existing ChatGPT
subscription. Unsupported gpt-5.6 and gpt-5.3-codex probes preserved privately;
no paid API fallback. These probes are not benchmark samples.
