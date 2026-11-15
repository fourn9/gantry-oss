# Verification intent and measured evidence

Crew Bots can record a structured verification plan before choosing a tool. The
`plan_verification` action states the purpose, question, assumptions, missing
inputs, selected checks and intended next steps. It does not execute a tool,
certify safety, change acceptance or grant permission.

```json
{
  "plan_path": "physical-plan.json",
  "check_ids": ["interface"],
  "purpose": "Check the integrated carrier and controller change",
  "question": "Do nominal clearance and controller behavior meet the frozen criteria?",
  "assumptions": ["Nominal rigid geometry; declared simulation model"],
  "missing_inputs": [],
  "tool_name": "verify",
  "expected_outputs": ["report.json"],
  "next_steps": {
    "pass": "Review remaining requirements and limitations before reporting",
    "fail": "Inspect measured failure and choose a geometry or controller correction",
    "unknown": "Obtain the missing input or resolve the tool failure before drawing conclusions"
  }
}
```

The physical plan must already exist in the task baseline. Its bytes must still
match both the baseline and the current saved state. Criteria, conditions,
evaluator declaration and requirement references are copied from that file;
the action cannot replace them. Selected input files are checked against the
current saved manifest, and their hashes are recorded with the state ID.

`expected_outputs` must name exactly the selected report paths. Every report
must be within the task's write scope. The tool must be in the owner-approved
runtime and have a matching evidence mapping, for example:

```json
{
  "local_tools": {
    "verify": {
      "argv": ["/absolute/installed/python", "-B", "verify.py"],
      "timeout_seconds": 60
    }
  },
  "tool_evidence": {
    "verify": {"plan_path": "physical-plan.json"}
  }
}
```

Missing files, changed input bytes, unavailable tools, absent mappings, report
scope gaps or declared missing inputs produce `status: unexecutable` and concrete
missing items. The runtime does not invent inputs or install a solver. `planned`
only means these planning checks passed; it does not mean execution succeeded or
that the physical model is adequate. Existing results, when available, are
explicitly labeled `recorded_result` with their applicable status.

Each action is stored through the existing `record_bot_action` path as
`kind: plan_verification`, with the original arguments and complete result.
The normal durable action journal reconciles a lost recording acknowledgement.
Plans can be retrieved through the existing action records and peer evidence
views. The Bot chooses the subsequent `tool` action; the existing tool-evidence
mapping publishes fresh reports with execution provenance. `publish_physical`
remains available for explicit report publication, but imported reports alone
do not establish that an installed tool generated them. No next-step branch runs
automatically.

Keep CAD construction separate from verification when using the engineering
CLI's frozen execution path: construction may generate STEP outputs, while
verification reads those saved STEP inputs. Rewriting a frozen evaluator input
during execution makes the result unknown. Native geometry checks and simulated
controller tests retain their own limits; neither is physical certification.

For scalar engineering data, the `extract_evidence` action accepts `subject_id`,
`path`, `profile`, and `fields` containing `name`, a JSON `pointer`, and optional
`unit`, `frame`, `time_basis`. The runtime supplies the current saved state ID.
Core extracts exact saved values and source hashes; model-provided values or
replacement state IDs are not accepted. Extraction does not establish physical
meaning or satisfy acceptance by itself.

Planning is bounded to 20 selected checks, 100 distinct input files, 256 MiB
total acquired inputs, a 1 MiB physical plan and a 128 KB returned plan. Narrow
the selection when a bound is reached; no selected criteria are silently dropped.

Regression verification: `python -m unittest discover -s tests -p
test_crew_verification.py`. These tests use anonymous fixtures and deterministic
model choices; they are not evidence of model quality or engineering speedup.
