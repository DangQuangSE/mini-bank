/**
 * Mini Bank - Daily Task Tracker (Google Apps Script)
 *
 * Cách dùng:
 * 1. Mở Google Sheet (hoặc tạo mới) -> Extensions > Apps Script.
 * 2. Xóa nội dung Code.gs mặc định, dán toàn bộ file này vào.
 * 3. Chọn function "setupMiniBankTracker" trên thanh công cụ -> bấm Run.
 * 4. Cấp quyền khi được hỏi (script chỉ thao tác trên chính Sheet đang mở).
 * 5. Quay lại Google Sheet, sẽ thấy 2 tab: "Dashboard" và "Tasks".
 *
 * Sau lần setup đầu tiên, dùng menu "Mini Bank Tracker" trên thanh menu
 * của Sheet để rebuild hoặc tính lại lịch (ví dụ sau khi đổi Start Date).
 */

const TASKS_SHEET = 'Tasks';
const DASHBOARD_SHEET = 'Dashboard';

const STATUS_OPTIONS = ['Not Started', 'In Progress', 'Done', 'Blocked'];
const PRIORITY_OPTIONS = ['High', 'Medium', 'Low'];

const P1 = 'Phase 1 - Core Banking & Auth';
const P2 = 'Phase 2 - Extended Banking Features';
const P3 = 'Phase 3 - Async Processing & Loans';
const P4 = 'Phase 4 - Security & Risk';
const P5 = 'Phase 5 - Microservices Extraction';
const P6 = 'Phase 6 - Polish, Frontend & Ship';

const HEADERS = [
  'ID', 'Phase', 'Week', 'Category', 'Task', 'Description',
  'Priority', 'Est. Hours', 'Scheduled Date', 'Status', 'Done', 'Completed Date', 'Notes'
];

// [Phase, Week, Category, Task, Description, Priority, Hours]
const TASKS = [
  // Phase 1 - Core Banking & Auth (Week 1-4)
  [P1, 'Week 1', 'Setup', 'Kiểm tra môi trường local', 'Chạy docker compose up với Postgres, start app, xác nhận /actuator/health trả về UP', 'High', 2],
  [P1, 'Week 1', 'Database', 'Thiết kế ERD User & Account', 'Vẽ sơ đồ quan hệ User 1-N Account, ghi lại các quyết định thiết kế', 'High', 2],
  [P1, 'Week 1', 'Database', 'Viết Flyway migration V1', 'Tạo bảng users, accounts với constraint và index phù hợp', 'High', 2],
  [P1, 'Week 1', 'Backend', 'Tạo JPA entity User & Account', 'Viết entity, mapping, và Spring Data repository tương ứng', 'High', 2],
  [P1, 'Week 1', 'Testing', 'Test repository với Testcontainers', 'Viết test CRUD cho User/Account repository chạy trên Postgres thật', 'Medium', 2],

  [P1, 'Week 2', 'Backend', 'API đăng ký tài khoản', 'DTO validation, hash password bằng BCrypt, kiểm tra trùng email/username', 'High', 2],
  [P1, 'Week 2', 'Security', 'Cấu hình Spring Security cơ bản', 'Thêm starter-security, khai báo SecurityFilterChain, permit endpoint đăng ký/đăng nhập', 'High', 2],
  [P1, 'Week 2', 'Security', 'Xây dựng JWT util và API đăng nhập', 'Hàm generate/parse/validate token, endpoint login trả về access token', 'High', 2],
  [P1, 'Week 2', 'Security', 'JWT authentication filter', 'Viết filter đọc token từ header và gán vào SecurityContext', 'High', 2],
  [P1, 'Week 2', 'Security', 'Phân quyền theo role', 'Định nghĩa CUSTOMER/TELLER/ADMIN, áp dụng @PreAuthorize cho 1 endpoint mẫu', 'High', 2],

  [P1, 'Week 3', 'Backend', 'API mở tài khoản', 'Sinh số tài khoản, liên kết với user đang đăng nhập', 'High', 2],
  [P1, 'Week 3', 'Backend', 'API xem danh sách/chi tiết tài khoản', 'Kiểm tra quyền sở hữu trước khi trả dữ liệu', 'Medium', 2],
  [P1, 'Week 3', 'Backend', 'Trạng thái tài khoản', 'ACTIVE/FROZEN/CLOSED, endpoint riêng cho admin thao tác', 'Medium', 2],
  [P1, 'Week 3', 'Backend', 'Global exception handling', '@RestControllerAdvice, định dạng response lỗi thống nhất', 'High', 2],
  [P1, 'Week 3', 'Testing', 'Unit test cho account service', 'Dùng Mockito test các rule nghiệp vụ của account module', 'Medium', 2],

  [P1, 'Week 4', 'Database', 'Thiết kế double-entry ledger', 'Bảng transactions và ledger_entries, Flyway V2', 'High', 2],
  [P1, 'Week 4', 'Backend', 'API deposit & withdraw', 'Cập nhật số dư với optimistic locking', 'High', 2],
  [P1, 'Week 4', 'Backend', 'API transfer tiền', '2 ledger entry trong 1 transaction, hỗ trợ idempotency key', 'High', 2],
  [P1, 'Week 4', 'Testing', 'Test concurrency cho transfer', 'Mô phỏng nhiều transfer song song trên cùng 1 tài khoản, kiểm tra không mất dữ liệu', 'High', 2],
  [P1, 'Week 4', 'Backend', 'API lịch sử giao dịch', 'Phân trang, lọc theo ngày/loại giao dịch', 'Medium', 2],

  // Phase 2 - Extended Banking Features (Week 5-8)
  [P2, 'Week 5', 'Database', 'Thiết kế schema tiết kiệm/term deposit', 'Flyway migration cho savings_account', 'Medium', 2],
  [P2, 'Week 5', 'Backend', 'API mở sổ tiết kiệm', 'Nhận principal, lãi suất, kỳ hạn', 'Medium', 2],
  [P2, 'Week 5', 'Backend', 'Scheduled job tính lãi', 'Dùng @Scheduled để cộng dồn lãi định kỳ', 'Medium', 2],
  [P2, 'Week 5', 'Backend', 'Logic phạt khi rút sớm', 'Tính penalty khi tất toán trước hạn', 'Medium', 2],
  [P2, 'Week 5', 'Testing', 'Unit test tính lãi/penalty', 'Đảm bảo công thức tính đúng với các trường hợp biên', 'Medium', 2],

  [P2, 'Week 6', 'Database', 'Thiết kế standing order', 'Schema và API tạo/hủy lệnh chuyển tiền định kỳ', 'Medium', 2],
  [P2, 'Week 6', 'Backend', 'Scheduled job thực thi standing order', 'Tái sử dụng transfer service có sẵn', 'Medium', 2],
  [P2, 'Week 6', 'Backend', 'Xử lý lỗi standing order', 'Không đủ số dư, retry/backoff, ghi log thất bại', 'Medium', 2],
  [P2, 'Week 6', 'Testing', 'Integration test standing order', 'Kiểm tra job chạy đúng lịch và đúng số tiền', 'Medium', 2],

  [P2, 'Week 7', 'Backend', 'Truy vấn dữ liệu sao kê', 'Aggregate giao dịch theo tài khoản và khoảng thời gian', 'Medium', 2],
  [P2, 'Week 7', 'Backend', 'Xuất file PDF sao kê', 'Dùng OpenPDF/iText để generate statement', 'Medium', 2],
  [P2, 'Week 7', 'Backend', 'API tải sao kê', 'Endpoint download, cache file đã generate', 'Low', 2],

  [P2, 'Week 8', 'Database', 'Thiết kế audit log', 'Bảng audit_log, AOP aspect bắt các method nhạy cảm', 'Medium', 2],
  [P2, 'Week 8', 'Backend', 'Lưu audit trail', 'Ghi actor, action, before/after, timestamp', 'Medium', 2],
  [P2, 'Week 8', 'Backend', 'API tra cứu audit log', 'Endpoint cho admin, hỗ trợ filter', 'Low', 2],
  [P2, 'Week 8', 'Testing', 'Integration test savings + standing order', 'Kiểm tra end-to-end 2 module vừa làm', 'Medium', 2],
  [P2, 'Week 8', 'Backend', 'Refactor pattern dùng chung', 'Rút gọn validation/service pattern lặp lại ở Phase 2', 'Low', 2],
  [P2, 'Week 8', 'Docs', 'OpenAPI cho Phase 1-2', 'Bổ sung annotation springdoc cho toàn bộ endpoint đã có', 'Low', 2],
  [P2, 'Week 8', 'Testing', 'Load test API transfer', 'Dùng k6/JMeter đo throughput hiện tại làm baseline', 'Low', 2],
  [P2, 'Week 8', 'Backend', 'Buffer/catch-up', 'Hoàn thành phần còn lại của tuần 5-7 nếu bị trễ', 'Low', 2],

  // Phase 3 - Async Processing & Loans (Week 9-12)
  [P3, 'Week 9', 'DevOps', 'Thêm Kafka vào docker-compose', 'Verify producer/consumer hello-world hoạt động', 'Medium', 2],
  [P3, 'Week 9', 'Backend', 'Định nghĩa TransactionCompletedEvent', 'Publish event từ deposit/withdraw/transfer', 'Medium', 2],
  [P3, 'Week 9', 'Backend', 'Module notification', 'Consumer log/mock gửi email/SMS khi nhận event', 'Medium', 2],
  [P3, 'Week 9', 'Backend', 'Dead-letter và retry', 'Xử lý khi consume event thất bại', 'Medium', 2],

  [P3, 'Week 10', 'Database', 'Thiết kế schema loan', 'loan_application, loan, repayment_schedule', 'Medium', 2],
  [P3, 'Week 10', 'Backend', 'API đăng ký vay', 'Kèm check điều kiện vay đơn giản', 'Medium', 2],
  [P3, 'Week 10', 'Backend', 'Quy trình duyệt vay', 'State machine PENDING -> APPROVED/REJECTED', 'Medium', 2],
  [P3, 'Week 10', 'Backend', 'Sinh lịch trả nợ', 'Tính amortization schedule khi khoản vay được duyệt', 'Medium', 2],

  [P3, 'Week 11', 'Backend', 'API trả nợ thủ công', 'Cập nhật schedule và dư nợ còn lại', 'Medium', 2],
  [P3, 'Week 11', 'Backend', 'Job nhắc lịch trả nợ', 'Publish notification event trước hạn trả', 'Low', 2],
  [P3, 'Week 11', 'Backend', 'Job phát hiện quá hạn', 'Đánh dấu khoản vay overdue/default', 'Medium', 2],
  [P3, 'Week 11', 'Testing', 'Unit test amortization', 'Kiểm tra logic tính lịch trả nợ và phát hiện quá hạn', 'Medium', 2],

  [P3, 'Week 12', 'Testing', 'Integration test loan end-to-end', 'Duyệt vay -> trả nợ -> nhận notification', 'Medium', 2],
  [P3, 'Week 12', 'Backend', 'Refactor loan + notification', 'Đồng bộ pattern với các module trước', 'Low', 2],
  [P3, 'Week 12', 'Docs', 'OpenAPI cho loan/notification', 'Bổ sung tài liệu API', 'Low', 2],
  [P3, 'Week 12', 'Docs', 'Ghi chú kiến trúc', 'Tại sao dùng event ở đây, rủi ro nếu consumer không idempotent', 'Low', 2],
  [P3, 'Week 12', 'Backend', 'Resilience check', 'Kiểm tra transfer vẫn chạy được khi broker down', 'Medium', 2],
  [P3, 'Week 12', 'Testing', 'Test retry Kafka consumer', 'Mô phỏng consumer thất bại và kiểm tra retry', 'Medium', 2],
  [P3, 'Week 12', 'Testing', 'Performance check lịch trả nợ', 'Đo thời gian generate schedule với khoản vay dài hạn', 'Low', 2],
  [P3, 'Week 12', 'Backend', 'Buffer/catch-up', 'Xử lý phần còn thiếu của Phase 3', 'Low', 2],

  // Phase 4 - Security & Risk (Week 13-16)
  [P4, 'Week 13', 'Database', 'Thiết kế schema thẻ (card)', 'Virtual card gắn với account, có hạn mức', 'Medium', 2],
  [P4, 'Week 13', 'Backend', 'API phát hành thẻ ảo', 'Mock sinh số thẻ/CVV, ghi chú concern về PCI trong README', 'Medium', 2],
  [P4, 'Week 13', 'Backend', 'API mô phỏng chi tiêu thẻ', 'Kiểm tra và trừ hạn mức', 'Medium', 2],
  [P4, 'Week 13', 'Backend', 'API khóa/mở/hủy thẻ', 'Các thao tác quản lý vòng đời thẻ', 'Medium', 2],

  [P4, 'Week 14', 'Backend', 'Thiết kế rule engine đơn giản', 'Interface cho amount threshold, velocity check', 'High', 2],
  [P4, 'Week 14', 'Backend', 'Áp dụng rule khi tạo giao dịch', 'Đánh dấu giao dịch nghi ngờ', 'High', 2],
  [P4, 'Week 14', 'Backend', 'Hàng đợi duyệt giao dịch nghi ngờ', 'Endpoint cho admin approve/reject', 'Medium', 2],
  [P4, 'Week 14', 'Testing', 'Unit test từng fraud rule', 'Kiểm tra riêng lẻ mỗi rule', 'Medium', 2],

  [P4, 'Week 15', 'Security', 'Sinh và lưu OTP', 'TTL cho OTP, endpoint yêu cầu OTP cho hành động nhạy cảm', 'High', 2],
  [P4, 'Week 15', 'Security', 'Xác thực OTP trước giao dịch lớn', 'Gắn bước verify OTP vào transfer vượt ngưỡng', 'High', 2],
  [P4, 'Week 15', 'Security', 'Rate limit cho OTP', 'Chặn spam yêu cầu OTP (Bucket4j hoặc counter đơn giản)', 'Medium', 2],

  [P4, 'Week 16', 'Security', 'Rate limit login/register', 'Chống brute-force', 'High', 2],
  [P4, 'Week 16', 'Security', 'Tự rà soát OWASP', 'SQLi, mass assignment, CORS, input validation', 'High', 2],
  [P4, 'Week 16', 'Security', 'Cấu hình security headers', 'CSP, HSTS, frame-options trong Spring Security', 'Medium', 2],
  [P4, 'Week 16', 'Testing', 'Test rate limit và OTP', 'Xác nhận các cơ chế hoạt động đúng', 'Medium', 2],
  [P4, 'Week 16', 'Security', 'Rà soát secrets', 'Chuyển hết config nhạy cảm sang env var/.env.example', 'High', 2],
  [P4, 'Week 16', 'DevOps', 'Quét lỗ hổng dependency', 'OWASP Dependency-Check hoặc mvn versions check', 'Low', 2],
  [P4, 'Week 16', 'Docs', 'Viết phần Security Decisions', 'Ghi rõ phạm vi đã làm và chưa làm trong README', 'Low', 2],
  [P4, 'Week 16', 'Testing', 'Regression Phase 1-3', 'Chạy lại toàn bộ test sau khi thêm security filter', 'Medium', 2],
  [P4, 'Week 16', 'Backend', 'Buffer/catch-up', 'Xử lý phần còn thiếu của Phase 4', 'Low', 2],

  // Phase 5 - Microservices Extraction (Week 17-20)
  [P5, 'Week 17', 'Architecture', 'Xác định service boundary', 'Định nghĩa API contract cho notification-service', 'Medium', 2],
  [P5, 'Week 17', 'DevOps', 'Tạo multi-module structure', 'Tách module/repo riêng cho notification-service', 'Medium', 2],
  [P5, 'Week 17', 'Backend', 'Tách notification-service', 'Chuyển code sang app Spring Boot riêng, tự quản lý schema nếu cần', 'Medium', 2],

  [P5, 'Week 18', 'DevOps', 'Setup Spring Cloud Gateway', 'Route request tới monolith và notification-service', 'Medium', 2],
  [P5, 'Week 18', 'DevOps', 'Thêm service discovery', 'Dùng Eureka hoặc static config routing', 'Medium', 2],
  [P5, 'Week 18', 'Backend', 'Gọi service qua REST/Feign', 'Thay thế gọi in-process bằng gọi qua network', 'Medium', 2],

  [P5, 'Week 19', 'Backend', 'Circuit breaker + retry', 'Dùng Resilience4j cho các cuộc gọi liên service', 'Medium', 2],
  [P5, 'Week 19', 'DevOps', 'Structured logging', 'Chuẩn hóa log dạng JSON trên các service', 'Low', 2],
  [P5, 'Week 19', 'DevOps', 'Metrics với Prometheus', 'Micrometer + Actuator, dashboard Grafana cơ bản', 'Medium', 2],
  [P5, 'Week 19', 'DevOps', 'Distributed tracing', 'OpenTelemetry xuyên suốt gateway - monolith - notification-service', 'Medium', 2],

  [P5, 'Week 20', 'Architecture', 'Định nghĩa contract statement-service', 'Chuẩn bị tách service thứ 2', 'Medium', 2],
  [P5, 'Week 20', 'Backend', 'Tách statement-service', 'Áp dụng lại quy trình đã làm với notification-service', 'Medium', 2],
  [P5, 'Week 20', 'DevOps', 'Cập nhật docker-compose full stack', 'Chạy đồng thời tất cả service', 'Medium', 2],
  [P5, 'Week 20', 'Testing', 'Integration test toàn chuỗi', 'Gateway -> monolith -> cả 2 service tách rời', 'Medium', 2],
  [P5, 'Week 20', 'Docs', 'Viết ADR cho việc tách service', 'Ghi rõ lý do và tradeoff', 'Low', 2],
  [P5, 'Week 20', 'Testing', 'Chaos test', 'Tắt notification-service, kiểm tra circuit breaker hoạt động', 'Medium', 2],
  [P5, 'Week 20', 'Docs', 'Rà soát eventual consistency', 'Đánh giá rủi ro dữ liệu không đồng bộ giữa các service', 'Low', 2],
  [P5, 'Week 20', 'Testing', 'So sánh performance trước/sau tách', 'Đo latency cho luồng notification', 'Low', 2],
  [P5, 'Week 20', 'Docs', 'Cập nhật OpenAPI theo kiến trúc mới', 'Phản ánh đúng service boundary mới', 'Low', 2],
  [P5, 'Week 20', 'Backend', 'Buffer/catch-up', 'Xử lý phần còn thiếu của Phase 5', 'Low', 2],

  // Phase 6 - Polish, Frontend & Ship (Week 21-24)
  [P6, 'Week 21', 'Testing', 'Tăng coverage unit test', 'Mục tiêu 80%+ cho service layer các module chính', 'Medium', 2],
  [P6, 'Week 21', 'Docs', 'Hoàn thiện OpenAPI/Swagger', 'Rà soát toàn bộ schema và ví dụ', 'Low', 2],
  [P6, 'Week 21', 'Docs', 'Vẽ architecture diagram', 'Kiểu C4, cập nhật vào README', 'Medium', 2],

  [P6, 'Week 22', 'Frontend', 'Khởi tạo Next.js app', 'Layout cơ bản, API client, cấu hình env trỏ về backend', 'Medium', 2],
  [P6, 'Week 22', 'Frontend', 'Trang đăng nhập/đăng ký', 'Gọi API auth, xử lý lưu JWT', 'Medium', 2],

  [P6, 'Week 23', 'Frontend', 'Trang dashboard', 'Danh sách tài khoản và số dư', 'Medium', 2],
  [P6, 'Week 23', 'Frontend', 'Form chuyển tiền + lịch sử giao dịch', 'Bảng có phân trang', 'Medium', 2],
  [P6, 'Week 23', 'Frontend', 'Trang admin tối thiểu', 'Duyệt giao dịch nghi ngờ, duyệt khoản vay', 'Low', 2],

  [P6, 'Week 24', 'DevOps', 'Dockerize toàn bộ hệ thống', 'docker-compose profile cho demo full stack local', 'Medium', 2],
  [P6, 'Week 24', 'DevOps', 'Thiết lập CI', 'GitHub Actions build + test mỗi lần push', 'Medium', 2],
  [P6, 'Week 24', 'Frontend', 'Hoàn thiện UI state', 'Loading/error/empty, kiểm tra lại toàn bộ user journey', 'Medium', 2],
  [P6, 'Week 24', 'Docs', 'Quay video/chụp ảnh demo', 'Chuẩn bị tư liệu cho CV', 'Low', 2],
  [P6, 'Week 24', 'Docs', 'Viết case-study cho README', 'Quyết định thiết kế, tradeoff, điều sẽ làm khác', 'Medium', 2],
  [P6, 'Week 24', 'Testing', 'Regression cuối cùng', 'Kiểm tra toàn bộ module trước khi chốt bản', 'High', 2],
  [P6, 'Week 24', 'Backend', 'Buffer/catch-up 1', 'Dự phòng thời gian trễ lịch', 'Low', 2],
  [P6, 'Week 24', 'Backend', 'Buffer/catch-up 2', 'Dự phòng thời gian trễ lịch', 'Low', 2],
  [P6, 'Week 24', 'Backend', 'Buffer/catch-up 3', 'Dự phòng thời gian trễ lịch', 'Low', 2],
  [P6, 'Week 24', 'Backend', 'Buffer/catch-up 4', 'Dự phòng thời gian trễ lịch', 'Low', 2],
  [P6, 'Week 24', 'Backend', 'Buffer/catch-up 5', 'Dự phòng thời gian trễ lịch', 'Low', 2],
  [P6, 'Week 24', 'Docs', 'Tổng kết và chuẩn bị phỏng vấn', 'Liệt kê các câu hỏi/kiến thức có thể được hỏi từ chính project này', 'Medium', 2],
];

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Mini Bank Tracker')
    .addItem('Build / Rebuild Tracker', 'setupMiniBankTracker')
    .addItem('Recalculate Schedule', 'recalculateSchedule')
    .addToUi();
}

function setupMiniBankTracker() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  buildTasksSheet(ss);
  buildDashboardSheet(ss);
  recalculateSchedule();
  SpreadsheetApp.getUi().alert('Mini Bank Tracker đã sẵn sàng. Xem tab "Dashboard" và "Tasks".');
}

function buildTasksSheet(ss) {
  let sheet = ss.getSheetByName(TASKS_SHEET);
  if (sheet) {
    sheet.clear();
    sheet.clearFormats();
  } else {
    sheet = ss.insertSheet(TASKS_SHEET);
  }
  sheet.setTabColor('#38761d');

  sheet.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]);
  sheet.getRange(1, 1, 1, HEADERS.length)
    .setBackground('#1c4587')
    .setFontColor('#ffffff')
    .setFontWeight('bold')
    .setHorizontalAlignment('center');
  sheet.setFrozenRows(1);

  const rows = TASKS.map((t, i) => {
    const [phase, week, category, task, description, priority, hours] = t;
    return [i + 1, phase, week, category, task, description, priority, hours, '', 'Not Started', false, '', ''];
  });

  sheet.getRange(2, 1, rows.length, HEADERS.length).setValues(rows);

  sheet.setColumnWidth(1, 40);
  sheet.setColumnWidth(2, 240);
  sheet.setColumnWidth(3, 70);
  sheet.setColumnWidth(4, 90);
  sheet.setColumnWidth(5, 260);
  sheet.setColumnWidth(6, 340);
  sheet.setColumnWidth(7, 80);
  sheet.setColumnWidth(8, 80);
  sheet.setColumnWidth(9, 110);
  sheet.setColumnWidth(10, 110);
  sheet.setColumnWidth(11, 60);
  sheet.setColumnWidth(12, 110);
  sheet.setColumnWidth(13, 220);

  const priorityRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(PRIORITY_OPTIONS, true)
    .setAllowInvalid(false)
    .build();
  sheet.getRange(2, 7, rows.length, 1).setDataValidation(priorityRule);

  const statusRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(STATUS_OPTIONS, true)
    .setAllowInvalid(false)
    .build();
  sheet.getRange(2, 10, rows.length, 1).setDataValidation(statusRule);

  sheet.getRange(2, 11, rows.length, 1).insertCheckboxes();

  sheet.getRange(2, 9, rows.length, 1).setNumberFormat('yyyy-mm-dd');
  sheet.getRange(2, 12, rows.length, 1).setNumberFormat('yyyy-mm-dd');

  const statusRange = sheet.getRange(2, 10, rows.length, 1);
  const priorityRange = sheet.getRange(2, 7, rows.length, 1);
  const rules = [
    SpreadsheetApp.newConditionalFormatRule().whenTextEqualTo('Done').setBackground('#d9ead3').setFontColor('#274e13').setRanges([statusRange]).build(),
    SpreadsheetApp.newConditionalFormatRule().whenTextEqualTo('In Progress').setBackground('#fff2cc').setFontColor('#7f6000').setRanges([statusRange]).build(),
    SpreadsheetApp.newConditionalFormatRule().whenTextEqualTo('Blocked').setBackground('#f4cccc').setFontColor('#990000').setRanges([statusRange]).build(),
    SpreadsheetApp.newConditionalFormatRule().whenTextEqualTo('Not Started').setBackground('#f3f3f3').setFontColor('#666666').setRanges([statusRange]).build(),
    SpreadsheetApp.newConditionalFormatRule().whenTextEqualTo('High').setFontColor('#990000').setBold(true).setRanges([priorityRange]).build(),
  ];
  sheet.setConditionalFormatRules(rules);

  sheet.getRange(1, 1, rows.length + 1, HEADERS.length).createFilter();
  sheet.setRowHeights(2, rows.length, 24);
  sheet.getRange(2, 1, rows.length, HEADERS.length).setVerticalAlignment('top').setWrap(true);
}

function buildDashboardSheet(ss) {
  let sheet = ss.getSheetByName(DASHBOARD_SHEET);
  if (sheet) {
    sheet.clear();
    sheet.clearFormats();
    const charts = sheet.getCharts();
    charts.forEach(c => sheet.removeChart(c));
  } else {
    sheet = ss.insertSheet(DASHBOARD_SHEET);
  }
  sheet.setTabColor('#1c4587');
  ss.setActiveSheet(sheet);
  ss.moveActiveSheet(1);

  sheet.getRange('A1').setValue('Mini Bank - Project Tracker').setFontSize(18).setFontWeight('bold').setFontColor('#1c4587');
  sheet.getRange('A2').setValue('6 tháng, khoảng 2 giờ code mỗi ngày làm việc (T2-T6).').setFontStyle('italic').setFontColor('#666666');

  sheet.getRange('A4').setValue('Start Date').setFontWeight('bold');
  const existingStart = sheet.getRange('B4').getValue();
  sheet.getRange('B4')
    .setValue(existingStart instanceof Date ? existingStart : new Date())
    .setNumberFormat('yyyy-mm-dd')
    .setBackground('#fff2cc');
  sheet.getRange('C4').setValue('<- đổi ngày này rồi chạy menu "Recalculate Schedule"').setFontColor('#999999').setFontStyle('italic');

  sheet.getRange('A5').setValue('Hours / Session').setFontWeight('bold');
  sheet.getRange('B5').setValue(2);

  sheet.getRange('A7').setValue('Total Tasks').setFontWeight('bold');
  sheet.getRange('B7').setFormula('=COUNTA(' + TASKS_SHEET + '!A2:A)');

  sheet.getRange('A8').setValue('Completed').setFontWeight('bold');
  sheet.getRange('B8').setFormula('=COUNTIF(' + TASKS_SHEET + '!J2:J,"Done")');

  sheet.getRange('A9').setValue('Completion %').setFontWeight('bold');
  sheet.getRange('B9').setFormula('=IF(B7=0,0,B8/B7)').setNumberFormat('0.0%');

  sheet.getRange('A10').setValue('Total Est. Hours').setFontWeight('bold');
  sheet.getRange('B10').setFormula('=SUM(' + TASKS_SHEET + '!H2:H)');

  sheet.getRange('A11').setValue('Est. Finish Date').setFontWeight('bold');
  sheet.getRange('B11').setFormula('=MAX(' + TASKS_SHEET + '!I2:I)').setNumberFormat('yyyy-mm-dd');

  sheet.getRange('A4:B11').setBorder(true, true, true, true, true, false);

  const header = ['Phase', 'Tasks', 'Done', 'In Progress', 'Blocked', '% Complete'];
  sheet.getRange(13, 1, 1, header.length).setValues([header])
    .setFontWeight('bold').setBackground('#1c4587').setFontColor('#ffffff');

  const phases = [];
  TASKS.forEach(t => { if (phases.indexOf(t[0]) === -1) phases.push(t[0]); });

  phases.forEach((phase, i) => {
    const row = 14 + i;
    sheet.getRange(row, 1).setValue(phase);
    sheet.getRange(row, 2).setFormula('=COUNTIF(' + TASKS_SHEET + '!B:B,A' + row + ')');
    sheet.getRange(row, 3).setFormula('=COUNTIFS(' + TASKS_SHEET + '!B:B,A' + row + ',' + TASKS_SHEET + '!J:J,"Done")');
    sheet.getRange(row, 4).setFormula('=COUNTIFS(' + TASKS_SHEET + '!B:B,A' + row + ',' + TASKS_SHEET + '!J:J,"In Progress")');
    sheet.getRange(row, 5).setFormula('=COUNTIFS(' + TASKS_SHEET + '!B:B,A' + row + ',' + TASKS_SHEET + '!J:J,"Blocked")');
    sheet.getRange(row, 6).setFormula('=IF(B' + row + '=0,0,C' + row + '/B' + row + ')').setNumberFormat('0.0%');
  });

  const tableEndRow = 13 + phases.length;
  sheet.getRange(13, 1, phases.length + 1, header.length).setBorder(true, true, true, true, true, true);

  sheet.setColumnWidth(1, 260);
  for (let c = 2; c <= 6; c++) sheet.setColumnWidth(c, 100);

  const chartRange = sheet.getRange(13, 1, phases.length + 1, 3);
  const chart = sheet.newChart()
    .setChartType(Charts.ChartType.COLUMN)
    .addRange(chartRange)
    .setPosition(14, 8, 0, 0)
    .setOption('title', 'Tiến độ theo Phase (Tasks vs Done)')
    .setOption('legend', { position: 'top' })
    .setOption('width', 640)
    .setOption('height', 320)
    .build();
  sheet.insertChart(chart);
}

function recalculateSchedule() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const dashboard = ss.getSheetByName(DASHBOARD_SHEET);
  const tasksSheet = ss.getSheetByName(TASKS_SHEET);
  if (!dashboard || !tasksSheet) return;

  const startValue = dashboard.getRange('B4').getValue();
  const lastRow = tasksSheet.getLastRow();
  const numTasks = lastRow - 1;
  if (numTasks <= 0) return;

  let current = new Date(startValue);
  while (isWeekend(current)) {
    current = addDays(current, 1);
  }

  const dates = [];
  for (let i = 0; i < numTasks; i++) {
    dates.push([current]);
    current = nextWorkingDay(current);
  }

  tasksSheet.getRange(2, 9, numTasks, 1).setValues(dates);
  tasksSheet.getRange(2, 9, numTasks, 1).setNumberFormat('yyyy-mm-dd');
}

function isWeekend(date) {
  const day = date.getDay();
  return day === 0 || day === 6;
}

function addDays(date, n) {
  const d = new Date(date);
  d.setDate(d.getDate() + n);
  return d;
}

function nextWorkingDay(date) {
  let next = addDays(date, 1);
  while (isWeekend(next)) {
    next = addDays(next, 1);
  }
  return next;
}

function onEdit(e) {
  const sheet = e.range.getSheet();
  if (sheet.getName() !== TASKS_SHEET) return;

  const row = e.range.getRow();
  const col = e.range.getColumn();
  if (row === 1) return;

  const DONE_COL = 11;
  const STATUS_COL = 10;
  const COMPLETED_COL = 12;

  if (col === DONE_COL) {
    const checked = e.range.getValue();
    const statusCell = sheet.getRange(row, STATUS_COL);
    const completedCell = sheet.getRange(row, COMPLETED_COL);
    if (checked === true) {
      statusCell.setValue('Done');
      completedCell.setValue(new Date()).setNumberFormat('yyyy-mm-dd');
    } else {
      if (statusCell.getValue() === 'Done') {
        statusCell.setValue('In Progress');
      }
      completedCell.clearContent();
    }
  }

  if (col === STATUS_COL) {
    const status = e.range.getValue();
    const doneCell = sheet.getRange(row, DONE_COL);
    doneCell.setValue(status === 'Done');
  }
}
