# Testing — TDD + Strategy

TDD workflow, test pyramid, test organization, and tooling guidance. Language-independent.

---

## The TDD Cycle

**RED → GREEN → REFACTOR** — always in this order.

1. **RED**: Write a failing test describing desired behavior
2. **GREEN**: Write the minimum code to make it pass — nothing more
3. **REFACTOR**: Clean up while keeping tests green

Never write implementation before a failing test exists.

---

## Test Pyramid

```
         ┌──────┐
         │  E2E │          ← few, slow, catch integration gaps
         ├──────────┤
         │Integration│     ← real DB/services, test boundaries
         ├──────────────┤
         │   Unit Tests   │ ← fast, isolated, most of the suite
         └────────────────┘
```

Target distribution: ~70% unit / 20% integration / 10% E2E.

- **Unit**: business logic, service layer, pure functions — mock external dependencies only
- **Integration**: persistence layer, external service clients — use real infrastructure (containers > in-memory)
- **E2E / contract**: API surface, auth flows, critical user paths only

---

## What to Test

| Layer | What to test |
|-------|--------------|
| Domain | Invariants, domain logic, value object rules |
| Application / Service | Return values, side effects (calls to repos/services), error cases |
| Validators | All valid + invalid input cases |
| Infrastructure / Repository | Real queries against real DB — not mocked |
| Transport / Handler | Auth, routing, request parsing, response shape |

---

## Key Principles

- Test **observable behavior** (return values, HTTP status codes, side effects), not implementation internals
- Each test is fully **self-contained** — no shared mutable state between tests
- **Real infrastructure** for integration tests — in-memory substitutes hide real bugs (use Testcontainers or a shared CI DB)
- **Arrange / Act / Assert** — one logical assertion per test, clear structure
- Test names describe **behavior**: `GetById_WhenNotFound_Returns404` not `testGetById`
- **No sleeps**: use proper async awaits or polling helpers — `sleep()` creates flakiness

---

## Anti-Patterns

| Wrong | Right |
|-------|-------|
| Write implementation first | Tests first — RED before GREEN |
| In-memory DB for integration tests | Real DB in containers |
| Mocking the class under test | Mock only external dependencies |
| Tests depending on each other | Each test is fully self-contained |
| Testing private methods | Test through the public interface |
| Sleeping in tests | Polling helper or proper async support |
| Asserting implementation calls | Assert observable outcomes |

---

## Framework Reference

| Language | Unit / Integration | E2E |
|----------|--------------------|-----|
| TypeScript / JS | Vitest (faster, ESM-native), Jest (mature) | Playwright |
| Python | Pytest (standard), unittest (built-in) | Playwright, Selenium |
| Go | `testing` (built-in), testify | — |
| .NET | xUnit, NUnit | Playwright |
| Java | JUnit 5, Testcontainers | Selenium, Playwright |

For DB integration tests, Testcontainers spins up real DB instances in Docker — prefer this over shared test databases.

---

## Contract Testing (Microservices)

Consumer-driven contracts prevent integration breakage across service boundaries without full E2E tests.

Pattern (Pact):
```
Consumer writes a test describing what it expects from the Provider.
  → Pact generates a contract file.
Provider verifies the contract against its actual implementation in CI.
  → If provider changes break a consumer contract, CI fails immediately.
```

Use contract tests instead of E2E for inter-service API compatibility. E2E tests are too slow and brittle for this purpose.

---

## Load Testing

Run against a production-like environment, not dev. Never against production directly.

Thresholds to define before running:
- p95 response time < 500ms
- p99 response time < 1s
- Error rate < 1%
- Test at 2× expected peak concurrent users

Tools: **k6** (developer-friendly, scriptable), **Gatling** (JVM, advanced scenarios), **JMeter** (GUI, traditional).

---

## Database Migration Testing

Every migration must have:
- **Forward test**: run migration → verify new schema + data integrity
- **Rollback test**: run migration → rollback → verify original schema restored
- **Data preservation test**: seed data before migration → verify no data loss after

Run migration tests in CI against a real DB using the production migration tool. Never test migrations only in development.

---

## Security Testing in CI

| Type | What it catches | When to run |
|------|-----------------|-------------|
| SAST (static) | Code-level vulnerabilities, secrets in code | Every PR |
| Dependency scan (SCA) | Known CVEs in dependencies | Every PR + daily |
| DAST (dynamic) | Runtime vulnerabilities against running app | On deploy to staging |

Tools: SonarQube / Semgrep (SAST), `npm audit` / Snyk (SCA), OWASP ZAP (DAST).

---

## CI Pipeline Order

```
Unit tests → Integration tests → Contract tests → Build → Deploy to staging → DAST → E2E
```

Fail fast: unit tests first (seconds), integration second (minutes), E2E last (minutes–tens of minutes). Never run E2E on every commit.

---

## Coverage Targets

- **80%+** overall — enforced in CI as a hard gate
- **100%** for auth/permission logic and financial calculations — no exceptions
- Never chase coverage numbers: an untested sad path matters more than a trivially covered happy path
- New code: 90%+ before merge
