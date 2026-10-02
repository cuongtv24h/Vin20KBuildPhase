"""Kiểm tra kết nối nhà cung cấp LLM — đúng cách để không bị chặn oan, và lỗi thì phải hiểu được.

Vì sao tách khỏi endpoint: bản đầu gọi `GET {base_url}/models` bằng `httpx` mặc định, nên:

1. **Bị Cloudflare chặn**: httpx mặc định gửi `User-Agent: python-httpx/...`; nhà cung cấp nào đứng sau
   Cloudflare có bật chống bot sẽ trả `403` kèm trang `"Just a moment..."` (HTML) — dù API vẫn dùng bình
   thường từ ứng dụng khác (trình duyệt hoặc client khác). Nay gửi header tường minh, dùng chung với client
   thật (`src/services/llm_http.py`).
2. **Chỉ thử `/models`**: nhiều gateway (proxy OpenAI-compatible) không mở `/models` nhưng vẫn chạy tốt
   `/chat/completions` — đúng endpoint mà ứng dụng thật dùng. Nay thử cả hai, và báo đã thử bằng đường nào.
3. **Đổ HTML thô vào màn hình**: Admin nhận một đống `<!DOCTYPE html>...` vô nghĩa. Nay nhận dạng HTML/Cloudflare
   và nói rõ nguyên nhân + việc cần kiểm tra.

Từ đợt 10 bổ sung phần "chặn thì phải biết chặn kiểu gì": khi gặp Cloudflare, probe **thử thêm một lần bằng
chế độ header còn lại** (ứng dụng ↔ trình duyệt) và tra IP công khai của máy chủ, để câu trả lời trả lời được
đúng câu hỏi: *đổi header là qua, hay nhà cung cấp chặn IP máy chủ này?* — hai nguyên nhân này cách sửa khác hẳn nhau.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass

import httpx

from src.services.llm_http import (
    APP_USER_AGENT,
    build_headers,
    headers_mode,
    other_mode,
    public_ip,
)

#: Giữ tên cũ cho tương thích (test và tài liệu đang dùng).
USER_AGENT = APP_USER_AGENT

#: Base URL mặc định khi Admin để trống (giống nhà cung cấp OpenAI).
DEFAULT_BASE_URL = "https://api.openai.com/v1"

#: Dấu hiệu trang challenge của Cloudflare (bot-protection) trong phần đầu nội dung trả về.
CLOUDFLARE_MARKERS = ("just a moment", "cf-chl", "attention required", "cloudflare", "checking your browser")


@dataclass(frozen=True)
class ProbeResult:
    """Kết quả một lần kiểm tra kết nối (không phụ thuộc FastAPI/DB → test được trực tiếp)."""

    ok: bool
    #: OK | ERROR | UNREACHABLE | NOT_CONFIGURED
    status: str
    detail: str
    latency_ms: float
    #: Đường đã dùng để kết luận: "GET /models" hoặc "POST /chat/completions".
    method: str | None = None
    url: str | None = None
    http_status: int | None = None


def _looks_like_html(text: str, content_type: str) -> bool:
    head = (text or "")[:600].lower()
    return "text/html" in (content_type or "").lower() or "<!doctype html" in head or "<html" in head


def _is_cloudflare(text: str) -> bool:
    head = (text or "")[:2000].lower()
    return any(marker in head for marker in CLOUDFLARE_MARKERS)


def _looks_like_json(text: str, content_type: str) -> bool:
    """True nếu thân phản hồi thật sự là JSON (một số server trả HTML cho MỌI đường dẫn, kèm 200)."""
    body = (text or "").strip()
    if not body:
        return False
    if "json" in (content_type or "").lower():
        return True
    try:
        parsed = json.loads(body)
    except (ValueError, TypeError):
        return False
    return isinstance(parsed, dict)


def _short(text: str, limit: int = 200) -> str:
    clean = " ".join((text or "").split())
    return clean if len(clean) <= limit else clean[: limit - 1] + "…"


def _diagnose(status_code: int, text: str, content_type: str, url: str, mitigated: str = "") -> str:
    """Biến phản hồi lỗi thành câu tiếng Việt nói rõ nên kiểm tra gì — không bao giờ đổ HTML thô."""
    if _looks_like_html(text, content_type):
        if _is_cloudflare(text):
            # Câu này còn được thay bằng bản đầy đủ hơn ở `_cloudflare_detail` khi có kết quả chẩn đoán.
            kind = "challenge (bắt trình duyệt giải JavaScript)" if "just a moment" in text.lower() else "chặn"
            return (
                f"Bị Cloudflare {kind} ở {url} (HTTP {status_code}). Đây là chặn ở phía hạ tầng nhà cung cấp, "
                "không phải lỗi Base URL hay API key."
            )
        return (
            f"{url} trả về trang HTML thay vì JSON (HTTP {status_code}). Base URL nhiều khả năng đang trỏ vào "
            "trang web thay vì API — kiểm tra lại, thường phải thêm `/v1`."
        )
    if status_code == 401:
        return f"Khoá bị từ chối (HTTP 401) tại {url}. Kiểm tra lại API key."
    if status_code == 403:
        return f"Nhà cung cấp từ chối (HTTP 403) tại {url}. Khoá có thể thiếu quyền, hoặc IP máy chủ bị chặn."
    if status_code == 404:
        return f"Không thấy endpoint tại {url} (HTTP 404). Kiểm tra Base URL (thường phải có `/v1`)."
    if status_code == 429:
        return f"Bị giới hạn tốc độ (HTTP 429) tại {url} — thử lại sau."
    return f"Nhà cung cấp trả HTTP {status_code} tại {url}: {_short(text)}"


def _cloudflare_detail(
    url: str,
    status_code: int,
    *,
    mode: str,
    alt_mode_ok: bool | None,
    ip: str,
) -> str:
    """Câu trả lời cho ca Cloudflare: máy chủ này bị chặn, và cần làm gì.

    Phải nói rõ hệ quả quan trọng nhất: **Copilot gọi API từ chính máy chủ này**, nên nếu nhà cung cấp
    chặn ở tầng IP/hạ tầng thì không có cách sửa nào ở phía ứng dụng — chỉ có allowlist IP, hostname khác,
    hoặc proxy. Còn nếu chỉ chặn theo kiểu header thì nói ngay cách bật.
    """
    lines = [
        f"Cloudflare đang chặn MÁY CHỦ NÀY bằng trang challenge “Just a moment…” ở {url} (HTTP {status_code}) "
        "— không phải lỗi Base URL hay API key.",
        "Copilot gọi API từ chính máy chủ này nên nhà cung cấp sẽ không dùng được cho tới khi thông mạng.",
    ]
    if alt_mode_ok is True:
        other = other_mode(mode)
        lines.append(
            f"Chẩn đoán: gửi header kiểu {'trình duyệt' if other == 'browser' else 'ứng dụng'} thì QUA được ⇒ "
            "nhà cung cấp chỉ chấp nhận kiểu client đó. Cách sửa: thêm "
            f"`LLM_HTTP_HEADERS={other}` vào `.env` của máy chủ rồi chạy `git up --force`, sau đó bấm Test lại."
        )
    else:
        diff = ""
        if alt_mode_ok is False:
            diff = (
                "Chẩn đoán: đã thử cả hai kiểu header (ứng dụng và trình duyệt) đều bị chặn ⇒ nhiều khả năng "
                "chặn theo IP/dải IP máy chủ, không sửa được bằng header. "
            )
        lines.append(
            diff
            + "Cách xử lý (chọn một): (1) nhờ nhà cung cấp allowlist IP công khai của máy chủ"
            + (f" {ip}" if ip else " (xem IP trong khối này — bật `LLM_PUBLIC_IP` nếu chưa tự tra được)")
            + "; (2) hỏi nhà cung cấp hostname API khác không qua Cloudflare (thường là `api.<tên miền>`); "
            "(3) trỏ Base URL qua một proxy/relay ở mạng khác."
        )
    return "\n".join(lines)


async def _try_chat(client: httpx.AsyncClient, chat_url: str, model: str, api_key: str, mode: str) -> tuple[bool, str]:
    """Một lượt `POST /chat/completions`. Trả `(thành công, chẩn đoán nếu hỏng)`."""
    headers = build_headers(api_key, mode=mode, json_body=True)
    try:
        resp = await client.post(
            chat_url,
            headers=headers,
            json={
                "model": model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
            },
        )
    except Exception as exc:  # noqa: BLE001 — lỗi mạng hiển thị cho Admin, không raise
        return False, f"Không gọi được {chat_url}: {exc}"
    ctype = resp.headers.get("content-type", "")
    if 200 <= resp.status_code < 300 and not _looks_like_html(resp.text, ctype) and _looks_like_json(resp.text, ctype):
        return True, ""
    mitigated = resp.headers.get("cf-mitigated", "")
    return False, _diagnose(resp.status_code, resp.text, ctype, chat_url, mitigated)


def _is_cloudflare_failure(text: str) -> bool:
    return "Cloudflare" in text and "challenge" in text


async def probe_llm_provider(
    base_url: str | None,
    api_key: str | None,
    model_name: str | None = None,
    *,
    timeout: float = 8.0,
) -> ProbeResult:
    """Gọi thử nhà cung cấp: ưu tiên `GET /models`, sau đó `POST /chat/completions` (endpoint app thật dùng).

    Header lấy từ `src/services/llm_http.py` — **giống hệt** client thật, để test và chạy thật không lệch nhau.
    Trả về `ProbeResult` với `detail` luôn đọc được (không HTML thô), kèm đường đã thử để Admin đối chiếu.
    """
    base = (base_url or DEFAULT_BASE_URL).strip().rstrip("/")
    if not api_key:
        return ProbeResult(ok=False, status="NOT_CONFIGURED", detail="Chưa có API key.", latency_ms=0.0)

    mode = headers_mode()
    model = (model_name or "").strip() or "gpt-4o-mini"
    attempts: list[str] = []
    started_all = time.perf_counter()
    cloudflare_hit = False

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        # 1) GET /models — rẻ và cho biết luôn danh sách model.
        models_url = f"{base}/models"
        attempt_started = time.perf_counter()
        try:
            resp = await client.get(models_url, headers=build_headers(api_key, mode=mode))
            ctype = resp.headers.get("content-type", "")
            if resp.status_code == 200 and not _looks_like_html(resp.text, ctype) and _looks_like_json(resp.text, ctype):
                try:
                    count = len(resp.json().get("data", []))
                except Exception:  # noqa: BLE001 — 200 nhưng thân không phải JSON như mong đợi
                    count = 0
                latency = (time.perf_counter() - attempt_started) * 1000.0
                note = f"{count} model khả dụng" if count else "phản hồi hợp lệ"
                return ProbeResult(
                    ok=True,
                    status="OK",
                    detail=f"Kết nối thành công qua GET /models ({note}).",
                    latency_ms=round(latency, 2),
                    method="GET /models",
                    url=models_url,
                    http_status=200,
                )
            detail = _diagnose(resp.status_code, resp.text, ctype, models_url, resp.headers.get("cf-mitigated", ""))
            attempts.append(detail)
            cloudflare_hit = cloudflare_hit or _is_cloudflare_failure(detail)
        except Exception as exc:  # noqa: BLE001 — lỗi mạng hiển thị cho Admin, không raise
            attempts.append(f"Không gọi được {models_url}: {exc}")

        # 2) POST /chat/completions — endpoint mà ứng dụng thật dùng; nhiều gateway không mở /models.
        chat_url = f"{base}/chat/completions"
        attempt_started = time.perf_counter()
        try:
            resp = await client.post(
                chat_url,
                headers=build_headers(api_key, mode=mode, json_body=True),
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 1,
                },
            )
            chat_ctype = resp.headers.get("content-type", "")
            if (
                200 <= resp.status_code < 300
                and not _looks_like_html(resp.text, chat_ctype)
                and _looks_like_json(resp.text, chat_ctype)
            ):
                latency = (time.perf_counter() - attempt_started) * 1000.0
                return ProbeResult(
                    ok=True,
                    status="OK",
                    detail=(
                        "Kết nối thành công qua POST /chat/completions (đúng endpoint ứng dụng dùng; "
                        f"GET /models không dùng được: {_short(attempts[0], 140)})."
                    ),
                    latency_ms=round(latency, 2),
                    method="POST /chat/completions",
                    url=chat_url,
                    http_status=resp.status_code,
                )
            detail = _diagnose(resp.status_code, resp.text, chat_ctype, chat_url, resp.headers.get("cf-mitigated", ""))
            attempts.append(detail)
            cloudflare_hit = cloudflare_hit or _is_cloudflare_failure(detail)
        except Exception as exc:  # noqa: BLE001 — lỗi mạng hiển thị cho Admin, không raise
            attempts.append(f"Không gọi được {chat_url}: {exc}")

        # 3) Cả hai đường đều hỏng và Base URL chưa có đoạn phiên bản (/v1, /v2…): thử thêm `/v1`.
        #    Rất nhiều Admin dán địa chỉ gốc, trong khi API nằm ở `/v1` — ứng dụng khác dùng đúng `/v1`
        #    nên chạy được, còn ở đây thì không. Khi đó phải nói rõ cần sửa Base URL, không chỉ báo lỗi.
        if not re.search(r"/v\d+$", base):
            v1_chat_url = f"{base}/v1/chat/completions"
            try:
                resp = await client.post(
                    v1_chat_url,
                    headers=build_headers(api_key, mode=mode, json_body=True),
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 1,
                    },
                )
                v1_ctype = resp.headers.get("content-type", "")
                if (
                    200 <= resp.status_code < 300
                    and not _looks_like_html(resp.text, v1_ctype)
                    and _looks_like_json(resp.text, v1_ctype)
                ):
                    latency = (time.perf_counter() - started_all) * 1000.0
                    return ProbeResult(
                        ok=False,
                        status="ERROR",
                        detail=(
                            f"API trả lời ở {base}/v1 nhưng KHÔNG trả lời ở Base URL hiện tại ({base}). "
                            f"Sửa Base URL thành {base}/v1 rồi lưu lại — test lại sẽ xanh."
                        ),
                        latency_ms=round(latency, 2),
                        method="POST /v1/chat/completions",
                        url=v1_chat_url,
                        http_status=resp.status_code,
                    )
            except Exception:  # noqa: BLE001 — bước dò thêm, hỏng thì bỏ qua và dùng chẩn đoán gốc
                pass

        # 4) Bị Cloudflare chặn: đây là ca cần chẩn đoán kỹ nhất (nguyên nhân có thể ở phía nhà cung cấp,
        #    không phải cấu hình). Thử thêm chế độ header còn lại + tra IP công khai của máy chủ.
        alt_mode_ok: bool | None = None
        ip = ""
        if cloudflare_hit:
            alt_mode = other_mode(mode)
            alt_ok, _ = await _try_chat(client, chat_url, model, api_key, alt_mode)
            alt_mode_ok = alt_ok
            if not alt_ok and not re.search(r"/v\d+$", base):
                alt_ok, _ = await _try_chat(client, f"{base}/v1/chat/completions", model, api_key, alt_mode)
                alt_mode_ok = alt_ok
            ip = await public_ip()

    latency = (time.perf_counter() - started_all) * 1000.0
    unreachable = all("Không gọi được" in a for a in attempts)
    # Lỗi Cloudflare/HTML ở lần thử chat sát thực tế hơn → đưa lên trước để Admin đọc thấy ngay.
    primary = attempts[-1] if len(attempts) > 1 else attempts[0]
    if cloudflare_hit:
        primary = _cloudflare_detail(f"{base}/chat/completions", 403, mode=mode, alt_mode_ok=alt_mode_ok, ip=ip)
    # Cả hai đường đều bị Cloudflare ⇒ câu chẩn đoán đã nói đủ, không lặp lại.
    # Nhưng nếu `/models` cho câu trả lời khác (khoá sai, trang chủ…) thì phải giữ lại — đó mới là thông tin.
    ca_hai_deu_cloudflare = cloudflare_hit and bool(attempts) and _is_cloudflare_failure(attempts[0])
    extra = (
        f" (đã thử GET /models: {_short(attempts[0], 160)})"
        if len(attempts) > 1 and attempts[0] not in primary and not ca_hai_deu_cloudflare
        else ""
    )
    return ProbeResult(
        ok=False,
        status="UNREACHABLE" if unreachable else "ERROR",
        detail=primary + extra,
        latency_ms=round(latency, 2),
        method=None,
        url=base,
        http_status=None,
    )
