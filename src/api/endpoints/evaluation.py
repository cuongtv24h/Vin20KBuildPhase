"""
Public Key Discovery, JWKS, and Independent Attestation Verification Endpoints (Spike 3 / Phase 4).
Owner: TechLead (cuongtv_02560)
"""

from __future__ import annotations

import base64
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from src.services.approval import KMSServerSigner

router = APIRouter(tags=["evaluation"])


class VerifySignatureRequest(BaseModel):
    snapshot_hash: str
    signature_b64: str
    public_key_b64: str | None = None


@router.get("/.well-known/jwks.json")
async def get_jwks() -> dict[str, Any]:
    """
    Public JWKS Endpoint (RFC 8037):
    Publishes Ed25519 public keys for independent verification by third-party auditors.
    """
    signer = KMSServerSigner()
    raw_pub_bytes = signer.get_public_key_raw_bytes()
    x_b64url = base64.urlsafe_b64encode(raw_pub_bytes).decode("utf-8").rstrip("=")

    return {
        "keys": [
            {
                "kty": "OKP",
                "crv": "Ed25519",
                "kid": "vlandfuture-kms-root-2026",
                "use": "sig",
                "x": x_b64url,
            }
        ]
    }


@router.get("/api/v1/evaluation/public-key")
async def get_server_public_key() -> dict[str, Any]:
    """Returns the active server attestation Ed25519 public key in Base64."""
    signer = KMSServerSigner()
    return {
        "algorithm": "Ed25519",
        "format": "RFC 8032 / RFC 8037",
        "key_id": "vlandfuture-kms-root-2026",
        "public_key_b64": signer.get_public_key_base64(),
    }


@router.post("/api/v1/evaluation/verify")
async def verify_signature_endpoint(req: VerifySignatureRequest) -> dict[str, Any]:
    """
    Public verification tool: verifies an Ed25519 signature against a snapshot hash.
    """
    signer = KMSServerSigner()
    pub_bytes = (
        base64.b64decode(req.public_key_b64)
        if req.public_key_b64
        else signer.get_public_key_raw_bytes()
    )

    is_valid = KMSServerSigner.verify_signature(
        public_key_raw_bytes=pub_bytes,
        snapshot_hash=req.snapshot_hash,
        signature_base64=req.signature_b64,
    )

    return {
        "snapshot_hash": req.snapshot_hash,
        "is_valid": is_valid,
        "algorithm": "Ed25519",
    }
