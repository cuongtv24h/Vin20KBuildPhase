"""UDS server của Math Engine — nhận yêu cầu, tính, trả kết quả.

Vòng đời mỗi connection: đọc request (N-10B payload) → chạy engine →
trả `PricingCalculationOutput` + `calculation_output_hash`. Không state giữa
các request (stateless worker), không retry trong server (retry do caller).
"""



async def serve(socket_path: str) -> None:
    """Khởi động sidecar tại `socket_path` (Unix Domain Socket)."""
    raise NotImplementedError("C-06: UDS server loop")
