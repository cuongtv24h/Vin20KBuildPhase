#!/usr/bin/env python3
"""Đối chiếu môi trường đang chạy với `requirements.lock.txt` — dùng trước/sau khi deploy.

Vì sao có: `requirements.txt` chỉ là DẢI phiên bản (có chặn major) nên hai máy cài cùng file vẫn ra
khác nhau. `requirements.lock.txt` là bản chốt đã chạy đủ test + ruff sạch. Script này trả lời đúng
một câu hỏi: "máy này có đang chạy đúng bản chốt không, lệch chỗ nào?" — in ra vài dòng để dán vào
chat/issue thay vì phải dán cả 128 dòng `pip freeze`.

Cách dùng:
    .venv/bin/python scripts/check_env_drift.py             # báo cáo, luôn exit 0
    .venv/bin/python scripts/check_env_drift.py --strict    # exit 1 nếu có lệch (dùng trong CI/deploy)
    .venv/bin/python scripts/check_env_drift.py --json      # máy đọc

Không cần lib ngoài. Chỉ đọc metadata của môi trường Python đang chạy script.
"""

from __future__ import annotations

import argparse
import json
import sys
from importlib import metadata
from pathlib import Path

LOCK_FILE = Path(__file__).resolve().parent.parent / "requirements.lock.txt"

#: Những gói mà sai phiên bản từng làm đổi hành vi/API — lệch ở đây là phải xử lý trước khi tin kết quả test.
CRITICAL = (
    "fastapi",
    "pydantic",
    "sqlalchemy",
    "langchain",
    "langchain-openai",
    "langgraph",
    "langgraph-checkpoint-postgres",
    "llama-index-core",
    "uvicorn",
)


def canonical(name: str) -> str:
    """Chuẩn hoá tên gói theo PEP 503 (`zope.interface` == `zope-interface`)."""
    return name.lower().replace("_", "-").replace(".", "-")


def read_lock(path: Path) -> dict[str, str]:
    """Đọc các dòng `name==version` từ file lock, bỏ comment/dòng rỗng."""
    if not path.exists():
        raise SystemExit(f"Không tìm thấy {path} — chưa sinh lock? (pip freeze > requirements.lock.txt)")
    pins: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or "==" not in line:
            continue
        name, version = line.split("==", 1)
        pins[canonical(name.strip())] = version.strip()
    return pins


def installed_versions() -> dict[str, str]:
    """Phiên bản thực tế của mọi gói trong môi trường hiện tại."""
    found: dict[str, str] = {}
    for dist in metadata.distributions():
        name = dist.metadata["Name"]
        if name:
            found[canonical(name)] = dist.version
    return found


def compare(pins: dict[str, str], installed: dict[str, str]) -> dict[str, list[dict[str, str]]]:
    mismatched, missing, extra = [], [], []
    for name, want in sorted(pins.items()):
        got = installed.get(name)
        if got is None:
            missing.append({"package": name, "lock": want})
        elif got != want:
            mismatched.append(
                {"package": name, "lock": want, "installed": got, "critical": name in CRITICAL}
            )
    for name, got in sorted(installed.items()):
        if name not in pins:
            extra.append({"package": name, "installed": got})
    mismatched.sort(key=lambda row: (not row["critical"], row["package"]))
    return {"mismatched": mismatched, "missing": missing, "extra": extra}


def report(pins: dict[str, str], diff: dict[str, list[dict[str, str]]]) -> int:
    """In báo cáo tiếng Việt; trả số lỗi cần chặn deploy (lệch/thiếu)."""
    mismatched, missing, extra = diff["mismatched"], diff["missing"], diff["extra"]
    critical = [row for row in mismatched if row["critical"]]

    print(f"Lock: {LOCK_FILE.name} ({len(pins)} gói) · Python {sys.version.split()[0]}")
    if not mismatched and not missing:
        print(f"KHỚP toàn bộ {len(pins)} gói chốt." + (f" (thừa {len(extra)} gói phụ — vô hại)" if extra else ""))
        return 0

    if critical:
        print(f"\n[NGHIÊM TRỌNG] {len(critical)} gói từng đổi API đang lệch — chưa nên tin kết quả test/eval:")
        for row in critical:
            print(f"  - {row['package']}: lock {row['lock']} · đang chạy {row['installed']}")

    plain = [row for row in mismatched if not row["critical"]]
    if plain:
        print(f"\nLệch phiên bản ({len(plain)} gói):")
        for row in plain:
            print(f"  - {row['package']}: lock {row['lock']} · đang chạy {row['installed']}")

    if missing:
        print(f"\nTHIẾU so với lock ({len(missing)} gói): " + ", ".join(r["package"] for r in missing[:20]))

    if extra:
        names = ", ".join(r["package"] for r in extra[:10])
        print(f"\nGói ngoài lock ({len(extra)}): {names}{' …' if len(extra) > 10 else ''}")

    print("\nXử lý: `.venv/bin/pip install -r requirements.lock.txt` (đúng bản chốt),")
    print("hoặc nếu máy này MỚI hơn và đã test lại: `pip freeze > requirements.lock.txt` rồi commit.")
    return len(mismatched) + len(missing)


def main() -> int:
    parser = argparse.ArgumentParser(description="Đối chiếu môi trường với requirements.lock.txt")
    parser.add_argument("--strict", action="store_true", help="exit 1 nếu có gói lệch/thiếu (dùng trong CI/deploy)")
    parser.add_argument("--json", action="store_true", help="in JSON thay vì báo cáo tiếng Việt")
    args = parser.parse_args()

    pins = read_lock(LOCK_FILE)
    diff = compare(pins, installed_versions())
    drift = len(diff["mismatched"]) + len(diff["missing"])

    if args.json:
        print(json.dumps({"lock": str(LOCK_FILE), "lock_packages": len(pins), "drift": drift, **diff}, ensure_ascii=False, indent=2))
    else:
        report(pins, diff)

    if args.strict and drift:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
