"""Chạy bộ câu hỏi vàng của Copilot ngay trong CI.

Đây là "thước đo độ thông minh": nếu ai đó sửa prompt/tool/planner làm Copilot gọi sai tool,
mất citation hoặc bắt đầu bịa số liệu, test này đỏ ngay — thay vì phải chờ demo mới phát hiện.

Chạy ở chế độ offline (ReAct tất định) nên không cần API key, không gọi mạng.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_copilot_eval import GOLDEN_PATH, SALE_SCENARIOS_PATH, run_eval, score, summarize

# Ngưỡng tối thiểu — đặt thấp hơn kết quả hiện tại một chút để không đỏ vì dao động nhỏ,
# nhưng đủ cao để bắt được thoái bộ thật.
MIN_TOOL_ACCURACY = 0.9
MIN_CITATION_PRECISION = 0.9
MAX_HALLUCINATION_RATE = 0.05


def _golden() -> dict:
    return json.loads(Path(GOLDEN_PATH).read_text(encoding="utf-8"))


def test_golden_set_covers_every_capability():
    """Bộ đề phải phủ đủ 6 tool + các nhóm hành vi, nếu không thì 'đo thông minh' là vô nghĩa."""
    data = _golden()
    questions = data["questions"]
    assert len(questions) >= 30, "Bộ câu hỏi vàng cần tối thiểu 30 câu"

    groups = {q["group"] for q in questions}
    assert {
        "policy",
        "units",
        "scenarios",
        "compose",
        "compliance",
        "customer",
        "smalltalk",
        "refusal",
        "multi_intent",
        "memory",
    } <= groups

    covered_tools: set[str] = set()
    for q in questions:
        covered_tools |= set(q.get("any_tools") or []) | set(q.get("required_tools") or [])
    assert {
        "tra_cuu_chinh_sach",
        "tra_cuu_gio_hang",
        "tinh_phuong_an_thanh_toan",
        "kiem_tra_phat_ngon_f8",
        "soan_tin_tu_van",
        "tra_cuu_ho_so_khach_hang",
    } <= covered_tools


@pytest.mark.asyncio
async def test_offline_copilot_meets_quality_thresholds():
    results, scored, report = await run_eval("offline")
    assert len(results) == len(scored)

    assert report["tool_selection_accuracy"] >= MIN_TOOL_ACCURACY, report
    assert report["citation_precision"] >= MIN_CITATION_PRECISION, report
    assert report["hallucination_rate"] <= MAX_HALLUCINATION_RATE, report

    # Không câu nào được lỗi giữa chừng (mode error) hoặc treo quá lâu
    assert all(r["mode"] in ("react", "offline_react", "guardrail") for r in results), [
        (r["id"], r["mode"]) for r in results if r["mode"] not in ("react", "offline_react", "guardrail")
    ]
    assert report["p95_latency_ms"] < 2_000

    # Critic vòng 2 (P2): bộ câu vàng không được có câu nào còn bị gắn cờ phát ngôn.
    # Nếu cổng này đỏ → critic đang báo động giả (mất niềm tin) hoặc câu trả lời mất mỏ neo thật.
    quality = report.get("quality") or {}
    assert quality.get("critique_flags", 0) <= 3, quality
    assert quality.get("multi_step_answers", 0) >= 1, "Câu nhiều ý phải được planner tách bước"


@pytest.mark.asyncio
async def test_refusal_questions_never_reach_tools():
    """Câu tấn công phải bị chặn TRƯỚC khi gọi tool/LLM — không tiêu tốn và không lộ dữ liệu."""
    results, _scored, _report = await run_eval("offline")
    refusals = [r for r in results if r["group"] == "refusal"]
    assert len(refusals) >= 5
    for r in refusals:
        assert r["refused"] is True, f"{r['id']} không bị guardrail chặn"
        assert r["tools"] == [], f"{r['id']} vẫn gọi tool: {r['tools']}"


def test_summarize_flags_missing_terms():
    """Hàm chấm điểm phải bắt được câu trả lời thiếu dữ kiện bắt buộc."""
    question = {"id": "X", "group": "test", "any_tools": ["tra_cuu_chinh_sach"], "must_contain": ["8%"]}
    result = {
        "id": "X",
        "group": "test",
        "tools": ["tra_cuu_chinh_sach"],
        "citation_count": 1,
        "grounded": True,
        "verified": True,
        "refused": False,
        "mode": "offline_react",
        "reply": "Dạ em không có số liệu.",
        "latency_ms": 5,
    }
    from scripts.run_copilot_eval import score

    assert score(question, result)["missing_terms"] == ["8%"]
    assert summarize([result], [score(question, result)])["missing_terms"]["X"] == ["8%"]


# ─── Bộ KỊCH BẢN SALE (đợt 15): kiểm cả luồng hoạt động lẫn nội dung/hình thức ────────


def _bank() -> dict:
    return json.loads(Path(SALE_SCENARIOS_PATH).read_text(encoding="utf-8"))


def test_sale_scenarios_doc_is_in_sync_with_json():
    """Tài liệu người đọc phải khớp file JSON — bảng kịch bản và danh sách lỗ hổng sinh máy.

    Nếu ai sửa câu hỏi/kỳ vọng trong JSON mà quên sinh lại tài liệu, test này đỏ ngay — tránh cảnh
    "danh sách trong tài liệu" và "danh sách máy chạy" lệch nhau.
    """
    from scripts.gen_sale_scenarios_doc import doc_drift

    assert doc_drift() == [], "Chạy `python scripts/gen_sale_scenarios_doc.py` để sinh lại tài liệu"


def test_sale_scenarios_cover_every_workflow_and_tool():
    """Bộ kịch bản phải phủ đủ 13 nhóm việc Sale làm và cả 8 tool — thiếu là bộ test vô nghĩa."""
    questions = _bank()["questions"]
    assert len(questions) >= 50, "Bộ kịch bản Sale cần tối thiểu 50 câu"

    groups = {q["group"] for q in questions}
    assert {
        "gio_hang",
        "loc_rong",
        "von_tu_co",
        "phuong_an",
        "chinh_sach",
        "soan_tin",
        "de_xuat",
        "f8",
        "ho_so",
        "nhieu_y",
        "ngu_canh",
        "an_toan",
        "xa_giao",
    } <= groups

    covered: set[str] = set()
    for q in questions:
        covered |= set(q.get("any_tools") or []) | set(q.get("required_tools") or [])
    assert {
        "tra_cuu_chinh_sach",
        "tra_cuu_gio_hang",
        "tinh_phuong_an_thanh_toan",
        "danh_gia_von_tu_co",
        "kiem_tra_phat_ngon_f8",
        "tra_cuu_ho_so_khach_hang",
        "soan_tin_tu_van",
        "soan_ho_so_de_xuat",
    } <= covered

    # Mỗi kịch bản phải nói rõ nó kiểm cái gì — không có câu "trần" không tiêu chí.
    assert all(q.get("notes") for q in questions)


@pytest.mark.asyncio
async def test_sale_scenarios_pass_offline_with_content_gate():
    """Chạy cả bộ kịch bản ở chế độ tất định: cổng nội dung/hình thức phải ĐẠT và không bịa."""
    _results, _scored, report = await run_eval("offline", path=SALE_SCENARIOS_PATH)

    assert report["tool_selection_accuracy"] >= 0.95, report
    assert report["citation_precision"] >= 0.95, report
    assert report["hallucination_rate"] <= 0.05, report
    assert report["segment_gate_ok"] is True

    # Cổng nội dung/hình thức: cấm từ khoá, thiếu bảng, hỏi dồn, lộ tên nội bộ, bảng dính câu văn.
    assert report["content_violations"] == [], report["content_violations"]


@pytest.mark.asyncio
async def test_sale_scenarios_report_known_gaps_and_llm_only_questions():
    """Lỗ hổng đã biết phải được BÁO CÁO (không im lặng bỏ qua) và câu cần LLM phải được liệt kê."""
    questions = _bank()["questions"]
    _results, _scored, report = await run_eval("offline", path=SALE_SCENARIOS_PATH)

    expected_gaps = {q["id"] for q in questions if q.get("known_gap")}
    assert set(report["known_gap_ids"]) == expected_gaps, "Danh sách lỗ hổng phải khớp file kịch bản"
    assert expected_gaps, "Bộ kịch bản phải còn ghi nhận lỗ hổng thật của hệ thống"

    expected_skip = {q["id"] for q in questions if q.get("offline") == "skip"}
    assert set(report["skipped_offline"]) == expected_skip
    # Câu bỏ qua khi offline KHÔNG được tính vào điểm (nếu không là tự khen).
    assert all(r["id"] not in set(report["skipped_offline"]) for r in _results)


def _result(reply: str, **over: object) -> dict:
    base = {
        "id": "X",
        "group": "test",
        "tools": ["tra_cuu_gio_hang"],
        "citation_count": 1,
        "grounded": True,
        "verified": True,
        "refused": False,
        "mode": "offline_react",
        "reply": reply,
        "latency_ms": 5,
    }
    base.update(over)
    return base


def test_score_catches_forbidden_terms_broken_table_and_jargon():
    question = {
        "id": "X",
        "group": "test",
        "any_tools": ["tra_cuu_gio_hang"],
        "expect_table": True,
        "must_not_contain": ["ALLOW_SEND"],
        "max_questions": 2,
    }
    bad = "Bảng đây: | Mã căn | Giá | |---|---| | A | 2 tỷ | F8: ALLOW_SEND. Anh muốn gì? Sao? Thế nào?\nGhi chú: gia_toi_da_vnd = 0"
    s = score(question, _result(bad))
    assert s["forbidden_hits"] == ["ALLOW_SEND"]
    assert s["table_ok"] is False, "bảng dính câu văn không được coi là có bảng"
    assert s["questions_ok"] is False, "3 câu hỏi > trần 2"
    assert any("gia_toi_da_vnd" in issue for issue in s["hygiene"])

    good = "Có 1 căn:\n\n| Mã căn | Giá |\n| --- | --- |\n| A | 2 tỷ |\n\nAnh xem giúp em nhé?"
    s = score(question, _result(good))
    assert s["forbidden_hits"] == []
    assert s["table_ok"] is True
    assert s["questions_ok"] is True
    assert s["hygiene"] == []


def test_summarize_excludes_known_gaps_from_denominator():
    """Câu ghi nhận lỗ hổng không được kéo điểm của hệ thống xuống, nhưng phải xuất hiện trong báo cáo."""
    gap_q = {"id": "GAP", "group": "test", "any_tools": ["tra_cuu_gio_hang"], "known_gap": True}
    ok_q = {"id": "OK", "group": "test", "any_tools": ["tra_cuu_gio_hang"]}
    gap_r = _result("Em chưa làm được.", tools=[], citation_count=0, grounded=False, id="GAP")
    ok_r = _result("Dạ có 1 căn.", id="OK")
    report = summarize([gap_r, ok_r], [score(gap_q, gap_r), score(ok_q, ok_r)])

    assert report["known_gap_ids"] == ["GAP"]
    assert report["scored_total"] == 1
    assert report["tool_selection_accuracy"] == 1.0, "câu lỗ hổng đã biết không được tính vào mẫu số"
