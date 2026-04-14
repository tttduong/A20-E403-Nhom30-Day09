# Báo Cáo Nhóm — Lab Day 09: Multi-Agent Orchestration

**Tên nhóm:** Nhom30  
**Ngày nộp:** 2026-04-14  
**Repo:** A20-E403-Nhom30-Day09

---

## 1. Kiến trúc nhóm đã xây dựng

Nhóm triển khai kiến trúc Supervisor-Worker với 3 worker chính: `retrieval_worker`, `policy_tool_worker`, `synthesis_worker`, và một nhánh `human_review` cho case rủi ro cao. Luồng tổng thể là: user question -> supervisor route -> worker chuyên trách -> synthesis -> output có confidence và trace. Tất cả run được ghi vào `artifacts/traces/*`, đồng thời có grading log riêng trong `artifacts/grading_run.jsonl`.

Routing logic của supervisor là rule-based bằng keyword và risk flag. Câu hỏi chứa refund/access/policy sẽ đi policy worker; câu chứa SLA/P1/ticket đi retrieval; nếu có dấu hiệu rủi ro kiểu `ERR-*` thì đi `human_review`. Nhóm ưu tiên route_reason rõ ràng để debug nhanh hơn thay vì dùng classifier phức tạp.

MCP tools tích hợp trong `mcp_server.py` gồm:
- `search_kb(query, top_k)` để truy xuất knowledge chunks.
- `get_ticket_info(ticket_id)` để lấy thông tin ticket P1.
- `check_access_permission(access_level, requester_role, is_emergency)` để kiểm tra điều kiện cấp quyền.

Ví dụ trace thực tế: ở câu gq09, `workers_called` gồm `policy_tool_worker`, `retrieval_worker`, `synthesis_worker`, và `mcp_tools_used` ghi nhận tool call phục vụ câu hỏi đa bước.

---

## 2. Quyết định kỹ thuật quan trọng nhất

**Quyết định:** Chuẩn hóa retrieval dense theo OpenAI embedding và re-index Chroma để đồng bộ dimension, thay vì giữ fallback lexical làm đường chạy chính.

**Bối cảnh:** Trong quá trình integration, nhánh MCP `search_kb` từng gặp lỗi do collection/index không đồng bộ embedding dimension. Nếu chỉ giữ fallback lexical, pipeline vẫn chạy được nhưng chất lượng retrieval cho câu multi-hop giảm và khó bám đúng định hướng dense retrieval của bài lab.

**Các phương án đã cân nhắc:**

| Phương án | Ưu điểm | Nhược điểm |
|-----------|---------|-----------|
| Giữ lexical làm mặc định | Ổn định, ít phụ thuộc | Chất lượng semantic thấp hơn, lệch hướng dense retrieval |
| Đồng bộ dense + re-index Chroma | Đúng thiết kế kỹ thuật, cải thiện retrieval ngữ nghĩa | Tốn thời gian setup/test lại |

**Phương án đã chọn và lý do:** Nhóm chọn đồng bộ dense retrieval bằng `text-embedding-3-small` và re-index Chroma trước khi chạy test/grading chính thức. Lý do là đảm bảo đúng kỹ thuật yêu cầu của bài, đồng thời giữ trace phản ánh đúng hệ thống thật (không chỉ là bản fallback tạm thời).

**Bằng chứng trace/code:** Các run sau khi re-index không còn lỗi mismatch dimension; `eval_trace.py` và `--grading` chạy thành công, `grading_run.jsonl` sinh đủ 10 dòng với schema đúng.

---

## 3. Kết quả grading questions

Nhóm đã chạy chính thức `python eval_trace.py --grading` với `data/grading_questions.json` (10 câu). Kết quả thu được trong `artifacts/grading_run.jsonl` có đầy đủ các trường bắt buộc cho từng dòng: `id`, `question`, `answer`, `sources`, `supervisor_route`, `route_reason`, `workers_called`, `mcp_tools_used`, `confidence`, `hitl_triggered`, `timestamp`.

Do không có script chấm raw theo rubric criteria trong repo, nhóm chưa tự động tính chính xác tổng raw/96. Tuy nhiên, về mặt vận hành và format nộp, pipeline đã hoàn thành 10/10 câu không crash, có route_reason rõ và trace đủ.

**Câu xử lý tốt:** `gq01` và `gq05` (nhóm SLA/P1) vì route retrieval rõ, nguồn nhất quán, confidence tốt.  
**Câu khó/partial tiềm năng:** `gq07` (abstain/hallucination risk) và `gq09` (multi-hop cross-domain) vì đòi hỏi vừa đầy đủ nội dung vừa không bịa.

Với `gq07`, nhóm ưu tiên trả lời an toàn theo evidence, tránh hallucination. Với `gq09`, trace đã ghi nhận nhiều worker trong sequence và có tool usage, đạt mục tiêu quan sát luồng multi-agent.

---

## 4. So sánh Day 08 vs Day 09 — Quan sát của nhóm

Điểm thay đổi rõ nhất là tính quan sát hệ thống. Ở Day 09, mỗi câu đều có `supervisor_route`, `route_reason`, `workers_called`, và log worker IO, nên việc tìm nguyên nhân sai nhanh hơn đáng kể so với pipeline đơn khối.

Theo run gần nhất trong `artifacts/eval_report.json`, nhóm ghi nhận các chỉ số vận hành chính như `avg_confidence`, `avg_latency_ms`, `routing_distribution`, `mcp_usage_rate`, `hitl_rate`. Đây là dữ liệu trực tiếp để điền `docs/single_vs_multi_comparison.md`.

Về chênh lệch số liệu giữa Day08 và Day09: Day08 có thêm bộ LLM-as-Judge scorecard (Faithfulness/Relevance/Recall/Completeness), còn artifact Day09 hiện ưu tiên trace-level metrics. Đây là khác biệt chuẩn đo của hai lab, không phải thiếu deliverable bắt buộc. Nhóm vẫn đáp ứng rubric Day09 vì file so sánh đã có hơn 2 metrics thực tế và có kết luận dựa trên trace.

Điều bất ngờ nhất là phần khó nhất không phải “viết thêm worker”, mà là đồng bộ integration (state keys, schema trace, định dạng artifact) để mọi thành phần cùng khớp khi chấm. Multi-agent giúp debug rõ, nhưng yêu cầu kỷ luật dữ liệu cao hơn.

Trường hợp multi-agent chưa giúp nhiều là câu đơn giản một tài liệu: số bước xử lý nhiều hơn single-agent nên có thể tăng latency. Tuy nhiên trade-off này chấp nhận được vì đổi lại khả năng audit/debug tốt hơn.

---

## 5. Phân công và đánh giá nhóm

**Phân công thực tế:**

| Thành viên | Phần đã làm | Sprint |
|------------|-------------|--------|
| Member A | Supervisor routing + AgentState + route_reason | 1 |
| Member B | Retrieval worker + Chroma retrieval path | 2 |
| Member C | Policy worker + MCP tools + dispatch stability | 3 |
| Member D | Synthesis worker + technical docs | 2,4 |
| Member E | Integration + trace/eval + grading artifact gate | 4 |

Nhóm làm tốt ở điểm phối hợp theo contract: mỗi worker có trách nhiệm rõ, integration dùng trace để xác định lỗi đúng owner. Điểm chưa tốt là có giai đoạn số liệu docs chưa đồng bộ với run cuối, phải chạy lại và cập nhật thủ công. Nếu làm lại, nhóm sẽ thêm checklist “freeze metrics before docs update” để giảm lệch số liệu.

---

## 6. Nếu có thêm 1 ngày, nhóm sẽ làm gì?

Nhóm sẽ bổ sung evaluator tự động cho grading criteria theo từng câu để ước lượng raw score nội bộ trước khi nộp, thay vì chỉ kiểm tra format/trace. Đồng thời, nhóm sẽ thêm một script kiểm tra consistency giữa `eval_report.json`, `docs/*.md`, và `grading_run.jsonl` để tránh lệch số liệu khi có nhiều lần chạy.
