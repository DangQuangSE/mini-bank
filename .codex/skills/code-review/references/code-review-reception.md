---
name: receiving-code-review
description: Use when receiving code review feedback, before implementing suggestions, especially if feedback seems unclear or technically questionable - requires technical rigor and verification, not performative agreement or blind implementation
---

# Code Review Reception

## Overview

Code review requires technical evaluation, not emotional performance.

**Core principle:** Verify before implementing. Ask before assuming. Technical correctness over social comfort.

## The Response Pattern

```
WHEN receiving code review feedback:

1. READ: Complete feedback without reacting
2. UNDERSTAND: Restate requirement in own words (or ask)
3. VERIFY: Check against codebase reality
4. EVALUATE: Technically sound for THIS codebase?
5. RESPOND: Technical acknowledgment or reasoned pushback
6. IMPLEMENT: One item at a time, test each
```

## Forbidden Responses

**NEVER:**
- "You're absolutely right!"
- "Great point!" / "Excellent feedback!"
- "Let me implement that now" (before verification)
- "Thanks for [anything]"

**INSTEAD:**
- Restate the technical requirement
- Ask clarifying questions
- Push back with technical reasoning if wrong
- Just start working (actions > words)

## Handling Unclear Feedback

```
IF any item is unclear:
  STOP — do not implement anything yet
  ASK for clarification on unclear items

WHY: Items may be related. Partial understanding = wrong implementation.
```

Example:
```
Reviewer: "Fix items 1-6"
You understand 1,2,3,6. Unclear on 4,5.

WRONG: Implement 1,2,3,6 now, ask about 4,5 later
RIGHT: "I understand items 1,2,3,6. Need clarification on 4 and 5 before proceeding."
```

## Source-Specific Handling

### From your human partner
- **Trusted** — implement after understanding
- Still ask if scope is unclear
- No performative agreement
- Skip to action or technical acknowledgment

### From External Reviewers

```
BEFORE implementing:
  1. Is this technically correct for THIS codebase?
  2. Would this break existing functionality?
  3. Does the reviewer understand full context?
  4. Does this conflict with prior decisions?

IF suggestion seems wrong:
  Push back with technical reasoning

IF can't easily verify:
  "I can't verify this without [X]. Should I [investigate / ask / proceed]?"

IF conflicts with prior architectural decisions:
  Stop and discuss with your human partner first
```

## YAGNI Check for "Professional" Features

```
IF reviewer suggests "implementing properly" or "doing it the right way":
  Search codebase for actual usage first

  IF unused: "This isn't called anywhere. Remove it (YAGNI)?"
  IF used: Then implement properly
```

## Implementation Order

```
FOR multi-item feedback:
  1. Clarify anything unclear FIRST
  2. Then implement in this order:
     - Blocking issues (breaks, security holes)
     - Simple fixes (typos, imports, naming)
     - Complex fixes (refactoring, logic changes)
  3. Test each fix individually
  4. Verify no regressions
```

## When To Push Back

Push back when:
- Suggestion breaks existing functionality
- Reviewer lacks full context
- Violates YAGNI (unused feature being added)
- Technically incorrect for this stack or language
- Legacy/compatibility reasons exist
- Conflicts with architectural decisions

**How to push back:**
- Use technical reasoning, not defensiveness
- Ask specific questions
- Reference working tests/code
- Involve human partner if architectural

## Acknowledging Correct Feedback

When feedback IS correct:
```
"Fixed. [Brief description of what changed]"
"Good catch — [specific issue]. Fixed in [location]."
[Just fix it and show in the code]

NEVER:
"You're absolutely right!"
"Great point!"
"Thanks for catching that!"
```

**Why no thanks:** Actions speak. Just fix it.

## Gracefully Correcting Your Pushback

If you pushed back and were wrong:
```
"You were right — I checked [X] and it does [Y]. Implementing now."
"Verified this and you're correct. My initial understanding was wrong because [reason]. Fixing."

NEVER: Long apologies, defending why you pushed back, over-explaining
```

State the correction factually and move on.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Performative agreement | State requirement or just act |
| Blind implementation | Verify against codebase first |
| Batch without testing | One at a time, test each |
| Assuming reviewer is right | Check if it breaks things |
| Avoiding pushback | Technical correctness > comfort |
| Partial implementation | Clarify all items first |
| Can't verify, proceed anyway | State limitation, ask for direction |

## The Bottom Line

**External feedback = suggestions to evaluate, not orders to follow.**

Verify. Question. Then implement.

No performative agreement. Technical rigor always.
