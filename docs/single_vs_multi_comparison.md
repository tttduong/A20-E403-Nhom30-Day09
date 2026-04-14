# Single Agent vs Multi-Agent Comparison — Lab Day 09

**Nhóm:** Nhom30  
**Ngày:** 2026-04-14

> **Hướng dẫn:** So sánh Day 08 (single-agent RAG) với Day 09 (supervisor-worker).
> Phải có **số liệu thực tế** từ trace — không ghi ước đoán.
> Chạy cùng test questions cho cả hai nếu có thể.

---

## 1. Metrics Comparison

> Điền vào bảng sau. Lấy số liệu từ:
> - Day 08: chạy `python eval.py` từ Day 08 lab
> - Day 09: chạy `python eval_trace.py` từ lab này

| Metric | Day 08 (Single Agent) | Day 09 (Multi-Agent) | Delta | Ghi chú |
|--------|----------------------|---------------------|-------|---------|
| Avg confidence | N/A | 0.695 | N/A | Từ `python eval_trace.py` (15 traces) |
| Avg latency (ms) | N/A | 72 | N/A | Average `latency_ms` trên 15 traces |
| Abstain rate (%) | N/A | 6.7% (1/15) | N/A | q09 (ERR-403-AUTH) abstain |
| HITL rate (%) | N/A | 6.7% (1/15) | N/A | `hitl_triggered=True` |
| MCP usage rate (%) | N/A | 46.7% (7/15) | N/A | `mcp_tools_used` không rỗng |
| Routing visibility | ✗ Không có | ✓ Có route_reason | N/A | |
| Debug time (estimate) | N/A | ~2–5 phút | N/A | Đọc trace → khoanh routing/worker |
| ___________________ | ___ | ___ | ___ | |

> **Lưu ý:** Nếu không có Day 08 kết quả thực tế, ghi "N/A" và giải thích.

---

## 2. Phân tích theo loại câu hỏi

### 2.1 Câu hỏi đơn giản (single-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | N/A | Tốt trên test questions (không crash, grounded chunks) |
| Latency | N/A | Thấp (đa số 0–2ms; 1 case ~837ms do overhead) |
| Observation | N/A | Supervisor route thẳng retrieval/policy giúp trace rõ và dễ debug |

**Kết luận:** Multi-agent có cải thiện không? Tại sao có/không?

Trong lab này, lợi ích chính của multi-agent là **observability** và **khả năng kiểm soát abstain/hallucination** qua synthesis guardrails, hơn là “accuracy” tuyệt đối (vì Day 08 baseline không có số liệu).

### 2.2 Câu hỏi multi-hop (cross-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | N/A | N/A (chưa chấm tự động correctness) |
| Routing visible? | ✗ | ✓ |
| Observation | N/A | Có thể nhìn `workers_called` để xác nhận pipeline đã đi qua policy/retrieval trước synthesis |

**Kết luận:**

Day 09 cho thấy “multi-hop readiness” tốt hơn nhờ tách worker và trace; nhưng muốn đo accuracy cần thêm evaluator (hoặc grading_questions).

### 2.3 Câu hỏi cần abstain

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Abstain rate | N/A | 6.7% (1/15) |
| Hallucination cases | N/A | 0 observed trên set này (abstain thay vì bịa) |
| Observation | N/A | Guardrail `ERR-*` + evidence-threshold khiến q09 abstain đúng |

**Kết luận:**

Multi-agent giúp enforce abstain theo contract ở synthesis, giảm penalty hallucination cho grading.

---

## 3. Debuggability Analysis

> Khi pipeline trả lời sai, mất bao lâu để tìm ra nguyên nhân?

### Day 08 — Debug workflow
```
Khi answer sai → phải đọc toàn bộ RAG pipeline code → tìm lỗi ở indexing/retrieval/generation
Không có trace → không biết bắt đầu từ đâu
Thời gian ước tính: ___ phút
```

### Day 09 — Debug workflow
```
Khi answer sai → đọc trace → xem supervisor_route + route_reason
  → Nếu route sai → sửa supervisor routing logic
  → Nếu retrieval sai → test retrieval_worker độc lập
  → Nếu synthesis sai → test synthesis_worker độc lập
Thời gian ước tính: ___ phút
```

**Câu cụ thể nhóm đã debug:** _(Mô tả 1 lần debug thực tế trong lab)_

Bug: `run_id` chỉ có tới giây → chạy batch nhanh làm overwrite trace files, metrics sai. Fix: đổi `run_id` sang include microseconds (`%f`) để mỗi trace file unique.

---

## 4. Extensibility Analysis

> Dễ extend thêm capability không?

| Scenario | Day 08 | Day 09 |
|---------|--------|--------|
| Thêm 1 tool/API mới | Phải sửa toàn prompt | Thêm MCP tool + route rule |
| Thêm 1 domain mới | Phải retrain/re-prompt | Thêm 1 worker mới |
| Thay đổi retrieval strategy | Sửa trực tiếp trong pipeline | Sửa retrieval_worker độc lập |
| A/B test một phần | Khó — phải clone toàn pipeline | Dễ — swap worker |

**Nhận xét:**

_________________

---

## 5. Cost & Latency Trade-off

> Multi-agent thường tốn nhiều LLM calls hơn. Nhóm đo được gì?

| Scenario | Day 08 calls | Day 09 calls |
|---------|-------------|-------------|
| Simple query | 1 LLM call | ___ LLM calls |
| Complex query | 1 LLM call | ___ LLM calls |
| MCP tool call | N/A | ___ |

**Nhận xét về cost-benefit:**

Day 09 có thể tốn nhiều bước hơn (supervisor + worker chain), nhưng đổi lại trace rõ và giảm rủi ro hallucination bằng abstain. Trong môi trường có API key, synthesis sẽ là 1 LLM call; policy_tool có thể thêm MCP calls khi `needs_tool=True`.

---

## 6. Kết luận

> **Multi-agent tốt hơn single agent ở điểm nào?**

1. Observability: có `route_reason`, `workers_called`, `worker_io_logs` để debug nhanh.
2. Reliability: enforce grounded answering + abstain guardrails ở synthesis, giảm hallucination penalty.

> **Multi-agent kém hơn hoặc không khác biệt ở điểm nào?**

1. Latency/cost có thể tăng do nhiều bước và tool calls (tuỳ routing và số worker).

> **Khi nào KHÔNG nên dùng multi-agent?**

Khi bài toán đơn giản, không cần routing/observability, hoặc constraint cost/latency rất chặt và 1 agent đã đủ.

> **Nếu tiếp tục phát triển hệ thống này, nhóm sẽ thêm gì?**

Thêm evaluator tự động cho multi-hop correctness + reranker để giảm chunk nhiễu, và HITL thật (queue/UI) thay vì auto-approve.
