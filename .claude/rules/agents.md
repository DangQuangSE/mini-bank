---
paths:
  - ".claude/agents/**/*.md"
---

# Agent Design Rules

- **One job per agent.** If the description needs "and also", split or simplify.
- **Tool list = what it actually uses.** No `Write` if it never writes. No `Bash` if it only reads.
- **Check before creating.** The finalize trio (project-manager, docs-manager, git-manager) and code-reviewer are shared — never duplicate them.
- **Model tiering:** haiku for bookkeeping (scout, git-manager, docs-manager, project-manager); sonnet for reasoning (debugger, tester, code-reviewer, planner, plan-researcher, plan-reviewer).
- **Every output agent defines pass/fail.** Tests report results. Commits confirm staged files. Reviews state verdict explicitly.
- **Challenge existence.** Can the main agent handle it inline? What's the blast radius if it fails mid-pipeline?
