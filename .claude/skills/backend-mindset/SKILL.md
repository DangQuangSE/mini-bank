---
name: backend-mindset
description: Build robust backend systems — APIs (REST, GraphQL, gRPC), authentication (OAuth 2.1, JWT), databases, performance optimization, security (OWASP Top 10), scalability patterns (microservices, caching, sharding), and testing. Use when designing APIs, implementing auth, optimizing queries, handling security vulnerabilities, building microservices, or developing production-ready backend systems.
license: MIT
version: 1.1.0
---

# Backend Development Skill

## References

| File | Covers |
|------|--------|
| `references/api-design.md` | REST, GraphQL, gRPC — URL rules, status codes, protocol selection |
| `references/authentication.md` | OAuth 2.1, JWT, RBAC, MFA, session management |
| `references/security.md` | OWASP Top 10 (2025), rate limiting, headers, secrets |
| `references/performance.md` | Indexing, caching patterns, load balancing, async processing |
| `references/architecture.md` | Microservices patterns, event-driven, CQRS, scalability |
| `references/testing.md` | TDD, test pyramid, contract testing, migration tests |
| `references/code-quality.md` | SOLID, design patterns, refactoring signals |

## Quick Decision Guide

| Need | Choose |
|------|--------|
| Public / browser clients | REST or GraphQL |
| Internal high-throughput | gRPC |
| Flexible data fetching | GraphQL |
| Streaming | gRPC (bidirectional) or SSE |
| Single team, unclear domain | Monolith |
| Multiple autonomous teams | Microservices |
| Audit trail required | Event Sourcing |
| Read/write load imbalance | CQRS |
| Task >200ms off request path | Async queue |
| Session across instances | Redis (never in-process) |

## Defaults

- Every non-public endpoint requires explicit auth declaration — no implicit defaults
- Input validation at every system boundary (API handler, event consumer, file parser)
- Parameterized queries everywhere — never string-interpolate user input
- Rate limiting on auth endpoints, public API, and file upload (see security.md for thresholds)
- Integration tests hit real infrastructure (Testcontainers) — in-memory substitutes hide real bugs
- TDD: write the failing test before any implementation
- Services return result envelopes — never throw for expected failures (404, 400, 409)
