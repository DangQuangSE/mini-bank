# Code Quality

SOLID principles, design patterns, clean code rules, and refactoring signals. Language-independent.

---

## SOLID Principles

### Single Responsibility (SRP)

A class or module has one reason to change — one job, one owner.

Violation: `UserService` does DB access + email sending + validation + report generation.
Fix: `UserRepository`, `EmailService`, `UserValidator`, `ReportService` — each with one concern.

Signal: if a class name needs "and" to describe what it does, split it.

### Open/Closed (OCP)

Open for extension, closed for modification.

Violation: `PaymentProcessor.process()` has if/else per payment method — adding a method means editing the class.
Fix: define a `PaymentStrategy` interface; each payment method implements it; `PaymentProcessor` accepts any strategy. New method = new class, no existing code touched.

Patterns that satisfy OCP: Strategy, Template Method.

### Liskov Substitution (LSP)

Subtypes must be substitutable for the base type without breaking callers.

Violation: `Penguin extends Bird` where `Bird.fly()` throws on `Penguin` — code using `Bird` gets surprise exceptions.
Fix: model behavior, not taxonomy. `FlyingBird` and `SwimmingBird` both implement `Bird.move()` differently.

Rule: if an override throws `NotImplemented` or `UnsupportedOperation`, the inheritance is wrong — use composition.

### Interface Segregation (ISP)

Clients shouldn't depend on methods they don't use.

Violation: `Worker` interface with `work()`, `eat()`, `sleep()` — `Robot` is forced to implement `eat()`.
Fix: split into `Workable`, `Eatable`, `Sleepable`. Each class implements only what applies.

### Dependency Inversion (DIP)

Depend on abstractions, not concretions.

Violation: `UserService` creates `new MySQLDatabase()` internally — tightly coupled to one DB engine.
Fix: inject a `Database` interface via constructor. DB choice moves to the composition root.

Rule: `new <dependency>` inside a class (not a value object) is almost always a violation. Inject it.

---

## Design Patterns

### Repository

Abstracts data access behind an interface. The service layer talks to the interface; implementations handle SQL/ORM/HTTP/etc. Swap implementations for testing without touching business logic.

```
interface UserRepository:
  findById(id) → User | null
  findByEmail(email) → User | null
  save(user) → void
  delete(id) → void

class PostgresUserRepository implements UserRepository: ...
class InMemoryUserRepository implements UserRepository: ...  # test double
```

Use when any layer above data access shouldn't know how or where data is stored.

### Strategy

Encapsulates an algorithm behind an interface so implementations are swappable at runtime.

```
interface PaymentStrategy:
  process(amount) → Result

PaymentProcessor(strategy: PaymentStrategy).process(amount)
# StripePayment, PayPalPayment, BankTransfer all implement PaymentStrategy
```

Use when multiple algorithms serve the same purpose, or the algorithm is chosen at runtime. Eliminates if/else chains on type.

### Factory

Centralizes object creation, hiding which concrete class is instantiated.

```
NotificationFactory.create("email") → EmailNotification
NotificationFactory.create("sms")   → SmsNotification
```

Use when callers shouldn't decide which concrete type to build, or creation logic is conditional/complex.

### Observer (Pub/Sub)

Subject maintains a list of observers and notifies them on state change. Emitter has no knowledge of its consumers.

```
eventBus.subscribe("order.created", EmailNotifier)
eventBus.subscribe("order.created", AuditLogger)
eventBus.emit("order.created", payload)
```

Use when multiple consumers react to the same event and the emitter should remain decoupled from side effects.

### Decorator

Wraps an object to add behavior without modifying its class. Composable.

```
request
  → AuthMiddleware(request)
  → RateLimitMiddleware(AuthMiddleware(request))
  → LoggingMiddleware(RateLimitMiddleware(...))
```

Use when you need composable behavior on top of an object, or the combination space makes subclassing impractical.

---

## Clean Code Rules

### Naming

- Names must communicate intent: `calculateTax(amount, rate)` not `calc(a, b)`
- Booleans: `isActive`, `hasPermission`, `canDelete` — never `flag`, `check`, `status`
- Avoid abbreviations unless universally standard (`id`, `url`, `dto` are fine; `usrRep`, `prc` are not)
- Constants in UPPER_SNAKE_CASE; any magic number or string that has meaning gets a name

### Function Shape

- One function, one level of abstraction — if you can extract a block with a meaningful name, do it
- Over 30 lines is a signal to decompose (not a hard limit)
- Prefer guard clauses over nesting:

```
# Avoid:
if valid:
  if authorized:
    if exists:
      doWork()

# Prefer:
if not valid: return error
if not authorized: return 403
if not exists: return 404
doWork()
```

### Error Handling

- Distinguish expected failures (typed result or domain exception) from unexpected ones (let propagate to global handler)
- Never swallow silently: `catch(e) {}` or `catch(e) { return null }` — log or rethrow
- Log at the point where context is richest: include entity ID, operation name, and original error
- Use domain exceptions (`UserNotFoundError`, `InsufficientFundsError`) — never `Error("something went wrong")`
- Expected failures (404, 400, 409) should not throw — return a result type or discriminated union

### DRY

Duplication is fine twice; three times, extract. The delay is intentional — premature abstraction from two instances creates wrong abstractions. Wait for the third occurrence to understand the real pattern.

---

## Refactoring Signals

| Code Smell                                                        | Refactoring                                      |
| ----------------------------------------------------------------- | ------------------------------------------------ |
| Method does multiple things                                       | Extract Method                                   |
| `if type == X / else if type == Y` chain                          | Replace Conditional with Polymorphism (Strategy) |
| Same logic copied across 3+ places                                | Extract to shared function / module              |
| 3+ levels of nesting                                              | Guard clauses; extract inner blocks              |
| Constructor with 5+ parameters                                    | Parameter Object or Builder                      |
| Class knows too much about another's internals                    | Introduce abstraction layer / Facade             |
| Long parameter list carries related data                          | Group into a value object                        |
| Feature envy (method uses another class's data more than its own) | Move Method to that class                        |

---

## Checklist

- [ ] Each class/function has one reason to change
- [ ] Dependencies injected, not instantiated inside class body
- [ ] No magic numbers or strings — named constants everywhere
- [ ] No silent exception swallowing
- [ ] Domain exceptions for expected failures; unexpected ones propagate
- [ ] No 3+ levels of nesting — guard clauses applied
- [ ] No logic duplicated 3+ times
- [ ] Comments explain _why_, not _what_ (the code already says what)
- [ ] Functions readable without tracing internals — good names carry the intent
