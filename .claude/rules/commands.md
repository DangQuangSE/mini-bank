---
paths:
  - ".claude/commands/**/*.md"
---

# Command Design Rules

- **Commands orchestrate only.** No review checklists, fix logic, or business rules — those belong in agents or skills.
- **Readable top-to-bottom in under a minute.** If it isn't, extract to agents.
- **Shared multi-step logic goes in an agent, not copy-pasted.** If a new command is a flag variation, make it a `--flag` on the existing one.
- **Every command ends with a verifiable outcome** — a report, a file, a test result, a commit hash. "Done" is not verifiable.
- **Challenge before adding.** Does this duplicate an existing command? Could it be a flag instead?
