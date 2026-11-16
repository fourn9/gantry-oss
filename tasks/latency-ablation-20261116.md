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

Completed experiment: frozen implementation 9cd451c; 16/16 accepted,
108 model calls. No parent solution/restart interventions during measurement.
Median paired elapsed changes: plan/tool -10.89%, descriptions -3.00%, exact
references +2.41%. All 28 reference-transformed inputs roundtrip exactly; all108
saved inputs audited. Provider prefix cache varied, so no pure inference-time or
whole-project/learning speedup claim. Raw journals private under outputs; sanitized
rows and report in docs/CREW_LATENCY_ABLATION_RESULT.md and linked JSON.
Local regression1981 (3skip), final harness4, Node124; all four CI jobs passed
for the experiment code commit. Defaults remain unchanged; no production promotion.
