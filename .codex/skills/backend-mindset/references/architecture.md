# Backend Architecture Patterns

Decision guidance for microservices, event-driven, and scalability patterns. Language-independent.

---

## Monolith vs Microservices

|                  | Monolith           | Microservices                                   |
| ---------------- | ------------------ | ----------------------------------------------- |
| Team size        | Small / single     | Multiple autonomous teams                       |
| Domain clarity   | Unclear / evolving | Well-defined bounded contexts                   |
| Scaling need     | Uniform            | Independent per service                         |
| Deployment risk  | All-or-nothing     | Isolated                                        |
| Operational cost | Low                | High (discovery, tracing, distributed failures) |
| Consistency      | ACID transactions  | Eventual                                        |

**Default to monolith until team size or scaling forces microservices.** A distributed monolith (services that all call each other synchronously) is worse than either choice.

---

## Core Microservices Patterns

### Database per Service

Each service owns its data store exclusively — no shared database. Cross-service queries use API calls or event-driven projections. Trade-off: no joins, potential data duplication.

### API Gateway

Single entry point for clients: handles auth, rate limiting, routing, and response transformation. Services behind it are not directly exposed. Use Kong, NGINX, or cloud-native (AWS API GW, Azure APIM).

### Circuit Breakers

Wraps calls to downstream services. States: `Closed` (passing) → `Open` (failing fast after threshold) → `Half-Open` (probe retry). Prevents cascade failures. Configure: timeout, error threshold %, reset interval.

### Saga (Distributed Transactions)

Use when a business operation spans multiple services and needs rollback on failure. Each step publishes success/failure events; failed steps trigger **compensating transactions** to undo prior steps in reverse order.

- **Choreography**: each service emits events that trigger the next step. Simple but hard to trace end-to-end.
- **Orchestration**: a central coordinator drives each step in sequence. Easier to debug and monitor, but the coordinator becomes a single point of failure.

Choreography for simple 2–3 step flows; orchestration for complex or long-running sagas.

### Service Discovery

Services register themselves at startup (Consul, Kubernetes DNS, Eureka). Callers resolve addresses dynamically. Mandatory for any non-trivial microservices deployment.

---

## Event-Driven Patterns

### Event Sourcing

Store the sequence of domain events instead of current state. Current state is derived by replaying the event log. Gives full audit trail and "time travel" queries (state at any past point).

Trade-offs: read-path requires projections (separate read models built from events); event schema evolution is hard to reverse; replay gets expensive at scale without snapshots.

Use when: audit trail is a hard requirement, or temporal queries are needed. Avoid when the domain is simple CRUD with no audit needs — the complexity cost is not worth it.

### Message Broker Selection

|            | Kafka                             | RabbitMQ                    |
| ---------- | --------------------------------- | --------------------------- |
| Model      | Event log (durable, replayable)   | Task queue (consumed once)  |
| Retention  | Configurable (days/forever)       | Until acknowledged          |
| Use case   | Event sourcing, analytics, replay | Job queues, async workflows |
| Ordering   | Per partition                     | Per queue                   |
| Throughput | Very high                         | Moderate                    |

### CQRS

Separate read and write models when read/write patterns diverge significantly. Write side: normalized, command-driven, optimized for consistency. Read side: denormalized projections, optimized for query shape.

Add CQRS only when read/write load imbalance or query complexity justifies the operational overhead — it is not a default.

---

## Scalability Patterns

### Horizontal Scaling

Add instances behind a load balancer. Requires: stateless services (session externalized to Redis/DB), shared nothing per instance. For DB read pressure, add read replicas and route read queries to them — writes still go to primary.

### Caching Layers (innermost to outermost)

```
Database → DB query cache → Application cache (Redis) → API Gateway cache → CDN
```

Cache at the layer closest to the compute consuming it. Don't cache what changes faster than the cache TTL.

### Database Sharding

Partition data horizontally when a single node is the bottleneck. Shard on a key with uniform distribution (hash-based). Range-based is simpler but creates hot spots. Cross-shard queries become expensive — model your access patterns first.

---

## Anti-Patterns

- **Distributed monolith**: microservices that synchronously call each other for every operation — all the operational cost, none of the isolation benefit
- **Chatty services**: too many small synchronous calls between services — batch or go async
- **Shared database**: microservices sharing a DB — destroys service independence
- **Over-engineering**: microservices on a team of 3 — operational overhead exceeds benefit
- **No circuit breakers**: cascade failures will take down healthy services along with failing ones
