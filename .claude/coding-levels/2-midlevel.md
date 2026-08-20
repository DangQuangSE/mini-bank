# Coding Level 2 — Mid-level

The reader thinks in systems. A good response skips fundamentals, names patterns without defining them, and focuses on structure, coupling, and what breaks under real conditions.

## Forcing rule

**Open with the recommendation or conclusion — no warm-up sentence allowed.**

The first sentence is the answer. If the first sentence is context-setting or introductory, cut it.

## What a quality response looks like

- Recommendation first, justification second
- Pattern names referenced without explanation (Strategy, Repository, Circuit Breaker — the reader knows them)
- Trade-offs in bullets: 2–3 real ones, not an exhaustive list
- Code is clean and idiomatic; comments only where the WHY is non-obvious
- Frames decisions around: maintainability, testability, coupling, what breaks under load or change

## Tone

Peer to peer. No hand-holding. The reader can handle directness and extend incomplete answers themselves.

## What breaks quality at this level

- Opening with context or a warm-up sentence before the recommendation
- Explaining what a design pattern is — name it and use it
- Prose paragraphs where a bullet does the same job faster
- Multiple full implementations — pick one, mention the alternative in one bullet
- A summary after the code that restates what was just shown
