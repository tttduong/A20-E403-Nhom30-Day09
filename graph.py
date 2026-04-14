import json
import os
from datetime import datetime
from typing import TypedDict, Literal, Optional

# ─────────────────────────────────────────────
# 1. Shared State — "Xương sống" dữ liệu của Graph
# ─────────────────────────────────────────────

class AgentState(TypedDict):
    """
    TypedDict định nghĩa cấu trúc dữ liệu đi xuyên suốt các Node.
    Đây là cơ chế 'Shared Memory' giúp các Agent phối hợp không cần truyền tham số rời rạc.
    """
    # [INPUT] Dữ liệu thô từ người dùng
    task: str                           

    # [DECISIONS] Các quyết định của Supervisor
    route_reason: str                   # Giải thích lý do chọn worker (phục vụ Traceability)
    risk_high: bool                     # Cờ đánh dấu tác vụ nhạy cảm/nguy hiểm
    needs_tool: bool                    # Cờ xác định có cần gọi MCP hay không
    hitl_triggered: bool                # Trạng thái chờ con người phê duyệt (Human-in-the-loop)

    # [WORKER OUTPUTS] Dữ liệu do các thành viên team (Worker Owners) điền vào
    retrieved_chunks: list              # Chunks văn bản từ ChromaDB
    retrieved_sources: list             # Danh sách tên file tài liệu
    policy_result: dict                 # Kết quả phân tích chính sách
    mcp_tools_used: list                # Nhật ký các công cụ bên ngoài đã gọi

    # [FINAL OUTPUT] Kết quả trả về cho User
    final_answer: str                   # Câu trả lời cuối cùng đã qua tổng hợp
    sources: list                       # Nguồn trích dẫn cụ thể [1], [2]
    confidence: float                   # Độ tự tin của mô hình (0.0 - 1.0)

    # [METADATA] Dữ liệu phục vụ giám sát và đánh giá (Observability)
    history: list                       # Log chi tiết hành động của từng Node
    workers_called: list                # Thứ tự các worker đã chạy (dùng để vẽ lại flow)
    supervisor_route: str               # Điểm đến tiếp theo do Supervisor chỉ định
    latency_ms: Optional[int]           # Tổng thời gian xử lý hệ thống
    run_id: str                         # ID duy nhất cho mỗi phiên làm việc


def make_initial_state(task: str) -> AgentState:
    """Khởi tạo trạng thái mặc định, đảm bảo các list không bị null khi bắt đầu."""
    return {
        "task": task,
        "route_reason": "",
        "risk_high": False,
        "needs_tool": False,
        "hitl_triggered": False,
        "retrieved_chunks": [],
        "retrieved_sources": [],
        "policy_result": {},
        "mcp_tools_used": [],
        "final_answer": "",
        "sources": [],
        "confidence": 0.0,
        "history": [],
        "workers_called": [],
        "supervisor_route": "",
        "latency_ms": None,
        "run_id": f"run_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
    }


# ─────────────────────────────────────────────
# 2. Supervisor Node — "Nhạc trưởng" điều phối
# ─────────────────────────────────────────────

def supervisor_node(state: AgentState) -> AgentState:
    """
    Đóng vai trò Intent Classifier.
    Chiến thuật: Keyword-based Routing kết hợp Risk Assessment.
    Ưu điểm: Tốc độ xử lý cực nhanh (<5ms), tiết kiệm token và dễ debug lý do route.
    """
    task = state["task"].lower()
    state["history"].append(f"[supervisor] received task: {state['task'][:80]}")

    # Danh mục từ khóa định danh (Cần cập nhật khi thêm Worker mới)
    policy_keywords = ["hoàn tiền", "refund", "flash sale", "license", "cấp quyền", "access", "level 3"]
    retrieval_keywords = ["p1", "escalation", "sla", "ticket"]
    risk_keywords = ["emergency", "khẩn cấp", "2am", "không rõ", "err-"]

    # Giá trị mặc định: Nếu không khớp gì thì đi vào Retrieval để tìm kiếm thông tin
    route = "retrieval_worker"
    route_reason = "Default route: general knowledge retrieval"
    needs_tool = False
    risk_high = False

    # Logic Phân loại (Priority: Policy > Retrieval)
    if any(kw in task for kw in policy_keywords):
        route = "policy_tool_worker"
        route_reason = "Task contains policy/access keyword -> policy_tool_worker"
        needs_tool = True # Đánh dấu cần dùng MCP Tools ở Sprint 3
    
    elif any(kw in task for kw in retrieval_keywords):
        route = "retrieval_worker"
        route_reason = "Task contains SLA/P1/Ticket keyword -> retrieval_worker"
    
    # Đánh giá mức độ rủi ro (Risk Assessment)
    if any(kw in task for kw in risk_keywords):
        risk_high = True
        route_reason += " | risk_high flagged due to urgency or ambiguity"

    # Chốt chặn cuối cùng: Nếu rủi ro cao + lỗi hệ thống lạ -> Đưa về con người
    if risk_high and "err-" in task:
        route = "human_review"
        route_reason = "Risk_high + unknown error code (ERR-*) -> human_review"

    # Cập nhật quyết định vào State
    state["supervisor_route"] = route
    state["route_reason"] = route_reason
    state["needs_tool"] = needs_tool
    state["risk_high"] = risk_high
    state["history"].append(f"[supervisor] route={route} reason={route_reason}")

    return state


# ─────────────────────────────────────────────
# 3. Route Decision — Cầu nối điều hướng
# ─────────────────────────────────────────────

def route_decision(state: AgentState) -> Literal["retrieval_worker", "policy_tool_worker", "human_review"]:
    """
    Hàm này đóng vai trò 'Ngã tư đường'. Nó đọc supervisor_route trong state
    để chỉ định node tiếp theo mà Graph sẽ thực thi.
    """
    route = state.get("supervisor_route", "retrieval_worker")
    return route  # type: ignore


# ─────────────────────────────────────────────
# 4. Human Review Node — Chốt chặn an toàn (HITL)
# ─────────────────────────────────────────────

def human_review_node(state: AgentState) -> AgentState:
    """
    Human-in-the-loop: Tạm dừng hệ thống để lấy ý kiến chuyên gia.
    Trong Lab này, đây là placeholder tự động approve sau khi ghi log cảnh báo.
    """
    state["hitl_triggered"] = True
    state["history"].append("[human_review] HITL triggered — awaiting human input")
    state["workers_called"].append("human_review")

    print(f"\n⚠️  HITL TRIGGERED")
    print(f"    Task: {state['task']}")
    print(f"    Reason: {state['route_reason']}")
    print(f"    Action: Auto-approving in lab mode (set hitl_triggered=True)\n")

    # Sau khi được con người 'duyệt', hệ thống quay lại quy trình chuẩn
    state["supervisor_route"] = "retrieval_worker"
    state["route_reason"] += " | human approved → retrieval"

    return state


# ─────────────────────────────────────────────
# 5. Build Graph — Bộ máy vận hành chính
# ─────────────────────────────────────────────

def build_graph():
    """
    Xây dựng Graph điều phối. 
    Lưu ý: Sprint này dùng logic Python thuần (Option A) để team dễ debug luồng đi.
    """
    def run(state: AgentState) -> AgentState:
        import time
        start = time.time()

        # BƯỚC 1: Supervisor ra quyết định
        state = supervisor_node(state)

        # BƯỚC 2: Điều hướng dựa trên quyết định
        route = route_decision(state)

        if route == "human_review":
            state = human_review_node(state)
            state = retrieval_worker_node(state) # Tiếp tục sau review
        elif route == "policy_tool_worker":
            state = policy_tool_worker_node(state)
            # Nếu check policy mà chưa có dữ liệu thô -> Gọi thêm Retrieval
            if not state["retrieved_chunks"]:
                state = retrieval_worker_node(state)
        else:
            state = retrieval_worker_node(state)

        # BƯỚC 3: Tổng hợp câu trả lời (Luôn chạy cuối cùng)
        state = synthesis_worker_node(state)

        # Ghi nhận thời gian xử lý toàn hệ thống
        state["latency_ms"] = int((time.time() - start) * 1000)
        state["history"].append(f"[graph] completed in {state['latency_ms']}ms")
        return state

    return run

# ─────────────────────────────────────────────
# 7. Public API
# ─────────────────────────────────────────────

_graph = build_graph()


def run_graph(task: str) -> AgentState:
    """Entry point: nhận câu hỏi, trả về AgentState với full trace."""
    state = make_initial_state(task)
    result = _graph(state)
    return result


def save_trace(state: AgentState, output_dir: str = "./artifacts/traces") -> str:
    """Lưu trace ra file JSON."""
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{output_dir}/{state['run_id']}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    return filename


# ─────────────────────────────────────────────
# 8. Manual Test
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("Day 09 Lab — Supervisor-Worker Graph")
    print("=" * 60)

    test_queries = [
        "SLA xử lý ticket P1 là bao lâu?",
        "Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — được không?",
        "Cần cấp quyền Level 3 để khắc phục P1 khẩn cấp. Quy trình là gì?",
        "Gặp lỗi hệ thống ERR-999 khi thực hiện escalation.",
    ]

    for query in test_queries:
        print(f"\n▶ Query: {query}")
        result = run_graph(query)
        print(f"  Route    : {result['supervisor_route']}")
        print(f"  Reason   : {result['route_reason']}")
        print(f"  Workers  : {result['workers_called']}")
        print(f"  Confidence: {result['confidence']}")
        print(f"  Latency  : {result['latency_ms']}ms")

        # Lưu trace
        trace_file = save_trace(result)
        print(f"  Trace saved → {trace_file}")

    print("\n✅ graph.py Sprint 1 complete. Ready for Sprint 2 (Worker Integration).")