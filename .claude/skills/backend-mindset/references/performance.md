# Performance & Scalability

Database optimization, caching patterns, load balancing, async processing, and monitoring. Language-independent. For scaling topology (horizontal/vertical, replicas, sharding) see architecture.md.

---

## Database

### Indexing

Index types and use cases:

| Type             | Use case                                                        |
| ---------------- | --------------------------------------------------------------- |
| B-tree (default) | Equality and range queries on most column types                 |
| Hash             | Equality-only lookups — faster than B-tree but no range support |
| GIN              | Full-text search, JSON/array containment                        |
| GiST             | Geospatial, range types, custom operators                       |

Composite index column order matters: put the equality filter column first, range/sort column last.

```sql
-- For: WHERE user_id = ? AND created_at > ?
CREATE INDEX idx_orders_user_date ON orders(user_id, created_at DESC);

-- Partial index — smaller, faster for filtered queries
CREATE INDEX idx_active_users ON users(email) WHERE active = true;
```

**Do not index:**

- Tables under ~1000 rows (seq scan is faster)
- Columns with very low cardinality (boolean, enum with 2–3 values)
- Columns updated on nearly every write (index maintenance cost outweighs read gain)

Use `EXPLAIN ANALYZE` (or equivalent) to confirm an index is actually used.

### N+1 Queries

Fetching related data in a loop = N+1 queries. Always use JOINs or batch loading:

```
# Bad — 1 query for posts + N queries for authors:
posts = db.query("SELECT * FROM posts")
for post in posts:
  post.author = db.query("SELECT * FROM users WHERE id = ?", post.author_id)

# Good — single JOIN:
posts = db.query("SELECT posts.*, users.name FROM posts JOIN users ON posts.author_id = users.id")

# Or batch:
author_ids = [p.author_id for p in posts]
authors = db.query("SELECT * FROM users WHERE id IN (?)", author_ids)
```

For GraphQL field resolvers, DataLoader is mandatory (see api-design.md).

### Connection Pooling

Never create a new DB connection per request — connection setup is expensive (~50ms). Use a connection pool.

Recommended formula: `pool_size = (cpu_core_count × 2) + effective_spindle_count`

Typical: 20–30 connections per app instance. Configure:

- `max`: hard ceiling (prevent DB overload)
- `min` / `idle`: warm connections to avoid cold-start latency
- `connectionTimeout`: fail fast rather than queue indefinitely (2–5s)
- `idleTimeout`: reclaim unused connections (30–60s)

---

## Caching

### Patterns

**Cache-Aside (Lazy Loading)** — most common:

```
function get(id):
  val = cache.get(key(id))
  if not val:
    val = db.query(id)
    cache.set(key(id), val, ttl=3600)
  return val
```

**Write-Through** — keeps cache in sync on every write, at the cost of write latency:

```
function update(id, data):
  db.update(id, data)
  cache.set(key(id), data, ttl=3600)
```

**Write-Behind (Write-Back)** — write to cache only, flush to DB asynchronously. Fastest writes; risk of data loss on crash. Use only when write throughput is extreme and some loss is tolerable.

### Invalidation

Cache invalidation is the hard problem. Rules:

- Delete on write/delete, not expire: `cache.del(key(id))` immediately after DB mutation
- Invalidate related keys too: deleting a user should also delete `user:{id}:posts`, `user:{id}:settings`, etc.
- Avoid `keys("user:*")` for bulk invalidation in production — O(n) blocks Redis. Use sets to track keys per entity, or TTL-only for low-risk data.

### Cache Key Convention

`{resource}:{id}:{attribute}` — e.g., `user:123`, `order:456:items`

Namespacing by resource makes targeted invalidation straightforward.

### TTL Guidance

| Data type                                     | TTL                         |
| --------------------------------------------- | --------------------------- |
| User session                                  | 15 min idle / 8 hr absolute |
| Hot read data (product catalog, config)       | 5–60 min                    |
| Computed aggregates (dashboards, counts)      | 1–5 min                     |
| Static reference data (countries, currencies) | 24 hr+                      |

Target cache hit rate: >80%. Below 60% means the cache is adding latency without reducing DB load.

### Cache Layers (innermost to outermost)

```
DB → DB query cache → App cache (Redis) → API Gateway cache → CDN
```

Cache at the layer closest to the compute consuming the data.

---

## Load Balancing

| Algorithm            | Behavior                                          | Use when                                            |
| -------------------- | ------------------------------------------------- | --------------------------------------------------- |
| Round Robin          | Distributes evenly in sequence                    | Requests have similar cost                          |
| Least Connections    | Routes to instance with fewest active connections | Variable-duration requests                          |
| IP Hash              | Same client → same instance (sticky sessions)     | Session state stored in-process (avoid if possible) |
| Weighted Round Robin | Round Robin with capacity weights                 | Mixed instance sizes                                |

Prefer stateless services + external session storage over sticky sessions — stickiness creates uneven load and complicates rolling deploys.

All instances behind a load balancer must expose a health check endpoint. A health check should verify DB and cache connectivity, not just process liveness.

---

## Async Processing

Move work off the request path when:

- Task takes >200ms (email, image processing, report generation, PDF export)
- Result isn't needed synchronously (webhooks, audit logging, notifications)
- Work can be retried on failure (payment reconciliation, external API calls)

Pattern:

```
POST /orders → create order in DB → enqueue "send-confirmation-email" job → return 201
Worker → dequeue → send email → mark job done
```

Queue design rules:

- Jobs must be idempotent (retried on worker crash)
- Store job payload in the queue, not a pointer to mutable state
- Set max retries and a dead-letter queue for poison messages
- Monitor queue depth as a leading indicator of overload

---

## CDN / Cache-Control Headers

Three patterns (apply to all HTTP servers):

```
# Static assets (hashed filenames — safe to cache forever)
Cache-Control: public, max-age=31536000, immutable

# API responses (public, refreshable)
Cache-Control: public, max-age=3600

# User-specific data (never shared across users)
Cache-Control: private, no-cache
```

For APIs: only GET responses with no authentication variation are CDN-cacheable. Authenticated or personalized responses must be `private`.

---

## Monitoring — Key Metrics

| Layer  | Metric                     | Alert threshold |
| ------ | -------------------------- | --------------- |
| API    | p99 latency                | >1s             |
| API    | Error rate                 | >1%             |
| API    | Throughput                 | Baseline ±30%   |
| DB     | Slow queries               | >500ms          |
| DB     | Connection pool saturation | >80%            |
| Cache  | Hit rate                   | <80%            |
| Queue  | Depth growth               | Not draining    |
| System | CPU / memory               | >80% sustained  |

Instrument at p50/p95/p99 — averages hide latency outliers. Alert on p99, investigate on p95.

Tools: Prometheus + Grafana (metrics), OpenTelemetry (distributed traces), Sentry (errors).

---

## Common Pitfalls

- **Missing indexes** — full table scans on every query; easy to miss until table grows past 100k rows
- **N+1 queries** — invisible in dev (small data), catastrophic in production
- **No connection pool** — new TCP connection per request adds 50–200ms
- **Synchronous long tasks** — blocking the request thread for email/PDF/export
- **Unbounded queries** — `SELECT *` on a 10M-row table with no `LIMIT`
- **Cache stampede** — many requests hit DB simultaneously when a popular key expires; use probabilistic early expiration or a lock
- **Stale cache on write** — updating DB but forgetting to invalidate cache; corrupted reads until TTL expires
