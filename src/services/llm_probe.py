"""Kiểm tra kết nối nhà cung cấp LLM — đúng cách để không bị chặn oan, và lỗi thì phải hiểu được.

Vì sao tách khỏi endpoint: bản đầu gọi `GET {base_url}/models` bằng `httpx` mặc định, nên:

1. **Bị Cloudflare chặn**: httpx mặc định gửi `User-Agent: python-httpx/...`; nhà cung cấp nào đứng sau
   Cloudflare có bật chống bot sẽ trả `403` kèm trang `"Just a moment..."` (HTML) — dù API vẫn dùng bình
   thường từ ứng dụng khác (trình duyệt hoặc client khác). Nay gửi `User-Agent`/`Accept` tường minh.
2. **Chỉ thử `/models`**: nhiều gateway (proxy OpenAI-compatible) không mở `/models` nhưng vẫn chạy tốt
   `/chat/completions` — đúng endpoint mà ứng dụng thật dùng. Nay thử cả hai, và báo đã thử bằng đường nào.
3. **Đổ HTML thô vào màn hình**: Admin nhận một đống `<!DOCTYPE html>...` vô nghĩa. Nay nhận dạng HTML/Cloudflare
   và nói rõ nguyên nhân + việc cần kiểm tra.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass

import httpx

#: Base URL mặc định khi Admin để trống (giống nhà cung cấp OpenAI).
DEFAULT_BASE_URL = "https://api.openai.com/v1"

#: Nhiều nhà cung cấp đứng sau Cloudflare chặn request thiếu User-Agent "trông giống thật".
#: Đây không phải giả mạo trình duyệt — chỉ là tên ứng dụng rõ ràng kèm nơi liên hệ, đủ để qua bộ lọc
#: "chặn client lạ không khai báo".
USER_AGENT = "P096-VLandFuture-Healthcheck/1.0 (+https://demoday.work.gd)"

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


def _diagnose(status_code: int, text: str, content_type: str, url: str) -> str:
    """Biến phản hồi lỗi thành câu tiếng Việt nói rõ nên kiểm tra gì — không bao giờ đổ HTML thô."""
    if _looks_like_html(text, content_type):
        if _is_cloudflare(text):
            return (
                f"Bị Cloudflare chặn (trang “Just a moment…” ở {url}). Nhà cung cấp đang bật chống bot với "
                "request không phải trình duyệt. Cần kiểm tra: (1) Base URL phải là địa chỉ API — thường có "
                "`/v1` ở cuối, không phải trang chủ; (2) nhà cung cấp có cho phép gọi API từ máy chủ không "
                "(một số chặn IP datacenter/AWS); (3) nếu là dịch vụ của mình, thêm đường dẫn API vào allowlist "
                "chống bot của Cloudflare."
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


async def probe_llm_provider(
    base_url: str | None,
    api_key: str | None,
    model_name: str | None = None,
    *,
    timeout: float = 8.0,
) -> ProbeResult:
    """Gọi thử nhà cung cấp: ưu tiên `GET /models`, sau đó `POST /chat/completions` (endpoint app thật dùng).

    Trả về `ProbeResult` với `detail` luôn đọc được (không HTML thô), kèm đường đã thử để Admin đối chiếu.
    """
    base = (base_url or DEFAULT_BASE_URL).strip().rstrip("/")
    if not api_key:
        return ProbeResult(ok=False, status="NOT_CONFIGURED", detail="Chưa có API key.", latency_ms=0.0)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    attempts: list[str] = []
    started_all = time.perf_counter()

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        # 1) GET /models — rẻ và cho biết luôn danh sách model.
        models_url = f"{base}/models"
        attempt_started = time.perf_counter()
        try:
            resp = await client.get(models_url, headers=headers)
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
            attempts.append(_diagnose(resp.status_code, resp.text, ctype, models_url))
        except Exception as exc:  # noqa: BLE001 — lỗi mạng hiển thị cho Admin, không raise
            attempts.append(f"Không gọi được {models_url}: {exc}")

        # 2) POST /chat/completions — endpoint mà ứng dụng thật dùng; nhiều gateway không mở /models.
        chat_url = f"{base}/chat/completions"
        attempt_started = time.perf_counter()
        try:
            resp = await client.post(
                chat_url,
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "model": (model_name or "").strip() or "gpt-4o-mini",
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
            attempts.append(_diagnose(resp.status_code, resp.text, chat_ctype, chat_url))
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
                    headers={**headers, "Content-Type": "application/json"},
                    json={
                        "model": (model_name or "").strip() or "gpt-4o-mini",
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

    latency = (time.perf_counter() - started_all) * 1000.0
    unreachable = all("Không gọi được" in a for a in attempts)
    # Lỗi Cloudflare/HTML ở lần thử chat sát thực tế hơn → đưa lên trước để Admin đọc thấy ngay.
    primary = attempts[-1] if len(attempts) > 1 else attempts[0]
    extra = f" (đã thử GET /models: {_short(attempts[0], 160)})" if len(attempts) > 1 and attempts[0] not in primary else ""
    return ProbeResult(
        ok=False,
        status="UNREACHABLE" if unreachable else "ERROR",
        detail=primary + extra,
        latency_ms=round(latency, 2),
        method=None,
        url=base,
        http_status=None,
    )
