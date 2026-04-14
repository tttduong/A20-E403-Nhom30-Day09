"""
workers/synthesis.py — Synthesis Worker
Sprint 2: Tổng hợp câu trả lời từ retrieved_chunks và policy_result.

Input (từ AgentState):
    - task: câu hỏi
    - retrieved_chunks: evidence từ retrieval_worker
    - policy_result: kết quả từ policy_tool_worker

Output (vào AgentState):
    - final_answer: câu trả lời cuối với citation
    - sources: danh sách nguồn tài liệu được cite
    - confidence: mức độ tin cậy (0.0 - 1.0)

Gọi độc lập để test:
    python workers/synthesis.py
"""

import os

WORKER_NAME = "synthesis_worker"

SYSTEM_PROMPT = """Bạn là trợ lý IT Helpdesk nội bộ.

Quy tắc nghiêm ngặt:
1. CHỈ trả lời dựa vào context được cung cấp. KHÔNG dùng kiến thức ngoài.
2. Nếu context không đủ để trả lời → nói rõ "Không đủ thông tin trong tài liệu nội bộ".
3. Trích dẫn nguồn cuối mỗi câu quan trọng: [tên_file].
4. Trả lời súc tích, có cấu trúc. Không dài dòng.
5. Nếu có exceptions/ngoại lệ → nêu rõ ràng trước khi kết luận.
"""

ABSTAIN_MESSAGE = "Không đủ thông tin trong tài liệu nội bộ để trả lời câu hỏi này."


def _call_llm(messages: list) -> str:
    """
    Gọi LLM để tổng hợp câu trả lời.
    TODO Sprint 2: Implement với OpenAI hoặc Gemini.
    """
    # Option A: OpenAI
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.1,  # Low temperature để grounded
            max_tokens=500,
        )
        return response.choices[0].message.content
    except Exception:
        pass

    # Option B: Gemini
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        model = genai.GenerativeModel("gemini-1.5-flash")
        combined = "\n".join([m["content"] for m in messages])
        response = model.generate_content(combined)
        return response.text
    except Exception:
        pass

    # Fallback: trả về message báo lỗi (không hallucinate)
    return "[SYNTHESIS ERROR] Không thể gọi LLM. Kiểm tra API key trong .env."


def _build_context(chunks: list, policy_result: dict) -> str:
    """Xây dựng context string từ chunks và policy result."""
    parts = []

    if chunks:
        parts.append("=== TÀI LIỆU THAM KHẢO ===")
        for i, chunk in enumerate(chunks, 1):
            source = chunk.get("source", "unknown")
            text = chunk.get("text", "")
            score = chunk.get("score", 0)
            parts.append(f"[{i}] Nguồn: {source} (relevance: {score:.2f})\n{text}")

    if policy_result:
        if policy_result.get("policy_version_note"):
            parts.append("\n=== POLICY VERSION NOTE ===")
            parts.append(str(policy_result.get("policy_version_note")))

        if policy_result.get("exceptions_found"):
            parts.append("\n=== POLICY EXCEPTIONS ===")
            for ex in policy_result.get("exceptions_found", []):
                rule = ex.get("rule", "")
                src = ex.get("source", "")
                if src:
                    parts.append(f"- {rule} [{src}]")
                else:
                    parts.append(f"- {rule}")

    if not parts:
        return "(Không có context)"

    return "\n\n".join(parts)


def _estimate_confidence(chunks: list, answer: str, policy_result: dict) -> float:
    """
    Ước tính confidence dựa vào:
    - Số lượng và quality của chunks
    - Có exceptions không
    - Answer có abstain không

    TODO Sprint 2: Có thể dùng LLM-as-Judge để tính confidence chính xác hơn.
    """
    if not chunks:
        return 0.1  # Không có evidence → low confidence

    if "Không đủ thông tin" in answer or "không có trong tài liệu" in answer.lower():
        return 0.3  # Abstain → moderate-low

    # Weighted average của chunk scores
    if chunks:
        avg_score = sum(c.get("score", 0) for c in chunks) / len(chunks)
    else:
        avg_score = 0

    # Penalty nếu có exceptions (phức tạp hơn)
    exception_penalty = 0.05 * len(policy_result.get("exceptions_found", []))

    confidence = min(0.95, avg_score - exception_penalty)
    return round(max(0.1, confidence), 2)

def _extract_sources_from_chunks(chunks: list) -> list[str]:
    sources: list[str] = []
    seen = set()
    for c in chunks or []:
        src = (c or {}).get("source", "unknown")
        if src not in seen:
            sources.append(src)
            seen.add(src)
    return sources


def _has_any_citation(answer: str, sources: list[str]) -> bool:
    a = (answer or "").lower()
    for s in sources:
        if not s:
            continue
        if f"[{s.lower()}]" in a:
            return True
    return False


def _ensure_citations(answer: str, sources: list[str]) -> str:
    """
    Enforce at least 1 citation marker when we have evidence.
    We keep it minimal to avoid rewriting user-facing content too much.
    """
    if not sources:
        return answer
    if _has_any_citation(answer, sources):
        return answer
    # If model forgot citations, append a short sources line (still grounded).
    # Format requested in prompt: [tên_file]
    cites = " ".join([f"[{s}]" for s in sources if s])
    if not cites:
        return answer
    return (answer.rstrip() + f"\n\nNguồn: {cites}\n")


def _fallback_summarize(task: str, chunks: list, policy_result: dict) -> str:
    """
    Fallback when LLM is unavailable: produce an extractive, grounded answer.
    This is intentionally conservative to avoid hallucination.
    """
    # If policy exceptions exist, surface them first.
    if policy_result and policy_result.get("exceptions_found"):
        lines = []
        if policy_result.get("policy_version_note"):
            lines.append(str(policy_result["policy_version_note"]))
        for ex in policy_result.get("exceptions_found", []):
            rule = (ex or {}).get("rule", "").strip()
            src = (ex or {}).get("source", "")
            if rule:
                lines.append(f"- {rule}" + (f" [{src}]" if src else ""))
        if lines:
            return "\n".join(lines)

    # Otherwise: return the most relevant chunk verbatim (trimmed).
    best = None
    for c in chunks or []:
        if best is None or c.get("score", 0) > best.get("score", 0):
            best = c
    if not best:
        return ABSTAIN_MESSAGE

    text = (best.get("text", "") or "").strip()
    if len(text) > 700:
        text = text[:700].rstrip() + "..."
    src = best.get("source", "")
    if src:
        return f"{text}\n\nNguồn: [{src}]"
    return text


def synthesize(task: str, chunks: list, policy_result: dict) -> dict:
    """
    Tổng hợp câu trả lời từ chunks và policy context.

    Returns:
        {"answer": str, "sources": list, "confidence": float}
    """
    sources = _extract_sources_from_chunks(chunks)

    # Hard abstain if no evidence. (Avoid hallucination penalty.)
    if not chunks:
        answer = ABSTAIN_MESSAGE
        confidence = _estimate_confidence(chunks, answer, policy_result)
        return {"answer": answer, "sources": [], "confidence": confidence}

    # Guardrail: if task asks about specific ERR-* code but none of the chunks mention it,
    # abstain instead of fabricating.
    task_lower = (task or "").lower()
    import re
    m = re.search(r"\b(err-[a-z0-9_-]+)\b", task_lower)
    if m:
        code = m.group(1)
        if not any(code in (c.get("text", "").lower()) for c in chunks):
            answer = ABSTAIN_MESSAGE
            confidence = _estimate_confidence([], answer, policy_result)
            return {"answer": answer, "sources": [], "confidence": confidence}

    # Guardrail: weak/irrelevant evidence → abstain.
    max_score = max((c.get("score", 0.0) for c in chunks), default=0.0)
    if max_score < 0.35:
        answer = ABSTAIN_MESSAGE
        confidence = _estimate_confidence([], answer, policy_result)
        return {"answer": answer, "sources": [], "confidence": confidence}

    context = _build_context(chunks, policy_result)

    # Build messages
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""Câu hỏi: {task}

{context}

Yêu cầu bắt buộc:
- Chỉ dùng thông tin có trong context, không suy đoán.
- Nếu thiếu chi tiết để kết luận chắc chắn, hãy abstain rõ ràng: "{ABSTAIN_MESSAGE}"
- Mỗi ý quan trọng phải có citation theo dạng [tên_file] (ví dụ: [sla_p1_2026.txt]).

Hãy trả lời câu hỏi dựa vào tài liệu trên."""
        }
    ]

    answer = _call_llm(messages)
    if isinstance(answer, str) and answer.startswith("[SYNTHESIS ERROR]"):
        answer = _fallback_summarize(task, chunks, policy_result)
    answer = _ensure_citations(answer, sources)
    confidence = _estimate_confidence(chunks, answer, policy_result)

    return {
        "answer": answer,
        "sources": sources,
        "confidence": confidence,
    }


def run(state: dict) -> dict:
    """
    Worker entry point — gọi từ graph.py.
    """
    task = state.get("task", "")
    chunks = state.get("retrieved_chunks", [])
    policy_result = state.get("policy_result", {})

    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state["workers_called"].append(WORKER_NAME)

    worker_io = {
        "worker": WORKER_NAME,
        "input": {
            "task": task,
            "chunks_count": len(chunks),
            "has_policy": bool(policy_result),
        },
        "output": None,
        "error": None,
    }

    try:
        result = synthesize(task, chunks, policy_result)
        state["final_answer"] = result["answer"]
        state["sources"] = result["sources"]
        state["confidence"] = result["confidence"]
        # Contract: confidence thấp thì nên trigger HITL
        if state.get("confidence", 0.0) < 0.4:
            state["hitl_triggered"] = True

        worker_io["output"] = {
            "answer_length": len(result["answer"]),
            "sources": result["sources"],
            "confidence": result["confidence"],
        }
        state["history"].append(
            f"[{WORKER_NAME}] answer generated, confidence={result['confidence']}, "
            f"sources={result['sources']}"
        )

    except Exception as e:
        worker_io["error"] = {"code": "SYNTHESIS_FAILED", "reason": str(e)}
        state["final_answer"] = f"SYNTHESIS_ERROR: {e}"
        state["confidence"] = 0.0
        state["history"].append(f"[{WORKER_NAME}] ERROR: {e}")

    state.setdefault("worker_io_logs", []).append(worker_io)
    return state


# ─────────────────────────────────────────────
# Test độc lập
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Synthesis Worker — Standalone Test")
    print("=" * 50)

    test_state = {
        "task": "SLA ticket P1 là bao lâu?",
        "retrieved_chunks": [
            {
                "text": "Ticket P1: Phản hồi ban đầu 15 phút kể từ khi ticket được tạo. Xử lý và khắc phục 4 giờ. Escalation: tự động escalate lên Senior Engineer nếu không có phản hồi trong 10 phút.",
                "source": "sla_p1_2026.txt",
                "score": 0.92,
            }
        ],
        "policy_result": {},
    }

    result = run(test_state.copy())
    print(f"\nAnswer:\n{result['final_answer']}")
    print(f"\nSources: {result['sources']}")
    print(f"Confidence: {result['confidence']}")

    print("\n--- Test 2: Exception case ---")
    test_state2 = {
        "task": "Khách hàng Flash Sale yêu cầu hoàn tiền vì lỗi nhà sản xuất.",
        "retrieved_chunks": [
            {
                "text": "Ngoại lệ: Đơn hàng Flash Sale không được hoàn tiền theo Điều 3 chính sách v4.",
                "source": "policy_refund_v4.txt",
                "score": 0.88,
            }
        ],
        "policy_result": {
            "policy_applies": False,
            "exceptions_found": [{"type": "flash_sale_exception", "rule": "Flash Sale không được hoàn tiền."}],
        },
    }
    result2 = run(test_state2.copy())
    print(f"\nAnswer:\n{result2['final_answer']}")
    print(f"Confidence: {result2['confidence']}")

    print("\n✅ synthesis_worker test done.")
