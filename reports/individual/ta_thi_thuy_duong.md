# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Tạ Thị Thùy Dương
**Vai trò trong nhóm:** Worker Owner (Retrieval)
**Ngày nộp:** 2026-04-14 (Day 09)

---

## 1. Tôi phụ trách phần nào?

Tôi phụ trách toàn bộ `workers/retrieval.py` — worker chịu trách nhiệm tìm kiếm evidence từ Knowledge Base và trả về chunks cho các worker khác.

**Module/file tôi chịu trách nhiệm:**
- File chính: `workers/retrieval.py`
- Functions tôi implement:
  - `_get_collection()` — kết nối ChromaDB, đọc env vars `CHROMA_DB_PATH` và `CHROMA_COLLECTION` thay vì hardcode
  - `retrieve_dense()` — dense retrieval hai tầng: query 10 candidates, lọc threshold, handoff 3 chunks
  - `retrieve_lexical()` — fallback lexical retrieval không phụ thuộc ML (keyword overlap scoring)
  - `run(state)` — worker entry point, ghi `retrieved_chunks`, `retrieved_sources`, `worker_io_logs` vào AgentState

**Cách công việc của tôi kết nối với thành viên khác:**
Output `retrieved_chunks` là đầu vào bắt buộc của synthesis_worker (An) và được policy_tool_worker (Hậu) dùng khi không có chunks sẵn. `mcp_server.py` (Hậu) cũng gọi trực tiếp `retrieve_dense()` trong tool `search_kb`. Sau khi xong, tôi cập nhật `contracts/worker_contracts.yaml` field `actual_implementation.status = "done"` để team biết retrieval sẵn sàng tích hợp.

**Bằng chứng:** Xem `workers/retrieval.py` — constants `TOP_K_SEARCH=10`, `TOP_K_SELECT=3`, `ABSTAIN_THRESHOLD=0.3`; `_get_collection()` dùng `os.getenv()`; `retrieve_dense()` two-stage filter.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì?

**Quyết định:** Thiết kế two-stage top_k retrieval kết hợp abstain threshold 0.3, thay vì query thẳng top_k=3.

**Cơ chế:**
- Stage 1: query ChromaDB (hoặc lexical index) lấy `top_k_search=10` candidates
- Stage 2: lọc bỏ mọi chunk có `score < 0.3`, sau đó chỉ giữ `top_k_select=3` để handoff

**Các lựa chọn thay thế:**
- Query thẳng `top_k=3` — đơn giản hơn nhưng thiếu recall, dễ bỏ sót candidate tốt bị rank thấp do noise embedding
- Không có threshold — synthesis nhận chunk với score ~0.1 không liên quan, tăng nguy cơ hallucination

**Lý do tôi chọn cách này:**
Two-stage cho phép recall rộng ở stage 1 và precision cao ở stage 2. Threshold 0.3 đủ để loại bỏ noise nhưng không quá chặt gây abstain nhầm khi evidence thực sự tồn tại trong docs.

**Trade-off đã chấp nhận:**
Với lexical scoring, threshold 0.3 vẫn để lọt một số chunk không liên quan (ví dụ `hr_leave_policy.txt` score 0.368 xuất hiện trong SLA query). Đây là giới hạn của whole-document indexing, không phải của two-stage design.

**Bằng chứng từ test:**
```
Query: "SLA ticket P1 la bao lau?"
  [0.540] sla_p1_2026.txt        ← relevant ✅
  [0.389] access_control_sop.txt ← marginal ✅
  [0.368] hr_leave_policy.txt    ← noise (whole-doc overlap) ⚠️
→ Chunks: 3, tất cả score ≥ 0.3 → pass threshold
→ retrieved_sources: ['sla_p1_2026.txt', 'access_control_sop.txt', 'hr_leave_policy.txt']
```

---

## 3. Tôi đã sửa một lỗi gì?

**Lỗi:** README index script thiếu `col.add()` — collection ChromaDB luôn rỗng dù script "chạy thành công"

**Symptom:**
Chạy `python workers/retrieval.py` sau khi thực hiện đúng Step 3 README vẫn ra warning:
```
⚠️  Collection 'day09_docs' chưa có data. Chạy index script trong README trước.
```
Mọi query đều trả về `retrieved_chunks = []` → synthesis worker không có evidence → trả lời "Không đủ thông tin" hoặc hallucinate. Toàn bộ pipeline bị ảnh hưởng.

**Root cause:**
Script trong `README.md` Step 3 mở file, đọc content, nhưng **không gọi `col.add()`**:
```python
# BUG trong README — chỉ print, không thực sự index
for fname in os.listdir(docs_dir):
    with open(os.path.join(docs_dir, fname)) as f:
        content = f.read()
    print(f'Indexed: {fname}')  # misleading — không có gì được add vào collection
print('Index ready.')           # sai — collection vẫn rỗng
```

**Cách sửa:**
Thêm embed + `col.add()` vào loop:
```python
embedding = model.encode([content])[0].tolist()
col.add(
    ids=[fname],
    documents=[content],
    embeddings=[embedding],
    metadatas=[{'source': fname}]
)
```

**Bằng chứng trước/sau:**
```
# Trước khi sửa:
retrieved_chunks = []   (collection rỗng, mọi query đều abstain)

# Sau khi chạy script đúng:
Indexed: access_control_sop.txt
Indexed: hr_leave_policy.txt
Indexed: it_helpdesk_faq.txt
Indexed: policy_refund_v4.txt
Indexed: sla_p1_2026.txt
Done. Total docs: 5

# Query SLA sau khi fix:
[0.540] sla_p1_2026.txt: SLA TICKET - QUY ĐỊNH XỬ LÝ SỰ CỐ...
[0.389] access_control_sop.txt: QUY TRÌNH KIỂM SOÁT TRUY CẬP...
```

---

## 4. Tôi tự đánh giá đóng góp của mình

**Tôi làm tốt nhất ở điểm nào?**
Thiết kế two-stage retrieval khớp chính xác với spec. Phát hiện và sửa bug README index script — đây là lỗi blocking cả team vì không ai có chunks để test end-to-end. Cập nhật contract kịp thời để Hậu và An biết retrieval sẵn sàng.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**
Indexing whole-document (mỗi file = 1 chunk) làm score không phản ánh đúng relevance của đoạn cụ thể. `hr_leave_policy.txt` lọt top 3 cho SLA query vì keyword overlap tình cờ ở cấp độ toàn văn bản. Paragraph-level chunking sẽ sạch hơn nhiều.

**Nhóm phụ thuộc vào tôi ở đâu?**
An (synthesis) bị block hoàn toàn nếu `retrieved_chunks` rỗng hoặc thiếu field `source`. Hậu (MCP) gọi trực tiếp `retrieve_dense()` — nếu signature sai là crash `tool_search_kb`.

**Phần tôi phụ thuộc vào thành viên khác:**
Cần Hiền đảm bảo `retrieval_worker_node` trong `graph.py` gọi `retrieval_run(state)` thật sự thay vì placeholder hardcode. Nếu A chưa wire, toàn bộ retrieval logic của tôi không được chạy trong graph.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì?

Tôi sẽ chuyển từ whole-document indexing sang **paragraph-level chunking** khi build ChromaDB index.

Bằng chứng từ trace: query "SLA ticket P1" trả `hr_leave_policy.txt` (score 0.368) vì toàn bộ file HR có đủ keyword overlap tình cờ. Nếu chunk theo đoạn văn (`\n\n` separator, ~150-300 tokens/chunk), file HR không có đoạn nào nhắc đến "SLA" hay "P1" → bị lọc ra khỏi top 10 ngay từ stage 1. Precision của `retrieved_chunks` tăng, synthesis nhận evidence sạch hơn và confidence cao hơn.

---

*File: `reports/individual/ta_thi_thuy_duong.md`*
