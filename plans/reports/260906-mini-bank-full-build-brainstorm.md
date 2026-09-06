# Brainstorm: Mini Bank full 120-task roadmap → per-phase implementation guidelines

**Date:** 2026-09-06

## Ideas Explored

- **Rebuild spec.md from scratch** — original `plans/mini-bank-full-build/spec.md` referenced in memory no longer exists on disk (empty directory, likely written on a different machine/worktree that isn't available here). Considered redoing full scope discovery.
- **Modular-monolith substitution for Phase 5** — a prior session had decided to drop real microservices extraction (gateway, service discovery, distributed tracing) in favor of observability/resilience patterns inside the monolith. Re-surfaced as the default option this session.
- **Literal TaskTracker.gs roadmap** — user's final direction: follow the original 120-task roadmap in `tools/task-tracker/TaskTracker.gs` exactly as written, including Phase 5's real microservices extraction (Spring Cloud Gateway, Eureka/service discovery, Feign, Resilience4j, OpenTelemetry). No substitution.
- **Guideline granularity** — considered per-task (~110+ files, too granular to navigate), per-week (~24 files, matches original schedule but verbose), and per-phase (6 files) — chosen as the right balance of detail vs. navigability.

## User's Direction

User reversed the prior session's monolith-only decision: "làm như trong Tasktracker đã định nghĩa" (do it exactly as defined in TaskTracker). This means Phase 5 keeps real microservice extraction (notification-service, statement-service, gateway, service discovery, OpenTelemetry tracing, chaos test with circuit breaker) rather than being replaced by monolith-internal observability.

Deliverable: one guideline Markdown file per phase (6 files total) under `plans/mini-bank-full-build/guidelines/`, each covering that phase's weeks/tasks with technical how-to guidance — since no implementation has started yet, this is a pre-build reference, not the post-build `GUIDELINE.md` described in an earlier memory (which covers what was actually built, after the fact).

## Open Questions

- Whether the post-build consolidated `GUIDELINE.md` (design decisions + interview Q&A, per earlier memory) is still wanted once each phase ships, in addition to these pre-build guidelines — not addressed this session.
- `spring-boot-starter-parent` version `4.1.0` in `mini-bank-be/pom.xml` was flagged in a prior memory as unusually new/unverified — not re-checked this session.
- No `/ck:plan` has been run yet; these guideline files are reference material, not an execution-ready phased plan.

## Risks

- Phase 5 (real microservices extraction) is the highest-effort, highest-risk phase — splitting notification-service and statement-service out of the monolith, wiring gateway/service discovery/tracing, is a substantial infra lift for a solo, learning-focused project.
- 6 phases × ~20 tasks each is a large surface; guideline quality may need to trade off depth per task to stay reviewable in one file per phase.
