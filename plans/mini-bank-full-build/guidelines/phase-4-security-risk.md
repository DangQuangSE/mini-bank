# Phase 4 — Security & Risk (Week 13–16)

> Nguồn: `tools/task-tracker/TaskTracker.gs` (P4). 20 task.
> Stack thêm: Bucket4j (rate limit), OWASP Dependency-Check.
> Phụ thuộc: reuse optimistic-locking pattern (Phase 1), state-machine pattern (Phase 1/3), Kafka infra (Phase 3) cho OTP delivery mock.

## Cấu trúc package thêm

```
com.minibank
├── card/       # Card entity, CardService
├── fraud/       # FraudRule interface + implementations, FraudCheckService
└── otp/         # OtpService, rate limiter
```

## Definition of Done

- Card phát hành/khóa/mở/hủy, mô phỏng chi tiêu trừ đúng hạn mức.
- Giao dịch nghi ngờ bị đánh dấu và vào hàng đợi duyệt, OTP bắt buộc cho giao dịch vượt ngưỡng.
- Rate limit chặn brute-force login/OTP, security headers chuẩn, không secret hardcode.
- Regression Phase 1-3 vẫn pass sau khi thêm toàn bộ filter mới.

---

## Week 13 — Virtual Card

### 1. Thiết kế schema thẻ (card) (Medium)

**Tư duy xử lý:** Đây là mock — không lưu số thẻ/CVV thật dạng plaintext kể cả trong demo. `card_number_masked` chỉ lưu 4 số cuối, CVV không lưu (chỉ dùng để verify tại thời điểm mô phỏng chi tiêu nếu cần, không persist).

```sql
-- V7__cards.sql
CREATE TABLE cards (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES accounts(id),
    card_number_masked VARCHAR(20) NOT NULL,  -- vd "**** **** **** 1234"
    limit_amount NUMERIC(19,4) NOT NULL,
    used_amount NUMERIC(19,4) NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    expiry_date DATE NOT NULL,
    version BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);
```

---

### 2. API phát hành thẻ ảo (Medium)

```java
@Transactional
public Card issue(Long accountId, BigDecimal limitAmount, String username) {
    Account account = ownedAccount(accountId, username);
    Card card = new Card();
    card.setAccount(account);
    card.setCardNumberMasked(maskedNumber());
    card.setLimitAmount(limitAmount);
    card.setExpiryDate(LocalDate.now().plusYears(3));
    return cardRepository.save(card);
}

private String maskedNumber() {
    String last4 = String.format("%04d", new SecureRandom().nextInt(10000));
    return "**** **** **** " + last4;
    // Ghi chú PCI-DSS: hệ thống thật xử lý card data cần tokenization/HSM, ngoài phạm vi demo này.
}
```

---

### 3. API mô phỏng chi tiêu thẻ (Medium)

**Tư duy xử lý:** Cùng pattern optimistic locking đã dùng ở `Account` (Phase 1 task 17) — `@Version` trên `Card` bắt conflict khi nhiều request chi tiêu đồng thời trên cùng thẻ.

```java
@Transactional
public void charge(Long cardId, BigDecimal amount) {
    Card card = cardRepository.findById(cardId).orElseThrow(() -> new NotFoundException("Card not found"));
    if (card.getStatus() != CardStatus.ACTIVE) throw new BusinessRuleException("Card is not active");
    BigDecimal remaining = card.getLimitAmount().subtract(card.getUsedAmount());
    if (remaining.compareTo(amount) < 0) throw new BusinessRuleException("Exceeds card limit");
    card.setUsedAmount(card.getUsedAmount().add(amount)); // @Version tự check conflict khi flush
}
```

---

### 4. API khóa/mở/hủy thẻ (Medium)

```java
public enum CardStatus { ACTIVE, LOCKED, CANCELLED }

public void changeStatus(Long cardId, CardStatus target) {
    Card card = cardRepository.findById(cardId).orElseThrow(...);
    if (card.getStatus() == CardStatus.CANCELLED) {
        throw new BusinessRuleException("Cannot change status of a cancelled card");
    }
    card.setStatus(target); // ACTIVE <-> LOCKED; -> CANCELLED (không quay lại được)
}
```

---

## Week 14 — Fraud Rule Engine

### 5. Thiết kế rule engine đơn giản (High)

**Tư duy xử lý:** Interface + `List<FraudRule>` autowired — thêm rule mới chỉ cần thêm 1 `@Component` implement interface, không sửa code engine trung tâm (Open/Closed Principle).

```java
// fraud/FraudRule.java
public interface FraudRule {
    boolean matches(TransactionContext ctx);
    String reason();
}

// fraud/TransactionContext.java
public record TransactionContext(Long accountId, BigDecimal amount, Instant occurredAt) {}

// fraud/rules/AmountThresholdRule.java
@Component
public class AmountThresholdRule implements FraudRule {
    private static final BigDecimal THRESHOLD = new BigDecimal("50000000"); // 50tr VND

    @Override public boolean matches(TransactionContext ctx) {
        return ctx.amount().compareTo(THRESHOLD) > 0;
    }
    @Override public String reason() { return "Amount exceeds threshold"; }
}

// fraud/rules/VelocityCheckRule.java
@Component
@RequiredArgsConstructor
public class VelocityCheckRule implements FraudRule {
    private final LedgerEntryRepository ledgerEntryRepository;
    private static final int MAX_TX_PER_WINDOW = 5;
    private static final Duration WINDOW = Duration.ofMinutes(10);

    @Override public boolean matches(TransactionContext ctx) {
        Instant since = ctx.occurredAt().minus(WINDOW);
        long count = ledgerEntryRepository.countByAccountIdAndCreatedAtAfter(ctx.accountId(), since);
        return count > MAX_TX_PER_WINDOW;
    }
    @Override public String reason() { return "Too many transactions in a short window"; }
}
```

---

### 6. Áp dụng rule khi tạo giao dịch (High)

**Tư duy xử lý:** Quyết định thiết kế quan trọng — giao dịch bị flag **vẫn hoàn tất** (không hold), chỉ đánh dấu để admin review sau. Chọn cách này vì đơn giản hơn implement "hold" (cần thêm state PENDING_REVIEW cho balance, ảnh hưởng UX). Ghi rõ tradeoff này trong README.

```java
// fraud/FraudCheckService.java
@Service
@RequiredArgsConstructor
public class FraudCheckService {
    private final List<FraudRule> rules; // Spring tự inject tất cả bean implement FraudRule

    public Optional<String> check(TransactionContext ctx) {
        return rules.stream()
            .filter(rule -> rule.matches(ctx))
            .map(FraudRule::reason)
            .findFirst();
    }
}

// TransactionService.transfer — sau khi tạo Transaction (Phase 1 task 18)
Optional<String> flagReason = fraudCheckService.check(new TransactionContext(from.getId(), amount, Instant.now()));
flagReason.ifPresent(reason -> {
    tx.setFlagged(true);
    tx.setFlagReason(reason);
});
```

```sql
ALTER TABLE transactions ADD COLUMN flagged BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE transactions ADD COLUMN flag_reason VARCHAR(255);
ALTER TABLE transactions ADD COLUMN review_status VARCHAR(20) DEFAULT 'NONE'; -- NONE, PENDING, APPROVED, REJECTED
```

---

### 7. Hàng đợi duyệt giao dịch nghi ngờ (Medium)

**Tư duy xử lý:** Cùng pattern PENDING/APPROVED/REJECTED đã dùng ở loan application (Phase 3 task 7) — tái sử dụng ý tưởng, không phát minh state machine mới.

```java
@PreAuthorize("hasRole('ADMIN')")
@GetMapping("/api/transactions/flagged")
public Page<TransactionResponse> flaggedQueue(Pageable pageable) {
    return transactionRepository.findByFlaggedTrueAndReviewStatus(ReviewStatus.PENDING, pageable)
        .map(TransactionResponse::from);
}

@PreAuthorize("hasRole('ADMIN')")
@PostMapping("/api/transactions/{id}/review")
public void review(@PathVariable Long id, @RequestParam ReviewStatus decision) {
    Transaction tx = transactionRepository.findById(id).orElseThrow(...);
    tx.setReviewStatus(decision); // APPROVED hoặc REJECTED
}
```

---

### 8. Unit test từng fraud rule (Medium)

```java
class AmountThresholdRuleTest {
    AmountThresholdRule rule = new AmountThresholdRule();

    @Test void flagsAboveThreshold() {
        assertThat(rule.matches(ctx(amount("50000001")))).isTrue();
    }
    @Test void doesNotFlagAtThreshold() {
        assertThat(rule.matches(ctx(amount("50000000")))).isFalse(); // biên: đúng ngưỡng không flag
    }
}
```
Test rule thuần Java (không cần Spring context) — chỉ `VelocityCheckRule` cần mock repository.

---

## Week 15 — OTP

### 9. Sinh và lưu OTP (High)

**Tư duy xử lý:** TTL ngắn (5 phút), không log OTP ra console dù là mock gửi SMS (thói quen đúng dù đây chỉ là demo).

```java
// otp/OtpService.java
@Service
@RequiredArgsConstructor
public class OtpService {
    private final StringRedisTemplate redis; // hoặc bảng DB với expires_at nếu chưa có Redis
    private static final Duration TTL = Duration.ofMinutes(5);

    public String generate(String accountId) {
        String otp = String.format("%06d", new SecureRandom().nextInt(1_000_000));
        redis.opsForValue().set(otpKey(accountId), otp, TTL);
        return otp; // gửi qua kênh mock (log service riêng, KHÔNG log trực tiếp ở đây)
    }

    public boolean verify(String accountId, String candidate) {
        String stored = redis.opsForValue().get(otpKey(accountId));
        boolean valid = stored != null && stored.equals(candidate);
        if (valid) redis.delete(otpKey(accountId)); // one-time-use: xóa ngay sau khi verify thành công
        return valid;
    }

    private String otpKey(String accountId) { return "otp:" + accountId; }
}
```

---

### 10. Xác thực OTP trước giao dịch lớn (High)

```java
// application.properties
transfer.otp-threshold=10000000

// TransactionController — flow 2 bước
@PostMapping("/transfer/request-otp")
public void requestOtp(@RequestBody TransferRequest req) {
    if (req.amount().compareTo(otpThreshold) > 0) {
        otpService.generate(req.fromAccountId().toString());
    }
}

@PostMapping("/transfer")
public TransactionResponse transfer(@Valid @RequestBody TransferRequest req,
                                     @RequestParam(required = false) String otp) {
    if (req.amount().compareTo(otpThreshold) > 0) {
        if (otp == null || !otpService.verify(req.fromAccountId().toString(), otp)) {
            throw new UnauthorizedException("Valid OTP required for this amount");
        }
    }
    return TransactionResponse.from(transactionService.transfer(...));
}
```

---

### 11. Rate limit cho OTP (Medium)

**Công nghệ:** Bucket4j — implement token bucket algorithm, cấu hình số request tối đa/khoảng thời gian.

```java
@Service
public class OtpRateLimiter {
    private final Map<String, Bucket> buckets = new ConcurrentHashMap<>();

    public boolean tryConsume(String accountId) {
        Bucket bucket = buckets.computeIfAbsent(accountId, k -> newBucket());
        return bucket.tryConsume(1);
    }

    private Bucket newBucket() {
        Bandwidth limit = Bandwidth.classic(3, Refill.intervally(3, Duration.ofMinutes(15))); // 3 request/15 phút
        return Bucket.builder().addLimit(limit).build();
    }
}
```

---

## Week 16 — Hardening & Regression

### 12. Rate limit login/register (High)

```java
// auth/LoginRateLimitFilter.java
@Component
@RequiredArgsConstructor
public class LoginRateLimitFilter extends OncePerRequestFilter {
    private final Map<String, Bucket> buckets = new ConcurrentHashMap<>();

    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain)
            throws ServletException, IOException {
        if (req.getRequestURI().equals("/api/auth/login") && "POST".equals(req.getMethod())) {
            String ip = req.getRemoteAddr();
            Bucket bucket = buckets.computeIfAbsent(ip, k ->
                Bucket.builder().addLimit(Bandwidth.classic(5, Refill.intervally(5, Duration.ofMinutes(1)))).build());
            if (!bucket.tryConsume(1)) {
                res.setStatus(429);
                res.getWriter().write("{\"error\":\"Too many login attempts\"}");
                return;
            }
        }
        chain.doFilter(req, res);
    }
}
```

### 13. Tự rà soát OWASP (High)

Checklist rà soát thủ công (không cần code mới, chỉ audit code đã viết Phase 1-3):
- **SQLi:** grep toàn repo tìm `createNativeQuery`/string-concat SQL — xác nhận 100% dùng JPA method/`@Query` với `:param` binding.
- **Mass assignment:** xác nhận mọi `@PostMapping`/`@PutMapping` nhận DTO riêng (`RegisterRequest`, `TransferRequest`...), không bind entity trực tiếp — đã áp dụng từ Phase 1 task 6, giờ audit các endpoint Phase 2-4 mới thêm (savings, loan, card).
- **CORS:** whitelist origin rõ ràng.
- **Input validation:** `@Valid` trên mọi DTO input — audit endpoint nào thiếu.

```java
// common/config/CorsConfig.java
@Bean
public CorsConfigurationSource corsConfigurationSource() {
    CorsConfiguration config = new CorsConfiguration();
    config.setAllowedOrigins(List.of("http://localhost:3000")); // FE dev — KHÔNG dùng "*"
    config.setAllowedMethods(List.of("GET", "POST", "PUT", "PATCH", "DELETE"));
    config.setAllowedHeaders(List.of("Authorization", "Content-Type"));
    UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
    source.registerCorsConfiguration("/**", config);
    return source;
}
```

### 14. Cấu hình security headers (Medium)

```java
// SecurityConfig — bổ sung vào filterChain (task 7, Phase 1)
.headers(headers -> headers
    .contentSecurityPolicy(csp -> csp.policyDirectives("default-src 'self'"))
    .httpStrictTransportSecurity(hsts -> hsts.includeSubDomains(true).maxAgeInSeconds(31536000))
    .frameOptions(frame -> frame.deny()))
```

### 15. Test rate limit và OTP (Medium)

```java
@Test void sixthLoginAttemptWithinMinuteIsRejected() {
    for (int i = 0; i < 5; i++) assertEquals(200, attemptLogin("wrong-pass").getStatus());
    assertEquals(429, attemptLogin("wrong-pass").getStatus()); // 6th bị chặn
}

@Test void otpCannotBeReused() {
    String otp = otpService.generate("acc1");
    assertTrue(otpService.verify("acc1", otp));
    assertFalse(otpService.verify("acc1", otp)); // lần 2 phải fail
}
```

### 16. Rà soát secrets (High)

```bash
# grep tìm secret hardcode còn sót
grep -rnE "(password|secret|api[_-]?key)\s*=\s*[\"'][^\"'{]" src/main --include="*.java" --include="*.properties"
```
Chuyển toàn bộ sang env var (`JWT_SECRET`, `DB_PASSWORD` đã làm ở Phase 1 task 1/8) — cập nhật `.env.example` với placeholder, không commit `.env` thật.

### 17. Quét lỗ hổng dependency (Low)

```xml
<plugin>
    <groupId>org.owasp</groupId>
    <artifactId>dependency-check-maven</artifactId>
    <version>9.2.0</version>
</plugin>
```
`mvn org.owasp:dependency-check-maven:check` — ghi lại CVE nghiêm trọng (nếu có) vào README, không bắt buộc fix hết ở demo nhưng phải biết.

### 18. Viết phần Security Decisions (Low)

README: liệt kê đã làm (rate limit, OTP, fraud rule, security headers, OWASP audit) và **chưa làm** (không có WAF, không có real card tokenization/PCI compliance, không có 2FA hardware key, không có distributed rate limiter cho multi-instance) — trung thực về phạm vi.

### 19. Regression Phase 1-3 (Medium)

Chạy lại toàn bộ test suite — đặc biệt kiểm tra `LoginRateLimitFilter` (task 12) không chặn nhầm test client chạy nhiều request liên tiếp, và OTP filter không chặn nhầm transfer nhỏ (dưới threshold).

### 20. Buffer/catch-up (Low)

Dự phòng.

---

## Kiến thức hay bị hỏi khi phỏng vấn (từ phase này)

- Token bucket algorithm: hoạt động thế nào, vì sao chọn thay vì fixed-window counter (tránh burst traffic ngay đầu mỗi window).
- OTP one-time-use enforcement: race condition nếu 2 request verify cùng lúc — liên hệ lại optimistic locking/atomic operation (Redis `DEL` sau `GET` không atomic 100%, nên dùng Lua script hoặc `GETDEL` cho production thật).
- OWASP Top 10 áp dụng trực tiếp vào banking app: Broken Access Control (IDOR — đã chống từ Phase 1), Injection, Security Misconfiguration (CORS/headers).
- Vì sao rule engine dùng `List<FraudRule>` injection thay vì if-else chain (Open/Closed Principle, dễ test từng rule độc lập).
- Flagged transaction "hoàn tất nhưng đánh dấu" vs "hold chờ duyệt" — tradeoff UX vs an toàn, và hệ thống thật thường chọn gì (thường hold nếu risk cao, complete-and-flag nếu risk thấp — tiered response).
