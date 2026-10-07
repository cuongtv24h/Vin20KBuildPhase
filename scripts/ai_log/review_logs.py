#!/usr/bin/env python3
"""
Human-in-the-loop review tool for AI logs.
Allows inspecting, editing, approving, or discarding prompts before
submitting them to the grading server.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

LOG_DIR = Path(os.environ.get("AI_LOG_DIR", ".ai-log"))
PENDING_FILE = LOG_DIR / "pending_review.jsonl"
SESSION_FILE = LOG_DIR / "session.jsonl"


def load_pending_entries() -> list[dict]:
    if not PENDING_FILE.exists():
        return []
    entries = []
    with open(PENDING_FILE, encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                entries.append(json.loads(stripped))
            except json.JSONDecodeError:
                pass
    return entries


def save_pending_entries(entries: list[dict]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def append_to_session(approved_entries: list[dict]) -> None:
    if not approved_entries:
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(SESSION_FILE, "a", encoding="utf-8") as f:
        for entry in approved_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def trigger_submit() -> None:
    submit_script = Path(__file__).parent / "submit_log.py"
    py_exec = sys.executable
    print("\n[ai-log] Dang gui cac log da duyet len may chu...")
    res = subprocess.run([py_exec, str(submit_script)])
    if res.returncode != 0:
        print("[ai-log] Loi khi goi submit_log.py", file=sys.stderr)


def list_pending(entries: list[dict]) -> None:
    print(f"\n[ai-log] Danh sach prompt dang cho duyet (Tong: {len(entries)}):")
    print("-" * 70)
    for idx, e in enumerate(entries, 1):
        ts = e.get("ts", "")[:19].replace("T", " ")
        prompt = e.get("prompt", "").replace("\n", " ")
        if len(prompt) > 80:
            prompt = prompt[:77] + "..."
        print(f"[{idx:02d}] {ts} | {prompt}")
    print("-" * 70)


def review_interactive(entries: list[dict]) -> tuple[list[dict], list[dict]]:
    approved: list[dict] = []
    remaining: list[dict] = []

    print("\n[ai-log] Che do duyet tung buoc (Interactive Review):")
    print("Lenh ho tro: [y] Duyet | [e] Chinh sua | [d] Xoa bo | [s] Bo qua | [q] Dung lai\n")

    for idx, e in enumerate(entries, 1):
        ts = e.get("ts", "")[:19].replace("T", " ")
        prompt = e.get("prompt", "")
        print(f"--- Prompt {idx}/{len(entries)} [{ts}] ---")
        print(prompt)
        print("-" * 40)

        while True:
            try:
                choice = input("Lua chon [y/e/d/s/q]: ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                choice = "q"

            if choice == "y":
                approved.append(e)
                print("-> Da duyet.")
                break
            elif choice == "e":
                new_text = input("Nhap noi dung moi: ").strip()
                if new_text:
                    e["prompt"] = new_text
                    approved.append(e)
                    print("-> Da cap nhat va duyet.")
                else:
                    remaining.append(e)
                    print("-> Bo qua (khong thay doi).")
                break
            elif choice == "d":
                print("-> Da xoa bo (khong nop).")
                break
            elif choice == "s":
                remaining.append(e)
                print("-> Bo qua.")
                break
            elif choice == "q":
                remaining.extend(entries[idx - 1:])
                print("-> Tam dung duyet.")
                return approved, remaining
            else:
                print("Lenh khong hop le. Vui long chon y, e, d, s, hoac q.")

    return approved, remaining


def main() -> None:
    parser = argparse.ArgumentParser(description="Human review tool for AI logs")
    parser.add_argument("--all", "-a", action="store_true", help="Duyet tat ca prompt dang cho")
    parser.add_argument("--submit", "-s", action="store_true", help="Duyet tat ca va nop ngay len Phoenix")
    parser.add_argument("--list", "-l", action="store_true", help="Liet ke danh sach prompt cho duyet")
    parser.add_argument("--clear", "-c", action="store_true", help="Xoa toan bo prompt dang cho duyet")
    args = parser.parse_args()

    entries = load_pending_entries()
    if not entries:
        print("[ai-log] Khong co prompt nao dang cho duyet.")
        sys.exit(0)

    if args.clear:
        save_pending_entries([])
        print(f"[ai-log] Da xoa toan bo {len(entries)} prompt trong hang doi.")
        sys.exit(0)

    if args.list:
        list_pending(entries)
        sys.exit(0)

    if args.submit:
        append_to_session(entries)
        save_pending_entries([])
        print(f"[ai-log] Da duyet toan bo {len(entries)} prompt.")
        trigger_submit()
        sys.exit(0)

    if args.all:
        append_to_session(entries)
        save_pending_entries([])
        print(f"[ai-log] Da duyet toan bo {len(entries)} prompt va dua vao session.jsonl.")
        sys.exit(0)

    # Interactive menu
    list_pending(entries)
    print("\nChon thao tac:")
    print("  [1] Duyet tat ca va nop len Phoenix ngay")
    print("  [2] Duyet tat ca va luu vao session.jsonl (cho git push)")
    print("  [3] Duyet tung prompt mot (Phe duyet / Chinh sua / Xoa bo)")
    print("  [4] Xoa toan bo prompt dang cho")
    print("  [q] Thoat")

    try:
        opt = input("\nLua chon [1-4, q]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        opt = "q"

    if opt == "1":
        append_to_session(entries)
        save_pending_entries([])
        print(f"[ai-log] Da duyet {len(entries)} prompt.")
        trigger_submit()
    elif opt == "2":
        append_to_session(entries)
        save_pending_entries([])
        print(f"[ai-log] Da duyet {len(entries)} prompt va luu vao session.jsonl.")
    elif opt == "3":
        approved, remaining = review_interactive(entries)
        append_to_session(approved)
        save_pending_entries(remaining)
        print(f"\n[ai-log] Ket qua: Da duyet {len(approved)} prompt, Con lai {len(remaining)} prompt cho.")
        if approved:
            sub = input("Ban co muon nop ngay cac prompt da duyet len server khong? [y/N]: ").strip().lower()
            if sub == "y":
                trigger_submit()
    elif opt == "4":
        save_pending_entries([])
        print("[ai-log] Da huy toan bo prompt dang cho.")
    else:
        print("[ai-log] Thoat. Hang doi giu nguyen.")


if __name__ == "__main__":
    main()
