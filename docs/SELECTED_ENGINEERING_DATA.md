# Selected engineering data from saved sources

The `extract_json_evidence` API/CLI/MCP command reads selected scalar JSON
pointers from an authorized immutable development state. It reuses evidence views;
it does not replace original CAD, code, solver output or vendor metadata.

```json
{
  "state_id": "<saved-state>",
  "subject_id": "<hierarchy-id>",
  "path": "design.json",
  "profile": "configuration.v1",
  "fields": [{
    "name": "carrier_x_mm", "pointer": "/carrier_x_mm",
    "unit": "mm", "frame": "assembly", "time_basis": "configuration"
  }]
}
```

The returned view binds each value to a source artifact revision, path, content
hash and exact pointer. Missing or null fields remain unknown. Units, coordinate
frames and time meaning are caller declarations, not inferred or physically
certified. Contradictory observations remain available for assessment; recording
another view does not erase an earlier one.

Only saved JSON up to 1 MiB and 100 selected scalar fields is supported here.
Duplicate keys, nonfinite selected numbers, invalid pointer escapes and
noncanonical array indices are rejected. Secret-pattern scanning applies to
decoded content too. This is a bounded extraction facility, not a promise to
recognize every possible credential or engineering format.

The command uses the existing session/zone authorization and idempotency paths.
It cannot read an arbitrary host file or run a parser program. Native CAD
semantics, commercial tool APIs and solver adequacy still require their own
adapters and engineering verification.

Crew exposes the same capability as `extract_evidence`, supplying the current
saved state automatically. `get_design_assessment` compares selected observations
across states and follows declared dependencies to affected checks. Its bounded
coverage and retrieval requests tell the agent what is missing; a truncated view
must not be interpreted as a complete impact analysis.
