# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Trịnh Đức An  
**Vai trò trong nhóm:** Synthesis + Docs Owner  
**Ngày nộp:** 2026-04-14  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào?

Tôi phụ trách **Synthesis Worker** và **tài liệu kỹ thuật** cho Sprint 4. Cụ thể: `workers/synthesis.py` và 3 docs `docs/system_architecture.md`, `docs/routing_decisions.md`, `docs/single_vs_multi_comparison.md`.

Về kỹ thuật, `synthesis_worker` là “gate” cuối: nhận `task`, `retrieved_chunks`, `policy_result` và tạo `final_answer`, `sources`, `confidence` theo contract (`contracts/worker_contracts.yaml`), với ràng buộc số 1 là **không hallucinate**. Worker cũng phải ghi trace (`worker_io_logs`, `history`) và bật `hitl_triggered` khi confidence thấp.

**Bằng chứng:** `workers/synthesis.py` có các hàm `_build_context()`, `_estimate_confidence()`, `synthesize()`, `run(state)` và các guardrails (abstain + citation enforcement). 3 docs trong `docs/` đã được điền bằng số liệu từ `python eval_trace.py` và routing decisions từ trace thật trong `artifacts/traces/`.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì?

**Quyết định:** Tôi chọn thiết kế synthesis theo hướng **“conservative-first”**: ưu tiên abstain + evidence-only thay vì cố gắng trả lời “nghe hợp lý”. Quyết định này xuất phát trực tiếp từ rubric chấm grading: chỉ cần bịa 1 chi tiết không có trong tài liệu là bị penalty nặng (−50% điểm câu), còn abstain đúng lại được full điểm ở các câu kiểu gq07.

**Cơ chế tôi implement (trong `workers/synthesis.py`):**
- **Hard abstain** khi `retrieved_chunks=[]` (không có evidence).
- **Guardrail cho mã lỗi `ERR-*`**: nếu task có `ERR-...` mà chunks không chứa đúng mã đó → abstain (tránh bị “chunk nhiễu” kéo synthesis sang trả lời sai).
- **Evidence-quality gate**: nếu `max(chunk.score) < 0.35` → abstain (tức là retrieval đưa về evidence yếu/không liên quan).
- **Citation enforcement**: nếu có chunks nhưng model quên cite `[source]` → tự append dòng `Nguồn: [file]` để đáp ứng contract “answer có citation khi có evidence”.

**Trade-off tôi chấp nhận:** abstain có thể tăng ở vài case “thiếu 1 mảnh nhỏ”, nhưng trong grading thì *thà abstain có lý do còn hơn bịa*.

**Bằng chứng từ trace:** trong run test questions, câu `q09` (“ERR-403-AUTH…”) có `hitl_triggered=true` và confidence rất thấp (0.10) kèm answer abstain; routing vẫn trace được rõ ràng (human_review → retrieval → synthesis). Điều này chứng minh guardrail hoạt động đúng khi KB không có mã lỗi.

---

## 3. Tôi đã sửa một lỗi gì?

**Lỗi:** `synthesis_worker` có thể bị “dẫn dắt” bởi chunk nhiễu ở các câu hỏi dạng **mã lỗi `ERR-*`** (có chunks nhưng không liên quan) → rủi ro hallucination/penalty.

**Root cause:** Thiếu constraint “task mentions entity X ⇒ context must include X”.

**Cách sửa:** Tôi thêm guardrail trong `synthesize()`:
- Parse `ERR-...` từ `task`.
- Nếu không chunk nào chứa đúng mã đó → **abstain** (không cố trả lời).

**Bằng chứng trước/sau:** Sau khi thêm guardrail, `q09` trong batch `python eval_trace.py` ra confidence 0.10 và answer abstain; trace có `question_id: "q09"` và `hitl_triggered=true`.

---

## 4. Tôi tự đánh giá đóng góp của mình

**Tôi làm tốt nhất ở điểm nào?** Tôi biến synthesis thành “safety gate” thực sự: có abstain rõ ràng, confidence phản ánh evidence, có citation enforcement và policy-aware phrasing. Tôi cũng hoàn thiện 3 docs theo đúng yêu cầu rubric (routing decisions từ trace thật, metrics có số liệu).

**Tôi làm chưa tốt ở điểm nào?** Khi thiếu API key, LLM không gọi được nên phải dùng fallback extractive (grounded nhưng câu chữ kém hơn). Retrieval lexical đôi lúc đưa chunk nhiễu; synthesis chỉ giảm rủi ro chứ chưa giải quyết gốc (rerank/chunking).

**Nhóm phụ thuộc vào tôi ở đâu?** Nếu synthesis không enforce grounding/citation thì cả pipeline có thể trả lời “đúng kiểu văn” nhưng sai fact và bị penalty. Docs cũng là phần bắt buộc Sprint 4; thiếu số liệu thực sẽ mất điểm.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì?

Tôi sẽ thêm một bước **answer verifier** (rule-based + optional LLM-judge) để check: (1) answer có chứa entity quan trọng của task (vd `ERR-*`, “22:47/22:57”), (2) answer có ít nhất 1 citation khi có evidence, (3) nếu policy_result có `policy_version_note` thì answer bắt buộc nhắc lại. Nếu fail → hạ confidence + trigger HITL. Cải tiến này tăng “anti-hallucination” và làm trace dễ audit hơn trong grading_questions.

---

*File: `reports/individual/trinh_duc_an.md`*

