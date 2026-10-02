"""Đo độ tiêu tốn & hiệu năng gọi LLM (token, chi phí theo đơn giá, độ trễ).

Mỗi lượt gọi LLM ghi **một dòng JSONL**: nhà cung cấp, model, token vào/ra, độ trễ, thành công/lỗi,
có phải lượt fallback không, và **chi phí quy từ đơn giá** Admin khai báo
(`input_price_per_1m` / `output_price_per_1m`).

Trang quản trị dùng dữ liệu này cho tab "Chi phí & hiệu năng": tổng chi phí, tổng token, p50/p95
độ trễ, tỉ lệ lỗi, bảng theo nhà cung cấp và log các lượt gọi gần nhất.

Ghi bằng JSONL append-only (giống `copilot/feedback.py`) để không cần migration DB; đường dẫn lấy
từ `LLM_USAGE_PATH`, mặc định `data/llm_usage.jsonl`.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DEFAULT_USAGE_PATH = Path("data/llm_usage.jsonl")
#: Số bản ghi tối đa đọc để tổng hợp (đủ cho dashboard; file lớn hơn thì nên chuyển sang DB).
MAX_RECORDS_SCANNED = 20_000


def _path() -> Path:
    raw = os.environ.get("LLM_USAGE_PATH")
    return Path(raw) if raw else DEFAULT_USAGE_PATH


def compute_cost_usd(
    *,
    input_tokens: int,
    output_tokens: int,
    input_price_per_1m: float,
    output_price_per_1m: float,
) -> float:
    """Chi phí một lượt gọi = token vào/ra × đơn giá trên 1 triệu token."""
    return round(
        (max(0, input_tokens) / 1_000_000) * max(0.0, input_price_per_1m)
        + (max(0, output_tokens) / 1_000_000) * max(0.0, output_price_per_1m),
        6,
    )


def record_usage(
    *,
    provider: str,
    model_name: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    latency_ms: float = 0.0,
    ok: bool = True,
    error: str | None = None,
    is_fallback: bool = False,
    input_price_per_1m: float = 0.0,
    output_price_per_1m: float = 0.0,
    currency: str = "USD",
    conversation_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Ghi một lượt gọi LLM và trả bản ghi vừa ghi."""
    record = {
        "at": datetime.now(UTC).isoformat(),
        "provider": provider,
        "model_name": model_name,
        "input_tokens": int(max(0, input_tokens)),
        "output_tokens": int(max(0, output_tokens)),
        "latency_ms": round(float(latency_ms or 0.0), 2),
        "ok": bool(ok),
        "error": (error or None),
        "is_fallback": bool(is_fallback),
        "cost": compute_cost_usd(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_price_per_1m=input_price_per_1m,
            output_price_per_1m=output_price_per_1m,
        ),
        "currency": currency,
        "conversation_id": conversation_id,
        "user_id": user_id,
    }
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def _read_records(days: int) -> list[dict[str, Any]]:
    path = _path()
    if not path.exists():
        return []
    cutoff = datetime.now(UTC) - timedelta(days=max(1, days))
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            at = str(item.get("at") or "")
            try:
                if datetime.fromisoformat(at.replace("Z", "+00:00")) < cutoff:
                    continue
            except ValueError:
                continue
            records.append(item)
    return records[-MAX_RECORDS_SCANNED:]


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(int(len(ordered) * pct), len(ordered) - 1)
    return round(ordered[idx], 2)


def summarize_usage(days: int = 14) -> dict[str, Any]:
    """Tổng hợp cho tab "Chi phí & hiệu năng"."""
    records = _read_records(days)
    ok_records = [r for r in records if r.get("ok")]
    latencies = [float(r.get("latency_ms") or 0.0) for r in ok_records]
    total_in = sum(int(r.get("input_tokens") or 0) for r in records)
    total_out = sum(int(r.get("output_tokens") or 0) for r in records)
    total_cost = round(sum(float(r.get("cost") or 0.0) for r in records), 6)

    by_provider: dict[tuple[str, str], dict[str, Any]] = {}
    for r in records:
        key = (str(r.get("provider") or "unknown"), str(r.get("model_name") or "unknown"))
        bucket = by_provider.setdefault(
            key,
            {
                "provider": key[0],
                "model_name": key[1],
                "calls": 0,
                "failed_calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost": 0.0,
                "latencies": [],
            },
        )
        bucket["calls"] += 1
        if not r.get("ok"):
            bucket["failed_calls"] += 1
        bucket["input_tokens"] += int(r.get("input_tokens") or 0)
        bucket["output_tokens"] += int(r.get("output_tokens") or 0)
        bucket["cost"] = round(bucket["cost"] + float(r.get("cost") or 0.0), 6)
        if r.get("ok"):
            bucket["latencies"].append(float(r.get("latency_ms") or 0.0))

    providers = []
    for bucket in by_provider.values():
        lats = bucket.pop("latencies")
        bucket["avg_latency_ms"] = round(sum(lats) / len(lats), 2) if lats else 0.0
        bucket["p95_latency_ms"] = _percentile(lats, 0.95)
        bucket["error_rate"] = round(bucket["failed_calls"] / bucket["calls"], 4) if bucket["calls"] else 0.0
        providers.append(bucket)
    providers.sort(key=lambda b: b["cost"], reverse=True)

    # Xu hướng theo ngày (cho cột sparkline/bảng nhỏ ở UI).
    by_day: dict[str, dict[str, float]] = {}
    for r in records:
        day = str(r.get("at") or "")[:10]
        slot = by_day.setdefault(day, {"calls": 0, "cost": 0.0, "tokens": 0})
        slot["calls"] += 1
        slot["cost"] = round(slot["cost"] + float(r.get("cost") or 0.0), 6)
        slot["tokens"] += int(r.get("input_tokens") or 0) + int(r.get("output_tokens") or 0)

    return {
        "window_days": days,
        "total_calls": len(records),
        "failed_calls": len(records) - len(ok_records),
        "error_rate": round((len(records) - len(ok_records)) / len(records), 4) if records else 0.0,
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "total_tokens": total_in + total_out,
        "total_cost": total_cost,
        "currency": next((str(r.get("currency") or "USD") for r in records), "USD"),
        "p50_latency_ms": _percentile(latencies, 0.50),
        "p95_latency_ms": _percentile(latencies, 0.95),
        "avg_cost_per_call": round(total_cost / len(records), 6) if records else 0.0,
        "by_provider": providers,
        "by_day": [{"day": day, **values} for day, values in sorted(by_day.items())],
    }


def recent_usage(limit: int = 50) -> list[dict[str, Any]]:
    """Log các lượt gọi gần nhất (mới nhất trước) cho bảng chi tiết."""
    records = _read_records(days=90)
    return list(reversed(records[-max(1, limit) :]))
