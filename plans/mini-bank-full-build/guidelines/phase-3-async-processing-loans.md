# Phase 3 — Async Processing & Loans (Week 9–12)

> Nguồn: `tools/task-tracker/TaskTracker.gs` (P3). 20 task.
> Stack thêm: Apache Kafka, Spring Kafka (`spring-kafka`).
> Phụ thuộc: reuse `TransactionService` (Phase 1) cho repayment, reuse pattern state-machine + `GlobalExceptionHandler`.

## Cấu trúc package thêm

```
com.minibank
├── notification/     # TransactionCompletedEvent, NotificationConsumer
└── loan/              # LoanApplication, Loan, RepaymentSchedule, jobs
```

## Definition of Done

- Transaction event publish qua Kafka, notification consumer nhận và xử lý được (kể cả khi fail → dead-letter/retry).
- Vay được duyệt, sinh lịch trả nợ đúng công thức amortization, phát hiện quá hạn tự động.
- Transfer vẫn hoạt động khi Kafka broker down.

---

## Week 9 — Kafka & Notification

### 1. Thêm Kafka vào docker-compose (Medium)

```yaml
# docker-compose.yml (bổ sung)
services:
  kafka:
    image: apache/kafka:3.7.0   # KRaft mode — không cần Zookeeper riêng
    ports: ["9092:9092"]
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
```

Verify: `docker exec -it <container> kafka-console-producer.sh --topic test --bootstrap-server localhost:9092` + console-consumer ở terminal khác.

```xml
<!-- pom.xml -->
<dependency>
    <groupId>org.springframework.kafka</groupId>
    <artifactId>spring-kafka</artifactId>
</dependency>
```

---

### 2. Định nghĩa TransactionCompletedEvent (Medium)

**Công nghệ:** `@TransactionalEventListener(phase = AFTER_COMMIT)` — Spring chỉ gọi listener **sau khi** transaction DB commit thành công. Nếu publish event ngay trong `@Transactional` method mà transaction rollback sau đó, event đã publish sẽ là dữ liệu sai (nói dối rằng transaction đã xảy ra).

```java
// notification/event/TransactionCompletedEvent.java
public record TransactionCompletedEvent(
    Long transactionId, Long accountId, String type, BigDecimal amount, Instant occurredAt) {}

// transaction/TransactionService.java — publish qua Spring ApplicationEventPublisher trước, Kafka sau
@Service
@RequiredArgsConstructor
public class TransactionService {
    private final ApplicationEventPublisher eventPublisher;
    // ... existing fields (Phase 1)

    @Transactional
    public Transaction transfer(...) {
        // ... existing logic (Phase 1 task 18)
        eventPublisher.publishEvent(new TransactionCompletedEvent(
            tx.getId(), from.getId(), "TRANSFER", amount, Instant.now()));
        return tx;
    }
}

// notification/TransactionEventPublisher.java — cầu nối Spring event -> Kafka topic
@Component
@RequiredArgsConstructor
public class TransactionEventPublisher {
    private final KafkaTemplate<String, TransactionCompletedEvent> kafkaTemplate;

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void onTransactionCompleted(TransactionCompletedEvent event) {
        // fire-and-forget: lỗi publish Kafka KHÔNG được rollback transaction chính (đã commit rồi)
        kafkaTemplate.send("transaction-completed", String.valueOf(event.accountId()), event)
            .exceptionally(ex -> { log.error("Failed to publish event", ex); return null; });
    }
}
```

---

### 3. Module notification (Medium)

```java
// notification/NotificationConsumer.java
@Component
@Slf4j
public class NotificationConsumer {

    @KafkaListener(topics = "transaction-completed", groupId = "notification-service")
    public void onMessage(TransactionCompletedEvent event) {
        // Mock gửi email/SMS — demo project không tích hợp provider thật
        log.info("[NOTIFY] Account {} — {} of {} completed", event.accountId(), event.type(), event.amount());
    }
}
```

```properties
spring.kafka.bootstrap-servers=localhost:9092
spring.kafka.consumer.group-id=notification-service
spring.kafka.consumer.value-deserializer=org.springframework.kafka.support.serializer.JsonDeserializer
spring.kafka.producer.value-serializer=org.springframework.kafka.support.serializer.JsonSerializer
spring.json.trusted.packages=com.minibank.notification.event
```

---

### 4. Dead-letter và retry (Medium)

**Tư duy xử lý:** Retry với backoff tăng dần trước, thất bại đủ N lần mới đẩy sang dead-letter topic — tránh mất message do lỗi thoáng qua (transient), nhưng cũng không retry vô hạn chặn consumer group.

```java
// notification/config/KafkaErrorConfig.java
@Configuration
public class KafkaErrorConfig {

    @Bean
    public DefaultErrorHandler errorHandler(KafkaTemplate<Object, Object> template) {
        var recoverer = new DeadLetterPublishingRecoverer(template,
            (record, ex) -> new TopicPartition(record.topic() + ".DLT", record.partition()));
        var backOff = new ExponentialBackOff(1000L, 2.0); // 1s, 2s, 4s...
        backOff.setMaxElapsedTime(10_000L); // tổng tối đa 10s trước khi vào DLT
        return new DefaultErrorHandler(recoverer, backOff);
    }
}
```

---

## Week 10 — Loan Schema & Application

### 5. Thiết kế schema loan (Medium)

```sql
-- V6__loans.sql
CREATE TABLE loan_applications (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES accounts(id),
    amount NUMERIC(19,4) NOT NULL,
    term_months INT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    applied_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE loans (
    id BIGSERIAL PRIMARY KEY,
    application_id BIGINT NOT NULL REFERENCES loan_applications(id),
    principal NUMERIC(19,4) NOT NULL,
    interest_rate NUMERIC(5,4) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'  -- ACTIVE, OVERDUE, DEFAULT, PAID_OFF
);

CREATE TABLE repayment_schedules (
    id BIGSERIAL PRIMARY KEY,
    loan_id BIGINT NOT NULL REFERENCES loans(id),
    installment_no INT NOT NULL,
    due_date DATE NOT NULL,
    principal_due NUMERIC(19,4) NOT NULL,
    interest_due NUMERIC(19,4) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING'  -- PENDING, PAID, OVERDUE
);
CREATE INDEX idx_repayment_due_date ON repayment_schedules(due_date, status);
```

---

### 6. API đăng ký vay (Medium)

```java
@Transactional
public LoanApplication apply(Long accountId, BigDecimal amount, int termMonths, String username) {
    Account account = ownedAccount(accountId, username);
    if (account.getStatus() != AccountStatus.ACTIVE) {
        throw new BusinessRuleException("Account must be ACTIVE to apply for a loan");
    }
    if (hasActiveOverdueLoan(accountId)) {
        throw new BusinessRuleException("Cannot apply while an existing loan is overdue");
    }
    LoanApplication app = new LoanApplication();
    app.setAccount(account); app.setAmount(amount); app.setTermMonths(termMonths);
    return loanApplicationRepository.save(app);
}
```

---

### 7. Quy trình duyệt vay (Medium)

**Tư duy xử lý:** State machine tập trung 1 chỗ — cùng pattern đã dùng ở `AccountStatus`/`SavingsStatus` (Phase 1-2). Không set status tự do từ nhiều service khác nhau.

```java
public enum LoanApplicationStatus { PENDING, APPROVED, REJECTED }

// LoanService
@PreAuthorize("hasAnyRole('ADMIN', 'TELLER')")
@Transactional
public Loan approve(Long applicationId, BigDecimal rate) {
    LoanApplication app = loanApplicationRepository.findById(applicationId)
        .orElseThrow(() -> new NotFoundException("Application not found"));
    if (app.getStatus() != LoanApplicationStatus.PENDING) {
        throw new BusinessRuleException("Application already processed");
    }
    app.setStatus(LoanApplicationStatus.APPROVED);

    Loan loan = new Loan();
    loan.setApplication(app);
    loan.setPrincipal(app.getAmount());
    loan.setInterestRate(rate);
    loan.setStatus(LoanStatus.ACTIVE);
    loanRepository.save(loan);

    scheduleGenerator.generate(loan, app.getTermMonths()); // task 8
    return loan;
}
```

---

### 8. Sinh lịch trả nợ (Medium)

**Tư duy xử lý:** Dùng công thức **annuity** (equal installment: gốc + lãi cố định mỗi kỳ) — phổ biến hơn equal-principal cho vay tiêu dùng, và là công thức hay bị hỏi khi phỏng vấn.

```java
// loan/RepaymentScheduleGenerator.java
@Component
@RequiredArgsConstructor
public class RepaymentScheduleGenerator {
    private final RepaymentScheduleRepository scheduleRepository;

    public void generate(Loan loan, int termMonths) {
        BigDecimal monthlyRate = loan.getInterestRate().divide(BigDecimal.valueOf(12), 10, RoundingMode.HALF_UP);
        BigDecimal installment = calculateAnnuityInstallment(loan.getPrincipal(), monthlyRate, termMonths);

        BigDecimal remainingPrincipal = loan.getPrincipal();
        List<RepaymentSchedule> schedules = new ArrayList<>();
        for (int i = 1; i <= termMonths; i++) {
            BigDecimal interestDue = remainingPrincipal.multiply(monthlyRate).setScale(4, RoundingMode.HALF_UP);
            BigDecimal principalDue = installment.subtract(interestDue).setScale(4, RoundingMode.HALF_UP);
            remainingPrincipal = remainingPrincipal.subtract(principalDue);

            RepaymentSchedule s = new RepaymentSchedule();
            s.setLoan(loan); s.setInstallmentNo(i);
            s.setDueDate(LocalDate.now().plusMonths(i));
            s.setPrincipalDue(principalDue); s.setInterestDue(interestDue);
            schedules.add(s);
        }
        scheduleRepository.saveAll(schedules); // batch insert — không save() từng record trong loop
    }

    // Công thức annuity: A = P * r * (1+r)^n / ((1+r)^n - 1)
    private BigDecimal calculateAnnuityInstallment(BigDecimal principal, BigDecimal monthlyRate, int n) {
        double p = principal.doubleValue(), r = monthlyRate.doubleValue();
        double factor = Math.pow(1 + r, n);
        double installment = p * r * factor / (factor - 1);
        return BigDecimal.valueOf(installment).setScale(4, RoundingMode.HALF_UP);
    }
}
```

---

## Week 11 — Repayment & Overdue

### 9. API trả nợ thủ công (Medium)

```java
@Transactional
public void payInstallment(Long scheduleId, String username) {
    RepaymentSchedule schedule = scheduleRepository.findById(scheduleId)
        .orElseThrow(() -> new NotFoundException("Schedule not found"));
    if (schedule.getStatus() == RepaymentStatus.PAID) throw new BusinessRuleException("Already paid");

    BigDecimal amount = schedule.getPrincipalDue().add(schedule.getInterestDue());
    Account payerAccount = ownerAccountOf(schedule.getLoan(), username);
    transactionService.withdraw(payerAccount.getId(), amount, "LOAN-PAY-" + scheduleId); // reuse Phase 1

    schedule.setStatus(RepaymentStatus.PAID);
    updateLoanStatusIfFullyPaid(schedule.getLoan());
}
```

---

### 10. Job nhắc lịch trả nợ (Low)

```java
@Scheduled(cron = "0 0 8 * * *")
public void remindUpcoming() {
    LocalDate threshold = LocalDate.now().plusDays(3);
    List<RepaymentSchedule> upcoming = scheduleRepository
        .findByDueDateAndStatus(threshold, RepaymentStatus.PENDING);
    upcoming.forEach(s -> eventPublisher.publishEvent(
        new RepaymentReminderEvent(s.getLoan().getId(), s.getDueDate()))); // tái sử dụng Kafka infra Week 9
}
```

---

### 11. Job phát hiện quá hạn (Medium)

```java
@Scheduled(cron = "0 0 2 * * *")
@Transactional
public void detectOverdue() {
    List<RepaymentSchedule> overdue = scheduleRepository
        .findByDueDateBeforeAndStatus(LocalDate.now(), RepaymentStatus.PENDING);
    for (RepaymentSchedule s : overdue) {
        s.setStatus(RepaymentStatus.OVERDUE);
        long daysLate = ChronoUnit.DAYS.between(s.getDueDate(), LocalDate.now());
        if (daysLate > 90) { // ngưỡng default tự định nghĩa
            s.getLoan().setStatus(LoanStatus.DEFAULT);
        } else {
            s.getLoan().setStatus(LoanStatus.OVERDUE);
        }
    }
}
```

---

### 12. Unit test amortization (Medium)

```java
@Test
void annuityInstallmentIsConstantAcrossSchedule() {
    Loan loan = loanOf(principal("12000"), rate("0.12"), months(12));
    List<RepaymentSchedule> schedule = generator.generate(loan, 12);

    BigDecimal firstTotal = schedule.get(0).getPrincipalDue().add(schedule.get(0).getInterestDue());
    BigDecimal lastTotal = schedule.get(11).getPrincipalDue().add(schedule.get(11).getInterestDue());
    assertThat(firstTotal).isCloseTo(lastTotal, within(new BigDecimal("0.01"))); // annuity: installment cố định
}

@Test
void overdueDetectionRespectsDueDateBoundary() {
    // due_date = hôm nay -> chưa overdue; due_date = hôm qua -> overdue
}
```

---

## Week 12 — Integration, Resilience & Docs

### 13. Integration test loan end-to-end (Medium)

Full flow: đăng ký vay → duyệt (task 7) → sinh lịch (task 8) → trả nợ (task 9) → assert `NotificationConsumer` nhận event (dùng `@EmbeddedKafka` từ `spring-kafka-test` cho integration test, không cần Kafka thật).

### 14. Refactor loan + notification (Low)

Đồng bộ exception handling với `GlobalExceptionHandler` (Phase 1) — không tạo advice riêng cho loan module.

### 15. OpenAPI cho loan/notification (Low)

Thêm `@Operation`/`@ApiResponse` cho `/api/loans/**`.

### 16. Ghi chú kiến trúc (Low)

Ghi vào README: tại sao dùng event ở đây (decoupling — transaction chính không chờ gửi notification xong mới trả response), rủi ro nếu consumer không idempotent (retry Kafka có thể deliver message 2 lần — "at-least-once" delivery — nên gửi email trùng lặp nếu consumer không dedupe theo `transactionId`).

### 17. Resilience check (Medium)

```bash
docker stop <kafka-container>
# gọi API transfer — phải vẫn trả 200, KHÔNG bị block/lỗi vì Kafka down
curl -X POST http://localhost:8080/api/transactions/transfer -d '...'
```
Nếu fail: quay lại task 2 — publish phải là fire-and-forget với `.exceptionally()`, không await kết quả gửi Kafka trong request thread.

### 18. Test retry Kafka consumer (Medium)

```java
@Test
void consumerRetriesThenGoesToDeadLetter() {
    // trigger consumer throw exception có chủ đích (test-only listener override)
    // verify: retry theo ExponentialBackOff, cuối cùng message xuất hiện ở topic "transaction-completed.DLT"
}
```

### 19. Performance check lịch trả nợ (Low)

Đo thời gian `generate()` với `termMonths = 240` (vay 20 năm) — xác nhận dùng `saveAll()` (batch) chứ không `save()` từng record trong loop (đã áp dụng ở task 8).

### 20. Buffer/catch-up (Low)

Dự phòng.

---

## Kiến thức hay bị hỏi khi phỏng vấn (từ phase này)

- Eventual consistency: chấp nhận được cho notification (chậm vài giây không sao) nhưng không chấp nhận được cho balance update (Phase 1 vẫn dùng transaction đồng bộ).
- `@TransactionalEventListener(AFTER_COMMIT)` giải quyết vấn đề gì so với publish event ngay trong transaction (tránh publish event cho transaction bị rollback).
- Kafka delivery semantics: "at-least-once" là gì, vì sao consumer cần idempotent.
- Dead-letter queue pattern — khi nào retry vô hạn là sai lầm (message lỗi vĩnh viễn — vd dữ liệu sai format — sẽ chặn cả partition nếu không có DLQ).
- Annuity vs equal-principal amortization — khác nhau ở đâu, vì sao annuity phổ biến hơn cho vay tiêu dùng.
