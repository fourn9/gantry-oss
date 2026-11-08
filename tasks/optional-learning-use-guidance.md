# Optional experience-use feedback

Workflow: Addy Osmani agent-skills reviewed revision
`2686b620fc1fed2e8f60c704839c766b8594c6b6`: debugging, TDD and code review.

Observed problem: a Bot without a completed learning plan submitted an optional
experience-use annotation. Core correctly rejected it, but the error sounded like
a prerequisite to ordinary task completion. The Bot consequently reported blocked
after removing the annotation.

Acceptance:

- Keep requiring a completed plan for this attempt, an authorized non-rejected
  planned memory and actual same-attempt actions for any experience-use claim.
- Explain in rejection feedback and ordinary onboarding that `experience_use` and
  `finish.experience_uses` are optional; omit them or use an empty/null report field
  when unavailable. Ordinary finish still checks all other task requirements.
- Never discard a submitted claim silently, fabricate a plan or auto-link memories.
- Reproduce missing feedback in anonymous tests, then verify that no-plan/pending
  plan tasks finish when annotation is explicitly omitted, and that valid plans
  still enforce reference integrity. Do not change live task state or model input.

Production scope: `bot_continuity.py` error text and `bot_execution.py` instruction.
No permission, data migration, action schema or engineering decision change.

Validation: initial four tests reproduced three missing-guidance failures (0.254 s)
while the valid-plan integrity regression passed. After the wording/instruction
fix, all four passed (0.274 s). Added an action-loop regression proving a rejected
claim remains recorded, then explicit omission completes the task without creating
a plan or use record. Related suite: 278 tests passed in 28.037 s, no skips reported.

```sh
PYTHONPATH=tests python -m unittest test_optional_learning_use_guidance test_bot_learning test_bot_continuity test_crew_finish_feedback test_crew_runtime -q
```

This verifies protocol recovery using fixture inference, not whether a real model
will always choose the correct remedy. The live experiment was not restarted or
edited as part of this fix; any subsequent loading is separately recorded.
