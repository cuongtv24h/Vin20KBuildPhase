"""Dependency dùng chung cho API layer (auth, idempotency, phân quyền)."""

from fastapi import HTTPException, Request, status


async def get_idempotency_key(request: Request) -> str:
    """Bắt buộc header `Idempotency-Key: <UUIDv4>` trên mọi command ghi (TD-4.4).

    POST /quotes commit nguyên tử: insert Quote + Idempotency Record + Outbox
    Job trong MỘT transaction — replay cùng key trả kết quả cũ, không tạo quote mới.
    """
    key = request.headers.get("Idempotency-Key")
    if not key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Thiếu header Idempotency-Key (bắt buộc trên các command POST — TD-4.4)",
        )
    return key


async def get_current_principal(request: Request) -> dict:
    """Xác thực người gọi (Sales / Manager / Policy Admin / Customer).

    TODO(TechLead): JWT/session + RBAC theo ma trận quyền TD-4.4; quan trọng
    nhất là SoD — principal role phải đủ để N-02 và N-16 kiểm tra.
    """
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Auth chưa implement (C-05/TD-4.4)")


async def get_if_match_etag(request: Request) -> str | None:
    """Header `If-Match` cho optimistic concurrency (412 PRECONDITION_FAILED)."""
    return request.headers.get("If-Match")
