#!/usr/bin/env python3
"""Kiểm tra nhanh tầng nghe-nói (Whisper/Groq) — chạy trên VM hoặc máy dev, không cần mở trình duyệt.

Hai chế độ:

1. **Gọi thẳng nhà cung cấp** (mặc định) — trả lời "khoá Groq có chạy không, tiếng Việt ra sao, trễ bao lâu":

       .venv/bin/python scripts/check_stt_groq.py                      # gửi 1 giây im lặng (soi khoá/URL/model)
       .venv/bin/python scripts/check_stt_groq.py --file /tmp/cau-hoi.webm   # audio thật của Sale
       .venv/bin/python scripts/check_stt_groq.py --say "Khách hỏi căn ZEN A 1205"  # (cần máy có TTS/ghi âm sẵn)

2. **Gọi qua backend đã deploy** — trả lời "nginx + endpoint + quyền đã thông chưa":

       .venv/bin/python scripts/check_stt_groq.py --api-base https://demoday.work.gd --token "$TOKEN"

Khoá đọc theo đúng thứ tự sản phẩm: `STT_GROQ_API_KEY` → `.env` → (nếu `--provider openai`) `OPENAI_API_KEY`.
Script KHÔNG in khoá ra màn hình, chỉ in dạng che.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import wave
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.services.stt_providers import normalize_transcript, silent_wav  # noqa: E402

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "whisper-large-v3-turbo"


def read_env_file(path: Path) -> dict[str, str]:
    """Đọc `.env` theo kiểu `KEY=VALUE` (bỏ comment) — không cần thư viện ngoài."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def resolve_key(provider: str, explicit: str | None, env: dict[str, str]) -> tuple[str, str]:
    """Trả (khoá, nguồn). Nguồn để in ra cho người chạy biết khoá đang lấy từ đâu."""
    names = ("STT_GROQ_API_KEY",) if provider == "groq" else ("OPENAI_API_KEY",)
    if explicit:
        return explicit.strip(), "--key trên dòng lệnh"
    for name in names:
        value = os.environ.get(name) or env.get(name) or ""
        if value.strip() and not value.startswith("sk-your-"):
            return value.strip(), f"biến {name}"
    return "", f"không tìm thấy {names[0]} (shell/.env)"


def mask(key: str) -> str:
    if not key:
        return "(trống)"
    return f"{key[:4]}…{key[-4:]}" if len(key) > 12 else "…"


def call_provider(
    *, base_url: str, api_key: str, model: str, language: str, prompt: str, audio: bytes, filename: str, timeout: float
) -> dict[str, Any]:
    """Gọi `POST {base_url}/audio/transcriptions` — Groq và OpenAI dùng chung hình dạng API này."""
    url = f"{base_url.rstrip('/')}/audio/transcriptions"
    data: dict[str, Any] = {"model": model, "language": language}
    if prompt:
        data["prompt"] = prompt[:1_000]
    started = time.perf_counter()
    try:
        response = httpx.post(
            url,
            data=data,
            files={"file": (filename, audio, "application/octet-stream")},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        return {"ok": False, "detail": f"Lỗi mạng khi gọi {url}: {exc}", "latency_ms": (time.perf_counter() - started) * 1000}
    latency = (time.perf_counter() - started) * 1000
    if response.status_code >= 400:
        hint = {
            401: "Khoá sai hoặc bị thu hồi — dán lại khoá trong Groq Console → API Keys.",
            403: "Khoá đúng nhưng tài khoản chưa được bật model này (hoặc chưa xác minh).",
            404: "Sai model hoặc sai base_url — kiểm tra --model/--base-url.",
            413: "File audio quá lớn (trần gói free Groq là 25 MB).",
            429: "Chạm trần tốc độ/gói free (20 request/phút, 2.000 request/ngày) — chờ một chút hoặc nâng gói.",
        }.get(response.status_code, "")
        return {
            "ok": False,
            "status_code": response.status_code,
            "detail": response.text[:400],
            "hint": hint,
            "latency_ms": latency,
        }
    payload = response.json()
    return {
        "ok": True,
        "text": str(payload.get("text") or ""),
        "language": str(payload.get("language") or language),
        "latency_ms": latency,
        "status_code": response.status_code,
    }


def call_backend(*, api_base: str, token: str, audio: bytes, filename: str, content_type: str, timeout: float) -> dict[str, Any]:
    """Gọi `POST {api_base}/api/v1/stt/transcribe` — kiểm tra nginx (trần body), quyền và endpoint."""
    url = f"{api_base.rstrip('/')}/api/v1/stt/transcribe"
    started = time.perf_counter()
    try:
        response = httpx.post(
            url,
            files={"file": (filename, audio, content_type)},
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        return {"ok": False, "detail": f"Lỗi mạng khi gọi {url}: {exc}", "latency_ms": (time.perf_counter() - started) * 1000}
    latency = (time.perf_counter() - started) * 1000
    try:
        payload = response.json()
    except ValueError:
        payload = {"raw": response.text[:300]}
    hint = {
        401: "Token sai/hết hạn — lấy token mới từ POST /api/v1/auth/login.",
        403: "Tài khoản không phải nhân viên (endpoint này chặn khách).",
        413: "nginx đang chặn dung lượng — thêm `client_max_body_size 12m;` rồi reload nginx.",
        415: "Kiểu audio không nằm trong danh sách backend chấp nhận.",
        422: "File rỗng hoặc multipart sai cấu trúc (thiếu trường `file`).",
        429: "Hết hạn mức phút/ngày (STT_DAILY_MINUTES_BUDGET).",
        503: "Backend chưa có khoá nhà cung cấp nào — dán STT_GROQ_API_KEY vào .env rồi restart pm2.",
    }.get(response.status_code, "")
    return {
        "ok": response.status_code < 400,
        "status_code": response.status_code,
        "payload": payload,
        "hint": hint,
        "latency_ms": latency,
    }


def load_audio(args: argparse.Namespace) -> tuple[bytes, str, str]:
    """Trả (audio, tên file, kiểu nội dung). Không có `--file` thì sinh 1 giây im lặng để soi khoá/định dạng."""
    if args.file:
        path = Path(args.file)
        if not path.exists():
            raise SystemExit(f"Không thấy file audio: {path}")
        suffix = path.suffix.lower().lstrip(".") or "webm"
        content_type = {
            "webm": "audio/webm",
            "ogg": "audio/ogg",
            "wav": "audio/wav",
            "mp3": "audio/mpeg",
            "m4a": "audio/mp4",
            "mp4": "audio/mp4",
            "flac": "audio/flac",
        }.get(suffix, "application/octet-stream")
        audio = path.read_bytes()
        seconds = 0.0
        if suffix == "wav":
            try:
                # `wave.open` của Python 3.11 không nhận `pathlib.Path` — phải đưa chuỗi đường dẫn.
                with wave.open(str(path), "rb") as wav_file:
                    seconds = wav_file.getnframes() / float(wav_file.getframerate() or 16_000)
            except (wave.Error, OSError, EOFError):
                seconds = 0.0
        print(f"Audio: {path} ({len(audio):,} byte" + (f", {seconds:.1f} giây" if seconds else "") + f", {content_type})")
        return audio, path.name, content_type
    audio = silent_wav(args.probe_seconds, rate=16_000)
    print(f"Audio: {args.probe_seconds:.0f} giây IM LẶNG sinh tại chỗ ({len(audio):,} byte, audio/wav) — chỉ để soi khoá/URL/model.")
    return audio, "probe.wav", "audio/wav"


def main() -> int:
    parser = argparse.ArgumentParser(description="Kiểm tra tầng nghe-nói (Whisper qua Groq/OpenAI)")
    parser.add_argument("--file", help="Đường dẫn file audio thật (webm/wav/m4a/mp3/ogg/flac) để đo chất lượng tiếng Việt")
    parser.add_argument("--probe-seconds", type=float, default=1.0, help="Thời lượng file im lặng sinh tự động (mặc định 1 giây)")
    parser.add_argument("--provider", default="groq", choices=("groq", "openai"), help="Nhà cung cấp gọi thẳng (mặc định groq)")
    parser.add_argument("--key", help="Khoá API (mặc định đọc STT_GROQ_API_KEY / OPENAI_API_KEY từ shell hoặc .env)")
    parser.add_argument("--base-url", help="Ghi đè base_url (mặc định theo nhà cung cấp)")
    parser.add_argument("--model", help=f"Ghi đè model (mặc định {DEFAULT_MODEL} cho Groq, whisper-1 cho OpenAI)")
    parser.add_argument("--language", default="vi")
    parser.add_argument("--prompt", default="", help="Từ vựng mồi; mặc định dùng STT_PROMPT trong .env nếu có")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--api-base", help="Chế độ 2: gọi qua backend đã deploy (ví dụ https://demoday.work.gd)")
    parser.add_argument("--token", default="", help="Token nhân viên cho chế độ gọi qua backend")
    args = parser.parse_args()

    env = read_env_file(REPO_ROOT / ".env")
    audio, filename, content_type = load_audio(args)

    # ---- Chế độ 2: đi qua backend thật (nginx + quyền + endpoint) ----
    if args.api_base:
        if not args.token:
            print("\nThiếu --token. Lấy token bằng:")
            print("  curl -s -X POST $API/api/v1/auth/login -H 'Content-Type: application/json' \\")
            print("       -d '{\"user\":\"<tk>\",\"password\":\"<mk>\"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)[\"access_token\"])'")
            return 2
        result = call_backend(
            api_base=args.api_base, token=args.token, audio=audio, filename=filename, content_type=content_type, timeout=args.timeout
        )
        print(f"\nGọi {args.api_base}/api/v1/stt/transcribe → {result.get('status_code')} trong {result['latency_ms']:.0f} ms")
        if result["ok"]:
            payload = result["payload"]
            print(f"  provider : {payload.get('provider')} · model: {payload.get('model')}")
            print(f"  text     : {payload.get('text')!r}")
            print(f"  chuẩn hoá: {payload.get('normalized_text')!r}")
            print(f"  hạn mức  : {payload.get('quota')}")
            for warning in payload.get("warnings") or []:
                print(f"  cảnh báo : {warning}")
            print("\nKẾT LUẬN: luồng Sale nói → chữ đã THÔNG qua backend.")
            return 0
        print(f"  chi tiết : {result.get('payload') or result.get('detail')}")
        if result.get("hint"):
            print(f"  gợi ý    : {result['hint']}")
        print("\nKẾT LUẬN: chưa thông — sửa theo gợi ý rồi chạy lại.")
        return 1

    # ---- Chế độ 1: gọi thẳng nhà cung cấp ----
    api_key, source = resolve_key(args.provider, args.key, env)
    base_url = args.base_url or env.get("STT_GROQ_BASE_URL") or (GROQ_BASE_URL if args.provider == "groq" else OPENAI_BASE_URL)
    if args.provider == "openai" and not args.base_url:
        base_url = env.get("OPENAI_BASE_URL") or OPENAI_BASE_URL
    model = args.model or env.get("STT_MODEL") or (DEFAULT_MODEL if args.provider == "groq" else "whisper-1")
    prompt = args.prompt or env.get("STT_PROMPT") or (
        "The Zen Park, VLand Future Sapphire, ZEN-A-1205, KPBT, ân hạn, chiết khấu, vốn tự có"
    )

    print(f"Nhà cung cấp: {args.provider} · base_url {base_url} · model {model}")
    print(f"Khoá: {mask(api_key)} (nguồn: {source})")
    if not api_key:
        print("\nCHƯA CÓ KHOÁ. Cách lấy (free, không cần thẻ): https://console.groq.com → API Keys → Create API Key,")
        print("rồi ghi vào .env:  STT_GROQ_API_KEY=gsk_...   (hoặc truyền --key cho lần kiểm tra này).")
        return 2

    result = call_provider(
        base_url=base_url,
        api_key=api_key,
        model=model,
        language=args.language,
        prompt=prompt,
        audio=audio,
        filename=filename,
        timeout=args.timeout,
    )

    if not result["ok"]:
        print(f"\nTHẤT BẠI sau {result['latency_ms']:.0f} ms · HTTP {result.get('status_code', '-')}")
        print(f"  {result.get('detail')}")
        if result.get("hint"):
            print(f"  gợi ý: {result['hint']}")
        return 1

    text = result["text"]
    print(f"\nOK trong {result['latency_ms']:.0f} ms · ngôn ngữ nhận được: {result['language']}")
    print(f"  transcript : {text!r}")
    if text.strip():
        print(f"  chuẩn hoá  : {normalize_transcript(text)!r}")
        print("\nKẾT LUẬN: khoá + model + định dạng audio đều chạy. Dán khoá vào .env (hoặc PUT /api/v1/stt/providers/groq)")
        print("rồi bật micro trong /sale/workspace để thử trọn luồng.")
    else:
        print("\nTranscript rỗng là ĐÚNG với file im lặng — nghĩa là khoá/URL/model hợp lệ.")
        print("Muốn đo chất lượng tiếng Việt, chạy lại với audio thật:")
        print("  .venv/bin/python scripts/check_stt_groq.py --file /tmp/cau-hoi-cua-sale.webm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
