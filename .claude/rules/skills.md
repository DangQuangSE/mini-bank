---
paths:
  - ".claude/skills/**/*.md"
---

# Skill Design Rules

- **Behavioral guidance only, not documentation.** If removing a section wouldn't change Claude's output, remove it.
- **Under 500 lines. Under 300 is better.** Approaching the limit means the skill is doing too much — extract to `references/` or split.
- **description frontmatter = trigger. Body = behavior.** Don't restate the trigger in the body. Don't duplicate guidance already in CLAUDE.md or rules/.
- **Output skills define correct output.** Include a concrete example or success criteria — not just "produce a report".
- **Challenge overlap.** Is this a patch for a broken existing skill? Does it overlap with another skill's domain?
