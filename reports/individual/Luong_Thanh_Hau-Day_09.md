# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Lương Thanh Hậu
**Vai trò trong nhóm:** MCP Owner (Policy + MCP Owner)
**Ngày nộp:** 14/04/2026  
**Độ dài yêu cầu:** 500–800 từ

---

> **Lưu ý quan trọng:**
> - Viết ở ngôi **"tôi"**, gắn với chi tiết thật của phần bạn làm
> - Phải có **bằng chứng cụ thể**: tên file, đoạn code, kết quả trace, hoặc commit
> - Nội dung phân tích phải khác hoàn toàn với các thành viên trong nhóm
> - Deadline: Được commit **sau 18:00** (xem SCORING.md)
> - Lưu file với tên: `reports/individual/[ten_ban].md` (VD: `nguyen_van_a.md`)

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

**Module/file tôi chịu trách nhiệm:**
- File chính: `mcp_server.py` và `workers/policy_tool.py`.
- Functions tôi implement: `call_mcp_with_trace()`, `dispatch_tool()`, cùng logic handle policy (các ngoại lệ như Flash Sale, Digital Product) và tích hợp các MCP tools (`search_kb`, `get_ticket_info`). Tôi cũng thiết lập server HTTP cho MCP dùng FastAPI (phần Bonus).

**Cách công việc của tôi kết nối với phần của thành viên khác:**
Công việc của tôi đảm nhận vị trí trung tâm trong việc cấp quyền năng cho hệ thống tương tác với thế giới bên ngoài (external capability). Nếu Supervisor (Member A) điều hướng task về nhánh bắt lỗi rules hoặc tương tác ticket, task đó sẽ trôi vào `policy_tool.py`. Từ đó, logic của tôi sẽ kết nối mượt mà tới `mcp_server.py` để tìm kiếm Knowledge Base (thông qua Retrieval Owner - Member B) hoặc lấy dữ liệu Mock từ hệ thống ngoài rập khuôn. Mọi hoạt động được đóng gói trace chuẩn mực để Trace Owner ghi nhận kết quả cuối (mcp_usage_rate = ~42% theo kết quả eval_report.json).

**Bằng chứng (commit hash, file có comment tên bạn, v.v.):**
- File `mcp_server.py` function `call_mcp_with_trace` wrap theo chuẩn: `{"tool": "...", "input": {...}, "output": {...}}`.
- Báo cáo chạy test thực tế: Mảng `day09_multi_agent.mcp_usage_rate` đạt 18/42 (42%).

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Tôi quyết định không truy cập trực tiếp ChromaDB từ Policy Worker mà bắt buộc dòng chảy dữ liệu phải qua một abstraction layer là `_call_mcp_tool("search_kb", ...)` bên trong `workers/policy_tool.py` thông qua chuẩn của `mcp_server`.

**Lý do:**
Việc gọi DB trực tiếp dễ dàng hơn nhưng nó làm rối pattern Multi-Agent, khiến Worker tự ý lạm quyền và không đồng bộ hóa với định dạng Trace của Supervisor. Thông qua MCP interface (Model Context Protocol), mọi tool như tra cứu Policy, get Ticket Info đều được quy chuẩn schema (`inputSchema`, `outputSchema`).
Điều này còn mang lại lợi thế mở rộng vượt trội: Khi muốn tạo thêm các Tool khác, tôi chỉ đăng ký vào `TOOL_REGISTRY` thay vì sửa core logic của Worker. (Đúng như nhận định `"mcp_benefit"` ở file eval_report.json: sửa được năng lực mà không cần sửa core).

**Trade-off đã chấp nhận:**
Latency có phần tăng nhẹ do phải đi qua thêm một vòng đóng gói/phân giải payload chuẩn MCP, ngoài ra việc Mock Data tool đôi lúc khiến mã bị dài với `try / except` wrap thay vì simple function calls.

**Bằng chứng từ trace/code:**
Logic call trong file `workers/policy_tool.py`:
```python
if not chunks and needs_tool:
    mcp_record = _call_mcp_tool("search_kb", {"query": task, "top_k": 3})
    state["mcp_tools_used"].append(mcp_record)
    state["mcp_tool_called"].append(mcp_record)   # Tracing chuẩn Sprint 3
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** Supervisor Pipeline Crash do Dispatch Tool gọi những Tool không tồn tại hoặc sai Schema Input.

**Symptom (pipeline làm gì sai?):**
Trước đây, những công việc khi đi tới `policy_tool_worker` đôi lúc tự ảo giác gọi đại một phương thức (VD: `nonexistent_tool`) dẫn tới Exception Python văng thẳng lên graph chính -> Toàn bộ luồng supervisor đứt gãy -> Node kế tiếp (Synthesis) nhận vào output rỗng hoặc lỗi 500, trả về User câu báo lỗi thô thiển.

**Root cause (lỗi nằm ở đâu — indexing, routing, contract, worker logic?):**
Lỗi nằm ở worker logic tại hàm dispatch gốc khi không bọc `try / except` cẩn thận hoặc không validate schema đầu vào (`TypeError` khi argument không khớp).

**Cách sửa:**
Tại `mcp_server.py`, trong `dispatch_tool()`, tôi đóng gói toàn bộ lời gọi hàm `result = tool_fn(**tool_input)` vào block `try - except`. Nếu có TypeError, trả về dict Error thông báo chỉ rõ Invalid schema; hoặc nếu Exception thông thường trả error message để Worker vẫn ghi log, pass qua State báo lỗi thay vì crash toàn tập.

**Bằng chứng trước/sau:**
Trong log test của `mcp_server.py` hiện tại:
```
🛡️  Test: invalid tool (graceful error handling)
  ✅ dispatch_tool trả error dict (không crash): Tool 'nonexistent_tool' không tồn tại. Available: ['search_kb', 'get_ticket_info', 'check_access_permission', 'create_ticket']
```

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

**Tôi làm tốt nhất ở điểm nào?**
Tôi đã implement phần Error Handling và Wrapping chuẩn MCP Protocol rất đầy đủ. Việc implement FastAPI (tạo HTTP server với 3 endpoints) cũng chạy cực mượt, mở ra khả năng gọi MCP tool từ ngoài hệ thống.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**
Phần code `analyze_policy` của mình hiện chỉ dừng lại ở check bằng Keywords (Flash sale, kỹ thuật số...). Tôi mong muốn có thể áp dụng thêm LLM call để bắt các Exceptions chính sách ngầm phức tạp hơn nhưng thời gian bị dồn quá nhiều vào build REST API.

**Nhóm phụ thuộc vào tôi ở đâu?**
Sự sống còn của việc sử dụng công cụ mượt mà (MCP_usage_rate). Nếu phần `mcp_server` sập hoặc Dispatcher không chạy, toàn bộ phần Retrieval phụ thuộc Tool và Policy Worker sẽ vô dụng.

**Phần tôi phụ thuộc vào thành viên khác:**
Tôi cần phụ thuộc Retrieval Worker để tool `search_kb` có thể kéo data xịn. Cần Supervisor phân loại đúng `route_decision` vào nhánh `needs_tool=True` thì logic MCP của tay tôi mới được kích hoạt.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Tôi sẽ thử **nâng cấp function `analyze_policy` sang dùng LLM (GPT-4o-mini)** thay cho Rule-Based hiện tại, vì trace eval cho thấy các cases phức tạp (ví dụ hoàn tiền policy bị overlap version v3/v4 trước 01/02) dễ bị Regex/Keyword match fail. Tôi sẽ refactor logic gọi OpenAPI/Chroma client ở đấy để bảo đảm Worker nắm bắt được Exception trơn tru hơn.

---

*Lưu file này với tên: `reports/individual/luong_thanh_hau.md`*
