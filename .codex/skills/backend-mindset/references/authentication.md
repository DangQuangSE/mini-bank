# Authentication & Authorization

OAuth 2.1, JWT, RBAC, MFA, sessions, and password security. Language-independent.

---

## OAuth 2.1

### What Changed from 2.0

**Mandatory (2.1):**

- PKCE for all clients (not just public clients)
- Exact redirect URI matching
- `state` parameter for CSRF protection

**Deprecated:**

- Implicit grant (tokens in URL fragment — XSS risk)
- Resource owner password credentials grant
- Bearer tokens in query strings

### Authorization Code + PKCE Flow

```
1. Client generates:
   code_verifier = random 32-byte base64url string
   code_challenge = base64url(SHA-256(code_verifier))

2. Redirect user to authorization endpoint:
   ?response_type=code
   &client_id=...
   &redirect_uri=...  (must match exactly)
   &scope=openid profile email
   &state=<random nonce>
   &code_challenge=<challenge>
   &code_challenge_method=S256

3. Exchange code at token endpoint:
   POST /token
   grant_type=authorization_code
   code=<received code>
   code_verifier=<original verifier>
   redirect_uri=<same URI>

4. Server verifies: SHA-256(code_verifier) == stored code_challenge
```

The `state` value must be verified on callback to prevent CSRF. Store `code_verifier` in server-side session, not client storage.

---

## JWT

### Structure

```
Header.Payload.Signature
{ alg, typ } . { sub, iss, aud, exp, roles, ... } . HMAC/RSA signature
```

### Rules

- **Access token TTL**: 15 minutes. Refresh token TTL: 7 days.
- **Algorithm**: RS256 (asymmetric) for public APIs — private key signs, public key verifies. HS256 only for internal services where both sides are trusted.
- **Validate**: signature + `iss` (issuer) + `aud` (audience) + `exp` on every request. Missing any check is a vulnerability.
- **Minimal claims**: never put sensitive data in payload (JWT is base64, not encrypted).
- **Refresh token rotation**: issue a new refresh token on every use; invalidate the old one. If a rotated token is reused, treat it as a breach and revoke the family.

### Payload Shape

```json
{
  "sub": "<user-id>",
  "iss": "https://auth.yourdomain.com",
  "aud": "https://api.yourdomain.com",
  "exp": 1234567890,
  "iat": 1234567000,
  "roles": ["editor"]
}
```

---

## RBAC (Role-Based Access Control)

### Model

```
User → Roles → Permissions → Resources
```

Roles are stable groups (Admin, Editor, Viewer). Permissions are fine-grained actions (post:create, user:delete). A role bundles a set of permissions. Roles can form a hierarchy (Admin inherits Editor inherits Viewer).

### Rules

- **Deny by default**: no permission = no access. Never allow unless explicitly granted.
- **Least privilege**: assign the minimum role needed for the task.
- **Check ownership**: verify the caller owns the resource, not just that they have the role.
- **Use constants for role names**: never hardcode strings at call sites.
- **Audit**: log role assignments, revocations, and privilege-elevated actions.

---

## MFA

### TOTP (Authenticator App)

Time-based 6-digit code (RFC 6238). User scans QR code during enrollment; app generates codes every 30s.

- Server generates and stores a `base32` secret per user — never expose it after enrollment
- Verification: accept ±1 time step (30s window on each side) to handle clock drift
- On verification, check the code hasn't been used before (replay prevention)

### FIDO2 / WebAuthn (Passwordless — preferred for high-security)

Hardware-backed credential (security key, platform biometric). Phishing-resistant because the credential is scoped to the origin.

Flow:

```
Registration:
  Server → challenge → Client creates credential (public key stored server-side)

Authentication:
  Server → challenge → Client signs with private key (never leaves device)
  Server verifies signature with stored public key
```

Use FIDO2 for admin accounts or any high-value access. TOTP as fallback when hardware key is unavailable.

---

## Session Management

Cookie flags (all three are required — missing any one is a vulnerability):

- `HttpOnly` — no JS access; blocks XSS token theft
- `Secure` — HTTPS only
- `SameSite=Strict` — blocks CSRF

TTLs:

- Idle timeout: 15 minutes (reset on activity)
- Absolute timeout: 8 hours (no exceptions)

Store sessions server-side (Redis for distributed deployments). Regenerate session ID on login and on privilege elevation to prevent session fixation.

---

## Password Hashing

**Argon2id is the standard** (NIST SP 800-63B, PHC winner). Use bcrypt only if Argon2id is unavailable.

Argon2id recommended parameters:

```
memory:      64 MB minimum (production: 128 MB)
iterations:  3
parallelism: 4
```

Tune so hashing takes 200–500ms on your hardware — slow enough to deter brute force, fast enough for UX.

### NIST Password Policy (SP 800-63B)

- Minimum 12 characters (not 8)
- No forced composition rules (uppercase/number/symbol requirements reduce entropy — users just do `Password1!`)
- Check against breach databases (HaveIBeenPwned) on registration and change
- No periodic rotation — rotate only on confirmed compromise
- Allow all printable characters including spaces

---

## API Keys

- **Prefix by type/environment**: `sk_live_...`, `pk_test_...` — makes leaked keys identifiable at a glance
- **Store hashed**: SHA-256 hash the key; store only the hash. Show the raw key once at creation, never again.
- **Scoped**: separate read vs write keys; principle of least privilege
- **Rate-limited per key**: a compromised key should have limited blast radius
- **Rotatable**: expose a rotation endpoint; invalidate old key immediately on rotation

---

## Authentication Decision Matrix

| Use Case                 | Approach                                         |
| ------------------------ | ------------------------------------------------ |
| Web app / SPA            | OAuth 2.1 Authorization Code + PKCE              |
| Mobile app               | OAuth 2.1 + PKCE (system browser, not WebView)   |
| Server-to-server         | Client credentials grant + mTLS                  |
| Third-party API access   | API keys with scopes                             |
| High-security / admin    | WebAuthn/FIDO2 + MFA                             |
| Microservices (internal) | Service mesh mTLS + JWT for identity propagation |

---

## Security Checklist

- [ ] OAuth 2.1 with PKCE — implicit grant removed
- [ ] Access tokens expire in ≤15 minutes
- [ ] Refresh token rotation — reuse = revoke family
- [ ] JWT: RS256, validate `iss` + `aud` + `exp` + signature
- [ ] RBAC: deny by default, ownership check on mutations
- [ ] MFA required for admin and privileged accounts
- [ ] Passwords hashed with Argon2id (≥64 MB memory cost)
- [ ] Session cookies: HttpOnly + Secure + SameSite=Strict
- [ ] Rate limiting on auth endpoints: ≤10 attempts / 15 min
- [ ] Account lockout or progressive delay after failed attempts
- [ ] Breach database check on password registration/change
- [ ] Audit log for login, logout, role changes, token revocation
