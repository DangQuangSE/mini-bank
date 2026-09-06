# Phase 5 — Microservices Extraction (Week 17–20)

> Nguồn: `tools/task-tracker/TaskTracker.gs` (P5) — theo đúng roadmap gốc: tách microservice thật.
> Stack thêm: Spring Cloud Gateway, Eureka, OpenFeign, Resilience4j, Micrometer + Prometheus + Grafana, OpenTelemetry + Jaeger.

## Mục tiêu phase

Tách `notification-service` và `statement-service` khỏi monolith thành app Spring Boot độc lập, thêm gateway + service discovery + resilience + observability xuyên suốt. Phase rủi ro cao nhất — độ phức tạp hạ tầng tăng mạnh.

## Cấu trúc repo/module đề xuất

```
mini-bank-be/                  # monolith gốc (Phase 1-4)
notification-service/          # tách ở Week 17 — Spring Boot riêng
statement-service/             # tách ở Week 20 — Spring Boot riêng
gateway-service/               # Spring Cloud Gateway
eureka-server/                 # service discovery
```

## Definition of Done

- `notification-service` và `statement-service` chạy độc lập, gọi qua network.
- Gateway route đúng tới cả monolith và 2 service, service discovery hoạt động.
- Circuit breaker chặn cascading failure khi 1 service down (chaos test pass).
- `docker-compose` full stack chạy đồng thời tất cả thành phần.

---

## Week 17 — Notification Service Extraction

### 1. Xác định service boundary (Medium)

**Tư duy xử lý:** Contract-first — viết OpenAPI spec cho `notification-service` **trước** khi tách code, tránh leak internal model của monolith. Quyết định: `notification-service` **không cần DB riêng** — nó chỉ consume Kafka event và gửi notification (stateless), khác với `statement-service` (Week 20) cần đọc dữ liệu transaction.

```yaml
# notification-service/openapi.yaml (contract tối thiểu — chủ yếu consume Kafka, ít REST)
openapi: 3.0.0
info: { title: Notification Service, version: 1.0.0 }
paths:
  /actuator/health:
    get: { responses: { '200': { description: OK } } }
```

---

### 2. Tạo multi-module structure (Medium)

```xml
<!-- notification-service/pom.xml — Spring Boot app độc lập, KHÔNG phụ thuộc mini-bank-be -->
<parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>3.3.0</version>
</parent>
<dependencies>
    <dependency><groupId>org.springframework.kafka</groupId><artifactId>spring-kafka</artifactId></dependency>
    <dependency><groupId>org.springframework.cloud</groupId><artifactId>spring-cloud-starter-netflix-eureka-client</artifactId></dependency>
    <dependency><groupId>io.micrometer</groupId><artifactId>micrometer-registry-prometheus</artifactId></dependency>
</dependencies>
```

---

### 3. Tách notification-service (Medium)

**Tư duy xử lý:** Chuyển nguyên `NotificationConsumer` + `DeadLetterPublishingRecoverer` config từ Phase 3 sang app mới. Monolith **không cần biết** notification-service đã tách — nó vẫn publish lên topic Kafka `transaction-completed` y hệt Phase 3 task 2. Đây là bằng chứng rõ ràng cho lợi ích decoupling qua event.

```java
// notification-service/src/main/java/.../NotificationConsumer.java
// GIỐNG HỆT code Phase 3 task 3 — chỉ khác: chạy trong app/JVM riêng
@Component
@Slf4j
public class NotificationConsumer {
    @KafkaListener(topics = "transaction-completed", groupId = "notification-service")
    public void onMessage(TransactionCompletedEvent event) {
        log.info("[NOTIFY] Account {} — {} of {}", event.accountId(), event.type(), event.amount());
    }
}
```

---

## Week 18 — Gateway & Service Discovery

### 4. Setup Spring Cloud Gateway (Medium)

```yaml
# gateway-service/application.yml
spring:
  cloud:
    gateway:
      routes:
        - id: notification-service
          uri: lb://notification-service   # lb:// = load-balanced qua Eureka
          predicates: [ Path=/api/notifications/** ]
        - id: monolith
          uri: lb://mini-bank-be
          predicates: [ Path=/api/** ]
```

---

### 5. Thêm service discovery (Medium)

**Tư duy xử lý:** Eureka thể hiện đúng client-side service discovery pattern (mỗi service tự register, gateway tra cứu động) — chọn Eureka thay vì static config để minh họa đúng kiến trúc, dù tăng 1 thành phần hạ tầng cần vận hành. Ghi lựa chọn này vào ADR (task 15).

```java
// eureka-server/EurekaServerApplication.java
@SpringBootApplication
@EnableEurekaServer
public class EurekaServerApplication {
    public static void main(String[] args) { SpringApplication.run(EurekaServerApplication.class, args); }
}
```

```yaml
# mỗi service (monolith, notification-service, statement-service, gateway) thêm:
eureka:
  client:
    service-url:
      defaultZone: http://eureka-server:8761/eureka/
spring:
  application:
    name: mini-bank-be   # tên dùng để Eureka/Feign/Gateway tra cứu — đổi tương ứng mỗi service
```

---

### 6. Gọi service qua REST/Feign (Medium)

```java
// mini-bank-be/.../NotificationClient.java — nếu monolith cần gọi trực tiếp (ngoài Kafka)
@FeignClient(name = "notification-service") // tên khớp spring.application.name của service đích
public interface NotificationClient {
    @GetMapping("/actuator/health")
    ResponseEntity<String> health();
}
```
```java
@EnableFeignClients
@SpringBootApplication
public class MiniBankBeApplication { ... }
```

---

## Week 19 — Resilience & Observability

### 7. Circuit breaker + retry (Medium)

**Tư duy xử lý:** Circuit breaker có 3 state: CLOSED (bình thường) → OPEN (sau ngưỡng lỗi, chặn call ngay không chờ timeout) → HALF_OPEN (thử lại vài request để xem service đã hồi phục chưa).

```java
@FeignClient(name = "notification-service")
public interface NotificationClient {
    @GetMapping("/actuator/health")
    ResponseEntity<String> health();
}

@Service
@RequiredArgsConstructor
public class NotificationHealthChecker {
    private final NotificationClient client;

    @CircuitBreaker(name = "notificationService", fallbackMethod = "fallback")
    @Retry(name = "notificationService")
    public String checkHealth() {
        return client.health().getBody();
    }

    private String fallback(Exception ex) {
        return "notification-service unavailable"; // degrade thay vì lỗi 500
    }
}
```

```yaml
resilience4j:
  circuitbreaker:
    instances:
      notificationService:
        sliding-window-size: 10
        failure-rate-threshold: 50    # mở circuit sau 50% lỗi trong 10 request
        wait-duration-in-open-state: 10s
  retry:
    instances:
      notificationService:
        max-attempts: 3
        wait-duration: 500ms
```

---

### 8. Structured logging (Low)

```xml
<!-- logback-spring.xml -->
<encoder class="net.logstash.logback.encoder.LogstashEncoder">
    <includeMdcKeyName>traceId</includeMdcKeyName>
    <includeMdcKeyName>spanId</includeMdcKeyName>
</encoder>
```
`traceId` được OpenTelemetry (task 10) tự động đưa vào MDC — log JSON của mọi service đều có cùng `traceId` cho 1 request xuyên suốt gateway → monolith → service.

---

### 9. Metrics với Prometheus (Medium)

```properties
# mỗi service
management.endpoints.web.exposure.include=health,prometheus
management.metrics.tags.application=${spring.application.name}
```
```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'mini-bank'
    metrics_path: /actuator/prometheus
    static_configs:
      - targets: ['gateway:8080', 'mini-bank-be:8080', 'notification-service:8080']
```
Grafana dashboard cơ bản: request rate, error rate, latency p50/p99 (RED metrics) — import dashboard mẫu "Spring Boot Statistics" (ID 12900) làm điểm khởi đầu.

---

### 10. Distributed tracing (Medium)

```xml
<dependency><groupId>io.opentelemetry.instrumentation</groupId><artifactId>opentelemetry-spring-boot-starter</artifactId></dependency>
```
```properties
management.tracing.sampling.probability=1.0
management.otlp.tracing.endpoint=http://jaeger:4318/v1/traces
```
OpenTelemetry SDK tự propagate `traceparent` header qua Feign/RestTemplate/WebClient — không cần code thủ công. Xem trace end-to-end trong Jaeger UI: 1 request vào gateway sẽ hiện đủ span qua monolith và notification-service.

---

## Week 20 — Second Service, Full Stack, Validation

### 11. Định nghĩa contract statement-service (Medium)

Áp dụng lại task 1 — khác `notification-service`, `statement-service` cần đọc dữ liệu `ledger_entries` nên **cần** kết nối DB (schema riêng `statement_schema` trong cùng Postgres instance, hoặc DB riêng nếu muốn tách hẳn — ghi tradeoff vào ADR).

### 12. Tách statement-service (Medium)

Chuyển `StatementService` + `StatementPdfGenerator` (Phase 2 task 10-12) sang app riêng, expose `/api/statements/{accountId}` qua gateway route mới.

### 13. Cập nhật docker-compose full stack (Medium)

```yaml
services:
  postgres: { ... }          # Phase 1
  kafka: { ... }              # Phase 3
  eureka-server: { build: ./eureka-server, ports: ["8761:8761"] }
  gateway-service: { build: ./gateway-service, ports: ["8080:8080"], depends_on: [eureka-server] }
  mini-bank-be: { build: ./mini-bank-be, depends_on: [postgres, kafka, eureka-server] }
  notification-service: { build: ./notification-service, depends_on: [kafka, eureka-server] }
  statement-service: { build: ./statement-service, depends_on: [postgres, eureka-server] }
  prometheus: { image: prom/prometheus, ports: ["9090:9090"] }
  grafana: { image: grafana/grafana, ports: ["3001:3000"] }
  jaeger: { image: jaegertracing/all-in-one, ports: ["16686:16686", "4318:4318"] }
```
`docker compose up` — 1 lệnh chạy toàn bộ.

### 14. Integration test toàn chuỗi (Medium)

Test request qua gateway (`http://localhost:8080/api/notifications/...`) → verify route đúng tới service tách rời — có thể dùng Testcontainers cho từng service hoặc test thủ công qua script `curl` trong CI.

### 15. Viết ADR cho việc tách service (Low)

```markdown
# ADR-001: Extract notification-service and statement-service

## Context
Monolith Phase 1-4 đã ổn định. Muốn minh họa microservices pattern cho CV.

## Decision
Tách 2 service này trước (không phải account/transaction) vì bounded context ổn định,
ít phụ thuộc ngược vào core banking.

## Tradeoffs
- Eureka thay vì static routing: đúng pattern hơn, thêm 1 thành phần vận hành.
- statement-service dùng schema riêng cùng Postgres instance (không DB riêng hoàn toàn):
  giảm chi phí hạ tầng demo, đánh đổi bounded-context isolation.
```

### 16. Chaos test (Medium)

```bash
docker stop notification-service
# gọi API transfer qua gateway — PHẢI vẫn 200 (Kafka async, Phase 3 task 17 resilience check)
# gọi trực tiếp route notification-service qua gateway — PHẢI degrade có kiểm soát (circuit breaker OPEN), không hang
```

### 17. Rà soát eventual consistency (Low)

`statement-service` đọc dữ liệu transaction có thể có độ trễ nếu đồng bộ qua event thay vì query trực tiếp DB monolith — ghi rủi ro này vào README/ADR, không bắt buộc giải quyết ở demo.

### 18. So sánh performance trước/sau tách (Low)

So k6 baseline Phase 2 task 19 (gọi thẳng monolith) vs gọi qua gateway → service tách rời — ghi lại độ tăng latency do thêm network hop, giải thích được tradeoff này khi phỏng vấn.

### 19. Cập nhật OpenAPI theo kiến trúc mới (Low)

Mỗi service có OpenAPI riêng; gateway có thể aggregate qua `springdoc-openapi-gateway` hoặc đơn giản là liệt kê link tới từng service trong README.

### 20. Buffer/catch-up (Low)

Dự phòng — phase này dễ trễ lịch nhất do độ phức tạp hạ tầng, ưu tiên task High/Medium trước.

---

## Kiến thức hay bị hỏi khi phỏng vấn (từ phase này)

- Vì sao tách notification-service và statement-service trước (bounded context ổn định, ít phụ thuộc ngược) thay vì account/transaction (core, rủi ro cao nếu tách sai).
- Circuit breaker states (Closed/Open/Half-Open) và Resilience4j implement thế nào.
- Service discovery: Eureka (client-side discovery) vs alternative (DNS-based/static) — tradeoff vận hành.
- Distributed tracing giải quyết gì mà structured logging đơn lẻ từng service không giải quyết được (liên kết request xuyên nhiều service qua `traceId`).
- Trung thực khi được hỏi "đây có phải microservices thật không": đủ minh họa pattern (gateway, discovery, resilience, tracing) nhưng thiếu nhiều thứ production cần (per-service CI/CD độc lập, service mesh, contract testing tự động, độc lập scale đã kiểm chứng thực tế).
