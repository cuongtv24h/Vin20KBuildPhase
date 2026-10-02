#!/usr/bin/env python3
"""Đo độ thông minh của Sales Copilot trên bộ câu hỏi vàng.

Chạy được ở 2 chế độ:
- `--mode offline` (mặc định): dùng ReAct tất định — không cần API key, chạy được trong CI,
  đo đúng phần "không bao giờ chết lặng" của Copilot.
- `--mode llm`: dùng LLM thật (cần OPENAI_API_KEY) — đo chất lượng của bộ não chính.

Chỉ số (định nghĩa trong `eval/copilot/golden_questions.json`):
- tool_selection_accuracy — gọi đúng tool kỳ vọng
- citation_precision      — quyết định citation đúng (có/không)
- hallucination_rate      — tỷ lệ câu trả lời có dấu hiệu bịa
- p95_latency_ms          — phân vị 95 độ trễ một câu

Cách dùng:
    .venv/bin/python scripts/run_copilot_eval.py                    # offline, in bảng
    .venv/bin/python scripts/run_copilot_eval.py --json eval/results/copilot_report.json
    .venv/bin/python scripts/run_copilot_eval.py --mode llm --limit 10
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any

# Bộ eval chạy hàng chục lượt hỏi nên log hạ tầng của RAG/DB rất ồn — chỉ giữ lỗi thật.
logging.getLogger("src").setLevel(logging.ERROR)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agents.copilot.graph import CopilotRequest, stream_copilot  # noqa: E402

GOLDEN_PATH = ROOT / "eval" / "copilot" / "golden_questions.json"
SALE_SCENARIOS_PATH = ROOT / "eval" / "copilot" / "sale_scenarios.json"
DEFAULT_REPORT = ROOT / "eval" / "results" / "copilot_report.json"

#: Bộ kịch bản Sale (đợt 15) — phủ 12 nhóm việc Sale làm hằng ngày + luật hình thức P1.5b/P2.5.
#: Chấm thêm 4 nhóm tiêu chí nội dung mà bộ vàng không có:
#:   must_not_contain (CẤM xuất hiện), expect_table (phải có bảng), max_questions (tối đa N câu hỏi),
#:   và "vệ sinh hình thức" chung: không lộ snake_case nội bộ, không để bảng dính câu văn, không emoji mũi tên.
_INTERNAL_JARGON_RE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
_ARROW_EMOJI = "➡\ufe0f"


async def run_question(question: dict[str, Any], *, mode: str) -> dict[str, Any]:
    """Chạy một câu hỏi và trả về kết quả thô để chấm điểm."""
    context = question.get("context") or {}
    request = CopilotRequest(
        message=question["message"],
        history=[{"role": h["role"], "content": h["content"]} for h in question.get("history") or []],
        current_unit=context.get("current_unit"),
        lead_dossier_id=context.get("lead_dossier_id"),
        transaction_date=context.get("transaction_date"),
        project_id=context.get("project_id"),
    )

    started = time.perf_counter()
    events: list[tuple[str, dict[str, Any]]] = []
    if mode == "llm":
        async for event in stream_copilot(request):
            events.append((event.type, event.data))
    else:
        async for event in stream_copilot(request, llm_factory=_offline_llm_factory):
            events.append((event.type, event.data))
    elapsed_ms = (time.perf_counter() - started) * 1000

    final = next((d for k, d in reversed(events) if k == "final"), {})
    guardrail = next((d for k, d in events if k == "guardrail"), {})
    return {
        "id": question["id"],
        "group": question.get("group", "general"),
        "tools": [d.get("tool") for k, d in events if k == "action" and d.get("tool")],
        "citation_count": len(final.get("citations") or []),
        "grounded": bool(final.get("grounded")),
        "verified": bool(final.get("verified", True)),
        "refused": guardrail.get("is_safe") is False,
        "mode": final.get("mode"),
        "reply": str(final.get("reply") or ""),
        "latency_ms": round(elapsed_ms, 1),
        # Chi phí/chất lượng bổ sung (P2): đọc thẳng từ payload cuối, không tính lại.
        "critique_ok": bool((final.get("critique") or {}).get("ok", True)),
        "critique_issues": [i.get("code") for i in ((final.get("critique") or {}).get("issues") or [])],
        # Cổng CI P3.2: mọi lần lọc theo số phòng ngủ phải trả về ĐÚNG phân khúc đó.
        "segment_checks": [d.get("segment_check") for k, d in events if k == "observation" and d.get("segment_check")],
        # Chốt P3.3: câu tra cứu phải sạch cảnh báo — không còn ghi chú rỗng/hết hạn rà soát.
        "internal_notes": str(final.get("internal_notes") or ""),
        "observation_chars": int((final.get("context_budget") or {}).get("observation_chars") or 0),
        "cached_tool_results": int((final.get("context_budget") or {}).get("cached_tool_results") or 0),
        "plan_steps": len(final.get("plan") or []),
    }


def _offline_llm_factory() -> Any:
    """Ép Copilot rơi vào nhánh offline ReAct (tất định) mà không cần chờ timeout mạng."""

    class _OfflineLLM:
        def bind_tools(self, _tools: list[Any]) -> _OfflineLLM:  # pragma: no cover - luôn lỗi khi gọi
            return self

        async def ainvoke(self, _messages: list[Any]) -> Any:
            raise RuntimeError("EVAL_OFFLINE_MODE")

    return _OfflineLLM()


def score(question: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Chấm một câu theo 4 nhóm tiêu chí."""
    tools = set(result["tools"])
    required = set(question.get("required_tools") or [])
    any_tools = set(question.get("any_tools") or [])
    expect_no_tools = bool(question.get("expect_no_tools"))

    if required:
        tool_ok = required.issubset(tools)
    elif any_tools:
        tool_ok = bool(any_tools & tools)
    elif expect_no_tools:
        tool_ok = not tools
    else:
        tool_ok = True

    expect_citation = bool(question.get("expect_citation"))
    if expect_citation:
        citation_ok = result["citation_count"] > 0
    else:
        citation_ok = result["citation_count"] == 0

    expect_refusal = bool(question.get("expect_refusal"))
    expect_grounded = bool(question.get("expect_grounded"))

    # P3.2 — lỗi trộn phân khúc là lỗi CẤM: sai một ca là hỏng cả lượt đánh giá.
    segment_ok = all(check.get("ok", True) for check in (result.get("segment_checks") or []))
    # P3.3 — câu tra cứu không được còn ghi chú nội bộ rỗng/lạc hậu (số liệu phải đã đối chiếu được).
    expect_clean_notes = bool(question.get("expect_no_internal_notes"))
    notes_ok = not expect_clean_notes or not str(result.get("internal_notes") or "").strip()

    hallucinated = False
    # Câu bị guardrail chặn: `verified=False` là do input bị chặn, không phải bịa.
    if not result["verified"] and not (expect_refusal and result["refused"]):
        hallucinated = True
    if expect_grounded and not result["grounded"]:
        hallucinated = True
    if expect_refusal and not result["refused"]:
        hallucinated = True
    if not segment_ok:
        hallucinated = True  # trộn phân khúc: tính là sai nghiêm trọng (báo bằng cổng riêng bên dưới)
    if not notes_ok:
        hallucinated = True
    if question.get("expect_no_tools") and tools:
        hallucinated = True

    missing_terms = [t for t in question.get("must_contain") or [] if t.lower() not in result["reply"].lower()]

    # ── Tiêu chí NỘI DUNG/HÌNH THỨC (bộ kịch bản Sale) ──────────────────────────
    reply = str(result["reply"])
    lines = reply.split("\n")
    forbidden_hits = [t for t in question.get("must_not_contain") or [] if t.lower() in reply.lower()]
    table_ok = (not question.get("expect_table")) or any(
        line.strip().startswith("|") and line.strip().endswith("|") for line in lines
    )
    max_questions = question.get("max_questions")
    questions_ok = max_questions is None or reply.count("?") <= int(max_questions)

    # Vệ sinh hình thức — luật đã chốt, áp cho MỌI câu (không cần khai báo trong đề):
    #  1. không lộ định danh nội bộ kiểu `gia_toi_da_vnd` (P2.5);
    #  2. bảng phải nằm riêng dòng, không dính câu văn (P1.5b);
    #  3. không dùng emoji mũi tên ➡️ (P1.5b).
    hygiene: list[str] = []
    jargon = sorted(set(_INTERNAL_JARGON_RE.findall(reply)))
    if jargon:
        hygiene.append(f"lộ tên nội bộ: {', '.join(jargon[:3])}")
    if any("|" in line and not line.strip().startswith("|") for line in lines):
        hygiene.append("bảng dính câu văn (P1.5b)")
    if _ARROW_EMOJI in reply:
        hygiene.append("còn emoji mũi tên ➡️ (P1.5b)")

    return {
        "tool_ok": tool_ok,
        "citation_ok": citation_ok,
        "hallucinated": hallucinated,
        "missing_terms": missing_terms,
        "segment_ok": segment_ok,
        "notes_ok": notes_ok,
        "forbidden_hits": forbidden_hits,
        "table_ok": table_ok,
        "questions_ok": questions_ok,
        "hygiene": hygiene,
        "known_gap": bool(question.get("known_gap")),
    }


def summarize(results: list[dict[str, Any]], scored: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    latencies = sorted(r["latency_ms"] for r in results)
    p95_index = max(0, min(total - 1, int(round(0.95 * (total - 1))))) if total else 0
    per_group: dict[str, dict[str, int]] = {}
    for result, s in zip(results, scored, strict=True):
        bucket = per_group.setdefault(result["group"], {"total": 0, "tool_ok": 0, "citation_ok": 0, "hallucinated": 0})
        bucket["total"] += 1
        bucket["tool_ok"] += int(s["tool_ok"])
        bucket["citation_ok"] += int(s["citation_ok"])
        bucket["hallucinated"] += int(s["hallucinated"])

    segment_violations = [r["id"] for r, s in zip(results, scored, strict=True) if not s["segment_ok"]]

    # Câu ghi nhận lỗ hổng đã biết (known_gap) vẫn chạy và vẫn báo cáo, nhưng KHÔNG tính vào mẫu số
    # của các chỉ số — bộ chấm phải phản ánh đúng phần hệ thống đang làm được.
    scored_ids = [r["id"] for r, s in zip(results, scored, strict=True) if not s.get("known_gap")]
    known_gap_ids = [r["id"] for r, s in zip(results, scored, strict=True) if s.get("known_gap")]
    denominator = len(scored_ids) or 1
    by_id = {r["id"]: s for r, s in zip(results, scored, strict=True)}

    content_violations: list[dict[str, Any]] = []
    for qid in scored_ids:
        s = by_id[qid]
        for term in s["forbidden_hits"]:
            content_violations.append({"id": qid, "kind": "must_not_contain", "detail": term})
        if not s["table_ok"]:
            content_violations.append({"id": qid, "kind": "expect_table", "detail": "thiếu bảng markdown"})
        if not s["questions_ok"]:
            content_violations.append({"id": qid, "kind": "max_questions", "detail": "hỏi lại quá nhiều câu"})
        for issue in s["hygiene"]:
            content_violations.append({"id": qid, "kind": "hygiene", "detail": issue})

    return {
        "total": total,
        "scored_total": len(scored_ids),
        "known_gap_ids": known_gap_ids,
        "content_violations": content_violations,
        "forbidden_term_hits": [v for v in content_violations if v["kind"] == "must_not_contain"],
        "segment_gate_ok": not segment_violations,
        "segment_violations": segment_violations,
        "tool_selection_accuracy": round(sum(by_id[qid]["tool_ok"] for qid in scored_ids) / denominator, 4),
        "citation_precision": round(sum(by_id[qid]["citation_ok"] for qid in scored_ids) / denominator, 4),
        "hallucination_rate": round(sum(by_id[qid]["hallucinated"] for qid in scored_ids) / denominator, 4),
        "p95_latency_ms": latencies[p95_index] if latencies else 0.0,
        "mean_latency_ms": round(statistics.fmean(latencies), 1) if latencies else 0.0,
        "missing_terms": {r["id"]: s["missing_terms"] for r, s in zip(results, scored, strict=True) if s["missing_terms"]},
        "per_group": per_group,
        "quality": {
            "critique_flags": sum(1 for r in results if not r.get("critique_ok", True)),
            "critique_issue_codes": sorted({c for r in results for c in r.get("critique_issues") or []}),
            "multi_step_answers": sum(1 for r in results if (r.get("plan_steps") or 0) > 1),
            "estimated_observation_chars": sum(int(r.get("observation_chars") or 0) for r in results),
            "cached_tool_results": sum(int(r.get("cached_tool_results") or 0) for r in results),
        },
    }


async def run_eval(
    mode: str,
    limit: int | None = None,
    path: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Chạy một bộ câu hỏi (mặc định là bộ VÀNG) và chấm điểm.

    `path` cho phép chạy bộ KỊCH BẢN SALE (`eval/copilot/sale_scenarios.json`) — cùng bộ chấm, nhưng
    có thêm tiêu chí nội dung/hình thức. Câu có `offline: "skip"` bị bỏ qua khi chạy offline (chúng cần
    LLM hiểu câu) và được liệt kê riêng trong báo cáo để không ai tưởng là đã kiểm.
    """
    source = json.loads((path or GOLDEN_PATH).read_text(encoding="utf-8"))
    questions = source["questions"]
    if limit:
        questions = questions[:limit]

    skipped_offline = [q["id"] for q in questions if mode == "offline" and q.get("offline") == "skip"]
    active = [q for q in questions if not (mode == "offline" and q.get("offline") == "skip")]

    results: list[dict[str, Any]] = []
    for question in active:
        results.append(await run_question(question, mode=mode))
    scored = [score(q, r) for q, r in zip(active, results, strict=True)]
    report = summarize(results, scored)
    report["skipped_offline"] = skipped_offline
    report["question_file"] = str((path or GOLDEN_PATH).name)
    # Câu vừa là lỗ hổng đã biết vừa chỉ chạy được với LLM vẫn phải xuất hiện trong danh sách lỗ hổng —
    # bỏ qua khi chấm offline không có nghĩa là nó biến mất khỏi báo cáo.
    file_gaps = {q["id"] for q in questions if q.get("known_gap")}
    report["known_gap_ids"] = sorted(set(report["known_gap_ids"]) | (file_gaps & set(skipped_offline)))
    return results, scored, report


def print_report(results: list[dict[str, Any]], scored: list[dict[str, Any]], report: dict[str, Any], mode: str) -> None:
    print(f"\n=== Sales Copilot Eval ({mode}) ===")
    print(f"{'ID':<9}{'Nhóm':<14}{'Tool':<6}{'Cite':<6}{'Bịa':<5}{'ms':>8}  Ghi chú")
    for result, s in zip(results, scored, strict=True):
        flags = f"{'OK' if s['tool_ok'] else 'X':<6}{'OK' if s['citation_ok'] else 'X':<6}{'X' if s['hallucinated'] else '-':<5}"
        note = ", ".join(result["tools"]) or "—"
        if s["missing_terms"]:
            note += f" | thiếu: {s['missing_terms']}"
        if s.get("forbidden_hits"):
            note += f" | CẤM: {s['forbidden_hits']}"
        if s.get("hygiene"):
            note += f" | hình thức: {s['hygiene']}"
        if not s.get("table_ok", True):
            note += " | thiếu bảng"
        if s.get("known_gap"):
            note += " | [lỗ hổng đã biết]"

        print(f"{result['id']:<9}{result['group']:<14}{flags}{result['latency_ms']:>8.0f}  {note}")

    print("\n--- Chỉ số tổng ---")
    print(f"  tool_selection_accuracy : {report['tool_selection_accuracy']:.1%}")
    print(f"  citation_precision      : {report['citation_precision']:.1%}")
    print(f"  hallucination_rate      : {report['hallucination_rate']:.1%}")
    gate = "ĐẠT" if report.get("segment_gate_ok") else f"VI PHẠM ở {report.get('segment_violations')}"
    print(f"  cổng phân khúc (P3.2)   : {gate} — lọc N phòng ngủ phải trả về đúng N phòng ngủ")
    print(f"  p95_latency_ms          : {report['p95_latency_ms']:.0f} ms (trung bình {report['mean_latency_ms']:.0f} ms)")
    if report.get("scored_total") is not None and report.get("scored_total") != report.get("total"):
        print(f"  câu tính điểm           : {report['scored_total']} (bỏ {report['total'] - report['scored_total']} câu lỗ hổng đã biết)")
    violations = report.get("content_violations") or []
    print(f"  cổng nội dung/hình thức : {'ĐẠT' if not violations else 'VI PHẠM'} ({len(violations)} mục)")
    for v in violations[:12]:
        print(f"      - {v['id']}: [{v['kind']}] {v['detail']}")
    if report.get("known_gap_ids"):
        print(f"  lỗ hổng đã biết        : {', '.join(report['known_gap_ids'])} (xem notes trong file kịch bản)")
    if report.get("skipped_offline"):
        print(f"  chỉ chạy --mode llm    : {', '.join(report['skipped_offline'])}")
    quality = report.get("quality") or {}
    if quality:
        print("\n--- Chi phí & kiểm duyệt (P2) ---")
        print(f"  câu bị critic gắn cờ : {quality.get('critique_flags', 0)} {quality.get('critique_issue_codes') or ''}")
        print(f"  câu nhiều bước       : {quality.get('multi_step_answers', 0)}")
        print(f"  ký tự Observation    : {quality.get('estimated_observation_chars', 0):,} (cache dùng lại: {quality.get('cached_tool_results', 0)})")

    print("\n--- Theo nhóm ---")
    for group, bucket in sorted(report["per_group"].items()):
        print(
            f"  {group:<14} tool {bucket['tool_ok']}/{bucket['total']} · "
            f"cite {bucket['citation_ok']}/{bucket['total']} · bịa {bucket['hallucinated']}/{bucket['total']}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Đo chất lượng Sales Copilot trên bộ câu hỏi vàng.")
    parser.add_argument("--mode", choices=("offline", "llm"), default="offline")
    parser.add_argument("--limit", type=int, default=None, help="Chỉ chạy N câu đầu (để thử nhanh)")
    parser.add_argument("--json", type=Path, default=DEFAULT_REPORT, help="Nơi ghi báo cáo JSON")
    parser.add_argument(
        "--fail-under",
        type=float,
        default=None,
        help="Ngưỡng tool_selection_accuracy tối thiểu; dưới ngưỡng thì exit 1 (dùng trong CI)",
    )
    parser.add_argument(
        "--questions",
        type=Path,
        default=GOLDEN_PATH,
        help="File câu hỏi (mặc định: bộ vàng; dùng eval/copilot/sale_scenarios.json cho bộ kịch bản Sale)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Coi cả nội dung THIẾU (must_contain) là lỗi — nên bật khi chạy --mode llm trên VM",
    )
    args = parser.parse_args()

    results, scored, report = asyncio.run(run_eval(args.mode, args.limit, args.questions))
    print_report(results, scored, report, args.mode)

    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps({"mode": args.mode, "summary": report, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    try:
        shown_path = args.json.resolve().relative_to(ROOT)
    except ValueError:
        shown_path = args.json
    print(f"\nĐã ghi báo cáo: {shown_path}")

    # Cổng bắt buộc (chốt P3.2): trộn phân khúc là lỗi cấm — chặn CI bất kể có truyền --fail-under hay không.
    if not report.get("segment_gate_ok", True):
        print(f"THẤT BẠI: vi phạm phân khúc ở {report.get('segment_violations')}")
        return 1
    # Chốt P3.3: câu tra cứu không được còn ghi chú nội bộ (số liệu phải đã đối chiếu được).
    if report["hallucination_rate"] > 0:
        print(f"THẤT BẠI: hallucination_rate {report['hallucination_rate']:.1%} > 0%")
        return 1
    if args.fail_under is not None and report["tool_selection_accuracy"] < args.fail_under:
        print(f"THẤT BẠI: tool_selection_accuracy dưới ngưỡng {args.fail_under:.0%}")
        return 1
    # Cổng NỘI DUNG/HÌNH THỨC (đợt 15): nội dung bị cấm, thiếu bảng, hỏi dồn, lộ tên nội bộ, bảng dính
    # câu văn — đều là lỗi đã từng xảy ra thật nên phải chặn CI, không chỉ in ra cho đẹp.
    if report.get("content_violations"):
        print(f"THẤT BẠI: {len(report['content_violations'])} vi phạm nội dung/hình thức")
        return 1
    if args.strict and report.get("missing_terms"):
        print(f"THẤT BẠI (--strict): thiếu nội dung bắt buộc ở {list(report['missing_terms'])}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
