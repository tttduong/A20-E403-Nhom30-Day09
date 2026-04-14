# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Nguyễn Thị Thu Hiền - 2A202600212  
**Vai trò trong nhóm:** Supervisor Owner / Sprint1
**Ngày nộp:** 14/04/2026  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

Trong buổi Lab Day 09, tôi chịu trách nhiệm chính về "bộ não" điều phối của hệ thống: **Orchestration Layer**. Tôi là người đặt nền móng cho toàn bộ dự án bằng cách thiết kế cấu trúc đồ thị (Graph) điều hướng công việc.

**Module/file tôi chịu trách nhiệm:**
- File chính: `graph.py`
- Functions tôi implement: `supervisor_node` (phân loại ý định), `route_decision` (điều hướng logic), `human_review_node` (xử lý ngoại lệ), và `build_graph` (kết nối toàn bộ hệ thống).

**Cách công việc của tôi kết nối với phần của thành viên khác:**
Công việc của tôi đóng vai trò là "trạm trung chuyển" dữ liệu. Tôi định nghĩa `AgentState` — đây là bản hợp đồng dữ liệu dùng chung. Nếu không có phần của tôi, các bạn làm **Worker Owners** sẽ không biết lấy input từ đâu và trả output về đâu. Tôi cung cấp các placeholders chuẩn để team có thể "plug-and-play" các module Retrieval và Policy vào sau khi họ hoàn thành.

**Bằng chứng:**
Trong file `graph.py`, tôi đã cài đặt thành công logic điều hướng dựa trên 3 nhóm từ khóa chính. Kết quả chạy thử cho thấy hệ thống sinh ra trace đầy đủ tại `./artifacts/traces/`, ghi lại chính xác từng bước nhảy của Agent qua các node.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Tôi chọn phương pháp **Keyword-based Routing kết hợp với Risk Flagging** thay vì sử dụng một LLM phụ để phân loại Intent (Intent Classification).

**Lý do:**
Việc gọi một LLM chỉ để phân loại câu hỏi (ví dụ dùng GPT-4o-mini) sẽ làm tăng độ trễ (latency) thêm ít nhất 500ms - 800ms cho mỗi request. Trong bối cảnh bài Lab yêu cầu xử lý các tình huống Helpdesk và Policy có tập từ khóa đặc trưng (như "SLA", "P1", "hoàn tiền", "cấp quyền"), bộ lọc từ khóa của tôi chỉ mất dưới **5ms** để xử lý. 

Đặc biệt, tôi cài đặt thêm cơ chế **Risk Flagging** dựa trên mã lỗi `ERR-`. Quyết định này giúp hệ thống có một "chốt chặn" an toàn: bất kỳ câu hỏi nào chứa mã lỗi lạ và được đánh dấu rủi ro cao đều bị ép đi qua `human_review_node`. Điều này giải quyết được vấn đề "hallucination" (ảo tưởng) khi AI cố gắng giải thích các mã lỗi mà nó chưa từng thấy trong tài liệu.

**Trade-off đã chấp nhận:**
Hệ thống có thể phân loại sai nếu người dùng dùng từ đồng nghĩa không nằm trong bộ từ khóa (ví dụ: "trả lại tiền" thay vì "hoàn tiền"). Tuy nhiên, tôi ưu tiên tính minh bạch (Explainability) — nhìn vào `route_reason` là biết ngay tại sao hệ thống đi hướng đó.

**Bằng chứng từ trace/code:**
Trong kết quả chạy query `Gặp lỗi hệ thống ERR-999...`, hệ thống đã kích hoạt chính xác:
`Reason: Risk_high + unknown error code (ERR-*) -> human_review` với Latency chỉ **3ms**.

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** Ghi đè lịch sử thực thi (State Overwriting).

**Symptom:** Ban đầu, khi kiểm tra trace JSON, danh sách `workers_called` luôn chỉ chứa duy nhất một worker cuối cùng (ví dụ: `['synthesis_worker']`). Điều này khiến việc đánh giá hiệu quả của Supervisor trở nên bất khả thi vì không biết trước đó nó đã đi qua những đâu.

**Root cause:** Lỗi nằm ở cách tôi cập nhật State trong các hàm Node. Tôi đã sử dụng phép gán trực tiếp: `state["workers_called"] = ["retrieval_worker"]`. Trong kiến trúc State của Agent, mỗi bước thực thi cần phải "bồi đắp" thêm vào lịch sử chứ không được xóa bỏ dữ liệu cũ.

**Cách sửa:**
Tôi đã sửa lại logic cập nhật trong tất cả các Node. Thay vì gán mới, tôi sử dụng phương thức `.append()` để thêm tên worker hiện tại vào danh sách sẵn có. Ngoài ra, tôi bổ sung hàm `make_initial_state` để đảm bảo mọi run đều bắt đầu với một list trống sạch sẽ.

**Bằng chứng trước/sau:**
- **Trước:** `Workers: ['synthesis_worker']`
- **Sau:** `Workers: ['human_review', 'retrieval_worker', 'synthesis_worker']` (Trace hiển thị đúng lộ trình 3 bước xử lý lỗi hệ thống).

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

**Tôi làm tốt nhất ở điểm nào?**
Thiết kế cấu trúc State và Trace. Việc tôi quy định rõ các field như `route_reason` và `latency_ms` giúp việc debug của cả nhóm trở nên cực kỳ dễ dàng. Khi nhìn vào log, team không cần hỏi tôi "tại sao nó chạy thế này", vì lý do đã nằm ngay trong trace.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**
Phần xử lý `human_review_node` vẫn còn đơn giản (chỉ là placeholder). Tôi chưa kịp nghiên cứu sâu cách dùng `interrupt_before` của LangGraph để thực sự tạm dừng luồng xử lý và chờ input từ bàn phím.

**Nhóm phụ thuộc vào tôi ở đâu?**
Tôi là người nắm giữ "luồng đi". Nếu `graph.py` gặp lỗi logic vòng lặp vô hạn, toàn bộ team sẽ không thể sinh ra kết quả cuối cùng để làm báo cáo.

**Phần tôi phụ thuộc vào thành viên khác:**
Tôi cần các bạn **Worker Owners** cung cấp API thực tế. Hiện tại hệ thống đang chạy trên dữ liệu giả (Placeholder), nên kết quả trả ra chưa có giá trị thực tế về mặt thông tin nội bộ.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Tôi sẽ thử thay thế bộ lọc keyword bằng **Semantic Router** (sử dụng vector similarity để so sánh query với các "intent vectors"). Điều này sẽ giúp supervisor thông minh hơn, nhận diện được cả những câu hỏi không chứa từ khóa định danh, vì trace của các câu hỏi mẹo (trick questions) cho thấy bộ keyword hiện tại vẫn còn khá cứng nhắc.