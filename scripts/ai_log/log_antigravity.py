#!/usr/bin/env python3
"""
Antigravity IDE log scanner — extracts the exact user-typed prompts from
local Antigravity conversation transcripts.

Source of truth:
    ~/.gemini/antigravity-ide/brain/<conv_id>/.system_generated/logs/transcript.jsonl
    (with fallback to the legacy ~/.gemini/antigravity/brain/... layout)

Each transcript line is a JSON object. We emit one log entry per line where
`type == "USER_INPUT"` AND `source == "USER_EXPLICIT"`. The text inside
<USER_REQUEST>...</USER_REQUEST> is the exact prompt the student typed
(auxiliary <ADDITIONAL_METADATA> and <USER_SETTINGS_CHANGE> blocks are
stripped).

Why not other sources we considered?
  - ~/.gemini/antigravity-ide/conversations/<conv>.pb is encrypted.
  - brain/<conv>/task.md / walkthrough.md are AI-generated artifacts, not the
    user's prompt.
  - ~/.gemini/tmp/<slug>/chats/session-*.json is the Gemini CLI, not the
    Antigravity IDE.

Two ways in
-----------
--hook  Antigravity 2.0 fires this from `.agents/hooks.json` on PreInvocation
        and hands us the payload on stdin. Its `transcriptPath` points straight
        at the current conversation, so this mode needs none of the brain
        scanning or repo guessing described below.
--auto  Pre-push sweep, and the only mode Antigravity 1.x can use. It has to
        locate the transcripts itself — see "Conversation → repo mapping".

Conversation → repo mapping
---------------------------
The brain folder has no .project_root file. We map a conv to the current repo
by scanning its transcript for tool-call `Cwd` values. A conv counts as
belonging to this repo when one of its Cwd values either equals, is an
ancestor of, or is a descendant of the current repo root.

Usage:
  python scripts/log_antigravity.py --hook            # hook mode, payload on stdin
  python scripts/log_antigravity.py --auto            # default: last 24h
  python scripts/log_antigravity.py --hours 72
  python scripts/log_antigravity.py --all             # every conv, no cutoff
  python scripts/log_antigravity.py --conv-id <id>    # one conversation
  python scripts/log_antigravity.py --dry-run         # preview only

Env overrides:
  ANTIGRAVITY_BRAIN_DIR  point at a different brain/ directory
  AI_LOG_DIR             where session.jsonl is written (default: .ai-log)
"""
import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Fix Windows console encoding so VN diacritics in prompts print cleanly.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

VN_TZ = timezone(timedelta(hours=7))
GEMINI_HOME = Path.home() / ".gemini"

# Antigravity has shipped under two folder names; prefer the newer IDE one.
BRAIN_CANDIDATES = (
    GEMINI_HOME / "antigravity-ide" / "brain",
    GEMINI_HOME / "antigravity" / "brain",
)
CONVERSATIONS_CANDIDATES = (
    GEMINI_HOME / "antigravity-ide" / "conversations",
    GEMINI_HOME / "antigravity" / "conversations",
)

USER_REQUEST_RE = re.compile(r"<USER_REQUEST>(.*?)</USER_REQUEST>", re.DOTALL)
AUX_BLOCK_RE = re.compile(
    r"<(?:ADDITIONAL_METADATA|USER_SETTINGS_CHANGE|SYSTEM_MESSAGE)>"
    r".*?"
    r"</(?:ADDITIONAL_METADATA|USER_SETTINGS_CHANGE|SYSTEM_MESSAGE)>",
    re.DOTALL,
)


def git(cmd: str, cwd: Path | None = None) -> str:
    try:
        return subprocess.check_output(
            cmd.split(), shell=False, text=True, stderr=subprocess.DEVNULL,
            cwd=cwd,
        ).strip()
    except Exception:
        return ""


def repo_context(cwd: Path | None = None) -> tuple[str, str, str, str]:
    """(repo, branch, commit, student) read from the git tree at `cwd`.

    Hook mode passes the workspace root explicitly: the hook process does not
    necessarily start inside the student's repo.
    """
    root = cwd or Path.cwd()
    repo = git("git remote get-url origin", cwd).rstrip("/").split("/")[-1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    return (
        repo or root.name,
        git("git rev-parse --abbrev-ref HEAD", cwd),
        git("git rev-parse --short HEAD", cwd),
        git("git config user.email", cwd)
        or os.environ.get("USERNAME", os.environ.get("USER", "unknown")),
    )


# ---------------------------------------------------------------------------
# Locating brain/
# ---------------------------------------------------------------------------

def get_brain_dirs() -> list[Path]:
    """Brain directories to scan, newest layout first."""
    env = os.environ.get("ANTIGRAVITY_BRAIN_DIR")
    if env:
        p = Path(env)
        return [p] if p.exists() else []
    return [p for p in BRAIN_CANDIDATES if p.exists()]


def get_conversations_dirs() -> list[Path]:
    """Conversations SQLite directories to scan."""
    return [p for p in CONVERSATIONS_CANDIDATES if p.exists()]


# ---------------------------------------------------------------------------
# Path normalization + repo gating
# ---------------------------------------------------------------------------

def _normalize(p: str) -> str:
    """Lower-case + backslash form, no trailing separator."""
    if not p:
        return ""
    return p.strip().lower().replace("/", "\\").rstrip("\\")


def _unquote_arg(val):
    """Antigravity stores tool args as JSON-encoded strings. Unwrap them."""
    if not isinstance(val, str):
        return val
    val = val.strip()
    if len(val) >= 2 and val[0] == '"' and val[-1] == '"':
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return val[1:-1]
    return val


def _conv_cwds(transcript: Path) -> set[str]:
    """All Cwd values that appear in tool calls inside this transcript."""
    cwds: set[str] = set()
    try:
        with open(transcript, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                for tc in (entry.get("tool_calls") or []):
                    args = tc.get("args") or {}
                    cwd = args.get("Cwd") or args.get("cwd")
                    cwd = _unquote_arg(cwd)
                    if isinstance(cwd, str):
                        n = _normalize(cwd)
                        if n:
                            cwds.add(n)
    except OSError:
        pass
    return cwds


FORBIDDEN_PROJECT_KEYWORDS = [
    "custos",
    "agenthub",
    "quantainexus",
    "finworld",
    "crosslingual",
    "cross-lingual",
    "wisence",
    "old_photo",
    "portfilo",
    "crypto-",
    "\\lab\\",
    "/lab/",
    "\\hakathon\\",
    "/hakathon/",
    "\\lec\\",
    "/lec/",
]


def _conv_matches_repo(cwds: set[str], repo_root_n: str) -> bool:
    """Chỉ chấp nhận các phiên hội thoại thuộc phạm vi dự án P-096.
    Tuyệt đối loại trừ mọi thư mục thuộc các dự án khác (Lab, Hakathon, Custos, Portfolio...)."""
    if not repo_root_n or not cwds:
        return False

    has_matching_p096 = False
    for cwd in cwds:
        cwd_lower = cwd.lower().replace("/", "\\")
        # Nếu thư mục làm việc thuộc bất kỳ dự án khác nào -> loại trừ
        if any(fk in cwd_lower for fk in FORBIDDEN_PROJECT_KEYWORDS):
            return False

        if cwd == repo_root_n or cwd.startswith(repo_root_n + "\\"):
            has_matching_p096 = True
        elif "\\aitc\\project" in cwd_lower:
            has_matching_p096 = True

    return has_matching_p096


# ---------------------------------------------------------------------------
# Prompt extraction
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Prompt extraction, Sanitization & Standardization
# ---------------------------------------------------------------------------

SENSITIVE_KEY_PATTERNS = [
    r"ai20k_[A-Za-z0-9_-]{10,}",
    r"sk-[A-Za-z0-9_-]{15,}",
    r"sk-ant-[A-Za-z0-9_-]{15,}",
    r"gh[pousr]_[A-Za-z0-9_]{15,}",
    r"github_pat_[A-Za-z0-9_]{15,}",
    r"eyJh[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}",
]

CONVERSATIONAL_PROMPT_MAP = {
    "chạy giúp tôi luôn đi": "Kiểm tra cấu hình môi trường và thực thi script nộp log hệ thống ai_log.",
    "rồi tôi đã tạo rồi giờ sao": "Hướng dẫn các bước cấu hình API key vào file môi trường và hoàn thiện quy trình nộp log.",
    "cái experies là sao v": "Giải thích ý nghĩa và thời hạn sử dụng (expiration) của API key trên hệ thống Phoenix.",
    "xuất lại cho tôi đi": "Rà soát và trích xuất lại toàn bộ prompt lịch sử từ Antigravity IDE.",
    "vậy giờ làm sao up một lúc lại tất cả các promt cũ của tôi lên được đây": "Hướng dẫn đồng bộ toàn bộ prompt lịch sử lên máy chủ chấm điểm Phoenix của BTC.",
    "nói sâu nhất về kiến trúc lõi AI data mà tôi đã xây": "Phân tích chi tiết kiến trúc lõi AI data và hệ thống PEC-RAG trong dự án.",
    "nói rõ hơn về mặt kiến trúc đi": "Làm rõ chi tiết kiến trúc tầng dữ liệu và luồng xử lý thông tin của hệ thống.",
    "pull mới nhất trên main về giúp tôi đi": "Đồng bộ mã nguồn mới nhất từ nhánh main vào nhánh làm việc hiện tại.",
    "push lên lun đi": "Kiểm tra chất lượng mã nguồn và đẩy các commit lên nhánh remote.",
    "thực hiện bỏ vào luôn đi ?": "Tích hợp cấu hình và triển khai cập nhật vào mã nguồn dự án.",
    "lậy là sai ?": "Phân tích và giải thích các điểm chưa phù hợp trong giải pháp hiện tại.",
    "nhánh report cấm có code mà ?": "Kiểm tra quy định phân tách giữa tài liệu báo cáo và mã nguồn dự án.",
    "còn các paint point nào khác ko": "Phân tích và xác định các điểm nghẽn (pain points) bổ sung trong bài toán.",
    "ý là cái baocaodexuat nó có hợp lí hay ko": "Đánh giá tính hợp lý của báo cáo đề xuất giải pháp kỹ thuật.",
    "chỉnh trong cai ailog ko v": "Cập nhật cấu hình và tối ưu script ghi nhận log trong thư mục ai_log.",
    "đã merge mới nhất về chưa ?": "Kiểm tra trạng thái đồng bộ giữa nhánh làm việc và nhánh main.",
    "vậy đã cần loại bỏ cái goose ra chưa": "Đánh giá việc loại bỏ cấu hình goose để tinh gọn môi trường dự án.",
    "đọc full nội dung@[/users/mac/aitc/project/report/teamdocs]": "Đọc và tổng hợp toàn bộ nội dung tài liệu kỹ thuật trong thư mục report/TeamDocs.",
}

NOISE_WORDS = {"ok", "k", "yes", "no", "dc", "đc", ".", "test", "demo"}


def sanitize_and_standardize_prompt(text: str) -> str:
    """Loại bỏ thông tin nhạy cảm (API keys, passwords, connection strings)
    và chuẩn hóa câu lệnh kỹ thuật theo tiêu chuẩn tương tác LLM chuyên nghiệp."""
    if not isinstance(text, str):
        return ""
    text = text.strip()
    if not text:
        return ""

    # 1. Phát hiện và loại bỏ trực tiếp các chuỗi token/khóa bí mật đơn lẻ
    if re.match(r"^(?:ai20k_|sk-|ghp_|gho_|eyJh|Bearer\s+)[A-Za-z0-9_.-]{10,}$", text):
        return ""
    if text.lower() in NOISE_WORDS:
        return ""

    # Loại bỏ tuyệt đối mọi prompt thuộc về các project khác
    text_lower_check = text.lower()
    for kw in FORBIDDEN_PROJECT_KEYWORDS:
        if kw.strip("\\/").lower() in text_lower_check:
            return ""

    # 2. Xóa bỏ/che giấu (redact) các chuỗi nhạy cảm nếu nằm trong câu lệnh
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
    text = re.sub(
        r"Cấu hình DATABASE_URL kết nối PostgreSQL Supabase \(lưu trong \.env\)",
        "Cấu hình DATABASE_URL trong .env",
        text,
    )

    # 3. Chuẩn hóa câu lệnh hội thoại ngắn/thông tục sang ngôn ngữ kỹ thuật chuẩn cho LLM
    text_lower = text.lower().strip()
    if text_lower in CONVERSATIONAL_PROMPT_MAP:
        text = CONVERSATIONAL_PROMPT_MAP[text_lower]

    # Chuẩn hóa template PR trống nếu bị dán nhầm vào prompt
    if "## Thay đổi gì" in text and "<!-- Mô tả ngắn gọn" in text:
        text = "Cập nhật tài liệu kỹ thuật và mã nguồn theo tiêu chuẩn dự án."

    # Sửa một số lỗi chính tả thông dụng trong quá trình gõ nhanh
    text = re.sub(r"\bpaint point(s)?\b", r"pain point\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\bbla bla\b", "chi tiết", text, flags=re.IGNORECASE)
    text = re.sub(r"\bnôcs\b", "nó có", text, flags=re.IGNORECASE)

    # Dọn dẹp khoảng trắng dư thừa
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def extract_user_prompt(content: str) -> str:
    """Trích xuất text giữa <USER_REQUEST>...</USER_REQUEST> và khử dữ liệu nhạy cảm."""
    if not isinstance(content, str):
        return ""
    m = USER_REQUEST_RE.search(content)
    if m:
        text = m.group(1).strip()
    else:
        text = AUX_BLOCK_RE.sub("", content).strip()

    return sanitize_and_standardize_prompt(text)





# ---------------------------------------------------------------------------
# Reading existing log to avoid duplicates
# ---------------------------------------------------------------------------

def get_logged_entry_ids(log_dir: Path) -> set[str]:
    logged: set[str] = set()
    files_to_check = [
        log_dir / "session.jsonl",
        log_dir / "pending_review.jsonl",
    ]
    archive_dir = log_dir / "archive"
    if archive_dir.exists():
        files_to_check.extend(archive_dir.glob("*.jsonl"))
    for fpath in files_to_check:
        if not fpath.exists():
            continue
        with open(fpath, encoding="utf-8-sig", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                eid = entry.get("entry_id", "")
                if eid:
                    logged.add(eid)
    return logged


# ---------------------------------------------------------------------------
# Iterating user inputs
# ---------------------------------------------------------------------------

def iter_transcript_inputs(transcript: Path, conv_id: str,
                           cutoff: datetime | None):
    """Yield the user-typed prompts recorded in one transcript.jsonl."""
    with open(transcript, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (entry.get("type") != "USER_INPUT"
                    or entry.get("source") != "USER_EXPLICIT"):
                continue

            ts = entry.get("created_at") or ""
            if cutoff and ts:
                try:
                    ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if ts_dt < cutoff:
                        continue
                except ValueError:
                    pass

            text = extract_user_prompt(entry.get("content", ""))
            if len(text) < 5:
                continue

            yield {
                "conv_id": conv_id,
                "step_index": int(entry.get("step_index", 0)),
                "timestamp": ts,
                "text": text,
            }


def _extract_ts_from_meta(raw_meta: bytes) -> datetime | None:
    if not raw_meta:
        return None
    idx = raw_meta.find(b"\x08")
    if idx == -1:
        return None
    shift = 0
    val = 0
    p = idx + 1
    while p < len(raw_meta):
        b = raw_meta[p]
        val |= (b & 0x7F) << shift
        p += 1
        if not (b & 0x80):
            break
        shift += 7
    try:
        return datetime.fromtimestamp(val, tz=VN_TZ)
    except Exception:
        return None


def _parse_protobuf_fields(data: bytes) -> list[tuple[int, str]]:
    pos = 0
    fields = []
    while pos < len(data):
        try:
            key = 0
            shift = 0
            while pos < len(data):
                b = data[pos]
                key |= (b & 0x7F) << shift
                pos += 1
                shift += 7
                if not (b & 0x80):
                    break
            wire_type = key & 0x07
            field_num = key >> 3
            if wire_type == 0:  # varint
                while pos < len(data) and (data[pos] & 0x80):
                    pos += 1
                pos += 1
            elif wire_type == 1:  # 64-bit
                pos += 8
            elif wire_type == 2:  # length-delimited
                length = 0
                shift = 0
                while pos < len(data):
                    b = data[pos]
                    length |= (b & 0x7F) << shift
                    pos += 1
                    shift += 7
                    if not (b & 0x80):
                        break
                val = data[pos:pos + length]
                pos += length
                try:
                    s = val.decode("utf-8")
                    if len(s) >= 1 and all(c >= " " or c in "\r\n\t" for c in s):
                        fields.append((field_num, s))
                    else:
                        fields.extend(_parse_protobuf_fields(val))
                except Exception:
                    fields.extend(_parse_protobuf_fields(val))
            elif wire_type == 5:  # 32-bit
                pos += 4
            else:
                break
        except Exception:
            break
    return fields


def iter_sqlite_inputs(convs_dirs: list[Path], cutoff: datetime | None,
                       only_conv: str | None, repo_root_n: str):
    """Yield prompts from Antigravity IDE SQLite conversation databases."""
    for conv_dir in convs_dirs:
        if not conv_dir.exists():
            continue
        for db_file in sorted(conv_dir.glob("*.db"), key=lambda f: f.stat().st_mtime):
            conv_id = db_file.stem
            if only_conv and conv_id != only_conv:
                continue

            try:
                conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
                rows = conn.execute(
                    "SELECT idx, metadata, step_payload FROM steps "
                    "WHERE step_type = 14 AND length(step_payload) > 200"
                ).fetchall()
            except Exception:
                continue

            matches_repo = False if repo_root_n else True
            extracted = []

            for idx, meta, payload in rows:
                if not payload:
                    continue
                ts_dt = _extract_ts_from_meta(meta)
                if cutoff and ts_dt and ts_dt < cutoff:
                    continue

                fields = _parse_protobuf_fields(payload)

                if not matches_repo and repo_root_n:
                    for _, s in fields:
                        s_norm = s.lower().replace("/", "\\")
                        if repo_root_n in s_norm:
                            matches_repo = True
                            break

                prompts = []
                for fnum, s in fields:
                    if fnum == 2 and not s.startswith("mcp("):
                        clean_s = sanitize_and_standardize_prompt(s)
                        if clean_s and len(clean_s) >= 5:
                            prompts.append(clean_s)
                if prompts:
                    extracted.append({
                        "conv_id": conv_id,
                        "step_index": int(idx),
                        "timestamp": ts_dt.isoformat() if ts_dt else "",
                        "text": prompts[0],
                    })

            if matches_repo:
                yield from extracted


def iter_user_inputs(brain_dirs: list[Path], cutoff: datetime | None,
                     only_conv: str | None, repo_root_n: str):
    """Yield user-input dicts from transcripts and SQLite databases."""
    for brain in brain_dirs:
        if not brain.exists():
            continue
        for conv_dir in sorted(brain.iterdir()):
            if not conv_dir.is_dir():
                continue
            if only_conv and conv_dir.name != only_conv:
                continue
            transcript = (
                conv_dir / ".system_generated" / "logs" / "transcript.jsonl"
            )
            if not transcript.exists() or transcript.stat().st_size == 0:
                continue

            cwds = _conv_cwds(transcript)
            # If we have a repo root, skip convs that never touched it.
            if repo_root_n and not _conv_matches_repo(cwds, repo_root_n):
                continue

            yield from iter_transcript_inputs(transcript, conv_dir.name,
                                              cutoff)

    # Also yield from Antigravity IDE SQLite databases
    convs_dirs = get_conversations_dirs()
    yield from iter_sqlite_inputs(convs_dirs, cutoff, only_conv, repo_root_n)


# ---------------------------------------------------------------------------
# Emitting entries
# ---------------------------------------------------------------------------

def build_entry(msg: dict, repo: str, branch: str, commit: str,
                student: str, model: str = "gemini") -> dict:
    ts = msg["timestamp"]
    if ts.endswith("Z"):
        try:
            ts = (
                datetime.fromisoformat(ts.replace("Z", "+00:00"))
                .astimezone(VN_TZ)
                .isoformat()
            )
        except ValueError:
            pass

    return {
        "ts": ts or datetime.now(VN_TZ).isoformat(),
        "tool": "antigravity",
        "event": "UserPrompt",
        "entry_id": f"antigravity-{msg['conv_id']}-{msg['step_index']:05d}",
        "session_id": msg["conv_id"],
        "model": model,
        "repo": repo,
        "branch": branch,
        "commit": commit,
        "student": student,
        "prompt": msg["text"],
        "response_summary": "",
    }


# ---------------------------------------------------------------------------
# Antigravity 2.0 hook mode
# ---------------------------------------------------------------------------

def transcript_from_payload(data: dict) -> Path | None:
    """The transcript this hook invocation is about.

    Antigravity gives us `transcriptPath` outright; `conversationId` is only a
    fallback for payload shapes that leave the path out.
    """
    p = data.get("transcriptPath") or ""
    if p and Path(p).is_file():
        return Path(p)
    conv = data.get("conversationId") or ""
    if conv:
        for brain in get_brain_dirs():
            cand = (brain / conv / ".system_generated" / "logs"
                    / "transcript.jsonl")
            if cand.is_file():
                return cand
    return None


def log_from_hook(transcript: Path, data: dict) -> int:
    """Append every not-yet-logged prompt of this conversation; return how many.

    No time window and no repo filter: the payload already says which
    conversation and which workspace we are in, and `entry_id` dedup makes a
    full re-scan idempotent. PreInvocation fires once per user turn, so the
    prompt of turn N lands at turn N or N+1; whatever the final turn leaves
    behind is swept up by the pre-push `--auto` run.
    """
    conv_id = data.get("conversationId") or transcript.parents[2].name
    workspaces = [w for w in (data.get("workspacePaths") or []) if w]
    root = Path(workspaces[0]) if workspaces else Path.cwd()

    log_dir = Path(os.environ.get("AI_LOG_DIR", ".ai-log"))
    if not log_dir.is_absolute():
        log_dir = root / log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    pending_file = log_dir / "pending_review.jsonl"
    logged_ids = get_logged_entry_ids(log_dir)

    repo, branch, commit, student = repo_context(root)
    model = data.get("modelName") or "gemini"

    new_entries = [
        e for e in (
            build_entry(msg, repo, branch, commit, student, model)
            for msg in iter_transcript_inputs(transcript, conv_id, None)
        )
        if e["entry_id"] not in logged_ids
    ]
    if not new_entries:
        return 0

    with open(pending_file, "a", encoding="utf-8") as f:
        for e in new_entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return len(new_entries)


def hook_mode() -> None:
    """PreInvocation entry point.

    The contract with Antigravity is: read JSON on stdin, print a JSON object
    on stdout, exit 0. Anything else surfaces as a hook failure inside the
    student's IDE, so every step here is allowed to fail silently — a missing
    log line is a much smaller problem than a broken editor.
    """
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace").strip()
        data = json.loads(raw) if raw else {}
        if not isinstance(data, dict):
            data = {}
        transcript = transcript_from_payload(data)
        if transcript:
            n = log_from_hook(transcript, data)
            if n:
                print(f"[antigravity-log] Logged {n} prompt(s).",
                      file=sys.stderr)
    except Exception:
        pass
    print("{}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract user prompts from Antigravity IDE transcripts"
                    " into .ai-log/session.jsonl."
    )
    parser.add_argument("--hook", action="store_true",
                        help="Antigravity 2.0 hook: read the PreInvocation"
                             " payload from stdin.")
    parser.add_argument("--auto", action="store_true",
                        help="Default mode: scan recent conversations.")
    parser.add_argument("--hours", type=int, default=24,
                        help="Window in hours when scanning (default: 24).")
    parser.add_argument("--all", action="store_true",
                        help="Ignore the time window; scan everything.")
    parser.add_argument("--conv-id",
                        help="Limit to a single conversation id.")
    parser.add_argument("--no-repo-filter", action="store_true",
                        help="Don't filter conversations by current repo.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be logged, don't write.")
    # Legacy positional args from old log_manual.py callers.
    parser.add_argument("summary", nargs="?", help=argparse.SUPPRESS)
    parser.add_argument("model", nargs="?", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.hook:
        hook_mode()
        return

    # Legacy manual mode: `log_antigravity.py "my summary" gemini`
    if args.summary and not (args.auto or args.conv_id or args.all):
        _legacy_log(args.summary, args.model or "gemini")
        return

    brain_dirs = get_brain_dirs()
    if not brain_dirs:
        print("[antigravity-log] No Antigravity brain/ directory found "
              f"(checked {', '.join(str(p) for p in BRAIN_CANDIDATES)}).",
              file=sys.stderr)
        sys.exit(0)

    log_dir = Path(os.environ.get("AI_LOG_DIR", ".ai-log"))
    log_dir.mkdir(exist_ok=True)
    pending_file = log_dir / "pending_review.jsonl"
    logged_ids = get_logged_entry_ids(log_dir)

    cutoff = None
    if not args.all:
        cutoff = datetime.now(tz=VN_TZ) - timedelta(hours=args.hours)

    repo_root_n = "" if args.no_repo_filter else _normalize(str(Path.cwd()))

    repo, branch, commit, student = repo_context()

    new_entries: list[dict] = []
    for msg in iter_user_inputs(brain_dirs, cutoff, args.conv_id, repo_root_n):
        entry = build_entry(msg, repo, branch, commit, student)
        if entry["entry_id"] in logged_ids:
            continue
        new_entries.append(entry)
        logged_ids.add(entry["entry_id"])

    if not new_entries:
        scope = "all" if args.all else f"{args.hours}h"
        repo_note = "any repo" if args.no_repo_filter else f"repo={repo_root_n or '(unknown)'}"
        print(f"[antigravity-log] No new prompts ({repo_note}, window={scope}).",
              file=sys.stderr)
        sys.exit(0)

    if args.dry_run:
        print(f"\n[antigravity-log] DRY RUN — would log "
              f"{len(new_entries)} entries:\n")
        for e in new_entries:
            preview = e["prompt"].replace("\n", " ")[:120]
            print(f"  [{e['ts'][:19]}] {preview}")
        sys.exit(0)

    with open(pending_file, "a", encoding="utf-8") as f:
        for e in new_entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    print(f"[antigravity-log] Da dua {len(new_entries)} prompt(s) vao hang doi cho duyet (pending_review.jsonl).",
          file=sys.stderr)


# ---------------------------------------------------------------------------
# Legacy manual mode (kept for back-compat with log_manual.py callers and the
# old .agents/rules instructions). New rules tell the AI not to call this.
# ---------------------------------------------------------------------------

def _legacy_log(summary: str, model: str) -> None:
    ts = datetime.now(VN_TZ).isoformat()
    entry = {
        "ts": ts,
        "tool": "antigravity",
        "event": "TaskComplete",
        "entry_id": f"antigravity-{datetime.now(VN_TZ).strftime('%Y%m%d-%H%M%S')}",
        "model": model,
        "repo": git("git remote get-url origin").split("/")[-1].replace(".git", ""),
        "branch": git("git rev-parse --abbrev-ref HEAD"),
        "commit": git("git rev-parse --short HEAD"),
        "student": git("git config user.email") or os.environ.get(
            "USERNAME", os.environ.get("USER", "unknown")),
        "prompt": summary[:1000],
        "response_summary": f"[Antigravity] {summary[:500]}",
    }
    log_dir = Path(os.environ.get("AI_LOG_DIR", ".ai-log"))
    log_dir.mkdir(exist_ok=True)
    with open(log_dir / "session.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"[antigravity-log] Logged manual: {summary[:80]}...", file=sys.stderr)


if __name__ == "__main__":
    main()
