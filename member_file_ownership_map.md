# Mapping File Giữ Theo Member (A-B-C-D-E)

Tài liệu này chốt nhanh mỗi member nên giữ/chịu trách nhiệm file nào trong repo hiện tại để nộp lab.

## Member A — Supervisor Owner

- `graph.py`
- `contracts/worker_contracts.yaml` (phần state keys + routing contract, phối hợp với B/C/D)

## Member B — Retrieval Owner

- `workers/retrieval.py`
- `chroma_db/*` (nếu có thay đổi index phục vụ dense retrieval)
- `contracts/worker_contracts.yaml` (phần retrieval contract)

## Member C — Policy + MCP Owner

- `workers/policy_tool.py`
- `mcp_server.py`
- `contracts/worker_contracts.yaml` (phần policy + mcp contract)

## Member D — Synthesis + Docs Owner

- `workers/synthesis.py`
- `docs/system_architecture.md`
- `docs/routing_decisions.md`
- `docs/single_vs_multi_comparison.md`
- `reports/group_report.md` (sau 18:00 vẫn được cập nhật)

## Member E — Integration + Trace Owner

- `eval_trace.py`
- `artifacts/traces/*`
- `artifacts/grading_run.jsonl`
- `artifacts/eval_report.json`
- `reports/individual/quang_hien.md` (hoặc file cá nhân tương ứng, sau 18:00)

## File “nhóm cùng giữ” (không gán cứng 1 người)

- `README.md`
- `SCORING.md`
- `data/test_questions.json`
- `data/grading_questions.json`

## Chốt theo deadline

- **Trước 18:00**: code + contracts + docs kỹ thuật + `artifacts/grading_run.jsonl`.
- **Sau 18:00**: chỉ nên cập nhật `reports/group_report.md` và `reports/individual/*.md`.

