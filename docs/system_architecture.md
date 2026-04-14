# System Architecture — Lab Day 09

**Nhóm:** Nhom30  
**Ngày:** 2026-04-14  
**Version:** 1.0

---

## 1. Tổng quan kiến trúc

Hệ thống trả lời câu hỏi nội bộ CS + IT Helpdesk theo kiến trúc **Supervisor-Worker**:
- **Supervisor** quyết định route (retrieval / policy+tools / human_review) và ghi trace (`supervisor_route`, `route_reason`, `risk_high`, `needs_tool`).
- **Workers** thực thi kỹ năng chuyên biệt: retrieval lấy evidence chunks, policy check xử lý exception cases + gọi MCP tools, synthesis tổng hợp answer grounded + citation + confidence.
- **Trace** được lưu theo run vào `artifacts/traces/*.json` để debug và tính metrics (`eval_trace.py`).

**Pattern đã chọn:** Supervisor-Worker  
**Lý do chọn pattern này (thay vì single agent):**

- **Giảm hallucination**: synthesis chỉ được phép trả lời từ context; thiếu context thì abstain.
- **Debug rõ nguồn lỗi**: sai answer có thể phân tách thành routing sai / retrieval sai / policy sai / synthesis sai (xem `history`, `worker_io_logs`).
- **Dễ mở rộng**: thêm tool mới qua MCP hoặc thêm worker mới mà không “đập” prompt monolith.

---

## 2. Sơ đồ Pipeline

> Vẽ sơ đồ pipeline dưới dạng text, Mermaid diagram, hoặc ASCII art.
> Yêu cầu tối thiểu: thể hiện rõ luồng từ input → supervisor → workers → output.

**Ví dụ (ASCII art):**
```
User Request
     │
     ▼
┌──────────────┐
│  Supervisor  │  ← route_reason, risk_high, needs_tool
└──────┬───────┘
       │
   [route_decision]
       │
  ┌────┴────────────────────┐
  │                         │
  ▼                         ▼
Retrieval Worker     Policy Tool Worker
  (evidence)           (policy check + MCP)
  │                         │
  └─────────┬───────────────┘
            │
            ▼
      Synthesis Worker
        (answer + cite)
            │
            ▼
         Output
```

**Sơ đồ thực tế của nhóm:**

```
User task
  |
  v
Supervisor (graph.py)
  - sets: supervisor_route, route_reason, risk_high, needs_tool
  |
  +--> retrieval_worker ----------------------+
  |        - outputs: retrieved_chunks/sources|
  |                                           |
  +--> policy_tool_worker (optional MCP) -----+--> synthesis_worker
  |        - outputs: policy_result, mcp_tools_used     - outputs: final_answer, sources, confidence
  |
  +--> human_review (HITL placeholder) --(auto approve)--> retrieval_worker --> synthesis_worker
```

---

## 3. Vai trò từng thành phần

### Supervisor (`graph.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Đọc `task`, gắn flags rủi ro, route sang worker phù hợp; KHÔNG tự trả lời domain knowledge |
| **Input** | `task` |
| **Output** | supervisor_route, route_reason, risk_high, needs_tool |
| **Routing logic** | Keyword-based: refund/access → `policy_tool_worker`; SLA/P1/ticket → `retrieval_worker`; `ERR-*` + risk_high → `human_review` |
| **HITL condition** | `risk_high=True` và có dấu hiệu mơ hồ/khẩn cấp (vd `ERR-*`) |

### Retrieval Worker (`workers/retrieval.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Retrieve chunks từ `data/docs/*` (lexical fallback mặc định để tránh segfault dependency), trả `retrieved_chunks`, `retrieved_sources` |
| **Embedding model** | Mặc định: lexical overlap (không embedding). Tuỳ chọn: Chroma + OpenAI embeddings nếu set `USE_CHROMA=1` |
| **Top-k** | select = 3 (config `retrieval_top_k`) |
| **Stateless?** | Yes |

### Policy Tool Worker (`workers/policy_tool.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Phân tích policy và exception cases; khi `needs_tool=True` thì gọi MCP tools để bổ sung context |
| **MCP tools gọi** | `search_kb`, `get_ticket_info` (mock in-process) |
| **Exception cases xử lý** | flash_sale, digital_product (license/subscription), activated_product; có note về temporal scoping (trước 01/02/2026) |

### Synthesis Worker (`workers/synthesis.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **LLM model** | `gpt-4o-mini` (fallback: gemini-1.5-flash) |
| **Temperature** | 0.1 |
| **Grounding strategy** | Prompt “context-only”; enforce citation `[source]`; có guardrail cho `ERR-*` |
| **Abstain condition** | `retrieved_chunks=[]` hoặc evidence yếu / task có `ERR-*` nhưng chunks không chứa mã lỗi |

### MCP Server (`mcp_server.py`)

| Tool | Input | Output |
|------|-------|--------|
| search_kb | query, top_k | chunks, sources |
| get_ticket_info | ticket_id | ticket details |
| check_access_permission | access_level, requester_role | can_grant, approvers |
| create_ticket | priority, title, description | ticket_id, url |

---

## 4. Shared State Schema

> Liệt kê các fields trong AgentState và ý nghĩa của từng field.

| Field | Type | Mô tả | Ai đọc/ghi |
|-------|------|-------|-----------|
| task | str | Câu hỏi đầu vào | supervisor đọc |
| supervisor_route | str | Worker được chọn | supervisor ghi |
| route_reason | str | Lý do route | supervisor ghi |
| retrieved_chunks | list | Evidence từ retrieval | retrieval ghi, synthesis đọc |
| policy_result | dict | Kết quả kiểm tra policy | policy_tool ghi, synthesis đọc |
| mcp_tools_used | list | Tool calls đã thực hiện | policy_tool ghi |
| final_answer | str | Câu trả lời cuối | synthesis ghi |
| confidence | float | Mức tin cậy | synthesis ghi |
| hitl_triggered | bool | Cờ HITL | human_review / synthesis ghi |
| latency_ms | int | Tổng thời gian run | graph ghi |
| worker_io_logs | list | Log I/O từng worker | workers append |

---

## 5. Lý do chọn Supervisor-Worker so với Single Agent (Day 08)

| Tiêu chí | Single Agent (Day 08) | Supervisor-Worker (Day 09) |
|----------|----------------------|--------------------------|
| Debug khi sai | Khó — không rõ lỗi ở đâu | Dễ hơn — test từng worker độc lập |
| Thêm capability mới | Phải sửa toàn prompt | Thêm worker/MCP tool riêng |
| Routing visibility | Không có | Có route_reason trong trace |
| Hallucination control | Khó enforce | Dễ enforce ở synthesis (abstain + citations) |

**Nhóm điền thêm quan sát từ thực tế lab:**

- Với trace per-run trong `artifacts/traces/`, khi một câu “route sai” có thể thấy ngay `route_reason` và sequence `workers_called` để sửa đúng 1 chỗ (supervisor) thay vì đọc cả pipeline.

---

## 6. Giới hạn và điểm cần cải tiến

> Nhóm mô tả những điểm hạn chế của kiến trúc hiện tại.

1. Trong môi trường thiếu API key, LLM unavailable → cần fallback extractive (đã thêm) nhưng vẫn kém chất lượng so với LLM.
2. Lexical retrieval có thể retrieve chunks “nhiễu” (vd câu HR kéo nhầm refund chunk) → cần rerank/filters tốt hơn.
3. HITL hiện là placeholder auto-approve → nếu triển khai thật cần UI/queue và điều kiện trigger rõ hơn.
