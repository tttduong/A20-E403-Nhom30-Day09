# Routing Decisions Log — Lab Day 09

**Nhóm:** Nhom30  
**Ngày:** 2026-04-14

> **Hướng dẫn:** Ghi lại ít nhất **3 quyết định routing** thực tế từ trace của nhóm.
> Không ghi giả định — phải từ trace thật (`artifacts/traces/`).
> 
> Mỗi entry phải có: task đầu vào → worker được chọn → route_reason → kết quả thực tế.

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
- Correct routing? Yes / No

**Nhận xét:** _(Routing này đúng hay sai? Nếu sai, nguyên nhân là gì?)_

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
- Correct routing? Yes / No

**Nhận xét:**

Đúng. Đây là SLA retrieval + multi-detail trong 1 doc; route thẳng retrieval giúp đơn giản và rẻ hơn (không cần policy/tool).

---

## Routing Decision #3

**Task đầu vào:**
> ERR-403-AUTH là lỗi gì và cách xử lý?

**Worker được chọn:** `human_review` (HITL placeholder)  
**Route reason (từ trace):** `Risk_high + unknown error code (ERR-*) -> human_review | human approved → retrieval`  
**MCP tools được gọi:** `[]`  
**Workers called sequence:** `["human_review", "retrieval_worker", "synthesis_worker"]`

**Kết quả thực tế:**
- final_answer (ngắn): Abstain “Không đủ thông tin trong tài liệu nội bộ…” (không bịa)  
- confidence: 0.10
- Correct routing? Yes / No

**Nhận xét:**

Đúng. Với mã lỗi `ERR-*` không có trong KB, hệ thống trigger HITL và synthesis có guardrail để abstain nếu chunks không chứa đúng mã lỗi.

---

## Routing Decision #4 (tuỳ chọn — bonus)

**Task đầu vào:**
> _________________

**Worker được chọn:** `___________________`  
**Route reason:** `___________________`

**Nhận xét: Đây là trường hợp routing khó nhất trong lab. Tại sao?**

_________________

---

## Tổng kết

### Routing Distribution

| Worker | Số câu được route | % tổng |
|--------|------------------|--------|
| retrieval_worker | 8 | 53% |
| policy_tool_worker | 7 | 46% |
| human_review | 0* | 0% |

\* `human_review` là node tạm, nhưng `hitl_triggered` vẫn ghi nhận trong trace.

### Routing Accuracy

> Trong số X câu nhóm đã chạy, bao nhiêu câu supervisor route đúng?

- Câu route đúng: 15 / 15 (theo `expected_route` trong `data/test_questions.json` + trace route_reason)  
- Câu route sai (đã sửa bằng cách nào?): 0  
- Câu trigger HITL: 1 (q09: `ERR-*`)

### Lesson Learned về Routing

> Quyết định kỹ thuật quan trọng nhất nhóm đưa ra về routing logic là gì?  
> (VD: dùng keyword matching vs LLM classifier, threshold confidence cho HITL, v.v.)

1. Keyword routing đủ tốt cho lab nếu `route_reason` rõ + có HITL cho case mơ hồ (`ERR-*`).
2. “Policy/access” ưu tiên route sang `policy_tool_worker` để tránh bỏ sót exceptions (flash sale / digital product / activated product / temporal scoping).

### Route Reason Quality

> Nhìn lại các `route_reason` trong trace — chúng có đủ thông tin để debug không?  
> Nếu chưa, nhóm sẽ cải tiến format route_reason thế nào?

Các `route_reason` hiện có format ổn cho debug (đều không phải "unknown"). Cải tiến tiếp theo: chuẩn hoá prefix theo taxonomy (SLA|REFUND|ACCESS|ERRORCODE) + kèm keyword matched để dễ audit.
