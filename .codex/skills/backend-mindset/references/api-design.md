# API Design

REST principles, GraphQL, gRPC, and protocol selection. Language-independent.

---

## REST

### URL Rules

```
# Plural nouns, kebab-case, versioned, no verbs in path
GET    /api/v1/orders
GET    /api/v1/orders/{orderId}
POST   /api/v1/orders
PATCH  /api/v1/orders/{orderId}
DELETE /api/v1/orders/{orderId}

# Sub-resources — max 3 path segments after /api/v1
GET    /api/v1/orders/{orderId}/items     ✅
POST   /api/v1/auth/login                ✅  (verb ok for non-CRUD action)

# Too deep → flatten to independent resource
GET    /api/v1/projects/{id}/items/{iid}/tags/{tid}   ❌
```

### Status Codes

| Operation            | Method | Success | Error           |
| -------------------- | ------ | ------- | --------------- |
| List                 | GET    | 200     | —               |
| Get one              | GET    | 200     | 404             |
| Create               | POST   | 201     | 400             |
| Full update          | PUT    | 200     | 400 / 404       |
| Partial update       | PATCH  | 200     | 400 / 404       |
| Soft delete          | DELETE | 204     | 404             |
| Not authenticated    | any    | —       | 401             |
| Wrong role           | any    | —       | 403             |
| Business conflict    | any    | —       | 409             |
| Shape/format invalid | any    | —       | 422             |
| Rate limit exceeded  | any    | —       | 429             |
| Upstream failure     | any    | —       | 502 / 503 / 504 |

### Error Envelope

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": [{ "field": "email", "message": "Invalid email format" }]
  }
}
```

### Handler & Validation Layer

Handlers: parse → validate (structural: format, required, length) → call service → serialize.

Services return result envelopes — never throw for expected failures (404, 400, 409).
Business rules (uniqueness, ownership, state transitions) live in the service layer.

### Pagination

Query params: `page`, `pageSize`, `search`, domain-specific filters.

Response: `{ data: [...], total, page, pageSize }` — always include `total`.

### Filtering & Sorting

```
GET /api/v1/orders?status=active&sort=-createdAt,name
```

`-` prefix = DESC, no prefix = ASC.

### Versioning

URL versioning by default (`/api/v1/...`). Header versioning when URL pollution is a concern. Never query-param versioning — breaks HTTP caching.

### Authorization

Every endpoint must explicitly declare its auth requirement — no implicit defaults:

- Authenticated only (any valid token)
- Role/scope required (specific permission)
- Public (explicitly marked, not just "no auth added")

### Soft Delete

Mark deleted with `deletedAt` + `deletedBy` — never hard delete. All queries on soft-deletable resources must filter deleted records.

---

## GraphQL

### Schema Shape

```graphql
type Query {
  user(id: ID!): User
  users(limit: Int = 50, offset: Int = 0): [User!]!
}

type Mutation {
  createUser(input: CreateUserInput!): User!
}

type User {
  id: ID!
  email: String!
  posts: [Post!]! # always lazy-load via DataLoader
}
```

### N+1 — DataLoader is mandatory for field resolvers

```
function batchLoadPosts(authorIds):
  rows = db.query("SELECT * FROM posts WHERE author_id IN (?)", authorIds)
  return authorIds.map(id => rows.filter(r => r.authorId == id))

postLoader = DataLoader(batchLoadPosts)

resolve posts(user):
  return postLoader.load(user.id)
```

### Rules

- No offset pagination — use cursor-based (Relay spec); offset breaks under concurrent inserts
- Enforce depth limits and query complexity budgets before execution
- Return errors in response body, not as HTTP 4xx/5xx

---

## gRPC

Service-to-service only — requires gRPC-Web proxy for browsers.
Best for: internal microservices, high-throughput pipelines, streaming.

```protobuf
service UserService {
  rpc GetUser (GetUserRequest) returns (User);
  rpc StreamUsers (StreamUsersRequest) returns (stream User);
}

message User {
  string id = 1;
  string email = 2;
  int64 created_at = 3;
}
```

---

## Protocol Selection

|                          | REST     | GraphQL       | gRPC           |
| ------------------------ | -------- | ------------- | -------------- |
| Public / browser clients | ✅       | ✅            | ❌ needs proxy |
| Flexible data fetching   | ❌       | ✅            | ❌             |
| Internal microservices   | ✅       | ❌            | ✅             |
| Streaming                | SSE only | subscriptions | bi-directional |
| HTTP caching             | native   | complex       | none           |
| Operational complexity   | low      | moderate      | high           |

Default: REST for public APIs, gRPC for internal high-throughput services.

---
