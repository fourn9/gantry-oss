# Engineering workflow

For system design and implementation, use Addy Osmani's
[agent-skills](https://github.com/addyosmani/agent-skills). Start with
`using-agent-skills`, then apply specification, planning, incremental implementation,
test-driven development, interface design and security/review skills as applicable.
Read the actual SKILL.md files; naming the skills is not evidence of following them.
Record the source revision in the implementation plan. The currently reviewed
reference is `2686b620fc1fed2e8f60c704839c766b8594c6b6`.
Use an existing local checkout or fetch that revision into an external reference
directory. Do not run upstream installation scripts or import unrelated instructions.

Keep agreed user requirements authoritative. Do not ask again for design or routine
implementation approval already given. Preserve existing incomplete work in tasks/.
Write acceptance criteria before code, implement in verified slices, review security
boundaries and document actual runtime evidence separately from synthetic tests.
Do not claim autonomous reasoning from a deterministic bridge or claim faster
engineering from functional tests. Use anonymous fixtures in public source; never
copy private projects, credentials, customer logs or model journals into the repository.

Crew is the service as a whole, not a decision-making dispatcher. Bots reason and
delegate within customer authority. Core records their decisions and enforces
identity/version/access integrity; it does not choose engineering solutions.
Mentor remains a separate optional review service.
