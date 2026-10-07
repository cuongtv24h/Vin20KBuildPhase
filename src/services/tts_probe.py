"""Kiểm tra kết nối nhà cung cấp TTS — cùng triết lý với `llm_probe` (lỗi phải đọc được).

Vì sao không "thử tổng hợp một câu": mỗi lần gọi tổng hợp là **tốn tiền thật** và có nhà cung cấp tính
theo ký tự. Nút “Test kết nối” ở đây chỉ gọi các endpoint **danh mục/model/khả dụng** (miễn phí), rồi nói
rõ đã gọi đường nào. Nếu nhà cung cấp không mở endpoint nào kiểm tra được, câu trả lời phải nói thẳng là
"không kiểm tra tự động được" kèm cách kiểm bằng tay — không báo xanh giả.

Ba nhóm được xử lý:

1. **`mode = browser`** — đọc tại máy, không cần khoá ⇒ luôn sẵn sàng.
2. **OpenAI / gateway tương thích OpenAI** — `GET {base}/models` có `Authorization: Bearer` là đủ để biết
   khoá hợp lệ và endpoint sống (đúng cách tab “Nhà cung cấp LLM” đang làm).
3. **Nhà cung cấp khác** (Viettel, Vbee, FPT, Azure, self-host…) — thử `GET {base}` và `GET {base}/voices`;
   200/401/403/404 được diễn giải thành câu người đọc hiểu, không đổ HTML thô ra màn hình.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from src.services.llm_http import APP_USER_AGENT

# Dùng lại đúng bộ chẩn đoán của LLM probe để câu lỗi nhất quán giữa hai màn hình quản trị.
from src.services.llm_probe import (
    _diagnose,
    _is_cloudflare_failure,
    _looks_like_html,
    _looks_like_json,
)

#: Nhà cung cấp dùng giao thức OpenAI-compatible (có `/models`).
OPENAI_COMPATIBLE = {"openai", "openai_compatible", "groq", "openrouter", "deepseek"}


@dataclass(frozen=True)
class TtsProbeResult:
    """Kết quả một lần kiểm tra (không phụ thuộc FastAPI/DB → test trực tiếp được)."""

    ok: bool
    #: OK | ERROR | UNREACHABLE | NOT_CONFIGURED | UNSUPPORTED | NO_KEY_NEEDED
    status: str
    detail: str
    latency_ms: float
    method: str | None = None
    url: str | None = None


def _headers(api_key: str) -> dict[str, str]:
    headers = {"User-Agent": APP_USER_AGENT, "Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


async def probe_tts_provider(
    *,
    provider: str,
    base_url: str | None,
    api_key: str,
    mode: str = "api",
    env_key: str = "",
    timeout: float = 8.0,
) -> TtsProbeResult:
    """Kiểm tra kết nối tới nhà cung cấp TTS (xem docstring module để biết vì sao không tổng hợp thử)."""
    slug = (provider or "").strip().lower()
    if (mode or "api").strip().lower() == "browser":
        return TtsProbeResult(
            ok=True,
            status="NO_KEY_NEEDED",
            detail="Đọc tại trình duyệt (Web Speech API) — không cần khoá, không phát sinh chi phí.",
            latency_ms=0.0,
        )
    if not api_key:
        hint = f" (đặt khoá trong DB hoặc biến ENV {env_key})" if env_key else " (nhập khoá cho nhà cung cấp)"
        return TtsProbeResult(
            ok=False,
            status="NOT_CONFIGURED",
            detail=f"Chưa có khoá để kiểm tra{hint}.",
            latency_ms=0.0,
        )
    base = (base_url or "").strip().rstrip("/")
    if not base:
        return TtsProbeResult(
            ok=False,
            status="NOT_CONFIGURED",
            detail="Chưa khai Base URL cho nhà cung cấp này nên không kiểm tra được.",
            latency_ms=0.0,
        )

    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        # 1) OpenAI-compatible: `/models` cho biết luôn khoá hợp lệ và gateway sống.
        if slug in OPENAI_COMPATIBLE:
            url = f"{base}/models"
            try:
                resp = await client.get(url, headers=_headers(api_key))
                ctype = resp.headers.get("content-type", "")
                if resp.status_code == 200 and _looks_like_json(resp.text, ctype) and not _looks_like_html(resp.text, ctype):
                    count = 0
                    try:
                        count = len(resp.json().get("data", []))
                    except Exception:  # noqa: BLE001 — 200 nhưng thân không đúng dạng mong đợi
                        count = 0
                    note = f"{count} model khả dụng" if count else "phản hồi hợp lệ"
                    return TtsProbeResult(
                        ok=True,
                        status="OK",
                        detail=f"Kết nối thành công qua GET /models ({note}).",
                        latency_ms=round((time.perf_counter() - started) * 1000, 2),
                        method="GET /models",
                        url=url,
                    )
                detail = _diagnose(resp.status_code, resp.text, ctype, url, resp.headers.get("cf-mitigated", ""))
                return TtsProbeResult(
                    ok=False,
                    status="ERROR",
                    detail=detail,
                    latency_ms=round((time.perf_counter() - started) * 1000, 2),
                    method="GET /models",
                    url=url,
                )
            except Exception as exc:  # noqa: BLE001 — lỗi mạng phải hiển thị cho Admin, không raise
                return TtsProbeResult(
                    ok=False,
                    status="UNREACHABLE",
                    detail=f"Không gọi được {url}: {exc}",
                    latency_ms=round((time.perf_counter() - started) * 1000, 2),
                    method="GET /models",
                    url=url,
                )

        # 2) Nhà cung cấp khác: thử vài endpoint nhẹ, đọc mã trạng thái thay vì đoán.
        attempts: list[str] = []
        for path, label in (("/voices", "GET /voices"), ("", "GET base URL")):
            url = f"{base}{path}"
            try:
                resp = await client.get(url, headers=_headers(api_key))
            except Exception as exc:  # noqa: BLE001
                attempts.append(f"{label}: không gọi được ({exc})")
                continue
            ctype = resp.headers.get("content-type", "")
            if resp.status_code in (200, 204) and not _looks_like_html(resp.text, ctype):
                return TtsProbeResult(
                    ok=True,
                    status="OK",
                    detail=f"Kết nối thành công qua {label} (mã {resp.status_code}) — endpoint sống, khoá được chấp nhận.",
                    latency_ms=round((time.perf_counter() - started) * 1000, 2),
                    method=label,
                    url=url,
                )
            if resp.status_code in (401, 403):
                return TtsProbeResult(
                    ok=False,
                    status="ERROR",
                    detail=f"{label} trả mã {resp.status_code}: khoá bị từ chối hoặc tài khoản chưa được bật dịch vụ.",
                    latency_ms=round((time.perf_counter() - started) * 1000, 2),
                    method=label,
                    url=url,
                )
            attempts.append(_diagnose(resp.status_code, resp.text, ctype, url, resp.headers.get("cf-mitigated", "")))
            if _is_cloudflare_failure(attempts[-1]):
                break  # bị Cloudflare chặn thì thử tiếp cũng vô nghĩa — trả chẩn đoán Cloudflare ở dưới

        return TtsProbeResult(
            ok=False,
            status="UNSUPPORTED",
            detail=(
                "Không kiểm tra tự động được với nhà cung cấp này (endpoint kiểm tra không mở). "
                "Cách kiểm bằng tay: bấm nút “Đọc” một câu trả lời ngắn trong workspace Sale. "
                "Chi tiết các lần thử: " + " | ".join(attempts[:2])
            ),
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            method=None,
            url=base,
        )
