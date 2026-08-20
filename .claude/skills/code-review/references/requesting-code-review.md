---
name: requesting-code-review
description: Use when completing tasks, implementing major features, or before merging — trigger a code review via /code-review command or automatically through cook/fix pipelines
---

# Requesting Code Review

Catch issues before they cascade. Review early, review often.

## When to Request Review

**Mandatory:**
- After each task in subagent-driven development
- After completing major feature
- Before merge to main

**Optional but valuable:**
- When stuck (fresh perspective)
- Before refactoring (baseline check)
- After fixing complex bug

## How to Request

**User-invoked:**
```bash
/code-review              # review local uncommitted changes
/code-review 42           # review PR #42
/code-review <PR-URL>     # review by URL
```

**Automatic (via pipeline):**
- `ck:cook` and `ck:fix` do not replace final review. For planned work, request review after the quality receipt is current and `ck:test` has produced a fresh report.
- No manual invocation needed when using those pipelines.

## Act on Feedback

- Fix **CRITICAL** issues immediately — do not proceed
- Fix **HIGH** issues before the next task
- Note **MEDIUM/LOW** issues for later
- Push back if reviewer is wrong (with technical reasoning)

## Red Flags

**Never:**
- Skip review because "it's simple"
- Ignore CRITICAL issues
- Proceed with unfixed HIGH issues
- Argue with valid technical feedback
