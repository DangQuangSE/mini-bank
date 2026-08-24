# Mini Bank — Task Tracker (Google Sheets)

Google Apps Script tạo một trang quản lý task chuyên nghiệp trên Google Sheet:
lộ trình 6 tháng (120 task, ~2 giờ/task/ngày làm việc) theo đúng roadmap
modular monolith → microservices đã chốt cho project mini-bank.

## Cài đặt

1. Mở Google Sheet bạn muốn dùng (hoặc tạo sheet mới).
2. Vào **Extensions > Apps Script**.
3. Xoá nội dung `Code.gs` mặc định, dán toàn bộ nội dung [TaskTracker.gs](TaskTracker.gs) vào.
4. Trên thanh công cụ, chọn function `setupMiniBankTracker` → bấm **Run**.
5. Cấp quyền khi được hỏi (script chỉ thao tác trên chính Sheet đang mở).
6. Quay lại Google Sheet — sẽ có 2 tab: **Dashboard** và **Tasks**.

## Sử dụng hằng ngày

- Tab **Tasks**: mỗi dòng là 1 buổi code (~2 giờ). Tick vào cột **Done** khi
  hoàn thành — Status và Completed Date tự cập nhật.
- Tab **Dashboard**: tổng quan tiến độ theo từng Phase, ngày dự kiến hoàn
  thành, biểu đồ so sánh Done/Total theo phase.
- Đổi ô **Start Date** trên Dashboard rồi chạy menu **Mini Bank Tracker >
  Recalculate Schedule** nếu muốn dời lại lịch (script tự bỏ qua thứ 7/CN).
- Chạy lại **Build / Rebuild Tracker** bất cứ lúc nào để reset toàn bộ dữ
  liệu về trạng thái ban đầu (mất tiến độ đã tick — cẩn thận khi dùng).

## Cấu trúc dữ liệu

`TaskTracker.gs` chứa mảng `TASKS` — nguồn dữ liệu duy nhất cho toàn bộ
roadmap. Muốn chỉnh sửa/thêm task, sửa trực tiếp mảng này rồi chạy lại
**Build / Rebuild Tracker**.
