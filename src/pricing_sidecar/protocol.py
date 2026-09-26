"""Framing giao thức UDS giữa orchestrator và Math Engine.

TODO(Dev 2): chốt framing (length-prefixed JSON khuyến nghị) trong Spike 1,
ghi nhận quyết định vào `mydoc/baocaothaydoi.md` trước khi 2 phía implement.
"""

REQUEST_TIMEOUT_SECONDS = 2.0  # quá hạn → sidecar coi là client chết


def encode_request(payload: dict) -> bytes:
    raise NotImplementedError("C-06: request framing")


def decode_response(data: bytes) -> dict:
    raise NotImplementedError("C-06: response framing")
