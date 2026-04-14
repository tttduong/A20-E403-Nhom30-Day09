# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Hồ Quang Hiển  
**Vai trò trong nhóm:** Trace & Integration Owner 
**Ngày nộp:** 2026-04-14

---

## 1. Tôi phụ trách phần nào?

Trong nhóm, tôi phụ trách vai trò Integration + Trace Owner, tập trung vào ba việc chính: khóa luồng chạy end-to-end, chuẩn hóa trace schema, và tạo artifact phục vụ chấm điểm. Tôi trực tiếp chịu trách nhiệm các file `eval_trace.py`, `artifacts/grading_run.jsonl`, `artifacts/traces/*` và phối hợp rà soát các file liên quan như `graph.py`, `workers/*`, `mcp_server.py` để đảm bảo trace phản ánh đúng hành vi thực thi.

Công việc trọng tâm của tôi là biến phần “chạy được” thành phần “nộp được”. Điều này gồm: kiểm tra format JSONL theo rubric, xác nhận đủ field bắt buộc (`supervisor_route`, `route_reason`, `workers_called`, `mcp_tools_used`, `confidence`, `hitl_triggered`, `timestamp`), và loại bỏ sai lệch giữa code, trace, và phần mô tả trong docs.

Ngoài ra, tôi là đầu mối integration giữa các owner khác: khi có lỗi trong pipeline, tôi dùng trace để chỉ rõ lỗi nằm ở routing (A), retrieval (B), policy/MCP (C), hay synthesis/docs (D). Nhờ đó, mỗi thành viên sửa đúng phần của mình, giảm vòng lặp debug chéo.

---

## 2. Tôi đã đưa ra quyết định kỹ thuật gì?

**Quyết định:** Chuẩn hóa retrieval dense theo OpenAI embedding và re-index Chroma để đồng bộ dimension, thay vì giữ trạng thái fallback tạm thời.

Khi chạy integration thật trong `.venv` và `.env`, tôi gặp lỗi ở nhánh MCP `search_kb`: collection Chroma không đồng bộ embedding dimension với truy vấn, dẫn đến kết quả retrieval không ổn định. Nếu giữ nguyên trạng thái đó, trace vẫn có thể sinh ra nhưng chất lượng bằng chứng cho câu multi-hop giảm, ảnh hưởng trực tiếp đến grading.

Tôi cân nhắc hai phương án:
1. Giữ fallback lexical để ưu tiên “không crash”.
2. Chuẩn hóa lại dense pipeline để đúng hướng kỹ thuật của lab (dense retrieval + Chroma).

Tôi chọn phương án 2 cho bản chạy chính thức: cập nhật retrieval để ưu tiên `text-embedding-3-small`, re-index Chroma theo embedding tương ứng, sau đó chạy lại toàn bộ test và grading. Quyết định này giúp pipeline vừa ổn định vừa đúng định hướng kỹ thuật, thay vì chỉ “chạy qua”.

Trade-off là thời gian xử lý tăng so với fallback lexical, nhưng đổi lại trace thể hiện luồng đúng với thiết kế mong muốn và có giá trị hơn cho phần đánh giá kỹ thuật.

---

## 3. Tôi đã sửa một lỗi gì?

**Lỗi đã sửa:** `grading_run.jsonl` từng chứa field phụ không nằm trong format chấm chuẩn.

**Biểu hiện lỗi:** File JSONL sinh ra có thêm trường không cần thiết, dễ gây tranh luận khi đối chiếu rubric chấm.

**Nguyên nhân:** Trong quá trình hỗ trợ fallback theo nguồn câu hỏi, tôi thêm metadata phục vụ debug, nhưng không tách rõ chế độ debug và chế độ nộp chính thức.

**Cách sửa:**
- Chỉnh lại `run_grading_questions()` trong `eval_trace.py` để chỉ giữ các field đúng format chấm.
- Chạy lại lệnh `python eval_trace.py --grading`.
- Kiểm tra lại toàn bộ từng dòng JSONL theo bộ key bắt buộc.

**Bằng chứng sau sửa:**
- `artifacts/grading_run.jsonl` có đúng 10 dòng (tương ứng 10 câu grading).
- Mỗi dòng có đầy đủ trường bắt buộc, không còn field phụ.
- Pipeline grading chạy xong không crash và log route/confidence đầy đủ cho từng câu.

---

## 4. Tự đánh giá đóng góp

Điểm tôi làm tốt là giữ được vai trò release gate: mọi thay đổi đều đi qua kiểm tra “chạy thật + trace thật + format thật”. Tôi ưu tiên dữ liệu thực thi thay vì suy đoán, nên khi báo lỗi cho team luôn kèm bằng chứng từ trace hoặc output lệnh chạy.

Điểm tôi chưa tốt là chưa có evaluator tự động cho quality answer ở mức criterion-by-criterion, nên phần đánh giá vẫn dựa nhiều vào kiểm tra thủ công và thống kê tổng quát. Điều này đủ cho nộp lab, nhưng chưa đủ sâu nếu muốn tối ưu hệ thống lâu dài.

Nhóm phụ thuộc vào tôi ở phần kết thúc quy trình: nếu tôi không khóa artifact và schema đúng, nhóm có thể mất điểm dù code từng module đã tốt. Ngược lại, tôi phụ thuộc vào chất lượng module của các bạn A/B/C/D vì integration chỉ tốt khi từng worker chạy đúng contract.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì?

Tôi sẽ bổ sung một script validator chuyên cho grading log để tự động kiểm tra cả cấu trúc và nội dung tối thiểu theo rubric (ví dụ kiểm tra route_reason không rỗng, kiểm tra nguồn trích dẫn hợp lệ, kiểm tra tỷ lệ abstain bất thường). Mục tiêu là giảm rủi ro sai định dạng/sai chuẩn trước khi nộp và giúp team có một “quality gate” rõ ràng cho các lần chạy cuối. Cải tiến này nhỏ, trực tiếp, và phù hợp với vai trò Integration + Trace Owner.

