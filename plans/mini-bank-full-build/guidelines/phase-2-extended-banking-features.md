# Phase 2 — Extended Banking Features (Week 5–8)

> Nguồn: `tools/task-tracker/TaskTracker.gs` (P2). 20 task.
> Stack thêm: Spring `@Scheduled` + `@EnableScheduling`, OpenPDF, springdoc-openapi, k6.
> Phụ thuộc: dùng lại `AccountRepository`, `TransactionService.transfer/withdraw` (Phase 1) — **không** viết lại logic trừ/cộng tiền ở đây.

## Cấu trúc package thêm

```
com.minibank
├── savings/         # SavingsAccount, SavingsService, interest job
├── standingorder/    # StandingOrder, execution job
├── statement/        # StatementService, PDF generator
└── audit/             # AuditLog, @Audited aspect
```

## Definition of Done

- Sổ tiết kiệm tính lãi đúng qua scheduled job, có penalty khi rút sớm.
- Standing order tự chạy đúng lịch, xử lý được thiếu số dư mà không crash job khác.
- Sao kê PDF tải được, audit log ghi lại hành động nhạy cảm.
- OpenAPI docs phủ Phase 1-2, có baseline load test cho transfer.

---

## Week 5 — Savings / Term Deposit

### 1. Thiết kế schema tiết kiệm/term deposit (Medium)

**Tư duy xử lý:** Tiền gửi tiết kiệm phải trừ ngay khỏi `accounts.balance` (Phase 1) — số tiền "khóa" trong sổ tiết kiệm không còn khả dụng cho transfer/withdraw thông thường. `accrued_interest` tách riêng khỏi `principal` để giữ audit trail rõ ràng (biết chính xác đã tích lũy bao nhiêu, tránh cộng dồn nhầm vào gốc).

```sql
-- V3__savings.sql
CREATE TABLE savings_accounts (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES accounts(id),
    principal NUMERIC(19,4) NOT NULL,
    accrued_interest NUMERIC(19,4) NOT NULL DEFAULT 0,
    interest_rate NUMERIC(5,4) NOT NULL,   -- vd 0.0500 = 5%/năm
    term_months INT NOT NULL,
    start_date DATE NOT NULL,
    maturity_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE', -- ACTIVE, MATURED, CLOSED_EARLY
    created_at TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX idx_savings_account_id ON savings_accounts(account_id);
CREATE INDEX idx_savings_status ON savings_accounts(status);
```

```java
public enum SavingsStatus { ACTIVE, MATURED, CLOSED_EARLY }

@Entity @Table(name = "savings_accounts") @Getter @Setter
public class SavingsAccount {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY) private Long id;
    @ManyToOne @JoinColumn(name = "account_id") private Account account;
    @Column(precision = 19, scale = 4) private BigDecimal principal;
    @Column(name = "accrued_interest", precision = 19, scale = 4) private BigDecimal accruedInterest = BigDecimal.ZERO;
    @Column(name = "interest_rate", precision = 5, scale = 4) private BigDecimal interestRate;
    @Column(name = "term_months") private Integer termMonths;
    @Column(name = "start_date") private LocalDate startDate;
    @Column(name = "maturity_date") private LocalDate maturityDate;
    @Enumerated(EnumType.STRING) private SavingsStatus status = SavingsStatus.ACTIVE;
    @CreationTimestamp private Instant createdAt;
}
```

---

### 2. API mở sổ tiết kiệm (Medium)

**Tư duy xử lý:** Trừ tiền qua `TransactionService.withdraw` đã có ở Phase 1 (task 17) — tái sử dụng, không tự viết lại logic check balance + update.

```java
// savings/SavingsService.java
@Service
@RequiredArgsConstructor
public class SavingsService {
    private final SavingsAccountRepository savingsRepository;
    private final AccountRepository accountRepository;
    private final TransactionService transactionService; // Phase 1

    @Transactional
    public SavingsAccount open(Long accountId, BigDecimal principal, BigDecimal rate, int termMonths, String username) {
        Account account = accountRepository.findById(accountId)
            .orElseThrow(() -> new NotFoundException("Account not found"));
        if (!account.getUser().getUsername().equals(username)) throw new ForbiddenException("Not your account");

        // Trừ tiền qua service Phase 1 — không tự viết lại check-balance-and-update
        transactionService.withdraw(accountId, principal, "SAVINGS-OPEN-" + UUID.randomUUID());

        SavingsAccount savings = new SavingsAccount();
        savings.setAccount(account);
        savings.setPrincipal(principal);
        savings.setInterestRate(rate);
        savings.setTermMonths(termMonths);
        savings.setStartDate(LocalDate.now());
        savings.setMaturityDate(LocalDate.now().plusMonths(termMonths));
        return savingsRepository.save(savings);
    }
}
```

---

### 3. Scheduled job tính lãi (Medium)

**Công nghệ:** `@Scheduled(cron=...)` — Spring tự chạy method theo lịch cron, cần `@EnableScheduling` ở class `@Configuration` hoặc main class.

**Tư duy xử lý:** Công thức lãi đơn giản: `interest = principal * rate * days/365`. Chạy mỗi ngày, cộng dồn lãi của **đúng số ngày trôi qua kể từ lần tính trước** (không tính lại từ đầu) để tránh double-count nếu job chạy trễ/catch-up.

```java
// savings/InterestAccrualJob.java
@Component
@RequiredArgsConstructor
@Slf4j
public class InterestAccrualJob {
    private final SavingsAccountRepository savingsRepository;

    @Scheduled(cron = "0 5 0 * * *") // 00:05 mỗi ngày
    @Transactional
    public void accrueDailyInterest() {
        List<SavingsAccount> actives = savingsRepository.findByStatus(SavingsStatus.ACTIVE);
        for (SavingsAccount sa : actives) {
            BigDecimal dailyInterest = sa.getPrincipal()
                .multiply(sa.getInterestRate())
                .divide(BigDecimal.valueOf(365), 4, RoundingMode.HALF_UP);
            sa.setAccruedInterest(sa.getAccruedInterest().add(dailyInterest));
            if (!LocalDate.now().isBefore(sa.getMaturityDate())) {
                sa.setStatus(SavingsStatus.MATURED);
            }
        }
        log.info("Accrued interest for {} savings accounts", actives.size());
    }
}
```

---

### 4. Logic phạt khi rút sớm (Medium)

**Tư duy xử lý:** Định nghĩa rule rõ ràng, không hardcode số magic không giải thích được — ở đây chọn: rút sớm mất 50% lãi đã tích lũy (rule đơn giản, dễ giải thích khi phỏng vấn).

```java
private static final BigDecimal EARLY_WITHDRAWAL_PENALTY_RATE = new BigDecimal("0.5");

@Transactional
public void closeEarly(Long savingsId, String username) {
    SavingsAccount sa = ownedSavings(savingsId, username);
    if (sa.getStatus() != SavingsStatus.ACTIVE) throw new BusinessRuleException("Savings not active");

    boolean early = LocalDate.now().isBefore(sa.getMaturityDate());
    BigDecimal interestPaid = early
        ? sa.getAccruedInterest().multiply(BigDecimal.ONE.subtract(EARLY_WITHDRAWAL_PENALTY_RATE))
        : sa.getAccruedInterest();

    BigDecimal payout = sa.getPrincipal().add(interestPaid);
    transactionService.deposit(sa.getAccount().getId(), payout, "SAVINGS-CLOSE-" + savingsId);

    sa.setStatus(early ? SavingsStatus.CLOSED_EARLY : SavingsStatus.MATURED);
}
```

---

### 5. Unit test tính lãi/penalty (Medium)

```java
@Test
void earlyClosureAppliesPenalty() {
    SavingsAccount sa = savingsWith(principal("1000"), accrued("100"), maturity(futureDate));
    // rút sớm: interestPaid = 100 * (1 - 0.5) = 50
    BigDecimal expectedPayout = new BigDecimal("1050.00");
    // ... assert payout via captured argument to transactionService.deposit
}

@Test
void maturedClosureNoPenalty() {
    SavingsAccount sa = savingsWith(principal("1000"), accrued("100"), maturity(pastDate));
    BigDecimal expectedPayout = new BigDecimal("1100.00");
    // ... full interest paid, no penalty
}
```

---

## Week 6 — Standing Order

### 6. Thiết kế standing order (Medium)

```sql
-- V4__standing_orders.sql
CREATE TABLE standing_orders (
    id BIGSERIAL PRIMARY KEY,
    source_account_id BIGINT NOT NULL REFERENCES accounts(id),
    dest_account_number VARCHAR(20) NOT NULL,
    amount NUMERIC(19,4) NOT NULL,
    frequency VARCHAR(20) NOT NULL,        -- DAILY, WEEKLY, MONTHLY
    next_run_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    last_failure_reason VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX idx_so_next_run ON standing_orders(next_run_date, status);
```

**Tư duy xử lý:** Hủy order chỉ set `status = CANCELLED`, không xóa record — giữ lịch sử để audit.

---

### 7. Scheduled job thực thi standing order (Medium)

**Tư duy xử lý:** Gọi lại `TransactionService.transfer` (Phase 1) — standing order chỉ là "cái gì trigger transfer đúng lịch", không phải nghiệp vụ transfer mới.

```java
@Component
@RequiredArgsConstructor
@Slf4j
public class StandingOrderJob {
    private final StandingOrderRepository standingOrderRepository;
    private final AccountRepository accountRepository;
    private final TransactionService transactionService;

    @Scheduled(cron = "0 0 1 * * *") // 01:00 mỗi ngày
    public void runDueOrders() {
        List<StandingOrder> due = standingOrderRepository
            .findByNextRunDateLessThanEqualAndStatus(LocalDate.now(), StandingOrderStatus.ACTIVE);

        for (StandingOrder order : due) {
            executeOne(order); // per-order transaction — 1 order fail không ảnh hưởng order khác
        }
    }

    @Transactional
    public void executeOne(StandingOrder order) {
        try {
            Account dest = accountRepository.findByAccountNumber(order.getDestAccountNumber())
                .orElseThrow(() -> new NotFoundException("Destination account not found"));
            transactionService.transfer(
                order.getSourceAccount().getId(), dest.getId(), order.getAmount(),
                "STANDING-" + order.getId() + "-" + order.getNextRunDate());
            order.setNextRunDate(nextDate(order.getFrequency(), order.getNextRunDate()));
            order.setLastFailureReason(null);
        } catch (BusinessRuleException e) {
            // Task 8: không throw ra ngoài — job phải tiếp tục xử lý order khác
            order.setLastFailureReason(e.getMessage());
            log.warn("Standing order {} failed: {}", order.getId(), e.getMessage());
        }
    }

    private LocalDate nextDate(Frequency freq, LocalDate from) {
        return switch (freq) {
            case DAILY -> from.plusDays(1);
            case WEEKLY -> from.plusWeeks(1);
            case MONTHLY -> from.plusMonths(1);
        };
    }
}
```

---

### 8. Xử lý lỗi standing order (Medium)

**Tư duy xử lý:** Catch lỗi **per-order** trong `executeOne` (đã làm ở task 7) — nếu để lỗi văng ra ngoài `runDueOrders`, 1 order fail sẽ chặn tất cả order còn lại trong batch đó. Retry/backoff đơn giản hóa: không retry ngay, để lần chạy job **kế tiếp** (ngày mai) tự retry vì `next_run_date` chưa được update khi fail.

---

### 9. Integration test standing order (Medium)

```java
@Test
void jobExecutesDueOrderAndAdvancesSchedule() {
    StandingOrder order = createOrder(nextRunDate(today()), Frequency.WEEKLY, amount("50"));
    standingOrderJob.executeOne(order);

    assertThat(order.getNextRunDate()).isEqualTo(today().plusWeeks(1));
    assertThat(destAccountBalance()).isEqualByComparingTo(startBalance.add(new BigDecimal("50")));
}

@Test
void jobRecordsFailureWithoutAdvancingSchedule() {
    StandingOrder order = createOrder(nextRunDate(today()), Frequency.WEEKLY, amount("999999")); // vượt balance
    standingOrderJob.executeOne(order);

    assertThat(order.getLastFailureReason()).isNotNull();
    assertThat(order.getNextRunDate()).isEqualTo(today()); // KHÔNG advance khi fail
}
```

---

## Week 7 — Statement / PDF Export

### 10. Truy vấn dữ liệu sao kê (Medium)

```java
public interface LedgerEntryRepository extends JpaRepository<LedgerEntry, Long> {
    @Query("SELECT e FROM LedgerEntry e WHERE e.account.id = :accountId " +
           "AND e.createdAt BETWEEN :from AND :to ORDER BY e.createdAt")
    List<LedgerEntry> findForStatement(Long accountId, Instant from, Instant to);
}
```

**Tư duy xử lý:** Giới hạn khoảng thời gian query (vd tối đa 12 tháng) — chặn request sao kê full lịch sử không giới hạn có thể gây query nặng.

---

### 11. Xuất file PDF sao kê (Medium)

**Công nghệ:** OpenPDF — fork mã nguồn mở của iText 4 (LGPL/MPL, license thân thiện hơn iText5 AGPL).

```java
// statement/StatementPdfGenerator.java — tách riêng khỏi service nghiệp vụ
@Component
public class StatementPdfGenerator {

    public byte[] generate(Account account, List<LedgerEntry> entries, LocalDate from, LocalDate to) {
        Document document = new Document();
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        try {
            PdfWriter.getInstance(document, out);
            document.open();
            document.add(new Paragraph("Statement — " + account.getAccountNumber()));
            document.add(new Paragraph("Period: " + from + " to " + to));

            PdfPTable table = new PdfPTable(3);
            table.addCell("Date"); table.addCell("Direction"); table.addCell("Amount");
            for (LedgerEntry e : entries) {
                table.addCell(e.getCreatedAt().toString());
                table.addCell(e.getDirection().name());
                table.addCell(e.getAmount().toString());
            }
            document.add(table);
            document.close();
        } catch (DocumentException e) {
            throw new IllegalStateException("Failed to generate statement PDF", e);
        }
        return out.toByteArray();
    }
}
```

---

### 12. API tải sao kê (Low)

**Công nghệ:** Caffeine cache — in-memory cache đơn giản, đủ cho quy mô demo (không cần cache phân tán như Redis).

```java
@Cacheable(value = "statements", key = "#accountId + '-' + #from + '-' + #to")
public byte[] getStatementPdf(Long accountId, LocalDate from, LocalDate to) {
    Account account = accountRepository.findById(accountId).orElseThrow(...);
    List<LedgerEntry> entries = ledgerEntryRepository.findForStatement(accountId, ..., ...);
    return pdfGenerator.generate(account, entries, from, to);
}

@GetMapping("/{id}/statement")
public ResponseEntity<byte[]> downloadStatement(@PathVariable Long id,
        @RequestParam LocalDate from, @RequestParam LocalDate to) {
    byte[] pdf = statementService.getStatementPdf(id, from, to);
    return ResponseEntity.ok()
        .contentType(MediaType.APPLICATION_PDF)
        .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=statement.pdf")
        .body(pdf);
}
```

---

## Week 8 — Audit Log & Cleanup

### 13. Thiết kế audit log (Medium)

```sql
-- V5__audit_log.sql
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    actor VARCHAR(50) NOT NULL,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(50),
    before_json TEXT,
    after_json TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);
```

**Công nghệ:** Spring AOP (`@Aspect`) — bắt method có annotation tùy chỉnh `@Audited`, log actor/action/before-after mà không nhét code logging vào business logic.

---

### 14. Lưu audit trail (Medium)

```java
// audit/Audited.java
@Retention(RetentionPolicy.RUNTIME) @Target(ElementType.METHOD)
public @interface Audited {
    String action();
    String entityType();
}

// audit/AuditAspect.java
@Aspect
@Component
@RequiredArgsConstructor
public class AuditAspect {
    private final AuditLogRepository auditLogRepository;
    private final ObjectMapper objectMapper; // Jackson

    @AfterReturning(pointcut = "@annotation(audited)", returning = "result")
    public void logAfter(JoinPoint jp, Audited audited, Object result) {
        AuditLog log = new AuditLog();
        log.setActor(CurrentUser.username());
        log.setAction(audited.action());
        log.setEntityType(audited.entityType());
        // Field nhạy cảm (password hash...) không được ghi — serialize DTO/response, không serialize entity thô
        log.setAfterJson(toJsonSafely(result));
        auditLogRepository.save(log);
    }

    private String toJsonSafely(Object obj) {
        try { return objectMapper.writeValueAsString(obj); }
        catch (JsonProcessingException e) { return "{\"error\":\"serialization failed\"}"; }
    }
}

// Áp dụng trên endpoint nhạy cảm, vd đổi trạng thái account (Phase 1 task 13):
@Audited(action = "CHANGE_ACCOUNT_STATUS", entityType = "Account")
@PreAuthorize("hasAnyRole('ADMIN', 'TELLER')")
@PatchMapping("/{id}/status")
public AccountResponse changeStatus(@PathVariable Long id, @RequestBody StatusRequest req) { ... }
```

---

### 15. API tra cứu audit log (Low)

```java
@PreAuthorize("hasRole('ADMIN')")
@GetMapping("/api/audit-log")
public Page<AuditLog> search(
        @RequestParam(required = false) String actor,
        @RequestParam(required = false) String entityType,
        Pageable pageable) {
    return auditLogRepository.search(actor, entityType, pageable);
}
```

### 16. Integration test savings + standing order (Medium)

End-to-end: mở sổ tiết kiệm → job tính lãi chạy `n` lần → tất toán; tạo standing order → job chạy → balance cả 2 bên đổi đúng. Dùng `@SpringBootTest` + Testcontainers như Phase 1, gọi trực tiếp `job.accrueDailyInterest()` / `job.runDueOrders()` thay vì chờ cron thật.

### 17. Refactor pattern dùng chung (Low)

Soát ownership-check (`account.getUser().getUsername().equals(username)`) đã lặp ở `AccountService`, `SavingsService` — rút thành 1 helper `OwnershipChecker.requireOwner(account, username)` dùng chung. Chỉ refactor sau khi thấy lặp ≥3 chỗ, không làm sớm hơn.

### 18. OpenAPI cho Phase 1-2 (Low)

```java
@Operation(summary = "Mở sổ tiết kiệm", description = "Trừ tiền từ account nguồn, tạo kỳ hạn gửi tiết kiệm")
@ApiResponse(responseCode = "201", description = "Đã tạo")
@ApiResponse(responseCode = "422", description = "Không đủ số dư")
@PostMapping("/api/savings")
public ResponseEntity<SavingsResponse> open(@Valid @RequestBody OpenSavingsRequest req) { ... }
```

### 19. Load test API transfer (Low)

```javascript
// k6/transfer_baseline.js
import http from 'k6/http';
import { check } from 'k6';

export const options = { vus: 50, duration: '30s' };

export default function () {
  const res = http.post('http://localhost:8080/api/transactions/transfer',
    JSON.stringify({ fromAccountId: 1, toAccountId: 2, amount: 1, reference: `${__VU}-${__ITER}` }),
    { headers: { Authorization: `Bearer ${__ENV.TOKEN}`, 'Content-Type': 'application/json' } });
  check(res, { 'status is 200': (r) => r.status === 200 });
}
```
`k6 run k6/transfer_baseline.js` — ghi lại p95 latency & throughput làm baseline so sánh sau Phase 4/5.

### 20. Buffer/catch-up (Low)

Dự phòng — không phải task kỹ thuật mới.

---

## Kiến thức hay bị hỏi khi phỏng vấn (từ phase này)

- Vì sao dùng AOP cho audit log thay vì gọi trực tiếp trong service (tách biệt cross-cutting concern khỏi business logic, DRY).
- Cách tính lãi đơn giản (simple interest theo ngày) vs lãi kép — tradeoff đã chọn và vì sao chọn đơn giản cho demo project.
- Idempotent scheduled job trong môi trường nhiều instance: điều gì xảy ra nếu 2 instance app cùng chạy `@Scheduled` cùng lúc (double-execute) — câu trả lời trung thực: chưa xử lý (cần `ShedLock`/distributed lock), nằm ngoài phạm vi phase này, nên ghi vào README.
- Vì sao standing order job catch lỗi per-order thay vì để cả batch fail theo 1 exception.
