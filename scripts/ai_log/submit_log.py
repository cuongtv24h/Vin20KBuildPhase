#!/usr/bin/env python3
"""
Submit .ai-log/session.jsonl to grading server.
Called by git pre-push hook or manually.

After a successful submit, the live log is rotated:
  - Moved into .ai-log/archive/YYYY-MM-DD.jsonl (appended, never overwritten)
  - The live session.jsonl is recreated empty by the next hook write

If the POST fails, the pending file is restored so nothing is lost.
"""
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file, encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    _k, _v = _k.strip(), _v.strip().strip("'\"")
                    if _k not in os.environ:
                        os.environ[_k] = _v

SERVER_URL = os.environ.get("AI_LOG_SERVER", "")
API_KEY = os.environ.get("AI_LOG_API_KEY", "")
LOG_DIR = Path(os.environ.get("AI_LOG_DIR", ".ai-log"))
LOG_FILE = LOG_DIR / "session.jsonl"
ARCHIVE_DIR = LOG_DIR / "archive"

# Match server-side MAX_BATCH_ENTRIES so we never get a 422.
# If the local file has more than this, we submit the oldest BATCH_LIMIT
# and leave the rest for the next push.
BATCH_LIMIT = 500


def _archive(pending: Path) -> None:
    """Append pending file to today's archive. Never overwrites existing data."""
    if not pending.exists() or pending.stat().st_size == 0:
        return
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    archive_file = ARCHIVE_DIR / f"{today}.jsonl"
    with open(pending, "rb") as src, open(archive_file, "ab") as dst:
        shutil.copyfileobj(src, dst)


def _restore_pending(pending: Path) -> None:
    """Failure path: put pending back at LOG_FILE so the next push retries.
    If hook wrote new entries to LOG_FILE in the meantime, prepend pending."""
    if not pending.exists():
        return
    if LOG_FILE.exists():
        # Concat: pending (older) + LOG_FILE (newer) → LOG_FILE
        tmp = LOG_FILE.with_suffix(".merge.jsonl")
        with open(tmp, "wb") as out:
            with open(pending, "rb") as a:
                shutil.copyfileobj(a, out)
            with open(LOG_FILE, "rb") as b:
                shutil.copyfileobj(b, out)
        os.replace(tmp, LOG_FILE)
        pending.unlink()
    else:
        pending.rename(LOG_FILE)


def _sanitize_prompt(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = text.strip()
    if re.match(r"^(?:ai20k_|sk-|ghp_|gho_|eyJh|Bearer\s+)[A-Za-z0-9_.-]{10,}$", text):
        return ""
    if text.lower() in {"ok", "k", "yes", "no", "dc", "đc", ".", "test"}:
        return ""
    forbidden = ["custos", "agenthub", "quantainexus", "finworld", "crosslingual", "wisence", "old_photo", "portfilo"]
    if any(k in text.lower() for k in forbidden):
        return ""
    text = re.sub(r"ai20k_[A-Za-z0-9_-]{10,}", "[AI_LOG_API_KEY]", text)
    text = re.sub(r"sk-[A-Za-z0-9_-]{15,}", "[OPENAI_API_KEY]", text)
    text = re.sub(r"sk-ant-[A-Za-z0-9_-]{15,}", "[ANTHROPIC_API_KEY]", text)
    text = re.sub(r"gh[pousr]_[A-Za-z0-9_]{15,}", "[GITHUB_TOKEN]", text)
    text = re.sub(r"github_pat_[A-Za-z0-9_]{15,}", "[GITHUB_TOKEN]", text)
    text = re.sub(r"eyJh[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}", "[JWT_TOKEN]", text)
    text = re.sub(
        r"(?:postgresql|postgres|mysql|mongodb)(?:\+[a-zA-Z0-9_]+)?://[^\s<>\"']+",
        "postgresql://[USER]:[PASSWORD]@[HOST]:[PORT]/[DB]",
        text,
    )
    text = text.replace("Vin20K?24h365", "").replace("Vin20K24h365", "")
    return text


def main():
    if not SERVER_URL:
        print("[ai-log] AI_LOG_SERVER not set — skipping submission.", file=sys.stderr)
        sys.exit(0)

    if not LOG_FILE.exists() or LOG_FILE.stat().st_size == 0:
        print("[ai-log] No logs to submit.", file=sys.stderr)
        sys.exit(0)

    # Atomic rename closes the race window: hook writes that arrive after this
    # land in a fresh LOG_FILE, not in the batch we're about to POST.
    pending = LOG_FILE.with_name(f"session.pending.{int(time.time())}.jsonl")
    try:
        LOG_FILE.rename(pending)
    except FileNotFoundError:
        print("[ai-log] No logs to submit.", file=sys.stderr)
        sys.exit(0)

    entries = []
    leftover_lines = []
    with open(pending, encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            if len(entries) >= BATCH_LIMIT:
                leftover_lines.append(line)
                continue
            try:
                item = json.loads(stripped)
                clean_p = _sanitize_prompt(item.get("prompt", ""))
                if not clean_p or len(clean_p) < 5:
                    continue
                item["prompt"] = clean_p
                entries.append(item)
            except json.JSONDecodeError:
                pass  # drop unparseable line

    if not entries:
        # Nothing to send; archive whatever was there (probably junk) and bail.
        _archive(pending)
        pending.unlink()
        print("[ai-log] No valid entries to submit.", file=sys.stderr)
        sys.exit(0)

    payload = json.dumps({"entries": entries}, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    req = urllib.request.Request(
        SERVER_URL,
        data=payload,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            print(f"[ai-log] Submitted {len(entries)} entries → {resp.status}", file=sys.stderr)
    except (urllib.error.URLError, TimeoutError, Exception) as e:
        # Failure: restore the whole pending (including leftover) for next push.
        _restore_pending(pending)
        print(f"[ai-log] Submit failed: {e} — logs kept locally.", file=sys.stderr)
        sys.exit(0)  # Don't block push on server error

    # Success: archive the submitted batch, then handle any leftover.
    _archive(pending)
    pending.unlink()

    if leftover_lines:
        # More than BATCH_LIMIT entries existed; put the rest back so the
        # next push picks them up.
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.writelines(leftover_lines)
        print(
            f"[ai-log] {len(leftover_lines)} entries deferred to next push.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
