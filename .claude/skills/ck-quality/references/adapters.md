# Stack Adapters

Adapters add rules on top of `core-contract.md` for a specific stack. Load only the adapter(s) matching what's actually detected in scope — never load an adapter for a stack that isn't present.

Detection signals: `package.json` + `tsconfig.json`/`.ts` files → TypeScript/Node; `pyproject.toml`/`setup.py`/`*.py` → Python; `*.csproj`/`*.sln` → .NET; `.tsx`/`.jsx`/`.vue`/`.svelte` files or a UI framework dependency (React/Vue/Angular/Svelte) in `package.json` → Frontend; `migrations/`, `*.sql`, or an ORM/migration-tool dependency (Prisma/EF Core/Alembic/Flyway) → Database; a message-broker/queue dependency (Kafka, RabbitMQ, SQS, Azure Service Bus) or a file matching `*consumer*`/`*handler*`/`*subscriber*` in scope → Event-Driven. Extend this file with a new `##` section, same format including its own detection signal, when a new stack is needed — don't pre-build adapters nobody has asked for.

## TypeScript / Node (`TS`)

- `TS_NO_UNSAFE_ANY` (default: MEDIUM) — `any` is not used to bypass a type error; narrow or model the type instead.
- `TS_BARREL_EXPORT_INTENTIONAL` (default: LOW) — an `index.ts` re-export barrel is a deliberate public surface, not an accidental way to dodge import paths, and doesn't cause circular imports.
- `TS_PROMISE_HANDLED` (default: HIGH) — every Promise is awaited, returned, or explicitly voided (`void promise`) — never silently dropped.
- `TS_NO_FLOATING_ASYNC_IN_SYNC_CONTEXT` (default: HIGH) — an `async` function called from non-async code has its rejection handled.
- `TS_STRICT_NULL_RESPECTED` (default: MEDIUM) — non-null assertions (`!`) are justified, not a reflex to silence the compiler.

## Python (`PY`)

- `PY_NO_BARE_EXCEPT` (default: HIGH) — no bare `except:`; catch the specific exception type(s) expected.
- `PY_NO_MUTABLE_DEFAULT_ARG` (default: MEDIUM) — no mutable default argument (`def f(x=[])`).
- `PY_TYPE_HINTS_ON_PUBLIC_API` (default: LOW) — public functions/methods carry type hints.
- `PY_CONTEXT_MANAGER_FOR_RESOURCES` (default: MEDIUM) — files/connections/locks use `with`, not manual acquire/release.
- `PY_NO_STAR_IMPORT` (default: LOW) — no `from module import *` outside a deliberate re-export module.

## .NET (`DOTNET`)

- `DOTNET_DI_LIFETIME_CORRECT` (default: HIGH) — service lifetimes (singleton/scoped/transient) match actual state and thread-safety needs; no captive dependency (long-lived service holding a short-lived one).
- `DOTNET_CANCELLATION_TOKEN_PROPAGATED` (default: MEDIUM) — async methods accept and forward a `CancellationToken` through the call chain.
- `DOTNET_NO_SYNC_OVER_ASYNC` (default: HIGH) — no `.Result`/`.Wait()`/`GetAwaiter().GetResult()` on an async call from sync code.
- `DOTNET_RESOURCE_STRINGS_NOT_INLINE` (default: LOW) — user-facing strings needing localization go through resource files, not inline literals.
- `DOTNET_IDISPOSABLE_DISPOSED` (default: MEDIUM) — `IDisposable` instances are wrapped in `using`/`await using` or disposed deterministically.

## Frontend (`FE`)

- `FE_NO_UNBOUNDED_RERENDER_DEPENDENCY` (default: MEDIUM) — effect/computed dependencies are complete and don't cause unintended re-render loops.
- `FE_STATE_OWNERSHIP_CLEAR` (default: MEDIUM) — a piece of UI state has one clear owner (local vs. shared store), not duplicated in both.
- `FE_NO_SECRET_IN_CLIENT_BUNDLE` (default: BLOCKER) — no server secret/API key shipped into client-side code.
- `FE_ACCESSIBLE_INTERACTIVE_ELEMENT` (default: LOW) — interactive elements are keyboard-reachable and labeled.

## Database (`DB`)

- `DB_INDEX_MATCHES_QUERY_PATTERN` (default: MEDIUM) — a new frequent query path has a supporting index.
- `DB_CONSTRAINT_ENFORCES_INVARIANT` (default: HIGH) — invariants the app relies on (uniqueness, referential integrity) are backed by an actual DB constraint.
- `DB_MIGRATION_HAS_ROLLBACK_PATH` (default: MEDIUM) — a migration can be rolled back or is explicitly documented as irreversible with a reason.

## Event-Driven (`EVT`)

- `EVT_SCHEMA_VERSIONED` (default: MEDIUM) — event payloads carry a schema version; consumers tolerate unknown fields.
- `EVT_CONSUMER_IDEMPOTENT` (default: HIGH) — duplicate delivery of the same event doesn't double-apply an effect (overlaps `TXN_QUEUE_CONSUMER_IDEMPOTENT` in core-contract — don't double-report, cite whichever ID fits the evidence).
- `EVT_DEAD_LETTER_HANDLED` (default: MEDIUM) — a message that repeatedly fails processing is routed to a dead-letter path, not dropped or retried forever.
