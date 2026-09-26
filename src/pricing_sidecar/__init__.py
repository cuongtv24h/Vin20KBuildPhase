"""C-06 — Deterministic Financial Pricing Engine sidecar (Owner: Dev 2).

Tiến trình Python ĐỘC LẬP, không truy cập network, giao tiếp duy nhất qua
Unix Domain Socket (`/var/run/pricing/engine.sock` production, dev:
`./data/pricing.sock`).

Các bất biến của vùng code này:
- 100% `decimal.Decimal` (prec = 28), TUYỆT ĐỐI không float
- Không import gì từ `src.agents` / LLM — tách biệt triệt để nhận thức & tính toán
- Mục tiêu độ trễ < 5ms per call (Spike 1)
- Chuẩn tính toán: FCS v2.6 (`mydoc/0.2.financial-calculation-spec.md`)
- Benchmark: golden cases Δ = 0 VNĐ (`mydoc/dataset/fixtures/golden_scenarios.json`)
"""
