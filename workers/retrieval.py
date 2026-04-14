"""
workers/retrieval.py — Retrieval Worker
Sprint 2: Retrieval evidence chunks.

NOTE (stability on mac/conda):
- Một số môi trường (đặc biệt Anaconda + numpy BLAS) có thể segfault khi import
  các package nặng như `chromadb` hoặc `sentence_transformers`.
- Worker mặc định ưu tiên Chroma dense retrieval với OpenAI embedding;
  nếu dense bị lỗi sẽ fallback lexical
  để không làm vỡ pipeline.

Input (từ AgentState):
    - task: câu hỏi cần retrieve
    - (optional) retrieved_chunks nếu đã có từ trước

Output (vào AgentState):
    - retrieved_chunks: list of {"text", "source", "score", "metadata"}
    - retrieved_sources: list of source filenames
    - worker_io_log: log input/output của worker này

Gọi độc lập để test:
    python workers/retrieval.py
"""

import os
import re
from pathlib import Path

# ─────────────────────────────────────────────
# Worker Contract (xem contracts/worker_contracts.yaml)
# Input:  {"task": str, "top_k": int = 3}
# Output: {"retrieved_chunks": list, "retrieved_sources": list, "error": dict | None}
# ─────────────────────────────────────────────

WORKER_NAME = "retrieval_worker"
DEFAULT_TOP_K = 3
TOP_K_SEARCH = 10       # Số chunks query từ ChromaDB
TOP_K_SELECT = 3        # Số chunks handoff cho synthesis
ABSTAIN_THRESHOLD = 0.3 # Lọc bỏ chunk có score < threshold
_MINILM_MODEL = None


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", (text or "").lower())


def _load_kb_docs(docs_dir: str = "./data/docs") -> list[dict]:
    """
    Load internal KB docs from ./data/docs (5 files in this lab).
    Returns list of {source, text}.
    """
    base = Path(docs_dir)
    if not base.exists():
        return []
    docs: list[dict] = []
    for p in sorted(base.glob("*")):
        if not p.is_file():
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        docs.append({"source": p.name, "text": txt})
    return docs


def _split_chunks(text: str) -> list[str]:
    """
    Split doc into medium chunks without any ML dependency.
    """
    t = (text or "").strip()
    if not t:
        return []
    # Prefer paragraph-like chunks; fallback to sentences-ish.
    parts = [p.strip() for p in re.split(r"\n\s*\n+", t) if p.strip()]
    if len(parts) >= 3:
        return parts
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+", t) if p.strip()]


def retrieve_lexical(query: str, top_k_select: int = TOP_K_SELECT) -> list:
    """
    Lexical retrieval: keyword overlap scoring (0..1), returns top chunks.
    """
    q_tokens = _tokenize(query)
    if not q_tokens:
        return []
    q_set = set(q_tokens)

    docs = _load_kb_docs()
    scored: list[tuple[float, str, str]] = []  # (score, source, chunk_text)

    for d in docs:
        source = d["source"]
        for chunk in _split_chunks(d["text"]):
            c_tokens = _tokenize(chunk)
            if not c_tokens:
                continue
            c_set = set(c_tokens)
            overlap = len(q_set & c_set)
            if overlap == 0:
                continue
            # Normalize: overlap / query_terms (simple + stable)
            score = overlap / max(1, len(q_set))
            scored.append((score, source, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)

    candidates = []
    for score, source, chunk in scored[: max(top_k_select * 4, top_k_select)]:
        candidates.append(
            {
                "text": chunk,
                "source": source,
                "score": round(float(score), 4),
                "metadata": {"retrieval": "lexical"},
            }
        )

    # Apply abstain threshold first.
    candidates = [c for c in candidates if c["score"] >= ABSTAIN_THRESHOLD]
    if not candidates:
        return []

    # Keep source diversity for multi-hop questions:
    # pick best chunk per source first, then fill remaining slots by score.
    selected = []
    seen_sources = set()
    for c in candidates:
        src = c["source"]
        if src in seen_sources:
            continue
        selected.append(c)
        seen_sources.add(src)
        if len(selected) >= top_k_select:
            return selected

    if len(selected) < top_k_select:
        for c in candidates:
            if c in selected:
                continue
            selected.append(c)
            if len(selected) >= top_k_select:
                break

    return selected[:top_k_select]


def _get_collection():
    """
    Kết nối ChromaDB collection.
    Đọc path và collection name từ env vars CHROMA_DB_PATH, CHROMA_COLLECTION.
    """
    # Import lazily to avoid segfaults in some environments
    import chromadb
    chroma_path = os.getenv("CHROMA_DB_PATH", "./chroma_db")
    collection_name = os.getenv("CHROMA_COLLECTION", "day09_docs")
    client = chromadb.PersistentClient(path=chroma_path)
    try:
        collection = client.get_collection(collection_name)
    except Exception:
        # Auto-create nếu chưa có
        collection = client.get_or_create_collection(
            collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        print(f"⚠️  Collection '{collection_name}' chưa có data. Chạy index script trong README trước.")
    return collection


def _embed_query_minilm(query: str) -> list[float]:
    """
    Embed query bằng model local all-MiniLM-L6-v2 (dim=384).
    Phù hợp với index build theo README Day 09.
    """
    global _MINILM_MODEL
    if _MINILM_MODEL is None:
        from sentence_transformers import SentenceTransformer

        model_name = os.getenv("DENSE_EMBED_MODEL", "all-MiniLM-L6-v2")
        _MINILM_MODEL = SentenceTransformer(model_name)
    return _MINILM_MODEL.encode(query).tolist()


def _embed_query_openai(query: str) -> list[float]:
    """Embed query bằng OpenAI (dim=1536)."""
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
    resp = client.embeddings.create(input=query, model=model)
    return resp.data[0].embedding


def _dense_query_with_embedding(
    query_embedding: list[float],
    top_k_search: int,
    top_k_select: int,
    retrieval_backend: str,
) -> list:
    collection = _get_collection()
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k_search,
        include=["documents", "distances", "metadatas"],
    )

    chunks = []
    for doc, dist, meta in zip(
        results["documents"][0],
        results["distances"][0],
        results["metadatas"][0],
    ):
        score = round(1 - dist, 4)  # cosine similarity
        if score < ABSTAIN_THRESHOLD:
            continue
        chunks.append(
            {
                "text": doc,
                "source": (meta or {}).get("source", "unknown"),
                "score": score,
                "metadata": {**(meta or {}), "retrieval": f"dense:{retrieval_backend}"},
            }
        )

    return chunks[:top_k_select]


def retrieve_dense(
    query: str,
    top_k_search: int = TOP_K_SEARCH,
    top_k_select: int = TOP_K_SELECT,
) -> list:
    """
    Dense retrieval: embed query → query ChromaDB → lọc threshold → trả top_k_select chunks.

    Two-stage:
    - Bước 1: Query ChromaDB với n_results=top_k_search (mặc định 10)
    - Bước 2: Lọc bỏ chunk có score < ABSTAIN_THRESHOLD (0.3)
    - Bước 3: Trả về tối đa top_k_select (mặc định 3) chunks còn lại

    Returns:
        list of {"text": str, "source": str, "score": float, "metadata": dict}
    """
    backend = os.getenv("DENSE_EMBED_BACKEND", "openai").lower()
    backends = [backend] if backend in {"minilm", "openai"} else ["minilm", "openai"]
    last_error = None

    for b in backends:
        try:
            if b == "minilm":
                emb = _embed_query_minilm(query)
            else:
                emb = _embed_query_openai(query)
            return _dense_query_with_embedding(emb, top_k_search, top_k_select, b)
        except Exception as e:
            last_error = e
            continue

    print(f"⚠️  ChromaDB query failed: {last_error}")
    # Fallback an toàn: quay về lexical retrieval để không làm vỡ pipeline.
    return retrieve_lexical(query, top_k_select=top_k_select)


def run(state: dict) -> dict:
    """
    Worker entry point — gọi từ graph.py.

    Args:
        state: AgentState dict

    Returns:
        Updated AgentState với retrieved_chunks và retrieved_sources
    """
    task = state.get("task", "")
    # Keep for logging/contract consistency even when lexical mode is used
    top_k_search = state.get("retrieval_top_k_search", TOP_K_SEARCH)
    top_k_select = state.get("retrieval_top_k", TOP_K_SELECT)

    state.setdefault("workers_called", [])
    state.setdefault("history", [])

    state["workers_called"].append(WORKER_NAME)

    # Log worker IO (theo contract)
    worker_io = {
        "worker": WORKER_NAME,
        "input": {"task": task, "top_k_search": top_k_search, "top_k_select": top_k_select},
        "output": None,
        "error": None,
    }

    try:
        use_chroma = str(os.getenv("USE_CHROMA", "1")).lower() in {"1", "true", "yes"}
        if use_chroma:
            top_k_search = state.get("retrieval_top_k_search", TOP_K_SEARCH)
            chunks = retrieve_dense(task, top_k_search=top_k_search, top_k_select=top_k_select)
        else:
            chunks = retrieve_lexical(task, top_k_select=top_k_select)

        sources = list({c["source"] for c in chunks})

        state["retrieved_chunks"] = chunks
        state["retrieved_sources"] = sources

        worker_io["output"] = {
            "chunks_count": len(chunks),
            "sources": sources,
        }
        state["history"].append(
            f"[{WORKER_NAME}] retrieved {len(chunks)} chunks from {sources}"
        )

    except Exception as e:
        worker_io["error"] = {"code": "RETRIEVAL_FAILED", "reason": str(e)}
        state["retrieved_chunks"] = []
        state["retrieved_sources"] = []
        state["history"].append(f"[{WORKER_NAME}] ERROR: {e}")

    # Ghi worker IO vào state để trace
    state.setdefault("worker_io_logs", []).append(worker_io)

    return state


# ─────────────────────────────────────────────
# Test độc lập
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Retrieval Worker — Standalone Test")
    print("=" * 50)

    test_queries = [
        "SLA ticket P1 là bao lâu?",
        "Điều kiện được hoàn tiền là gì?",
        "Ai phê duyệt cấp quyền Level 3?",
    ]

    for query in test_queries:
        print(f"\n▶ Query: {query}")
        result = run({"task": query})
        chunks = result.get("retrieved_chunks", [])
        print(f"  Retrieved: {len(chunks)} chunks")
        for c in chunks[:2]:
            print(f"    [{c['score']:.3f}] {c['source']}: {c['text'][:80]}...")
        print(f"  Sources: {result.get('retrieved_sources', [])}")

    print("\n✅ retrieval_worker test done.")
