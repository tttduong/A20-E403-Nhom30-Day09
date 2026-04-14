# Single Agent vs Multi-Agent Comparison — Lab Day 09

**Nhóm:** Nhom30  
**Ngày:** 2026-04-14

---

## 1. Metrics Comparison

| Metric | Day 08 (Single Agent) | Day 09 (Multi-Agent) | Delta | Ghi chú |
|--------|----------------------|---------------------|-------|---------|
| Faithfulness (LLM-as-Judge, 1-5) | 4.70/5 | Chưa có score cùng thang trong artifact Day09 | Chưa đối chiếu trực tiếp | Day08 từ `results/scorecard_baseline.md` |
| Relevance (LLM-as-Judge, 1-5) | 4.80/5 | Chưa có score cùng thang trong artifact Day09 | Chưa đối chiếu trực tiếp | Day08 từ `results/scorecard_baseline.md` |
| Context Recall (LLM-as-Judge, 1-5) | 5.00/5 | Chưa có score cùng thang trong artifact Day09 | Chưa đối chiếu trực tiếp | Day08 từ `results/scorecard_baseline.md` |
| Completeness (LLM-as-Judge, 1-5) | 4.20/5 | Chưa có score cùng thang trong artifact Day09 | Chưa đối chiếu trực tiếp | Day08 từ `results/scorecard_baseline.md` |
| Avg confidence | Không ghi trong artifact Day08 | 0.525 | Không tính delta | Day09 từ `artifacts/eval_report.json` (latest 15 traces) |
| Avg latency (ms) | Không ghi trong artifact Day08 | 2744 | Không tính delta | Average `latency_ms` trên latest 15 traces |
| Abstain rate (%) | 10.0% (1/10) | 13.3% (2/15) | +3.3 điểm % | Day08 từ `A20-nhom30-403-day08-rag/logs/grading_run.json` |
| HITL rate (%) | 0% | 13.3% (2/15) | +13.3 điểm % | Day09 có `human_review` + `hitl_triggered` |
| MCP usage rate (%) | 0% | 46.7% (7/15) | +46.7 điểm % | Day08 không có MCP |
| Avg retrieved chunks/run | 3.0 | 3.0 | 0.0 | Day08 log và Day09 latest traces |
| Routing visibility | Không có route trace | Có `supervisor_route` + `route_reason` | Cải thiện rõ | |
| Routing accuracy vs expected_route | Không có trường expected_route trong log Day08 | 93.3% (14/15) | Không đối chiếu trực tiếp | q02 lệch route do rule ưu tiên policy/refund |

Ghi chú chuẩn đo:
- Day08 có score LLM-as-Judge (Faithfulness/Relevance/Recall/Completeness), nhưng artifact Day09 hiện không lưu bộ score cùng thang này.
- Day09 tập trung metrics trace/observability (`route_reason`, `workers_called`, `hitl_triggered`, `mcp_tools_used`, `latency_ms`), đúng trọng tâm Lab 09.
- Theo rubric Lab 09, file này chỉ yêu cầu có **ít nhất 2 metrics thực tế** và kết luận có bằng chứng; không bắt buộc phải có mọi metric đối xứng 1-1 giữa hai ngày.

---

## 2. Phân tích theo loại câu hỏi

### 2.1 Câu hỏi đơn giản (single-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | Faithfulness 4.70/5, Relevance 4.80/5 | Tốt trên test questions (không crash, grounded chunks) |
| Latency | Artifact Day08 không lưu `latency_ms` theo câu | Thấp (đa số 0–2ms; có case cao do overhead) |
| Observation | Trả lời ổn nhưng thiếu route-level observability | Supervisor route thẳng retrieval/policy giúp trace rõ và dễ debug |

**Kết luận:** Multi-agent có cải thiện không? Tại sao có/không?

Trong lab này, lợi ích chính của multi-agent là **observability** và **khả năng kiểm soát abstain/hallucination** qua synthesis guardrails. Khi answer sai, trace đủ chi tiết để khoanh vùng và sửa nhanh hơn.

### 2.2 Câu hỏi multi-hop (cross-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | Có score tổng quan (Faithfulness/Relevance cao), nhưng không có trace chuỗi xử lý | Tương đối ổn ở mức routing + coverage nguồn; chưa có điểm correctness tự động cùng thang Day08 |
| Routing visible? | ✗ | ✓ |
| Observation | Không quan sát được chuỗi xử lý nội bộ theo worker | Có thể nhìn `workers_called` để xác nhận pipeline đã đi qua policy/retrieval trước synthesis |

**Kết luận:**

Day 09 cho thấy “multi-hop readiness” tốt hơn nhờ `workers_called` + `mcp_tools_used` đầy đủ. Tuy nhiên, khi thiếu API key thì synthesis fallback còn thiên về extractive nên cần evaluator correctness để đo chất lượng cuối.

### 2.3 Câu hỏi cần abstain

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Abstain rate | 10.0% (1/10, từ log Day08) | 13.3% (2/15) |
| Hallucination cases | Có 1 câu dạng thiếu nguồn nhưng vẫn trả lời (q09) | 0 observed trên set này (abstain thay vì bịa) |
| Observation | Chưa có guardrail HITL/route nên khó chặn lỗi theo rủi ro | Guardrail `ERR-*` + evidence-threshold khiến q09 abstain đúng |

**Kết luận:**

Multi-agent giúp enforce abstain theo contract ở synthesis, giảm penalty hallucination cho grading.

---

## 3. Debuggability Analysis

### Day 08 — Debug workflow
```
Khi answer sai → phải đọc toàn bộ RAG pipeline code → tìm lỗi ở indexing/retrieval/generation
Không có trace → không biết bắt đầu từ đâu
Thời gian ước tính: chưa có số đo stopwatch trong artifact Day08
```

### Day 09 — Debug workflow
```
Khi answer sai → đọc trace → xem supervisor_route + route_reason
  → Nếu route sai → sửa supervisor routing logic
  → Nếu retrieval sai → test retrieval_worker độc lập
  → Nếu synthesis sai → test synthesis_worker độc lập
Thời gian ước tính: ~2-5 phút/case (đọc trace + test worker độc lập)
```

**Câu cụ thể nhóm đã debug:**

Bug: `graph.py` từng còn wrapper tạm nên trace/code dễ mismatch. Fix: nối trực tiếp worker thật trong graph và kiểm tra lại bằng `python eval_trace.py` để đảm bảo trace phản ánh đúng luồng chạy.

---

## 4. Extensibility Analysis

| Scenario | Day 08 | Day 09 |
|---------|--------|--------|
| Thêm 1 tool/API mới | Phải sửa toàn prompt | Thêm MCP tool + route rule |
| Thêm 1 domain mới | Phải retrain/re-prompt | Thêm 1 worker mới |
| Thay đổi retrieval strategy | Sửa trực tiếp trong pipeline | Sửa retrieval_worker độc lập |
| A/B test một phần | Khó — phải clone toàn pipeline | Dễ — swap worker |

**Nhận xét:**

Chi phí bước tăng nhẹ vì thêm policy worker + MCP calls, nhưng đổi lại trace rõ, dễ debug, và mở rộng tool mới không cần sửa toàn bộ orchestrator.

---

## 5. Cost & Latency Trade-off

| Scenario | Day 08 calls | Day 09 calls |
|---------|-------------|-------------|
| Simple query | 1 LLM call | 1 synthesis call (hoặc fallback nếu thiếu API key) |
| Complex query | 1 LLM call | 1 synthesis call + 2-3 MCP tool calls |
| MCP tool call | 0 | 0-3 calls tùy `needs_tool` và loại câu hỏi |

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
