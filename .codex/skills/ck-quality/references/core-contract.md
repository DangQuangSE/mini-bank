# Engineering Quality Contract — Core Rules

Single source of rules for `ck:quality`, `ck:cook` (preflight), `ck:fix`, and `code-review`. No skill restates these rules — they load this file (or the relevant tier of it) instead of copying prose into a prompt.

Every rule has a stable ID so findings can reference `rule: "DOM_SINGLE_SOURCE"` instead of a paraphrase, and a `default_severity` — the severity a reviewer should reach for absent phase-specific context. Actual severity in a finding always accounts for `introduced_by_current_change` (see `ck-quality/SKILL.md` §4).

A rule is never emitted as a finding unless it is `applicable` to the code in front of the reviewer, with a stated `confidence`. Don't force-fit a rule to look thorough.

## Loading Tiers

1. **Core — always loaded** (preflight and every gate/audit): Correctness, Domain Integrity, Ownership & Boundaries, Error Handling, Security, Readability & Maintainability, Change Safety.
2. **Context modules — load when the stack/change type is present:** Abstraction Discipline, Constants/Messages/Config, Data Consistency & Transactions, Concurrency & Async, API & Compatibility, Observability, Performance, Dependency Hygiene, Documentation & Decision Trace.
3. **Review triggers — load only during `ck:quality` review, never at preflight:** duplication detection, function-size/nesting heuristics, coupling analysis. These are lenses the reviewer applies, not rules Cook needs before writing a line.

Testing discipline (happy path / boundary / failure-path coverage, determinism, no weakened assertions) is owned by `ck:test`, not this contract — see `skills/ck-test/references` once that skill exists.

---

## Core Tier

### Correctness (`CORR`)

- `CORR_BOUNDARY_VALIDATION` (default: HIGH) — data crossing a system boundary (API, CLI, queue, file, DB read) is validated before use; never trust client or external-service input.
- `CORR_ERROR_CLASS_DISTINCT` (default: MEDIUM) — missing data, invalid data, unauthorized, not-found, conflict, and system error are handled as distinct cases, not collapsed into one generic error.
- `CORR_NO_SWALLOWED_EXCEPTION` (default: HIGH) — no empty catch blocks; no exception used as ordinary control flow.
- `CORR_DEFINED_BRANCH_BEHAVIOR` (default: MEDIUM) — null/empty/default/timeout/partial-failure branches have explicit, intentional behavior.
- `CORR_PRECISE_DATA_TYPE` (default: MEDIUM) — currency, datetime/timezone, and precision-sensitive values use a type that can't silently lose precision or drop offset.

### Domain Integrity (`DOM`)

- `DOM_SINGLE_SOURCE` (default: HIGH) — a business rule has exactly one authoritative implementation; a new implementation of an existing rule is a violation, not a rewrite.
- `DOM_NO_LOGIC_IN_TRANSPORT` (default: HIGH) — domain/business logic does not live in a controller, UI component, route handler, or ORM model unless the architecture explicitly puts it there.
- `DOM_BACKEND_AUTHORITY` (default: MEDIUM) — when the same rule is duplicated client- and server-side (e.g. form validation), the backend copy is authoritative; the frontend copy is UX-only, never trusted.
- `DOM_EXPLICIT_STATE_TRANSITION` (default: HIGH) — valid state transitions are modeled explicitly; an invalid transition is rejected, not silently allowed.

### Ownership & Boundaries (`OWN`)

- `OWN_SINGLE_CONCERN_OWNER` (default: MEDIUM) — each concern (transport, orchestration, domain rule, persistence, infra I/O, output mapping) is owned by one module describable in one sentence.
- `OWN_DECLARED_DEPENDENCY_DIRECTION` (default: HIGH) — dependencies flow one declared direction; domain does not import infrastructure or controllers.
- `OWN_NO_DIRECT_INFRA_FROM_TRANSPORT` (default: MEDIUM) — a controller/handler does not touch the database directly when a service/repository boundary exists.
- `OWN_NO_LEAKED_INFRA_TYPE` (default: MEDIUM) — ORM entities, vendor SDK objects, and infrastructure exceptions do not cross a public boundary unmapped.
- `OWN_NO_CIRCULAR_DEPENDENCY` (default: HIGH) — no import cycle between modules/layers.

### Error Handling (`ERR`)

- `ERR_TAXONOMY_CONSISTENT` (default: MEDIUM) — errors map to a small, consistent taxonomy instead of ad hoc types per module.
- `ERR_ROOT_CAUSE_PRESERVED` (default: MEDIUM) — wrapping an error preserves the original cause (chained/inner exception), not just a new message.
- `ERR_MAPPING_AT_BOUNDARY_ONLY` (default: MEDIUM) — error-to-response mapping happens once, at the appropriate boundary, not re-mapped at every layer.
- `ERR_NO_INTERNAL_DETAIL_TO_CLIENT` (default: HIGH) — stack traces / internal exception detail are never returned to a caller.
- `ERR_NO_DUPLICATE_LOGGING` (default: LOW) — the same error is not logged at every layer it passes through.
- `ERR_RETRY_POLICY_SOUND` (default: MEDIUM) — retries apply only to retryable failures (never validation/authorization/conflict), and have a limit, backoff, and jitter.
- `ERR_TIMEOUT_ON_EXTERNAL_CALL` (default: HIGH) — every external call (HTTP, DB, queue) has a timeout.
- `ERR_CLEANUP_GUARANTEED` (default: MEDIUM) — cleanup runs via `finally`/context-manager/equivalent, not only on the success path.

### Security (`SEC`)

- `SEC_NO_HARDCODED_SECRET` (default: BLOCKER) — no secret, token, or credential in source.
- `SEC_SERVER_SIDE_AUTHZ` (default: BLOCKER) — every protected operation checks authorization server-side; authentication is not treated as authorization.
- `SEC_PARAMETERIZED_QUERY` (default: BLOCKER) — no string-built SQL/shell/template with unparameterized user input.
- `SEC_OUTPUT_ENCODED_FOR_CONTEXT` (default: HIGH) — output is encoded for the context it's rendered into (HTML/attr/JS/URL).
- `SEC_NO_SENSITIVE_DATA_LOGGED` (default: HIGH) — passwords, tokens, and PII are never logged in plaintext.
- `SEC_LEAST_PRIVILEGE` (default: MEDIUM) — a new dependency, credential, or permission grant is scoped to what's actually needed.
- `SEC_UPLOAD_CONSTRAINED` (default: HIGH) — file upload limits type, size, filename, and storage path.
- `SEC_NO_SSRF_OPEN_REDIRECT` (default: HIGH) — redirect targets, URL fetches, and webhook destinations are validated against an allowlist or equivalent.
- `SEC_SECURE_RANDOMNESS` (default: HIGH) — randomness used for tokens/IDs with security relevance is cryptographically secure.

### Readability & Maintainability (`RDB`)

- `RDB_INTENT_NAMING` (default: LOW) — names express intent, not just type.
- `RDB_SINGLE_LEVEL_FUNCTION` (default: MEDIUM) — a function does one job at one abstraction level; size/nesting numbers are a *review trigger*, not an automatic failure.
- `RDB_NO_OPAQUE_BOOLEAN_PARAM` (default: LOW) — avoid unexplained boolean parameters (`process(true, false)`).
- `RDB_NO_DEAD_CODE` (default: LOW) — no commented-out code kept "just in case"; delete it.
- `RDB_COMMENT_EXPLAINS_WHY` (default: LOW) — a comment justifies its existence by explaining a non-obvious *why*, not restating *what*.
- `RDB_SCOPE_CONTAINED` (default: MEDIUM) — the Boy Scout Rule applies to code actually touched; it does not license an unrelated repo-wide refactor.

### Change Safety (`CHG`)

- `CHG_ROLLOUT_BACKWARD_COMPATIBLE` (default: HIGH) — a change is safe when old and new instances run simultaneously during rollout.
- `CHG_MIGRATION_DEPLOY_ORDER_SAFE` (default: HIGH) — DB migration and app deployment tolerate either running first.
- `CHG_FEATURE_FLAG_WHEN_RISKY` (default: MEDIUM) — a large or hard-to-roll-back feature is gated behind a flag.
- `CHG_NO_MIXED_CONCERNS_IN_ONE_CHANGE` (default: MEDIUM) — feature work, large refactors, and bulk reformatting are not bundled into one change.
- `CHG_SCOPE_DISCIPLINE` (default: MEDIUM) — files outside the phase's declared scope are not modified without a stated reason.
- `CHG_SAFE_CONFIG_DEFAULT` (default: MEDIUM) — new configuration has a safe default and is documented (e.g. `.env.example`).

---

## Context Modules

### Abstraction Discipline (`ABS`)

- `ABS_NO_SOLID_FOR_SOLIDS_SAKE` (default: MEDIUM) — an interface exists because there are multiple implementations, a system boundary, a swappable dependency, or genuine test-isolation need — not because "SOLID says so".
- `ABS_NO_VACUOUS_BASE_CLASS` (default: MEDIUM) — no `BaseService`/`Helper`/`Manager` introduced without clear, distinct semantics.
- `ABS_SAME_MEANING_NOT_JUST_SAME_SHAPE` (default: MEDIUM) — two similar-looking blocks are only merged into one abstraction when they share meaning and reason-to-change, not just syntax.
- `ABS_RULE_OF_THREE` (default: LOW) — first occurrence stays local; second occurrence is observed; third occurrence is when extraction is actually evaluated.

### Constants, Messages, Configuration (`CONST`)

- `CONST_CENTRALIZE_WHEN_MEANINGFUL` (default: MEDIUM) — centralize a value when it repeats, carries domain meaning, is an error code/event name/route/permission/config key, needs localization, or varies by environment.
- `CONST_NO_MEANINGLESS_LITERAL_CONSTANT` (default: LOW) — don't create constants for meaningless single-use literals (`const ONE = 1`).
- `CONST_MESSAGE_VS_CODE_SEPARATED` (default: MEDIUM) — user-facing (localizable) messages are distinct from stable machine-readable error codes.

### Data Consistency & Transactions (`TXN`)

- `TXN_BOUNDARY_MATCHES_OPERATION` (default: HIGH) — a transaction spans one business operation, not one repository call.
- `TXN_NO_EXTERNAL_CALL_INSIDE_TXN` (default: MEDIUM) — avoid holding a DB transaction open across an external API call.
- `TXN_RACE_HANDLED_AT_DATA_LAYER` (default: HIGH) — race conditions are handled with a DB constraint, lock, or optimistic-concurrency check — not only an `if` in application code.
- `TXN_IDEMPOTENT_ON_REPLAY` (default: HIGH) — an operation that may receive the same request twice produces one effect.
- `TXN_CONSTRAINT_NOT_REPLACED_BY_APP_CHECK` (default: MEDIUM) — unique/check/foreign-key constraints exist at the DB layer; app-level validation supplements, not replaces, them.
- `TXN_MIGRATION_REVERSIBLE_OR_SAFE` (default: MEDIUM) — migrations consider backward compatibility and rollback; no silent destructive rename/drop.
- `TXN_QUEUE_CONSUMER_IDEMPOTENT` (default: HIGH) — event/queue consumers assume at-least-once delivery and handle poison messages.

### Concurrency & Async (`CONC`)

- `CONC_NO_UNNECESSARY_SHARED_MUTABLE_STATE` (default: MEDIUM) — shared mutable state is avoided unless genuinely required.
- `CONC_NO_BLOCKING_IN_ASYNC` (default: HIGH) — no thread-blocking call inside an async flow.
- `CONC_BOUNDED_PARALLELISM` (default: MEDIUM) — parallel work has a bound, not unbounded fan-out.
- `CONC_CANCELLATION_AND_TIMEOUT_PROPAGATED` (default: MEDIUM) — cancellation tokens/timeouts propagate through the call chain for I/O.
- `CONC_NO_ASSUMED_SINGLE_DELIVERY` (default: MEDIUM) — code doesn't assume a request/event fires exactly once.
- `CONC_BACKGROUND_TASK_HAS_ERROR_HANDLING` (default: MEDIUM) — no fire-and-forget background task without failure handling.

### API & Compatibility (`API`)

- `API_STABLE_VERSIONED_CONTRACT` (default: HIGH) — public contracts have a versioning strategy and don't change field meaning silently.
- `API_FIELD_PRESENCE_SEMANTICS_CLEAR` (default: MEDIUM) — required/optional/nullable/omitted are distinguished deliberately.
- `API_CONSISTENT_ERROR_SCHEMA` (default: MEDIUM) — error responses share one schema.
- `API_PAGINATION_BOUNDED` (default: MEDIUM) — list endpoints are paginated with an enforced limit.
- `API_NO_DB_SCHEMA_AS_CONTRACT` (default: MEDIUM) — the API contract is not a direct passthrough of the DB schema.
- `API_BREAKING_CHANGE_DECLARED` (default: HIGH) — a breaking change is called out explicitly in the plan, not discovered later.

### Observability (`OBS`)

- `OBS_STRUCTURED_LOGGING` (default: LOW) — logs are structured, not ad hoc string concatenation.
- `OBS_CORRELATION_ID_PRESENT` (default: MEDIUM) — logs/traces carry a correlation/request/trace ID.
- `OBS_METRICS_COVER_SUCCESS_FAILURE_LATENCY` (default: LOW) — meaningful operations expose success/failure/latency/saturation metrics, not just logs.
- `OBS_EXTERNAL_CALL_DURATION_TRACKED` (default: LOW) — external calls record duration and result status.
- `OBS_BACKGROUND_JOB_STATUS_VISIBLE` (default: MEDIUM) — background jobs expose completion/failure state.

### Performance (`PERF`)

- `PERF_NO_N_PLUS_ONE` (default: HIGH) — no N+1 query pattern where eager-loading/batching is available.
- `PERF_STREAM_OR_PAGINATE_LARGE_DATA` (default: MEDIUM) — large datasets are paginated/streamed, not loaded wholesale.
- `PERF_BATCH_OVER_LOOP_EXTERNAL_CALL` (default: MEDIUM) — external calls in a loop are batched when the provider supports it.
- `PERF_CACHE_HAS_DEFINED_LIFECYCLE` (default: MEDIUM) — a new cache defines key, TTL, invalidation, consistency, and failure behavior — not just "add a cache".
- `PERF_OPTIMIZATION_HAS_EVIDENCE` (default: LOW) — non-obvious optimizations cite a measurement or explicit constraint, and don't sacrifice correctness/readability for an unmeasured gain.

### Dependency Hygiene (`DEP`)

- `DEP_JUSTIFIED_ADDITION` (default: LOW) — a new package solves something non-trivial to hand-roll; it isn't added for a one-line utility.
- `DEP_VENDOR_ISOLATED_FROM_DOMAIN` (default: MEDIUM) — business logic doesn't call a vendor SDK directly; it goes through a boundary.
- `DEP_UNUSED_REMOVED` (default: LOW) — dependencies no longer referenced are removed, not left in.
- `DEP_WRAPPER_HAS_PURPOSE` (default: LOW) — a wrapper around a dependency exists to protect a boundary or reduce coupling, not as a reflexive habit.

### Documentation & Decision Trace (`DOC`)

- `DOC_PUBLIC_CONTRACT_DOCUMENTED` (default: LOW) — public API / non-obvious contract has accompanying documentation.
- `DOC_ARCHITECTURE_DECISION_RECORDED` (default: LOW) — a significant architectural choice records context, options considered, trade-off, and consequence.
- `DOC_NO_REDUNDANT_DOCS` (default: LOW) — documentation doesn't restate what's directly readable from the code.
- `DOC_INTENTIONAL_LIMIT_IS_A_NON_GOAL` (default: LOW) — a deliberate scope limit is recorded as a non-goal, not left for the next reader to mistake as an oversight.

---

## Central Principle

Every code decision should make **ownership, dependency direction, failure behavior, and reason-for-change** explicit. If any of the four is unclear, the design is not finished — regardless of which specific rule ID applies.
