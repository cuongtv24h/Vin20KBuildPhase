#!/usr/bin/env python3
"""Sinh bằng chứng Gate 2.

Chạy 6 câu mẫu (mỗi nhóm một) qua Sales Copilot ở chế độ offline — ReAct tất định,
KHÔNG cần API key, KHÔNG cần mạng (LLM thay bằng `_OfflineLLM`). Ghi toàn bộ output
thực (reply, tools, citations, mode, grounded, trace) ra `mydoc/gate2/_evidence_raw.json`.

Chạy (dùng venv, không phải python global):
    PYTHONIOENCODING=utf-8 .venv/Scripts/python scripts/_gate2_evidence.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import asyncio  # noqa: E402

from run_copilot_eval import _offline_llm_factory, run_question, score  # noqa: E402

from src.agents.copilot.graph import CopilotRequest  # noqa: E402
from src.agents.copilot.service import CopilotService  # noqa: E402

GOLDEN = ROOT / "eval" / "copilot" / "golden_questions.json"
OUT = ROOT / "mydoc" / "gate2" / "_evidence_raw.json"

# Mỗi nhóm một ca — phủ đủ 6 "nghiệp vụ" để báo cáo Gate 2.
PICK = ["POL-01", "UNI-01", "SCE-01", "F8-01", "CMP-01", "REF-01"]


def build_request(q: dict) -> CopilotRequest:
    ctx = q.get("context") or {}
    return CopilotRequest(
        message=q["message"],
        history=[{"role": h["role"], "content": h["content"]} for h in q.get("history") or []],
        current_unit=ctx.get("current_unit"),
        lead_dossier_id=ctx.get("lead_dossier_id"),
        transaction_date=ctx.get("transaction_date"),
        project_id=ctx.get("project_id"),
    )


async def main() -> None:
    data = json.loads(GOLDEN.read_text(encoding="utf-8"))
    by_id = {q["id"]: q for q in data["questions"]}

    svc = CopilotService(llm_factory=_offline_llm_factory)
    records: list[dict] = []

    for qid in PICK:
        q = by_id[qid]
        request = build_request(q)
        final = await svc.run(request)  # payload cuối + `reasoning` trace đầy đủ
        scored_result = await run_question(q, mode="offline")
        scored = score(q, scored_result)

        # Trace ngắn gọn: chỉ giữ các bước quan trọng để đọc được, không nhồi cả bundle.
        trace_summary = [
            {
                "step": i,
                "type": t.get("type"),
                "tool": t.get("tool"),
                "ok": t.get("ok", t.get("verified", True)) if t.get("type") in ("observation", "final") else None,
            }
            for i, t in enumerate(final.get("reasoning") or [])
        ]

        records.append(
            {
                "id": qid,
                "group": q.get("group"),
                "input": {
                    "message": q["message"],
                    "context": q.get("context") or {},
                    "history": q.get("history") or [],
                },
                "final": {
                    "reply": final.get("reply"),
                    "tools_used": final.get("tools_used"),
                    "mode": final.get("mode"),
                    "grounded": final.get("grounded"),
                    "verified": final.get("verified"),
                    "iterations": final.get("iterations"),
                    "citations": final.get("citations"),
                    "plan_steps": len(final.get("plan") or []),
                    "internal_notes": final.get("internal_notes"),
                },
                "metrics_view": {
                    "tools": scored_result["tools"],
                    "citation_count": scored_result["citation_count"],
                    "grounded": scored_result["grounded"],
                    "refused": scored_result["refused"],
                    "latency_ms": scored_result["latency_ms"],
                },
                "score": {
                    k: scored[k]
                    for k in (
                        "tool_ok",
                        "citation_ok",
                        "hallucinated",
                        "segment_ok",
                        "notes_ok",
                        "hygiene",
                        "known_gap",
                    )
                },
                "trace": trace_summary,
            }
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"mode": "offline", "cases": records}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK wrote {OUT.relative_to(ROOT)} cases={len(records)}")


if __name__ == "__main__":
    asyncio.run(main())
