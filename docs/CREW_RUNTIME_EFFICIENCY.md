# Crew observation and recovery efficiency

This change reduces orchestration overhead. Bots still choose engineering work,
alternatives, delegation and acceptance evidence. It does not embed a preferred
engineering answer or replace Core's identity/version checks.

## What the elapsed-time audit showed

An anonymized development exercise took 8 h 48 min 13 s elapsed. Interval unions
of worker events, model receipts and OS power transitions separated these costs:

| Exclusive interval | Elapsed |
| --- | ---: |
| Host sleep | 3 h 55 min 17 s |
| Completed model calls, excluding sleep | 3 h 29 min 28 s |
| Repair/resume interruptions, excluding sleep | 1 h 12 min 27 s |
| Failed model calls, excluding sleep | 5 min 24 s |
| Remaining intervals | 5 min 37 s |

Rounded rows may differ by a second. Model intervals include CLI startup,
provider/network waits and generation; they are not pure thinking time.
Repair windows include waiting and do not measure operator labor. Private source
records stay outside this repository; this table is an aggregate audit result,
not a publicly reproducible engineering benchmark.

622 of 792 completed responses requested retrieval. Some rereads were necessary
to verify current state. A new ephemeral model call for every individual read
was nevertheless an avoidable round trip. Several interruptions also came from
input-size, read-cursor, observation-recency and recovery defects.

## Implemented changes

- `observe` retrieves 1–4 independent `read`, `context`, `inspect` or
  `inspect_json` requests in one model turn. Mutations, tool execution and nested
  batches are rejected. Read chunks contain at most 2,000 bytes, with exact byte
  cursors. Each response retains its request, source identity and error. A large
  result explicitly requests a narrower pointer/page. Peer observations are not
  an atomic cross-task snapshot.
- Source-checked recent reads and labelled historical context receipts survive
  subsequent turns, including batch item indexes. Newest observations are retained
  first. A changed file invalidates its old chunks.
- `handoff` indexes baseline/current state, changed paths and hashes, open checks,
  gaps and child-report references. Counts and hashes identify omitted details.
  The full assessment and exact authorized context remain available. This index
  does not certify a candidate or convert a completed task to formal adoption.
- The complete action input is bounded to 480,000 encoded bytes **after** adding
  schemas, tools and prior results. Optional previews yield first. A large previous
  result becomes a hash and task-history retrieval reference. Required authority
  is never silently shortened; irreducibly large input is held.
- JSON inspection screens decoded keys and values before emitting diagnostics,
  including JSON escapes and validated compressed envelopes.

Example model action:

```json
{
  "action": "observe",
  "arguments_json": "{\"requests\":[{\"action\":\"read\",\"arguments\":{\"path\":\"assembly.py\"}},{\"action\":\"context\",\"arguments\":{\"pointer\":\"/design_assessment/open_checks\"}}]}",
  "rationale": "Read the changed assembly and its unresolved checks together"
}
```

## Optional automatic recovery

Existing installations retain explicit-only recovery. To opt in, add to a
`bot_development` runtime configuration:

```json
"recovery_policy": {"max_attempts": 2, "cooldown_seconds": 30}
```

This changes the environment hash. Generate the new manifest with
`gantry-crew bot-worker --config /private/bot.json --journal /private/journals --manifest`
and approve it through the existing `configure_bot_runtime` owner operation.
Run the worker under the existing opt-in service supervisor documented in
[Persistent Bots](PERSISTENT_BOTS.md). No service is installed automatically.

Only locally attested, stopped inference with no uncertain effects is eligible.
A saved completed response is reused; a confirmed answer-free monthly timeout
or rate limit may be retried after cooldown and a fresh runtime fence. Durable
per-task-attempt counters cap automatic recovery at the configured 1–3 attempts.
The cap limits infrastructure retries, not engineering trials or normal model turns.
Already completed read/tool actions are not replayed by this path.

Subscription allowance exhaustion is different from a transient HTTP 429.
The monthly CLI's terminal, answer-free usage-limit response is reported as
`provider_usage_limited`. Automatic recovery leaves it held without consuming
retry allowance or requesting a worker restart. It does not buy credits or use
an API-key fallback. Reset dates in provider prose are not parsed as scheduling
authority. After confirming the allowance is restored and the old processes
have stopped, use the explicit `--recover-job`, `--confirm-stopped` and
`--retry-inference` path in [Bot development](BOT_DEVELOPMENT.md).
It archives the original invocation and preserves completed actions and inputs.
Late answers, live or missing process identities and unknown effects remain held.

Same-fence recovery requests a supervisor restart. A renewed worker still passes
Core's current authority, requirements and dependency checks. Live processes,
unknown local tool/edit effects, changed authority or malformed journals remain
held for explicit reconciliation. This narrow policy does not automatically
recover arbitrary bridges, reflection jobs or legacy Mentor jobs.

An asleep local host cannot run a worker or heartbeat. Use an awake customer
runner for unattended work. Preventing idle sleep is an OS deployment choice;
it does not guarantee continued execution with a laptop lid closed. This change
does not silently alter power settings or create a cloud runner.

## Phase timing

The iterative worker writes payload-free `timing/*.json` receipts alongside its
private action journal: context preparation, model/provider wait, action, record,
checkpoint and automatic recovery. Started spans that never close remain unknown.
No source content, prompts, tokens or exception messages are copied into timing.

```sh
python -m gantry.crew_timing /private/journals
```

The report gives phase sums and the union of closed wall-clock intervals. Parallel
phase sums must not be added as total elapsed time. Monotonic and wall duration
are both retained; their difference alone is not proof of sleep. Operator labor,
uncovered polling waits and CPU time require separate instrumentation. These
receipts are local runtime measurements, not automatically uploaded telemetry.

## Verification and limits

`test_crew_observe` runs the real authenticated Core, worker, artifact reads,
recording and replay with deterministic fixture responses. Retrieving four
identical small files then finishing requires **5 model turns with individual
reads, 2 with a batch**; bytes and source hashes match. This is a 60% call-count
reduction for that fixture, not a measured wall-time or robot-development speedup.
It does not show that an unconstrained LLM will always choose batching.

Other regressions cover Unicode budgets/cursors, cross-project access, no writes
in batches, mixed batch history order, final prompt limits in a real action loop,
escaped secret diagnostics, saved-result recovery, changed authority and unknown
effects. Full-suite/build results are recorded in the implementation task/PR.

The next performance experiment should keep task, model, starting state, tool
environment and acceptance fixed; include cold connection, inference, recording,
recovery and failures. Compare elapsed interval unions, model calls, redundant
reads and human interventions separately. Persistent provider conversations and
larger engineering trials remain future work; no paid API or private engineering
trial was started to validate this change.
