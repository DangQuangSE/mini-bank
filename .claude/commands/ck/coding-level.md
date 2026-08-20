---
name: coding-level
description: Set Claude's coding explanation level for this session/project (-1=Default → 5=God Mode)
---

Set the coding explanation depth. Levels control how Claude structures and explains responses.

## Levels

| # | Name | Style |
|---|------|-------|
| -1 | Default | Claude's built-in style — no injection, no overrides |
| 0 | ELI5 | No assumed knowledge — real-world analogies, every term explained |
| 1 | Junior | Explains WHY, mentor tone, names patterns, flags pitfalls |
| 2 | Mid-level | Design patterns, system thinking, recommendation-first |
| 3 | Senior | Trade-offs and architecture first, terse, no hand-holding |
| 4 | Tech Lead | Risk analysis, business impact, no implementation detail |
| 5 | God Mode | Code-first, zero ceremony, peer-level (default when no level set) |

## Usage

```
/ck:coding-level          # show current level + interactive menu
/ck:coding-level -1       # use Claude's default style (no injection)
/ck:coding-level 3        # set to Senior
/ck:coding-level reset    # remove config entirely (same as -1 but clears the key)
```

## How to execute this command

Read the argument `$ARGUMENTS`:

**No argument** — read `.ck.json` at the project root (default: 5 if not set), print the level table above, and ask the user to pick a number -1 through 5.

**Argument is a number -1 through 5** — write `.ck.json` at the project root:
```json
{ "codingLevel": <N> }
```
Confirm with one line: `Coding level set to <N> (<Name>). Takes effect next session.`

**Argument is `reset`** — remove the `codingLevel` key from `.ck.json` if it exists (keep other keys intact). Confirm: `Coding level reset. Claude's default style will be used.`

**Argument is anything else** — print usage and the level table.

The file lives at the project root as `.ck.json`. Do NOT write to `~/.claude/` or `.claude/`.
