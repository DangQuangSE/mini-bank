# Security — Backend Principles

OWASP Top 10 mitigation, input validation, rate limiting, secrets, and security headers. Language-independent. For auth-specific security (JWT, OAuth, MFA, passwords) see authentication.md.

---

## OWASP Top 10

### 1. Broken Access Control
- Enforce authorization on the server — never trust client-side checks
- RBAC + deny by default; verify ownership before mutations
- Log every access control failure

### 2. Cryptographic Failures
- TLS 1.3 minimum in transit — no HTTP, no TLS 1.0/1.1
- Encrypt sensitive data at rest (AES-256)
- Use CSPRNG for all tokens and nonces — never `Math.random()` or `rand()`
- Password hashing: Argon2id (see authentication.md)

### 3. Injection
- **SQL**: parameterized queries always — never string-interpolate user input
- **NoSQL**: typed query builders or ODM; reject raw user-supplied operators
- **Command injection**: never pass user input to shell commands; use library APIs
- **Path traversal**: sanitize file paths; reject `../` components

### 4. Insecure Design
- Threat model during design — identify trust boundaries before writing code
- Defense in depth: authentication + authorization + input validation + rate limiting, not just one layer
- Principle of least privilege at every layer: services, DB users, IAM roles, API scopes

### 5. Security Misconfiguration
- Remove default credentials and unused endpoints before deployment
- CORS: explicit allow-list of origins — never `*` in production
- Disable directory listing, stack traces in error responses, verbose error messages

### 6. Vulnerable & Outdated Components
- Run dependency audit in CI (`npm audit`, `pip-audit`, `govulncheck`, etc.)
- Automate update PRs via Renovate or Dependabot
- Lock files committed and verified in CI (SCA scan); fail build on out-of-sync lock file

### 7. Authentication Failures
See authentication.md for full detail. Critical controls:
- Rate limiting on login, OTP, and password reset (≤10 attempts / 15 min)
- Progressive delay or lockout after repeated failures
- Session regeneration on login and privilege elevation

### 8. Software & Data Integrity Failures
- Verify signatures and checksums for external artifacts (packages, Docker images)
- CI/CD pipelines run in isolated, immutable environments — no manual SSH into build agents
- Code signing for release artifacts

### 9. Logging & Monitoring Failures
- Log: auth events (success/fail), access control failures, sensitive data mutations
- Do NOT log: passwords, tokens, PII, raw credit card numbers
- Centralized log aggregation with alerting on anomalies
- Retain security logs ≥90 days

### 10. Server-Side Request Forgery (SSRF)
- Allow-list outbound URLs — reject anything not explicitly permitted
- Block requests to internal IP ranges (169.254.x.x, 10.x.x.x, 172.16–31.x.x, 127.x.x.x)
- Disable unnecessary URL schemes (`file://`, `gopher://`, `ftp://`)
- Network segmentation: backend services unreachable from the public internet

### Supply Chain Failures (2025)
- Audit dependencies before adding: check maintenance activity, ownership, CVE history
- Hash pinning for critical packages; monitor CVE databases for packages in use

---

## Input Validation

Validate at every system boundary — API handler, event consumer, file parser:

- **Allow-list over deny-list**: define what's valid; reject everything else
- **Check presence, type, format, length** before using any value
- **File uploads**: validate size + MIME type + magic bytes (not just extension)
- **Structural only at transport layer**: no business rules in validators — uniqueness, ownership live in the service layer

Never trust data from headers, query strings, cookies, or inter-service calls without validation.

---

## Rate Limiting

| Endpoint type | Limit |
|---------------|-------|
| Login / OTP / password reset | ≤10 attempts / 15 min |
| File upload | ≤10 requests / min |
| Public API (unauthenticated) | ≤100 requests / 15 min |
| Authenticated API | ≤1000 requests / 15 min |
| Admin endpoints | ≤50 requests / 15 min |

Apply per user/IP. Return `429` with `Retry-After` header. Use a distributed counter (Redis) across instances — per-process counters reset on restart.

---

## Security Headers

```
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=()
```

CSP is the most impactful for XSS mitigation. Start with `default-src 'self'` and relax only as needed with specific hashes or nonces.

---

## Secrets Management

- Never commit secrets — `.env` (gitignored) locally; env vars or vault in CI/production
- Use a secrets manager (Vault, AWS Secrets Manager, Azure Key Vault) for production credentials
- Fail hard on missing secrets at startup — never fall back to hardcoded defaults
- Rotate regularly; revoke and rotate immediately on any suspected exposure
- Separate credentials per environment — dev/staging/prod never share secrets

---

## Checklist

- [ ] TLS enforced; no HTTP in production
- [ ] Parameterized queries everywhere — no string interpolation
- [ ] Input validated at all system boundaries
- [ ] Auth on every non-public endpoint; ownership checked on mutations
- [ ] Rate limiting on auth and public endpoints
- [ ] Security headers on all responses
- [ ] CORS locked to explicit origins
- [ ] No secrets in source control
- [ ] Dependency audit in CI
- [ ] Errors don't leak stack traces or internal paths
- [ ] Auth and access-control failures logged
- [ ] MFA for admin accounts

---

## Common Pitfalls

- **Client-side validation only**: client checks are UX, not security — always re-validate server-side
- **`Math.random()` for tokens**: use CSPRNG; `Math.random()` is predictable
- **Trusting forwarded headers**: `X-Forwarded-For`, `X-User-Id` are spoofable without a controlled proxy
- **Over-broad CORS (`*`)**: allows any origin to read authenticated API responses via browser
- **Verbose error responses**: stack traces in production responses leak internal structure to attackers
- **Insufficient logging**: missing auth failures makes breach detection and forensics impossible
