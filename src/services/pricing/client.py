"""UDS client gọi Pricing Sidecar (C-06) — Owner: Dev 2 cung cấp server.

Sidecar chạy isolate: không network, chỉ Unix Domain Socket, độ trễ mục tiêu
< 5ms (Spike 1). Đường dẫn socket cấu hình qua env `PRICING_SIDECAR_SOCKET`.
"""

DEFAULT_SOCKET_PATH = "./data/pricing.sock"  # dev; production: /var/run/pricing/engine.sock


class PricingSidecarClient:
    """Client bất đồng bộ gửi `PricingCalculationInput` → nhận Output + hash."""

    def __init__(self, socket_path: str = DEFAULT_SOCKET_PATH):
        self.socket_path = socket_path

    async def calculate(self, payload: dict) -> dict:
        raise NotImplementedError("C-06: UDS client")

    async def health(self) -> bool:
        """Kiểm tra sidecar còn sống (dùng cho readiness probe)."""
        raise NotImplementedError("C-06: sidecar health check")
