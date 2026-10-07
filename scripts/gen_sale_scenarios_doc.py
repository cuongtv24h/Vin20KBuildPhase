#!/usr/bin/env python3
"""Sinh bản NGƯỜI ĐỌC của bộ kịch bản Sale từ file JSON (nguồn sự thật).

Vì sao cần: `eval/copilot/sale_scenarios.json` là nơi sửa câu hỏi/kỳ vọng, còn
`docs/team_report/copilot_sale_scenarios.md` là bản để Sale/QA đọc. Nếu chép tay, hai bên sẽ lệch nhau
ngay lần sửa đầu tiên — nên bảng trong tài liệu **sinh máy** từ JSON.

Cách dùng:
    python scripts/gen_sale_scenarios_doc.py              # ghi lại tài liệu
    python scripts/gen_sale_scenarios_doc.py --check       # chỉ kiểm tra tài liệu có khớp JSON không (CI)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "eval" / "copilot" / "sale_scenarios.json"
REPORT_PATH = ROOT / "eval" / "results" / "sale_scenarios_report.json"
DOC_PATH = ROOT / "docs" / "team_report" / "copilot_sale_scenarios.md"
RUN_COMMAND = ".venv/bin/python scripts/run_copilot_eval.py --questions eval/copilot/sale_scenarios.json"

GROUP_LABEL: dict[str, str] = {
    "gio_hang": "Tra cứu giỏ hàng",
    "loc_rong": "Lọc rỗng & điều hướng",
    "von_tu_co": "Vốn tự có / đòn bẩy",
    "phuong_an": "Phương án thanh toán & báo giá",
    "chinh_sach": "Chính sách (kèm hiệu lực theo ngày)",
    "soan_tin": "Soạn tin gửi khách",
    "de_xuat": "Hồ sơ đề xuất trình Quản lý",
    "f8": "Kiểm phát ngôn F8",
    "ho_so": "Hồ sơ khách hàng",
    "nhieu_y": "Nhiều ý trong một lượt",
    "ngu_canh": "Ngữ cảnh hội thoại",
    "an_toan": "An toàn & không bịa",
    "xa_giao": "Xã giao",
}


def _expectations(question: dict[str, Any]) -> str:
    bits: list[str] = []
    if question.get("required_tools"):
        bits.append("**BẮT BUỘC** " + ", ".join(f"`{t}`" for t in question["required_tools"]))
    elif question.get("any_tools"):
        bits.append("một trong: " + ", ".join(f"`{t}`" for t in question["any_tools"]))
    elif question.get("expect_no_tools"):
        bits.append("**không gọi tool**")
    if question.get("expect_table"):
        bits.append("**bảng**")
    if question.get("must_contain"):
        bits.append("phải có: " + ", ".join(f"`{t}`" for t in question["must_contain"]))
    if question.get("must_not_contain"):
        bits.append("CẤM: " + ", ".join(f"`{t}`" for t in question["must_not_contain"]))
    if question.get("notes_contain"):
        bits.append("banner nội bộ có: " + ", ".join(f"`{t}`" for t in question["notes_contain"]))
    if question.get("max_questions"):
        bits.append(f"≤{question['max_questions']} câu hỏi")
    if question.get("expect_no_internal_notes"):
        bits.append("sạch ghi chú nội bộ")
    return " · ".join(bits) or "—"


def _tables(questions: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for group, label in GROUP_LABEL.items():
        items = [q for q in questions if q.get("group") == group]
        if not items:
            continue
        blocks.append(f"### {label}\n")
        blocks.append("| Mã | Sale hỏi | Kỳ vọng máy kiểm | Kiểm điều gì |")
        blocks.append("|---|---|---|---|")
        for q in items:
            tag = ""
            if q.get("known_gap"):
                tag = " · lỗ hổng"
            if q.get("offline") == "skip":
                tag += " · chỉ LLM"
            note = str(q.get("notes") or "")
            if q.get("known_gap"):
                note = "**(lỗ hổng đã biết)** " + note
            if q.get("offline") == "skip":
                note = "**(chỉ chạy ở chế độ LLM)** " + note
            safe_note = note.replace("|", "\\|")
            blocks.append(f"| {q['id']}{tag} | {q['message']} | {_expectations(q)} | {safe_note} |")
        blocks.append("")
    return "\n".join(blocks)


def _known_gaps(questions: list[dict[str, Any]]) -> str:
    """Danh sách lỗ hổng đã biết — sinh từ chính file JSON để không bao giờ lệch."""
    gaps = [q for q in questions if q.get("known_gap")]
    if not gaps:
        return "_Không còn lỗ hổng nào được ghi nhận._"
    lines = ["| Mã | Sale hỏi | Vấn đề |", "|---|---|---|"]
    for q in gaps:
        reason = str(q.get("notes") or "").strip()
        # Ghi chú trong JSON mở đầu bằng nhãn vấn đề — lấy câu đầu cho gọn.
        first = reason.split(". ")[0].rstrip(".")
        lines.append(f"| {q['id']} | {q['message']} | {first.replace('|', chr(92) + '|')} |")
    return "\n".join(lines)


def _summary_table() -> str:
    if not REPORT_PATH.exists():
        return "_Chưa có báo cáo — chạy eval để sinh `eval/results/sale_scenarios_report.json`._"
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))["summary"]
    gate = "ĐẠT" if report["segment_gate_ok"] else "VI PHẠM"
    content = "ĐẠT" if not report["content_violations"] else f"VI PHẠM ({len(report['content_violations'])} mục)"
    return "\n".join(
        [
            "| Chỉ số | Kết quả |",
            "|---|---|",
            f"| Câu tính điểm | **{report['scored_total']} / {report['total']}** "
            f"({len(report['known_gap_ids'])} câu lỗ hổng đã biết, {len(report['skipped_offline'])} câu chỉ chạy ở chế độ LLM) |",
            f"| Gọi đúng tool | **{report['tool_selection_accuracy']:.0%}** |",
            f"| Citation đúng | **{report['citation_precision']:.0%}** |",
            f"| Bịa số liệu | **{report['hallucination_rate']:.1%}** |",
            f"| Cổng phân khúc (P3.2) | **{gate}** |",
            f"| Cổng nội dung/hình thức | **{content}** |",
            f"| p95 độ trễ | {report['p95_latency_ms']:.0f} ms |",
        ]
    )


def render() -> str:
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    questions = data["questions"]
    return f"""# Bộ kịch bản Sale hỏi Copilot — kiểm luồng hoạt động & chất lượng nội dung

> Tài liệu này **sinh máy** từ `eval/copilot/sale_scenarios.json` — đừng sửa tay.
> Sửa câu hỏi/kỳ vọng trong file JSON rồi chạy `python scripts/gen_sale_scenarios_doc.py`.

**Trạng thái:** đã chạy thật (chế độ tất định, offline). Bộ vàng giữ nguyên vai trò đo "gọi đúng tool";
bộ này đo thêm **nội dung trả ra có dùng được để tư vấn khách không**.

| | |
|---|---|
| File máy chạy được | `eval/copilot/sale_scenarios.json` ({len(questions)} kịch bản, {len(GROUP_LABEL)} nhóm) |
| Bộ chấm | `scripts/run_copilot_eval.py` — chấm thêm: `must_not_contain`, `expect_table`, `max_questions`, `notes_contain`, vệ sinh hình thức |
| Báo cáo | `eval/results/sale_scenarios_report.json` |
| Bàn giao việc #3 (time-travel chính sách) | `docs/team_report/handoff_policy_timetravel.md` |
| Cổng tự động | `tests/test_agents/copilot/test_copilot_eval.py` |

## 0. Danh sách câu hỏi nằm ở đâu

- **Bản máy đọc (nguồn sự thật):** `eval/copilot/sale_scenarios.json` — mỗi câu là một mục JSON có `id`,
  `group`, `message`, `context`/`history` (nếu có) và các kỳ vọng máy kiểm (`any_tools`, `required_tools`,
  `must_contain`, `must_not_contain`, `expect_table`, `max_questions`, `notes_contain`, `known_gap`,
  `offline: "skip"`). Sửa bộ câu hỏi là sửa file này.
- **Bản người đọc:** mục 2 của chính tài liệu này (bảng {len(GROUP_LABEL)} nhóm, kèm "kiểm điều gì").
- **Bộ vàng (khác, nhỏ hơn):** `eval/copilot/golden_questions.json` — 34 câu đo "gọi đúng tool" cho CI.
- **Báo cáo kết quả:** `eval/results/sale_scenarios_report.json`.

## 1. Chạy thế nào

```bash
# 1) Offline, không cần API key — kiểm luồng gọi tool + hình thức câu trả lời (dùng được trong CI)
{RUN_COMMAND}

# 2) Trên VM (có LLM thật) — kiểm luôn văn phong, câu hỏi ngược, cách diễn đạt
{RUN_COMMAND.replace("scripts/run_copilot_eval.py", "scripts/run_copilot_eval.py --mode llm")} --strict

# 3) Kiểm bằng mắt trong app: /sale → Phiên chat mới → dán từng câu ở cột "Sale hỏi".
```

- `--strict`: coi **thiếu nội dung bắt buộc** (`must_contain`) là lỗi. Nên bật khi chạy `--mode llm` trên VM.
- Cổng **nội dung/hình thức** (CẤM xuất hiện, thiếu bảng, hỏi dồn, lộ tên nội bộ, bảng dính câu văn, thiếu
  kết luận kiểm duyệt ở banner nội bộ) **chặn CI mặc định**.
- Câu `chỉ LLM` bị bỏ qua khi chạy offline và được liệt kê riêng trong báo cáo.
- Câu `lỗ hổng` vẫn chạy, vẫn báo cáo, nhưng không tính vào mẫu số điểm.

## 2. Bảng kịch bản theo nhóm việc của Sale

{_tables(questions)}
## 3. Phiếu chấm nội dung cho người đọc (khi kiểm bằng mắt trong app)

Máy kiểm được hình thức và từ khoá; **văn phong và tính "gửi được cho khách" thì phải người đọc**. Phiếu
6 điểm, mỗi điểm Đạt/Không — chỉ cần 1 điểm Không là câu đó chưa đạt:

| # | Câu hỏi kiểm | Đạt khi |
|---|---|---|
| 1 | **Số có đúng không?** | Mọi con số khớp dữ liệu engine; không có số nào tự suy ra |
| 2 | **Có nguồn bấm được không?** | Con số quan trọng đều có mỏ neo `[n]`, bấm mở ra đúng điều khoản/căn |
| 3 | **Sale gửi khách được ngay chưa?** | Không có chữ nội bộ (tên tool, mã F8, "ghi chú kiểm duyệt"); bấm "Copy cho khách" là ra văn bản dùng được |
| 4 | **Có nói rõ phạm vi con số không?** | Số của toàn giỏ phải gắn nhãn "toàn giỏ"; số của phân khúc phải nói rõ phân khúc |
| 5 | **Có bước tiếp theo không?** | Kết thúc bằng hành động bấm được hoặc 1–2 câu hỏi điều hướng, không phải ngõ cụt |
| 6 | **Có dài dòng/hỏi dồn không?** | Phần chính 4–6 câu, tối đa 2 câu hỏi ngược, không lặp lại yêu cầu của Sale |

## 4. Kết quả chạy thật (lần chạy gần nhất)

{_summary_table()}

## 5. Việc cần xử lý

### 5.1 Đã sửa

| Lỗi | Cách sửa |
|---|---|
| Kết luận kiểm F8 bị bộ chặn rò rỉ "nuốt" mất (kết luận buộc phải trích lại câu bị chặn, mà luật cấm lại khớp chính phần trích dẫn) | Chỉ miễn **văn bản do engine kiểm duyệt viết** (trùng nguyên văn) và **phần trích dẫn trong ngoặc kép** khớp đúng nội dung đang kiểm; câu model tự viết vẫn bị chặn — xem `reply_format.mask_review_text` |
| Bản nháp gửi khách trộn nhãn nội bộ (`Bản nháp (SUPPORTED)`, `F8: ALLOW_SEND`) | Thân tin và kết luận kiểm duyệt tách hai đường: `summary` = văn bản gửi khách, `internal_notes` = kết luận dạng tiếng Việt cho banner nội bộ; cổng CI kiểm cả hai chiều (`must_not_contain` + `notes_contain`) |

### 5.2 Đã bàn giao — lỗi "chính sách đúng ngày hiệu lực" (việc #3)

Bàn giao kèm đặc tả đầy đủ: **`docs/team_report/handoff_policy_timetravel.md`** (ba nguyên nhân + vị trí
code, hành vi đúng, tiêu chí nghiệm thu, cách kiểm chứng, ràng buộc kỹ thuật, hai phương án B/C).

Tóm tắt: hệ thống có thể trả về **chính sách không phủ ngày giao dịch** (ngày 15/07/2026 với The Zen Park)
mà vẫn ghi "đang hiệu lực", lại còn trộn hai dự án ⇒ Sale có thể trích sai văn bản. Ca kiểm chạy được ngay
cả offline: `CS-08`.

### 5.3 Lỗ hổng đã biết (sinh từ file JSON)

{_known_gaps(questions)}

### 5.4 Còn lại

- Tool tra giỏ thiếu tham số **giá TỐI THIỂU** ⇒ câu "giá trên 3 tỷ" không lọc được (`AT-05`).
- Ba kiểu câu rơi vào trả lời mặc định chung chung: phân khúc không tồn tại, nhờ tư vấn phát ngôn rủi ro,
  dự án ngoài dữ liệu (`RONG-04`, `AT-03`, `AT-04`).
- Lớp tất định chưa hiểu một số câu tự nhiên (danh sách `chỉ LLM` trong báo cáo) — chỉ ảnh hưởng khi Copilot
  rơi về chế độ dự phòng.
- Chip "mở rộng sang 2PN+1" giữ nguyên trần giá cũ nên bấm xong lại ra kết quả rỗng (`RONG-05`).

## 6. Điều bộ kịch bản này CHƯA kiểm được

1. **Văn phong do LLM viết** — chỉ đo được ở `--mode llm` trên VM (sandbox không có API key/egress).
2. **Hiển thị thật trên trình duyệt** — bảng canh cột, mỏ neo bấm được, nút "Copy cho khách", watermark.
3. **Hồ sơ khách hàng** — trong sandbox không có DB nên chỉ kiểm được "gọi đúng tool".
4. **Số liệu nghiệp vụ** — bộ này kiểm câu trả lời khớp engine, không kiểm engine tính đúng theo hợp đồng thật.
"""


def doc_drift() -> list[str]:
    """Kiểm tra phần **sinh từ JSON** của tài liệu có khớp không (dùng cho `--check` và CI).

    Chỉ so hai khối phụ thuộc JSON (bảng kịch bản §2 và danh sách lỗ hổng §5.3); phần số liệu ở §4 lấy từ
    báo cáo eval nên dao động giữa các lần chạy — so cả phần đó sẽ đỏ oan.
    """
    if not DOC_PATH.exists():
        return ["chưa có tài liệu bộ kịch bản"]
    current = DOC_PATH.read_text(encoding="utf-8")
    questions = json.loads(JSON_PATH.read_text(encoding="utf-8"))["questions"]
    problems: list[str] = []
    if _tables(questions).strip() not in current:
        problems.append("bảng kịch bản (§2) không khớp file JSON")
    if _known_gaps(questions).strip() not in current:
        problems.append("danh sách lỗ hổng (§5.3) không khớp file JSON")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Sinh tài liệu bộ kịch bản Sale từ file JSON.")
    parser.add_argument("--check", action="store_true", help="Chỉ kiểm tra tài liệu có khớp JSON không (dùng cho CI)")
    args = parser.parse_args()

    rendered = render()
    if args.check:
        problems = doc_drift()
        if problems:
            for problem in problems:
                print(f"LỆCH: {problem}")
            print("Chạy `python scripts/gen_sale_scenarios_doc.py` để sinh lại tài liệu.")
            return 1
        print("Tài liệu khớp JSON.")
        return 0

    DOC_PATH.write_text(rendered, encoding="utf-8")
    print(f"Đã ghi {DOC_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
