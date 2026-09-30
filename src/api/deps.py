"""
API Dependencies for Security, Idempotency, OCC, and RBAC / SoD (C-01 / Phase 4).
Owner: TechLead (cuongtv_02560)
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
from dataclasses import dataclass
from typing import Any

from fastapi import Header, HTTPException, Request, status

from src.contracts.errors import ErrorCode


def create_access_token(user: str, role: str) -> str:
    """Tạo access token mang thông tin user và role."""
    payload = json.dumps({"u": user, "r": role, "rnd": secrets.token_hex(8)})
    return "tk_" + base64.urlsafe_b64encode(payload.encode("utf-8")).decode("utf-8")


def parse_auth_token(token_str: str) -> tuple[str | None, str | None]:
    """Giải mã thông tin user và role từ access token."""
    token = token_str.replace("Bearer ", "").strip()
    if token.startswith("tk_"):
        try:
            raw = base64.urlsafe_b64decode(token[3:].encode("utf-8")).decode("utf-8")
            data = json.loads(raw)
            return data.get("u"), data.get("r")
        except Exception:
            return None, None
    elif token.startswith("token_"):
        parts = token.split("_")
        if len(parts) >= 3:
            return parts[1], parts[-2].upper()
    return None, None


@dataclass
class Principal:
    user_id: str
    role: str
    tenant_id: str

    def has_role(self, *roles: str) -> bool:
        def _norm(r: str) -> str:
            u = r.upper()
            return "SALE" if u in ("SALE", "SALES") else u
        user_role = _norm(self.role)
        return any(user_role == _norm(r) for r in roles)


# In-memory storage for Idempotency Cache (per-process fallback for tests & local dev)
_IDEMPOTENCY_STORE: dict[str, dict[str, Any]] = {}


def clear_idempotency_store() -> None:
    """Helper for testing: reset idempotency cache."""
    _IDEMPOTENCY_STORE.clear()


async def get_idempotency_key(
    request: Request,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> str | None:
    """
    Validates and enforces Idempotency-Key on mutating requests.
    - If key is new: records payload hash.
    - If key exists and payload matches: marks replay in request.state.
    - If key exists and payload differs: raises 409 Conflict.
    """
    if not idempotency_key:
        return None

    body = await request.body()
    payload_hash = hashlib.sha256(body).hexdigest()

    cached = _IDEMPOTENCY_STORE.get(idempotency_key)
    if cached is not None:
        if cached["payload_hash"] != payload_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": ErrorCode.IDEMPOTENCY_KEY_REUSE_PAYLOAD_MISMATCH.value,
                    "message": "Idempotency key reused with a different payload.",
                },
            )
        request.state.idempotency_cached = cached
    else:
        # Reserve slot
        _IDEMPOTENCY_STORE[idempotency_key] = {
            "payload_hash": payload_hash,
            "status_code": 200,
            "response": None,
        }
        request.state.idempotency_cached = None

    return idempotency_key


def record_idempotency_result(idempotency_key: str | None, status_code: int, response_data: Any) -> None:
    """Save finalized response for an Idempotency-Key."""
    if not idempotency_key:
        return
    if idempotency_key in _IDEMPOTENCY_STORE:
        _IDEMPOTENCY_STORE[idempotency_key]["status_code"] = status_code
        _IDEMPOTENCY_STORE[idempotency_key]["response"] = response_data


def parse_etag_version(if_match_header: str | None) -> int | None:
    """Extract integer version from ETag format: W/"1", "1", 1."""
    if not if_match_header:
        return None
    cleaned = if_match_header.strip()
    match = re.search(r'(\d+)', cleaned)
    if match:
        return int(match.group(1))
    return None


def get_if_match_etag(if_match: str | None = Header(None, alias="If-Match")) -> int | None:
    """Extract and parse ETag version from If-Match header."""
    return parse_etag_version(if_match)


def verify_occ(current_version: int, expected_version: int | None) -> None:
    """
    Enforces Optimistic Concurrency Control (OCC).
    Raises 412 Precondition Failed if expected_version is provided and does not match current_version.
    """
    if expected_version is not None and expected_version != current_version:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail={
                "code": ErrorCode.STALE_QUOTE_VERSION.value,
                "message": (
                    f"Optimistic Concurrency Control conflict: expected version {expected_version}, "
                    f"but quote current version is {current_version}."
                ),
            },
        )


def get_current_principal(
    authorization: str | None = Header(None, alias="Authorization"),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
    x_user_role: str | None = Header(None, alias="X-User-Role"),
    x_tenant_id: str = Header("DEFAULT", alias="X-Tenant-Id"),
) -> Principal:
    """Extracts Principal actor from request headers or Bearer token for RBAC & SoD enforcement."""
    user_id = x_user_id.strip() if x_user_id else None
    role = x_user_role.strip().upper() if x_user_role else None

    if (not role or not user_id) and authorization:
        t_user, t_role = parse_auth_token(authorization)
        if t_user and not user_id:
            user_id = t_user
        if t_role and not role:
            role = t_role.upper()

    return Principal(
        user_id=user_id or "SALES-001",
        role=role or "SALES",
        tenant_id=x_tenant_id.strip(),
    )


def enforce_sod(creator_id: str, approver_id: str) -> None:
    """
    Enforces Invariant #10 (Separation of Duties - SoD).
    Quote creator cannot approve their own quote.
    """
    if creator_id == approver_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": ErrorCode.SOD_CREATOR_APPROVER_IDENTICAL.value,
                "message": "Separation of Duties violation: quote creator cannot approve their own quote.",
            },
        )
