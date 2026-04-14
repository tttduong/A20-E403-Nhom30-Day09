# Routing Decisions Log — Lab Day 09

**Nhóm:** Nhom30  
**Ngày:** 2026-04-14

---

## Routing Decision #1

**Task đầu vào:**
> Khách hàng có thể yêu cầu hoàn tiền trong bao nhiêu ngày?

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `Task contains policy/access keyword -> policy_tool_worker`  
**MCP tools được gọi:** `["search_kb"]`  
**Workers called sequence:** `["policy_tool_worker", "retrieval_worker", "synthesis_worker"]`

**Kết quả thực tế:**
- final_answer (ngắn): Extract từ policy doc về “7 ngày làm việc…” (grounded) + cite `[policy_refund_v4.txt]`
- confidence: 0.83
- Correct routing: Yes

**Nhận xét:**

Đúng. Câu hỏi policy/refund nên đi qua policy worker để xử lý exceptions/temporal scoping nếu có; retrieval bổ sung evidence chunks trước synthesis.

---

## Routing Decision #2

**Task đầu vào:**
> Ticket P1 được tạo lúc 22:47. Ai sẽ nhận thông báo đầu tiên và qua kênh nào? Escalation xảy ra lúc mấy giờ?

**Worker được chọn:** `retrieval_worker`  
**Route reason (từ trace):** `Task contains SLA/P1/Ticket keyword -> retrieval_worker`  
**MCP tools được gọi:** `[]`  
**Workers called sequence:** `["retrieval_worker", "synthesis_worker"]`

**Kết quả thực tế:**
- final_answer (ngắn): Extract SLA P1 response/escalation rule + cite `[sla_p1_2026.txt]`
- confidence: 0.67
- Correct routing: Yes

**Nhận xét:**

Đúng. Đây là SLA retrieval + multi-detail trong 1 doc; route thẳng retrieval giúp đơn giản và rẻ hơn (không cần policy/tool).

---

## Routing Decision #3

**Task đầu vào:**
> ERR-403-AUTH là lỗi gì và cách xử lý?

**Worker được chọn:** `human_review` (HITL lab-mode auto-approve)  
**Route reason (từ trace):** `Risk_high + unknown error code (ERR-*) -> human_review | human approved → retrieval`  
**MCP tools được gọi:** `[]`  
**Workers called sequence:** `["human_review", "retrieval_worker", "synthesis_worker"]`

**Kết quả thực tế:**
- final_answer (ngắn): Abstain “Không đủ thông tin trong tài liệu nội bộ…” (không bịa)  
- confidence: 0.10
- Correct routing: Yes

**Nhận xét:**

Đúng. Với mã lỗi `ERR-*` không có trong KB, hệ thống trigger HITL và synthesis có guardrail để abstain nếu chunks không chứa đúng mã lỗi.

---

## Tổng kết

### Routing Distribution

| Worker | Số câu được route | % tổng |
|--------|------------------|--------|
| retrieval_worker | 8 | 53% |
| policy_tool_worker | 7 | 46% |
| human_review | 0* | 0% |

\* `human_review` là node trung gian (auto-approve), nên `supervisor_route` cuối cùng quay về `retrieval_worker`; HITL vẫn được ghi nhận qua `hitl_triggered`.

### Routing Accuracy

- Câu route đúng: 14 / 15 (đối chiếu `expected_route` trong `data/test_questions.json`)  
- Câu route sai: 1 (q02 bị route sang `policy_tool_worker` do keyword refund/policy ưu tiên)  
- Câu trigger HITL: 2 (`q08`, `q09` trong latest traces)

### Lesson Learned về Routing

1. Keyword routing đủ tốt cho lab nếu `route_reason` rõ + có HITL cho case mơ hồ (`ERR-*`).
2. “Policy/access” ưu tiên route sang `policy_tool_worker` để tránh bỏ sót exceptions (flash sale / digital product / activated product / temporal scoping).

### Route Reason Quality

Các `route_reason` hiện có format ổn cho debug (đều không phải "unknown"). Cải tiến tiếp theo: chuẩn hoá prefix theo taxonomy (SLA|REFUND|ACCESS|ERRORCODE) + kèm keyword matched để dễ audit.
