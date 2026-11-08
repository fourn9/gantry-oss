# Reuse a shared checkpoint across candidate branches

Workflow: Addy Osmani agent-skills reviewed revision2686b620fc1fed2e8f60c704839c766b8594c6b6. User-authorized repair of actual multi-candidate development.

Observed: integrating a correction into one candidate changed its sharing status to integrated and prevented a second candidate from using the same sealed source. An anonymous two-candidate test reproduced the exact invalid_state.

Repair: permit shared or integrated source checkpoints. Preserve exact-version checks, target baseline comparison, dependencies, conflicts, permissions and immutable sources. New unshared checkpoints remain refused; an integrated source still cannot be edited in place. Each immutable target state retains integrated_changes source/version provenance; the existing integrated_into field remains only the latest target, not exclusive ownership. No migration or historical rewrite.

Validation: stale refs, conflicting targets, unshared new changes and changed read dependencies remain blocked. Both candidate-specific files survive; results remain unverified/unadopted and replay matches.125related tests plus14worker-integration tests passed. During the live experiment Bots independently used a duplicate-change workaround before the repaired code was loaded; do not claim live use of the repaired path from that workaround.
