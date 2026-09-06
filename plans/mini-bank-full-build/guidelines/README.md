# Mini Bank — Implementation Guidelines (theo TaskTracker.gs)

6 file guideline dưới đây tương ứng 6 phase trong roadmap gốc `tools/task-tracker/TaskTracker.gs` (120 task, 24 tuần, ~2h/task). Mỗi file liệt kê toàn bộ task của phase kèm hướng dẫn kỹ thuật cụ thể (cách làm, pitfall, pattern tái sử dụng từ phase trước), và 1 mục "Kiến thức hay bị hỏi khi phỏng vấn" ở cuối.

Đây là tài liệu **trước khi build** (pre-implementation reference) — khác với `GUIDELINE.md` (dự kiến ở root sau khi code xong) ghi lại những gì đã thực sự được implement.

| Phase | File | Tuần | Trọng tâm |
|---|---|---|---|
| 1 | [phase-1-core-banking-auth.md](phase-1-core-banking-auth.md) | 1-4 | User/Account, JWT auth, double-entry ledger, transfer concurrency |
| 2 | [phase-2-extended-banking-features.md](phase-2-extended-banking-features.md) | 5-8 | Savings/term deposit, standing order, PDF statement, audit log |
| 3 | [phase-3-async-processing-loans.md](phase-3-async-processing-loans.md) | 9-12 | Kafka notification, loan + amortization schedule, overdue detection |
| 4 | [phase-4-security-risk.md](phase-4-security-risk.md) | 13-16 | Virtual card, fraud rule engine, OTP, rate limit, OWASP hardening |
| 5 | [phase-5-microservices-extraction.md](phase-5-microservices-extraction.md) | 17-20 | Tách notification-service + statement-service, gateway, discovery, resilience, tracing |
| 6 | [phase-6-polish-frontend-ship.md](phase-6-polish-frontend-ship.md) | 21-24 | Test coverage, Next.js frontend, Docker + CI, case-study |

## Quyết định phạm vi (2026-09-06)

Roadmap được theo **đúng nguyên bản** trong `TaskTracker.gs`, bao gồm Phase 5 tách microservices thật (gateway, service discovery, distributed tracing) — không thay bằng phương án monolith-only đã cân nhắc ở một phiên trước.

## Dependency giữa các phase

Mỗi phase build trực tiếp lên entity/service của phase trước — đặc biệt `Account`/`Transaction` (Phase 1) và Kafka event (Phase 3) được tái sử dụng xuyên suốt Phase 2, 3, 5. Đọc guideline theo đúng thứ tự phase, đừng nhảy cóc.
